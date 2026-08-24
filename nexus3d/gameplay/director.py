from __future__ import annotations

import math
from typing import Iterable, Optional

from panda3d.core import Vec3


class GameplayDirector:
    """Cross-mode polish that improves feel without owning game rules.

    The director intentionally works through capabilities discovered on the
    active mode.  That keeps every mini-game independent while allowing common
    improvements such as speed-sensitive FOV and crowd separation.
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
        self._fov_velocity = 0.0
        self._current_fov = float(app.save.setting("fov", 82.0))
        self._crowd_accumulator = 0.0

    def reset(self) -> None:
        self._last_camera_pos = None
        self._fov_velocity = 0.0
        self._current_fov = float(self.app.save.setting("fov", 82.0))
        self._crowd_accumulator = 0.0

    def update(self, dt: float, mode) -> None:
        if dt <= 0.0:
            return
        if mode is None or not getattr(mode, "active", False):
            self._restore_fov(dt)
            self._last_camera_pos = None
            return

        self._update_dynamic_fov(dt, mode)
        self._crowd_accumulator += dt
        if self._crowd_accumulator >= 1.0 / 30.0:
            step = min(0.08, self._crowd_accumulator)
            self._crowd_accumulator = 0.0
            self._separate_actor_group(mode, getattr(mode, "enemies", None), step)
            self._separate_actor_group(mode, getattr(mode, "zombies", None), step)

    def _restore_fov(self, dt: float) -> None:
        target = float(self.app.save.setting("fov", 82.0))
        self._current_fov = self._smooth(self._current_fov, target, 7.0, dt)
        try:
            self.app.camLens.setFov(self._current_fov)
        except Exception:
            pass

    def _update_dynamic_fov(self, dt: float, mode) -> None:
        base_fov = float(self.app.save.setting("fov", 82.0))
        game_id = str(getattr(mode, "game_id", ""))
        reference = self.SPEED_REFERENCE.get(game_id, 35.0)
        max_boost = self.FOV_BOOST.get(game_id, 6.0)

        camera_pos = self.app.camera.getPos(self.app.render)
        if self._last_camera_pos is None:
            camera_speed = 0.0
        else:
            camera_speed = (camera_pos - self._last_camera_pos).length() / max(0.0001, dt)
        self._last_camera_pos = Vec3(camera_pos)

        # Prefer explicit vehicle/runner speed where available because some
        # camera rigs intentionally lag behind the actor.
        explicit_speed = getattr(mode, "speed", None)
        if isinstance(explicit_speed, (int, float)):
            camera_speed = max(camera_speed, abs(float(explicit_speed)))

        speed_ratio = max(0.0, min(1.45, camera_speed / max(1.0, reference)))
        eased = 1.0 - math.exp(-speed_ratio * 1.75)
        boost = max_boost * eased

        if bool(getattr(mode, "nitro_active", False)):
            boost += 2.8
        if float(getattr(mode, "dash_timer", 0.0) or 0.0) > 0.0:
            boost += 3.5
        if bool(getattr(mode, "boosting", False)):
            boost += 2.5

        if getattr(mode, "paused", False) or getattr(mode, "game_over", False):
            boost = 0.0

        target = max(55.0, min(112.0, base_fov + boost))
        self._current_fov = self._smooth(self._current_fov, target, 8.5, dt)
        try:
            self.app.camLens.setFov(self._current_fov)
        except Exception:
            pass

    def _separate_actor_group(self, mode, group: Optional[Iterable], dt: float) -> None:
        if not group:
            return
        actors = [actor for actor in group if getattr(actor, "alive", True) and hasattr(actor, "rig")]
        if len(actors) < 2:
            return

        # Protect frame time if a wave becomes huge. Nearest-neighbour spatial
        # hashing would be overkill for the current arcade-scale populations.
        actors = actors[:48]
        pushes = [Vec3(0) for _ in actors]

        for i in range(len(actors)):
            pos_a = actors[i].rig.get_pos()
            radius_a = float(getattr(actors[i], "radius", 0.48))
            for j in range(i + 1, len(actors)):
                pos_b = actors[j].rig.get_pos()
                radius_b = float(getattr(actors[j], "radius", 0.48))
                delta = Vec3(pos_a.x - pos_b.x, pos_a.y - pos_b.y, 0.0)
                dist_sq = delta.lengthSquared()
                desired = radius_a + radius_b + 0.14
                if dist_sq >= desired * desired:
                    continue
                if dist_sq < 0.00001:
                    angle = (i * 1.618 + j * 0.731) * 6.283185307
                    direction = Vec3(math.cos(angle), math.sin(angle), 0.0)
                    distance = 0.001
                else:
                    distance = math.sqrt(dist_sq)
                    direction = delta / distance
                penetration = desired - distance
                impulse = direction * min(0.42, penetration * 0.52)
                pushes[i] += impulse
                pushes[j] -= impulse

        for actor, push in zip(actors, pushes):
            if push.lengthSquared() < 0.000001:
                continue
            pos = actor.rig.get_pos()
            # Scale by time so separation remains stable across frame rates.
            delta = push * min(1.0, dt * 30.0)
            if hasattr(mode, "move_with_collisions"):
                half = Vec3(
                    float(getattr(actor, "radius", 0.48)) * 0.75,
                    float(getattr(actor, "radius", 0.48)) * 0.75,
                    1.0,
                )
                try:
                    pos = mode.move_with_collisions(pos, delta, half)
                except Exception:
                    pos += delta
            else:
                pos += delta
            actor.rig.set_pos(pos)

    @staticmethod
    def _smooth(current: float, target: float, sharpness: float, dt: float) -> float:
        if sharpness <= 0.0:
            return target
        t = 1.0 - math.exp(-sharpness * max(0.0, dt))
        return current + (target - current) * t
