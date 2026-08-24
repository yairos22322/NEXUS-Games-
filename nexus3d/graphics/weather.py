from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List

from panda3d.core import AmbientLight, NodePath, TransparencyAttrib, Vec3, Vec4

from ..primitives import make_box, make_octahedron
from .weather_presets import WeatherPreset


@dataclass
class WeatherParticle:
    node: NodePath
    offset: Vec3
    velocity: Vec3
    spin: float
    phase: float


class WeatherField:
    """Camera-centred, reusable weather volume with adaptive density.

    Particles live in a local box around the camera and are wrapped instead of
    recreated.  Runtime scaling hides a tail of the pool, which is much cheaper
    than destroying/rebuilding geometry during an FPS drop.
    """

    def __init__(self, app, root: NodePath, preset: WeatherPreset, count: int, seed: int) -> None:
        self.app = app
        self.root = root.attachNewNode("weather-field")
        self.preset = preset
        self.rng = random.Random(seed ^ 0x57EA7E)
        self.particles: List[WeatherParticle] = []
        self.time = 0.0
        self.flash = 0.0
        self.runtime_scale = 1.0
        self._visible_count = 0
        self._light_node = None
        self._create(max(0, count))
        self._create_lightning_light()
        self.set_runtime_scale(1.0)

    def _create_lightning_light(self) -> None:
        if self.preset.lightning_chance <= 0.0:
            return
        if not bool(self.app.save.setting("lightning_world_flash", True)):
            return
        try:
            light = AmbientLight("weather-lightning-flash")
            light.setColor(Vec4(0.0, 0.0, 0.0, 1.0))
            self._light_node = self.app.render.attachNewNode(light)
            self.app.render.setLight(self._light_node)
        except Exception:
            self._light_node = None

    def _random_offset(self) -> Vec3:
        radius = self.preset.radius
        return Vec3(
            self.rng.uniform(-radius, radius),
            self.rng.uniform(-radius, radius),
            self.rng.uniform(-self.preset.vertical_range * 0.35, self.preset.vertical_range),
        )

    def _create(self, count: int) -> None:
        kind = self.preset.kind
        for index in range(count):
            if kind in ("rain", "storm"):
                node = make_box(
                    f"rain-{index}",
                    (0.018, 0.018, self.rng.uniform(0.35, 0.85)),
                    self.preset.color,
                    self.root,
                )
            elif kind in ("ash", "dust", "snow"):
                node = make_octahedron(
                    f"weather-{index}",
                    self.rng.uniform(0.025, 0.075),
                    self.preset.color,
                    self.root,
                )
            else:
                node = make_octahedron(
                    f"spark-{index}",
                    self.rng.uniform(0.015, 0.045),
                    self.preset.color,
                    self.root,
                )
            node.setTransparency(TransparencyAttrib.MAlpha)
            node.setLightOff(4)
            offset = self._random_offset()
            node.setPos(offset)
            velocity = Vec3(
                self.preset.wind_x + self.rng.uniform(-0.8, 0.8),
                self.preset.wind_y + self.rng.uniform(-0.8, 0.8),
                -abs(self.preset.fall_speed) * self.rng.uniform(0.80, 1.25),
            )
            self.particles.append(
                WeatherParticle(node, offset, velocity, self.rng.uniform(-90, 90), self.rng.uniform(0, math.tau))
            )

    def set_runtime_scale(self, scale: float) -> None:
        self.runtime_scale = max(0.35, min(1.0, float(scale)))
        if not self.particles:
            self._visible_count = 0
            return
        # Keep a useful minimum so weather never vanishes completely.
        minimum = min(len(self.particles), 12)
        target = max(minimum, int(round(len(self.particles) * self.runtime_scale)))
        if target == self._visible_count:
            return
        self._visible_count = target
        for index, particle in enumerate(self.particles):
            if index < target:
                particle.node.show()
            else:
                particle.node.hide()

    def update(self, dt: float) -> None:
        self.time += dt
        camera_world = self.app.camera.getPos(self.app.render)
        self.root.setPos(camera_world)
        radius = self.preset.radius
        low = -self.preset.vertical_range * 0.45
        high = self.preset.vertical_range

        # Only simulate visible nodes. Hidden tail nodes remain pooled and can be
        # brought back instantly when the adaptive governor raises quality.
        for index, particle in enumerate(self.particles):
            if index >= self._visible_count:
                continue
            particle.phase += dt
            particle.offset += particle.velocity * dt
            if self.preset.kind in ("ash", "dust", "snow"):
                particle.offset.x += math.sin(particle.phase * 1.7) * self.preset.turbulence * dt
                particle.offset.y += math.cos(particle.phase * 1.2) * self.preset.turbulence * dt
                particle.node.setH(particle.node.getH() + particle.spin * dt)
            if (
                particle.offset.z < low
                or abs(particle.offset.x) > radius
                or abs(particle.offset.y) > radius
            ):
                particle.offset = self._random_offset()
                particle.offset.z = high
            particle.node.setPos(particle.offset)

        if self.preset.lightning_chance > 0.0:
            if self.rng.random() < dt * self.preset.lightning_chance:
                self.flash = 1.0
            self.flash = max(0.0, self.flash - dt * 3.4)
            if self.flash > 0.0:
                boost = 1.0 + self.flash * 0.65
                self.root.setColorScale(boost, boost, boost * 1.05, 1.0)
            else:
                self.root.clearColorScale()

            if self._light_node is not None and not self._light_node.isEmpty():
                light = self._light_node.node()
                intensity = self.flash * self.flash
                light.setColor(Vec4(0.58 * intensity, 0.68 * intensity, 0.95 * intensity, 1.0))

    def destroy(self) -> None:
        if self._light_node is not None and not self._light_node.isEmpty():
            try:
                self.app.render.clearLight(self._light_node)
            except Exception:
                pass
            self._light_node.removeNode()
            self._light_node = None
        if not self.root.isEmpty():
            self.root.removeNode()
