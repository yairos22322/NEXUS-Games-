from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Dict, List, Optional

from panda3d.core import Vec3


@dataclass
class SpaceBrain:
    slot: int
    wing: float
    orbit_phase: float
    dodge_timer: float
    dodge: Vec3
    aggression: float


class SpaceCombatDirector:
    """Formation, evasion and shield pacing for Orbital Wars."""

    def __init__(self) -> None:
        self._brains: Dict[int, SpaceBrain] = {}
        self._rng = random.Random(0x4F52424954)
        self._shield_delay = 0.0
        self._last_shield: Optional[float] = None
        self._cleanup_timer = 0.0

    def reset(self) -> None:
        self._brains.clear()
        self._shield_delay = 0.0
        self._last_shield = None
        self._cleanup_timer = 0.0

    def update(self, dt: float, mode) -> None:
        if dt <= 0.0 or str(getattr(mode, "game_id", "")) != "orbital_wars":
            return
        self._update_shield(dt, mode)
        self._update_enemy_flight(dt, mode)
        self._cleanup_timer += dt
        if self._cleanup_timer > 2.5:
            self._cleanup_timer = 0.0
            live = {id(enemy) for enemy in getattr(mode, "enemies", []) if getattr(enemy, "alive", True)}
            for key in list(self._brains):
                if key not in live:
                    self._brains.pop(key, None)

    def _update_shield(self, dt: float, mode) -> None:
        if not hasattr(mode, "shield"):
            return
        shield = float(mode.shield)
        if self._last_shield is None:
            self._last_shield = shield
        if shield < self._last_shield - 0.1:
            self._shield_delay = 3.2
        else:
            self._shield_delay = max(0.0, self._shield_delay - dt)
        self._last_shield = shield

        # A delayed, modest recharge gives combat a push/pull rhythm. It never
        # heals hull and stops immediately when the player takes another hit.
        if self._shield_delay <= 0.0 and shield < 100.0 and not getattr(mode, "game_over", False):
            energy = float(getattr(mode, "energy", 100.0))
            rate = 5.5 if energy > 25.0 else 2.5
            mode.shield = min(100.0, shield + rate * dt)
            self._last_shield = float(mode.shield)

    def _update_enemy_flight(self, dt: float, mode) -> None:
        enemies: List = [
            e for e in getattr(mode, "enemies", [])
            if getattr(e, "alive", True) and hasattr(e, "rig") and not e.rig.root.isEmpty()
        ]
        if not enemies or not hasattr(mode, "player_pos"):
            return

        player = Vec3(mode.player_pos)
        player_projectiles = [
            p for p in getattr(mode, "projectiles", [])
            if str(getattr(p, "team", "")) == "player" and not p.node.isEmpty()
        ]

        for index, enemy in enumerate(enemies[:48]):
            brain = self._brain_for(enemy, index)
            pos = enemy.rig.root.getPos()
            kind = str(getattr(enemy, "kind", "fighter"))
            brain.orbit_phase += dt * (0.45 + float(getattr(enemy, "speed", 6.0)) * 0.025)
            brain.dodge_timer = max(0.0, brain.dodge_timer - dt)

            threat = self._nearest_projectile_threat(pos, player_projectiles)
            if threat is not None and brain.dodge_timer <= 0.0:
                projectile_pos, velocity, distance = threat
                lateral = Vec3(-velocity.z, 0.0, velocity.x)
                if lateral.lengthSquared() < 0.001:
                    lateral = Vec3(1 if index % 2 == 0 else -1, 0, 0.35)
                lateral.normalize()
                if self._rng.random() < 0.5:
                    lateral *= -1
                brain.dodge = lateral
                brain.dodge_timer = self._rng.uniform(0.32, 0.62)

            desired = self._formation_target(kind, index, len(enemies), brain, player, mode)
            to_target = desired - pos
            to_target.y *= 0.25
            if to_target.lengthSquared() > 0.001:
                max_step = float(getattr(enemy, "speed", 6.0)) * dt * 0.34
                if kind == "interceptor":
                    max_step *= 1.45
                elif kind == "capital":
                    max_step *= 0.35
                move = self._clamp_vector(to_target, max_step)
                pos += move

            if brain.dodge_timer > 0.0:
                dodge_strength = 5.8 if kind == "interceptor" else 3.5
                pos += brain.dodge * dodge_strength * dt

            # Capital ships stay central while fighters weave. Bombers make
            # slower attack runs instead of jittering like interceptors.
            if kind == "fighter":
                pos.x += math.sin(brain.orbit_phase + index) * dt * 0.9
                pos.z += math.cos(brain.orbit_phase * 0.8 + index) * dt * 0.55
            elif kind == "interceptor":
                pos.x += math.sin(brain.orbit_phase * 2.2 + index) * dt * 2.4
                pos.z += math.cos(brain.orbit_phase * 1.7 + index) * dt * 1.6
            elif kind == "bomber":
                pos.x += math.sin(brain.orbit_phase * 0.55 + index) * dt * 0.45

            pos.x = max(-24.0, min(24.0, pos.x))
            pos.z = max(-12.0, min(18.0, pos.z))
            pos.y = max(player.y + 7.0, min(105.0, pos.y))
            enemy.rig.root.setPos(pos)

            # Face into the flight path enough to make formations readable.
            try:
                dx = desired.x - pos.x
                dz = desired.z - pos.z
                enemy.rig.root.setR(max(-30.0, min(30.0, -dx * 2.2)))
                enemy.rig.root.setP(max(-16.0, min(16.0, dz * 1.4)))
            except Exception:
                pass

            # Fire discipline by role. Interceptors harass, bombers pause longer,
            # capital ships fire deliberate volleys.
            if hasattr(enemy, "fire_timer"):
                if kind == "bomber":
                    enemy.fire_timer = max(float(enemy.fire_timer), 0.18)
                elif kind == "capital":
                    volley = 0.25 + (math.sin(brain.orbit_phase * 1.4) * 0.5 + 0.5) * 0.55
                    if volley > 0.68:
                        enemy.fire_timer = max(float(enemy.fire_timer), 0.12)

    def _formation_target(self, kind: str, index: int, count: int, brain: SpaceBrain, player: Vec3, mode) -> Vec3:
        wave = max(1, int(getattr(mode, "wave", 1)))
        front_y = player.y + 31.0 + min(18.0, wave * 0.7)

        if kind == "capital":
            return Vec3(0.0, front_y + 17.0, 5.0)

        if kind == "bomber":
            lane = ((index % 3) - 1) * 8.0
            return Vec3(lane, front_y + 9.0, 4.0 + (index % 2) * 3.0)

        if kind == "interceptor":
            angle = brain.orbit_phase + brain.slot * (math.tau / max(4, min(8, count)))
            radius = 12.0 + (brain.slot % 3) * 2.4
            return Vec3(
                player.x + math.cos(angle) * radius,
                player.y + 22.0 + math.sin(angle * 0.5) * 5.0,
                player.z + 3.0 + math.sin(angle) * 7.0,
            )

        # Fighters use a broad V formation.
        row = brain.slot // 2 + 1
        side = brain.wing
        return Vec3(
            player.x + side * row * 4.6,
            front_y + row * 3.2,
            player.z + 3.0 + (row % 2) * 1.6,
        )

    def _nearest_projectile_threat(self, enemy_pos: Vec3, projectiles):
        best = None
        best_distance = 1e9
        for projectile in projectiles[:64]:
            pos = projectile.node.getPos()
            delta = enemy_pos - pos
            distance = delta.length()
            if distance > 9.0 or distance >= best_distance:
                continue
            velocity = Vec3(getattr(projectile, "velocity", Vec3(0, 1, 0)))
            if velocity.lengthSquared() < 0.001:
                continue
            direction = Vec3(velocity)
            direction.normalize()
            to_enemy = Vec3(delta)
            if to_enemy.lengthSquared() > 0.001:
                to_enemy.normalize()
            # Only dodge projectiles broadly travelling toward this ship.
            if direction.dot(to_enemy) < 0.68:
                continue
            best = (pos, velocity, distance)
            best_distance = distance
        return best

    def _brain_for(self, enemy, index: int) -> SpaceBrain:
        key = id(enemy)
        brain = self._brains.get(key)
        if brain is None:
            brain = SpaceBrain(
                slot=index,
                wing=-1.0 if index % 2 else 1.0,
                orbit_phase=self._rng.uniform(0, math.tau),
                dodge_timer=self._rng.uniform(0.0, 0.8),
                dodge=Vec3(0),
                aggression=self._rng.uniform(0.35, 0.9),
            )
            self._brains[key] = brain
        return brain

    @staticmethod
    def _clamp_vector(vector: Vec3, maximum: float) -> Vec3:
        result = Vec3(vector)
        length = result.length()
        if length > maximum > 0.0:
            result *= maximum / length
        return result
