from __future__ import annotations

import math
from typing import Iterable, Optional

from panda3d.core import Vec3

from .combat_feel import CombatFeelDirector
from .difficulty import AdaptiveDifficultyDirector
from .parkour import ParkourDirector
from .space_tactics import SpaceCombatDirector
from .tactical_ai import TacticalAI
from .vehicle_ai import VehicleDynamicsDirector
from ..graphics.motion_fx import MotionFX
from ..graphics.rig_detail import RigDetailDirector


class GameplayDirector:
    """Cross-mode gameplay, camera and simulation polish.

    Each mini-game remains responsible for its core rules. The shared director
    layers higher-level systems around those rules: tactical perception,
    adaptive encounter pressure, traffic decisions, space formations, parkour
    assists, FPS weapon feel, crowd separation, dynamic field of view, runtime
    rig detailing and cinematic motion FX.
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
        self.tactical = TacticalAI()
        self.vehicles = VehicleDynamicsDirector()
        self.space = SpaceCombatDirector()
        self.parkour = ParkourDirector()
        self.combat_feel = CombatFeelDirector()
        self.difficulty = AdaptiveDifficultyDirector()
        self.motion_fx = MotionFX(app)
        self.rig_detail = RigDetailDirector(app)
        self._last_camera_pos: Optional[Vec3] = None
        self._fov_velocity = 0.0
        self._current_fov = float(app.save.setting("fov", 82.0))
        self._crowd_accumulator = 0.0
        self._camera_lean = 0.0

    def reset(self) -> None:
        self._last_camera_pos = None
        self._fov_velocity = 0.0
        self._current_fov = float(self.app.save.setting("fov", 82.0))
        self._crowd_accumulator = 0.0
        self._camera_lean = 0.0
        self.tactical.reset()
        self.vehicles.reset()
        self.space.reset()
        self.parkour.reset()
        self.combat_feel.reset()
        self.difficulty.reset()
        self.motion_fx.reset()
        self.rig_detail.reset()

    def update(self, dt: float, mode) -> None:
        if dt <= 0.0:
            return
        if mode is None or not getattr(mode, "active", False):
            self._restore_fov(dt)
            self.motion_fx.update(dt, None)
            self._last_camera_pos = None
            return

        advanced_ai = bool(self.app.save.setting("advanced_ai", True))
        if advanced_ai:
            self.tactical.update(dt, mode)
            self.vehicles.update(dt, mode)
            self.space.update(dt, mode)
            self.parkour.update(dt, mode)
        self.combat_feel.update(dt, mode)
        if bool(self.app.save.setting("adaptive_difficulty", True)):
            self.difficulty.update(dt, mode)
        if bool(self.app.save.setting("procedural_rig_detail", True)):
            self.rig_detail.update(dt, mode)

        self._update_dynamic_fov(dt, mode)
        self._update_camera_lean(dt, mode)
        if bool(self.app.save.setting("motion_fx", True)):
            self.motion_fx.update(dt, mode)
        else:
            self.motion_fx.update(dt, None)

        self._crowd_accumulator += dt
        if advanced_ai and self._crowd_accumulator >= 1.0 / 30.0:
            step = min(0.08, self._crowd_accumulator)
            self._crowd_accumulator = 0.0
            self._separate_actor_group(mode, getattr(mode, "enemies", None), step)
            self._separate_actor_group(mode, getattr(mode, "zombies", None), step)

    def destroy(self) -> None:
        try:
            self.motion_fx.destroy()
        except Exception:
            pass

    def _restore_fov(self, dt: float) -> None:
        target = float(self.app.save.setting("fov", 82.0))
        self._current_fov = self._smooth(self._current_fov, target, 7.0, dt)
        try:
            self.app.camLens.setFov(self._current_fov)
        except Exception:
            pass

    def _update_dynamic_fov(self, dt: float, mode) -> None:
        if not bool(self.app.save.setting("dynamic_fov", True)):
            self._restore_fov(dt)
            return

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

        explicit_speed = getattr(mode, "speed", None)
        if isinstance(explicit_speed, (int, float)):
            camera_speed = max(camera_speed, abs(float(explicit_speed)))
        if hasattr(mode, "velocity"):
            try:
                camera_speed = max(camera_speed, Vec3(mode.velocity).length())
            except Exception:
                pass

        speed_ratio = max(0.0, min(1.45, camera_speed / max(1.0, reference)))
        eased = 1.0 - math.exp(-speed_ratio * 1.75)
        boost = max_boost * eased

        if bool(getattr(mode, "nitro_active", False)):
            boost += 2.8
        if float(getattr(mode, "dash_timer", 0.0) or 0.0) > 0.0:
            boost += 3.5
        if bool(getattr(mode, "boosting", False)):
            boost += 2.5

        ads_amount = max(0.0, min(1.0, float(getattr(mode, "ads_amount", 0.0) or 0.0)))
        if game_id == "neon_ops" and ads_amount > 0.0:
            boost *= 1.0 - ads_amount * 0.85
            base_fov -= 13.0 * ads_amount

        if getattr(mode, "paused", False) or getattr(mode, "game_over", False):
            boost = 0.0

        target = max(55.0, min(112.0, base_fov + boost))
        self._current_fov = self._smooth(self._current_fov, target, 8.5, dt)
        try:
            self.app.camLens.setFov(self._current_fov)
        except Exception:
            pass

    def _update_camera_lean(self, dt: float, mode) -> None:
        game_id = str(getattr(mode, "game_id", ""))
        target = 0.0
        if game_id == "street_rush":
            target = float(getattr(mode, "steer", 0.0)) * -1.8
        elif game_id == "neon_ops":
            key = getattr(mode, "key", None)
            if key is not None:
                target = ((1 if key["d"] else 0) - (1 if key["a"] else 0)) * -0.75
        elif game_id == "cyber_runner":
            key = getattr(mode, "key", None)
            if key is not None:
                target = ((1 if key["d"] else 0) - (1 if key["a"] else 0)) * -1.1
        elif game_id == "orbital_wars" and hasattr(mode, "velocity"):
            try:
                target = max(-2.2, min(2.2, -float(mode.velocity.x) * 0.15))
            except Exception:
                target = 0.0

        if getattr(mode, "paused", False) or getattr(mode, "game_over", False):
            target = 0.0
        self._camera_lean = self._smooth(self._camera_lean, target, 7.0, dt)
        try:
            hpr = self.app.camera.getHpr()
            desired_r = max(-8.0, min(8.0, hpr.z + self._camera_lean * dt * 8.0))
            self.app.camera.setR(desired_r)
        except Exception:
            pass

    def _separate_actor_group(self, mode, group: Optional[Iterable], dt: float) -> None:
        if not group:
            return
        actors = [actor for actor in group if getattr(actor, "alive", True) and hasattr(actor, "rig")]
        if len(actors) < 2:
            return

        actors = actors[:56]
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
