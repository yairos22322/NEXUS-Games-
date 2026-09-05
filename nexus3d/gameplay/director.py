from __future__ import annotations

import math
from typing import Iterable, Optional

from panda3d.core import Vec3

from .camera import CameraDirector
from .combat_feel import CombatFeelDirector
from .contracts import ContractDirector
from .destruction import DestructibleWorldDirector
from .difficulty import AdaptiveDifficultyDirector
from .environment_gameplay import EnvironmentGameplayDirector
from .hit_reactions import HitReactionDirector
from .missions import MissionDirector
from .navigation import NavigationDirector
from .parkour import ParkourDirector
from .perks import PerkDirector
from .projectile_safety import SweptProjectileSafety
from .run_modifiers import RunModifierDirector
from .space_tactics import SpaceCombatDirector
from .spatial import SpatialHash2D
from .tactical_ai import TacticalAI
from .vehicle_ai import VehicleDynamicsDirector
from .weapons import WeaponLoadoutDirector
from ..graphics.motion_fx import MotionFX
from ..graphics.player_lighting import PlayerLightingDirector
from ..graphics.rig_detail import RigDetailDirector
from ..graphics.runtime_lod import RuntimeLODDirector
from ..graphics.surface_feedback import SurfaceFeedbackDirector
from ..graphics.world_lighting import WorldLightingDirector


class GameplayDirector:
    """Cross-mode V4 gameplay, mission, camera, AI and world simulation director."""

    def __init__(self, app) -> None:
        self.app = app
        self.tactical = TacticalAI()
        self.navigation = NavigationDirector()
        self.vehicles = VehicleDynamicsDirector()
        self.space = SpaceCombatDirector()
        self.parkour = ParkourDirector()
        self.weapons = WeaponLoadoutDirector(app)
        self.combat_feel = CombatFeelDirector()
        self.projectile_safety = SweptProjectileSafety()
        self.hit_reactions = HitReactionDirector()
        self.difficulty = AdaptiveDifficultyDirector()
        self.environment_gameplay = EnvironmentGameplayDirector(app)
        self.contracts = ContractDirector(app)
        self.missions = MissionDirector(app)
        self.perks = PerkDirector(app)
        self.run_modifiers = RunModifierDirector(app)
        self.destruction = DestructibleWorldDirector()
        self.camera_director = CameraDirector(app)
        self.world_lighting = WorldLightingDirector(app)
        self.motion_fx = MotionFX(app)
        self.rig_detail = RigDetailDirector(app)
        self.runtime_lod = RuntimeLODDirector(app, self.rig_detail)
        self.surface_feedback = SurfaceFeedbackDirector(app)
        self.player_lighting = PlayerLightingDirector(app)
        self._spatial = SpatialHash2D(cell_size=3.2)
        self._crowd_accumulator = 0.0
        self._last_nav_revision = -1
        self._mode_identity: Optional[int] = None

    def reset(self) -> None:
        self._crowd_accumulator = 0.0
        self._last_nav_revision = -1
        self._mode_identity = None
        self._spatial.clear()
        for system in (
            self.tactical,
            self.navigation,
            self.vehicles,
            self.space,
            self.parkour,
            self.weapons,
            self.combat_feel,
            self.projectile_safety,
            self.hit_reactions,
            self.difficulty,
            self.environment_gameplay,
            self.contracts,
            self.missions,
            self.perks,
            self.run_modifiers,
            self.destruction,
            self.camera_director,
            self.world_lighting,
            self.motion_fx,
            self.runtime_lod,
            self.rig_detail,
            self.surface_feedback,
            self.player_lighting,
        ):
            try:
                system.reset()
            except Exception:
                pass

    def update(self, dt: float, mode) -> None:
        if dt <= 0.0:
            return

        if mode is None or not getattr(mode, "active", False):
            self.camera_director.update(dt, None)
            self.motion_fx.update(dt, None)
            self._mode_identity = None
            return

        if id(mode) != self._mode_identity:
            self._mode_identity = id(mode)
            progression = getattr(self.app, "progression", None)
            if progression is not None:
                try:
                    progression.apply_to_mode(mode)
                except Exception:
                    pass

        # Perks own a modal pause state and therefore run before the ordinary
        # pause short-circuit.
        if bool(self.app.save.setting("run_perks", True)):
            self.perks.update(dt, mode)

        if getattr(mode, "paused", False) or getattr(mode, "game_over", False):
            self.combat_feel.update(dt, mode)
            self.camera_director.update(dt, mode)
            self.motion_fx.update(dt, None)
            return

        if bool(self.app.save.setting("run_modifiers", True)):
            self.run_modifiers.update(dt, mode)

        if bool(self.app.save.setting("destructible_props", True)):
            self.destruction.update(dt, mode)
        nav_revision = int(getattr(mode, "nav_revision", 0))
        if nav_revision != self._last_nav_revision:
            self._last_nav_revision = nav_revision
            self.navigation.reset()

        if bool(self.app.save.setting("weather_gameplay", True)):
            self.environment_gameplay.update(dt, mode)
        if bool(self.app.save.setting("dynamic_world_lighting", True)):
            self.world_lighting.update(dt, mode)

        advanced_ai = bool(self.app.save.setting("advanced_ai", True))
        if advanced_ai:
            self.tactical.update(dt, mode)
            self.navigation.update(dt, mode)
            self.vehicles.update(dt, mode)
            self.space.update(dt, mode)
            self.parkour.update(dt, mode)

        if bool(self.app.save.setting("weapon_loadout", True)):
            self.weapons.update(dt, mode)
        self.combat_feel.update(dt, mode)

        if bool(self.app.save.setting("swept_projectiles", True)):
            self.projectile_safety.update(dt, mode)
        if bool(self.app.save.setting("hit_reactions", True)):
            self.hit_reactions.update(dt, mode)
        if bool(self.app.save.setting("adaptive_difficulty", True)):
            self.difficulty.update(dt, mode)
        if bool(self.app.save.setting("procedural_rig_detail", True)):
            self.rig_detail.update(dt, mode)
            if bool(self.app.save.setting("runtime_lod", True)):
                self.runtime_lod.update(dt, mode)

        if bool(self.app.save.setting("missions", True)):
            self.missions.update(dt, mode)
        if bool(self.app.save.setting("contracts", True)):
            self.contracts.update(dt, mode)
        if bool(self.app.save.setting("surface_feedback", True)):
            self.surface_feedback.update(dt, mode)
        if bool(self.app.save.setting("player_dynamic_lights", True)):
            self.player_lighting.update(dt, mode)

        # CameraDirector is deliberately last so individual modes can request
        # position/look-at changes without fighting the shared FOV/roll layer.
        self.camera_director.update(dt, mode)
        self.motion_fx.update(dt, mode if bool(self.app.save.setting("motion_fx", True)) else None)

        self._crowd_accumulator += dt
        if advanced_ai and self._crowd_accumulator >= 1.0 / 30.0:
            step = min(0.08, self._crowd_accumulator)
            self._crowd_accumulator = 0.0
            self._separate_actor_group(mode, getattr(mode, "enemies", None), step)
            self._separate_actor_group(mode, getattr(mode, "zombies", None), step)

    def destroy(self) -> None:
        for system in (
            self.contracts,
            self.missions,
            self.perks,
            self.run_modifiers,
            self.surface_feedback,
            self.player_lighting,
            self.motion_fx,
        ):
            try:
                if hasattr(system, "destroy"):
                    system.destroy()
                else:
                    system.reset()
            except Exception:
                pass

    def _separate_actor_group(self, mode, group: Optional[Iterable], dt: float) -> None:
        if not group:
            return
        actors = [
            actor
            for actor in group
            if getattr(actor, "alive", True)
            and hasattr(actor, "rig")
            and not actor.rig.root.isEmpty()
        ]
        if len(actors) < 2:
            return

        active = actors[:120]
        self._spatial.rebuild(
            (actor, actor.rig.get_pos(), float(getattr(actor, "radius", 0.48)))
            for actor in active
        )
        pushes = {id(actor): Vec3(0) for actor in active}

        for entry_a, entry_b in self._spatial.iter_unique_pairs(extra_radius=0.14):
            actor_a, actor_b = entry_a.obj, entry_b.obj
            delta = Vec3(
                entry_a.pos.x - entry_b.pos.x,
                entry_a.pos.y - entry_b.pos.y,
                0.0,
            )
            dist_sq = delta.lengthSquared()
            desired = entry_a.radius + entry_b.radius + 0.14
            if dist_sq >= desired * desired:
                continue
            if dist_sq < 0.00001:
                angle = (id(actor_a) * 0.0000017 + id(actor_b) * 0.0000009) % math.tau
                direction, distance = Vec3(math.cos(angle), math.sin(angle), 0.0), 0.001
            else:
                distance = math.sqrt(dist_sq)
                direction = delta / distance
            impulse = direction * min(0.42, (desired - distance) * 0.52)
            pushes[id(actor_a)] += impulse
            pushes[id(actor_b)] -= impulse

        for actor in active:
            push = pushes[id(actor)]
            if push.lengthSquared() < 0.000001:
                continue
            pos = actor.rig.get_pos()
            delta = push * min(1.0, dt * 30.0)
            if hasattr(mode, "move_with_collisions"):
                radius = float(getattr(actor, "radius", 0.48))
                try:
                    pos = mode.move_with_collisions(
                        pos,
                        delta,
                        Vec3(radius * 0.75, radius * 0.75, 1.0),
                    )
                except Exception:
                    pos += delta
            else:
                pos += delta
            actor.rig.set_pos(pos)
