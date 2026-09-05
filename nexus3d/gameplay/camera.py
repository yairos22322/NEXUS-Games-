from __future__ import annotations

import math
from typing import Optional

from panda3d.core import Vec3


class CameraDirector:
    """Single final authority for shared FOV and camera-roll polish.

    Individual modes remain responsible for camera position and look-at. This
    director applies the final lens FOV and a stable roll target after mode
    simulation, avoiding the cumulative roll drift that existed in V3.
    """

    SPEED_REFERENCE = {
        "neon_ops": 18.0,
        "street_rush": 78.0,
        "zombie_siege": 14.0,
        "orbital_wars": 95.0,
        "cyber_runner": 34.0,
    }
    FOV_BOOST = {
        "neon_ops": 7.0,
        "street_rush": 12.0,
        "zombie_siege": 5.0,
        "orbital_wars": 11.0,
        "cyber_runner": 10.0,
    }

    def __init__(self, app) -> None:
        self.app = app
        self._last_camera_pos: Optional[Vec3] = None
        self._current_fov = float(app.save.setting("fov", 82.0))
        self._current_roll = 0.0

    def reset(self) -> None:
        self._last_camera_pos = None
        self._current_fov = float(self.app.save.setting("fov", 82.0))
        self._current_roll = 0.0

    def update(self, dt: float, mode) -> None:
        dt = max(0.0, float(dt))
        if mode is None or not getattr(mode, "active", False):
            self._restore(dt)
            return
        self._update_fov(dt, mode)
        self._update_roll(dt, mode)

    def _restore(self, dt: float) -> None:
        base = float(self.app.save.setting("fov", 82.0))
        self._current_fov = self._smooth(self._current_fov, base, 7.0, dt)
        self._current_roll = self._smooth(self._current_roll, 0.0, 8.0, dt)
        try:
            self.app.camLens.setFov(self._current_fov)
        except Exception:
            pass
        self._last_camera_pos = None

    def _update_fov(self, dt: float, mode) -> None:
        if not bool(self.app.save.setting("dynamic_fov", True)):
            self._restore(dt)
            return
        base_fov = float(self.app.save.setting("fov", 82.0))
        game_id = str(getattr(mode, "game_id", ""))
        reference = self.SPEED_REFERENCE.get(game_id, 35.0)
        max_boost = self.FOV_BOOST.get(game_id, 6.0)

        camera_pos = self.app.camera.getPos(self.app.render)
        camera_speed = 0.0
        if self._last_camera_pos is not None and dt > 0.0:
            camera_speed = (camera_pos - self._last_camera_pos).length() / max(0.0001, dt)
        self._last_camera_pos = Vec3(camera_pos)

        explicit_speed = getattr(mode, "speed", None)
        if isinstance(explicit_speed, (int, float)):
            camera_speed = max(camera_speed, abs(float(explicit_speed)))
        if hasattr(mode, "velocity"):
            try:
                camera_speed = max(camera_speed, Vec3(mode.velocity).length())
            except Exception:
                pass

        ratio = max(0.0, min(1.45, camera_speed / max(1.0, reference)))
        boost = max_boost * (1.0 - math.exp(-ratio * 1.75))
        if bool(getattr(mode, "nitro_active", False)):
            boost += 2.8
        if float(getattr(mode, "dash_timer", 0.0) or 0.0) > 0.0:
            boost += 3.5
        if bool(getattr(mode, "boosting", False)):
            boost += 2.5

        ads = max(0.0, min(1.0, float(getattr(mode, "ads_amount", 0.0) or 0.0)))
        if game_id == "neon_ops" and ads > 0.0:
            boost *= 1.0 - ads * 0.85
            base_fov -= 13.0 * ads

        if getattr(mode, "paused", False) or getattr(mode, "game_over", False):
            boost = 0.0

        target = max(55.0, min(112.0, base_fov + boost))
        self._current_fov = self._smooth(self._current_fov, target, 8.5, dt)
        try:
            self.app.camLens.setFov(self._current_fov)
        except Exception:
            pass

    def _update_roll(self, dt: float, mode) -> None:
        if not bool(self.app.save.setting("camera_roll", True)):
            target = 0.0
        else:
            game_id = str(getattr(mode, "game_id", ""))
            target = 0.0
            if game_id == "street_rush":
                target = float(getattr(mode, "steer", 0.0)) * -2.3
            elif game_id in ("neon_ops", "cyber_runner"):
                key = getattr(mode, "key", None)
                if key is not None:
                    lateral = (1 if key["d"] else 0) - (1 if key["a"] else 0)
                    target = lateral * (-0.8 if game_id == "neon_ops" else -1.25)
            elif game_id == "orbital_wars" and hasattr(mode, "velocity"):
                try:
                    target = max(-2.6, min(2.6, -float(mode.velocity.x) * 0.18))
                except Exception:
                    target = 0.0
            if getattr(mode, "paused", False) or getattr(mode, "game_over", False):
                target = 0.0

        self._current_roll = self._smooth(self._current_roll, target, 8.0, dt)
        try:
            self.app.camera.setR(max(-8.0, min(8.0, self._current_roll)))
        except Exception:
            pass

    @staticmethod
    def _smooth(current: float, target: float, sharpness: float, dt: float) -> float:
        if sharpness <= 0.0:
            return target
        return current + (target - current) * (1.0 - math.exp(-sharpness * max(0.0, dt)))
