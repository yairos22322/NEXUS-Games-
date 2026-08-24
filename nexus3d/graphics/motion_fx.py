from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import List, Optional

from direct.gui.DirectGui import DirectFrame
from panda3d.core import NodePath, TransparencyAttrib, Vec3

from ..primitives import make_box


@dataclass
class SpeedStreak:
    node: NodePath
    x: float
    z: float
    depth: float
    speed: float
    seed: float


class MotionFX:
    """Pooled camera-space motion streaks and boost vignette.

    The effect is intentionally geometry-light and never allocates during the
    hot update path. It adds motion readability to fast game modes without a
    full motion-blur postprocess, which keeps the project compatible with the
    existing Panda3D renderer and fallback pipeline.
    """

    ACCENTS = {
        "neon_ops": (0.05, 0.90, 1.00, 1.0),
        "street_rush": (1.00, 0.12, 0.65, 1.0),
        "zombie_siege": (0.20, 0.85, 0.30, 1.0),
        "orbital_wars": (0.18, 0.48, 1.00, 1.0),
        "cyber_runner": (1.00, 0.42, 0.08, 1.0),
    }

    REFERENCES = {
        "neon_ops": 15.0,
        "street_rush": 72.0,
        "zombie_siege": 11.0,
        "orbital_wars": 18.0,
        "cyber_runner": 28.0,
    }

    def __init__(self, app, count: int = 44) -> None:
        self.app = app
        self.rng = random.Random(0x4D4F54494F4E)
        self.root = app.camera.attachNewNode("cinematic-motion-fx")
        self.root.setLightOff(10)
        self.streaks: List[SpeedStreak] = []
        self.game_id = ""
        self.intensity = 0.0
        self._camera_pos: Optional[Vec3] = None
        self._build(max(16, count))
        self._build_vignette()

    def _build(self, count: int) -> None:
        for index in range(count):
            x = self.rng.uniform(-4.4, 4.4)
            z = self.rng.uniform(-2.7, 2.7)
            depth = self.rng.uniform(3.5, 28.0)
            length = self.rng.uniform(0.14, 0.55)
            node = make_box(
                f"speed-streak-{index}",
                (self.rng.uniform(0.008, 0.026), length, self.rng.uniform(0.008, 0.026)),
                (0.7, 0.9, 1.0, 0.0),
                self.root,
                (x, depth, z),
            )
            node.setTransparency(TransparencyAttrib.MAlpha)
            node.setDepthWrite(False)
            node.setBin("transparent", 35)
            node.hide()
            self.streaks.append(
                SpeedStreak(
                    node=node,
                    x=x,
                    z=z,
                    depth=depth,
                    speed=self.rng.uniform(0.75, 1.55),
                    seed=self.rng.random(),
                )
            )

    def _build_vignette(self) -> None:
        self.vignette_root = DirectFrame(
            parent=self.app.aspect2d,
            frameColor=(0, 0, 0, 0),
            frameSize=(-1.78, 1.78, -1.0, 1.0),
            sortOrder=6,
        )
        self.edges = [
            DirectFrame(parent=self.vignette_root, frameColor=(0.1,0.6,1.0,0), frameSize=(-1.78,-1.50,-1.0,1.0)),
            DirectFrame(parent=self.vignette_root, frameColor=(0.1,0.6,1.0,0), frameSize=(1.50,1.78,-1.0,1.0)),
            DirectFrame(parent=self.vignette_root, frameColor=(0.1,0.6,1.0,0), frameSize=(-1.78,1.78,0.82,1.0)),
            DirectFrame(parent=self.vignette_root, frameColor=(0.1,0.6,1.0,0), frameSize=(-1.78,1.78,-1.0,-0.82)),
        ]

    def reset(self) -> None:
        self.intensity = 0.0
        self._camera_pos = None
        for streak in self.streaks:
            streak.node.hide()
        for edge in self.edges:
            edge["frameColor"] = (0.1, 0.6, 1.0, 0.0)

    def update(self, dt: float, mode) -> None:
        if dt <= 0.0 or mode is None or not getattr(mode, "active", False):
            self._fade(dt)
            return
        if getattr(mode, "paused", False) or getattr(mode, "game_over", False):
            self._fade(dt)
            return

        game_id = str(getattr(mode, "game_id", ""))
        self.game_id = game_id
        accent = self.ACCENTS.get(game_id, (0.4, 0.75, 1.0, 1.0))
        reference = self.REFERENCES.get(game_id, 30.0)
        speed = self._speed(dt, mode)
        ratio = max(0.0, min(1.55, speed / max(1.0, reference)))

        boost = 0.0
        if bool(getattr(mode, "nitro_active", False)):
            boost += 0.55
        if bool(getattr(mode, "boosting", False)):
            boost += 0.48
        if float(getattr(mode, "dash_timer", 0.0) or 0.0) > 0.0:
            boost += 0.62

        target = max(0.0, min(1.0, (ratio - 0.42) * 0.95 + boost))
        smoothing = 1.0 - math.exp(-dt * (9.0 if target > self.intensity else 5.0))
        self.intensity += (target - self.intensity) * smoothing

        visible_count = int(len(self.streaks) * max(0.0, min(1.0, self.intensity * 1.15)))
        travel = (8.0 + speed * 0.72) * dt
        for index, streak in enumerate(self.streaks):
            if index >= visible_count or self.intensity < 0.035:
                streak.node.hide()
                continue
            streak.node.show()
            streak.depth -= travel * streak.speed
            if streak.depth < 1.6:
                self._reset_streak(streak)
            perspective = max(0.18, min(1.0, 7.0 / max(2.0, streak.depth)))
            x = streak.x * (0.65 + perspective * 0.5)
            z = streak.z * (0.65 + perspective * 0.5)
            streak.node.setPos(x, streak.depth, z)
            length_scale = 0.65 + self.intensity * 3.8 + perspective * 0.7
            streak.node.setScale(1.0, length_scale, 1.0)
            alpha = max(0.0, min(0.58, self.intensity * (0.18 + streak.seed * 0.34)))
            streak.node.setColorScale(accent[0], accent[1], accent[2], alpha)

        edge_alpha = max(0.0, min(0.15, self.intensity * 0.12 + boost * 0.035))
        for edge in self.edges:
            edge["frameColor"] = (accent[0], accent[1], accent[2], edge_alpha)

    def _speed(self, dt: float, mode) -> float:
        explicit = getattr(mode, "speed", None)
        if isinstance(explicit, (int, float)):
            speed = abs(float(explicit))
        else:
            speed = 0.0

        if hasattr(mode, "velocity"):
            try:
                speed = max(speed, Vec3(mode.velocity).length())
            except Exception:
                pass

        camera_pos = self.app.camera.getPos(self.app.render)
        if self._camera_pos is not None and dt > 0.0001:
            speed = max(speed, (camera_pos - self._camera_pos).length() / dt)
        self._camera_pos = Vec3(camera_pos)
        return min(220.0, speed)

    def _reset_streak(self, streak: SpeedStreak) -> None:
        streak.depth = self.rng.uniform(20.0, 32.0)
        angle = self.rng.uniform(0, math.tau)
        radius = self.rng.uniform(1.0, 4.7)
        streak.x = math.cos(angle) * radius
        streak.z = math.sin(angle) * radius * 0.62
        streak.speed = self.rng.uniform(0.75, 1.55)
        streak.seed = self.rng.random()

    def _fade(self, dt: float) -> None:
        self.intensity += (0.0 - self.intensity) * min(1.0, max(0.0, dt) * 6.0)
        if self.intensity < 0.02:
            for streak in self.streaks:
                streak.node.hide()
        for edge in self.edges:
            edge["frameColor"] = (0.1, 0.6, 1.0, max(0.0, self.intensity * 0.08))

    def destroy(self) -> None:
        for edge in self.edges:
            try:
                edge.destroy()
            except Exception:
                pass
        try:
            self.vignette_root.destroy()
        except Exception:
            pass
        if not self.root.isEmpty():
            self.root.removeNode()
