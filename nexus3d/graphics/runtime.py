from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import math
from typing import Deque, Optional


@dataclass(frozen=True)
class RuntimeGraphicsSnapshot:
    fps: float
    frame_ms: float
    quality_scale: float
    target_fps: float
    pressure: float


class AdaptiveGraphicsController:
    """Small runtime governor for expensive procedural scene systems.

    The saved graphics preset remains the user's hard ceiling.  This controller
    only changes the *runtime density* of systems that are safe to scale while a
    game is running, such as weather particles, distant skyline detail and lens
    artifacts.  It deliberately does not rebuild the renderer every frame.
    """

    def __init__(self, app, initial_scale: float = 1.0) -> None:
        self.app = app
        self.enabled = bool(app.save.setting("adaptive_quality", True))
        self.target_fps = float(app.save.setting("target_fps", 72.0))
        self.target_fps = max(30.0, min(240.0, self.target_fps))
        self.scale = max(0.48, min(1.0, float(initial_scale)))
        self._samples: Deque[float] = deque(maxlen=150)
        self._smoothed_fps = self.target_fps
        self._pressure = 0.0
        self._cooldown = 0.0
        self._last_applied = -1.0
        self._low_fps_time = 0.0
        self._high_fps_time = 0.0

    @property
    def smoothed_fps(self) -> float:
        return self._smoothed_fps

    @property
    def pressure(self) -> float:
        return self._pressure

    def snapshot(self) -> RuntimeGraphicsSnapshot:
        fps = max(1.0, self._smoothed_fps)
        return RuntimeGraphicsSnapshot(
            fps=fps,
            frame_ms=1000.0 / fps,
            quality_scale=self.scale,
            target_fps=self.target_fps,
            pressure=self._pressure,
        )

    def reset(self) -> None:
        self._samples.clear()
        self._smoothed_fps = self.target_fps
        self._pressure = 0.0
        self._cooldown = 0.0
        self._low_fps_time = 0.0
        self._high_fps_time = 0.0

    def update(self, dt: float, environment: Optional[object] = None) -> None:
        if dt <= 0.0:
            return

        dt = min(0.25, dt)
        instant_fps = 1.0 / max(0.0001, dt)
        instant_fps = min(500.0, instant_fps)
        self._samples.append(instant_fps)

        # Exponential smoothing keeps single hitches from causing quality pops.
        alpha = 1.0 - math.exp(-dt * 2.6)
        self._smoothed_fps += (instant_fps - self._smoothed_fps) * alpha
        ratio = self._smoothed_fps / max(1.0, self.target_fps)
        self._pressure = max(0.0, min(1.0, (1.0 - ratio) / 0.42))

        if not self.enabled:
            self.scale = 1.0
            self._apply(environment, force=False)
            return

        if ratio < 0.82:
            self._low_fps_time += dt
            self._high_fps_time = max(0.0, self._high_fps_time - dt * 2.0)
        elif ratio > 1.08:
            self._high_fps_time += dt
            self._low_fps_time = max(0.0, self._low_fps_time - dt * 1.5)
        else:
            self._low_fps_time = max(0.0, self._low_fps_time - dt)
            self._high_fps_time = max(0.0, self._high_fps_time - dt)

        self._cooldown = max(0.0, self._cooldown - dt)
        changed = False

        # Drop quality quickly when the GPU/CPU is clearly overloaded.
        if self._low_fps_time > 0.75 and self._cooldown <= 0.0:
            severity = max(0.035, min(0.12, (0.92 - ratio) * 0.24))
            new_scale = max(0.48, self.scale - severity)
            changed = abs(new_scale - self.scale) > 0.001
            self.scale = new_scale
            self._low_fps_time = 0.0
            self._cooldown = 0.85

        # Recover slowly so quality does not oscillate in busy scenes.
        elif self._high_fps_time > 3.0 and self._cooldown <= 0.0:
            new_scale = min(1.0, self.scale + 0.035)
            changed = abs(new_scale - self.scale) > 0.001
            self.scale = new_scale
            self._high_fps_time = 0.0
            self._cooldown = 1.2

        self._apply(environment, force=changed)

    def _apply(self, environment: Optional[object], force: bool) -> None:
        if environment is None:
            return
        if not hasattr(environment, "set_runtime_scale"):
            return
        if not force and abs(self.scale - self._last_applied) < 0.025:
            return
        try:
            environment.set_runtime_scale(self.scale)
            self._last_applied = self.scale
        except Exception:
            # A graphics governor must never be able to crash gameplay.
            return
