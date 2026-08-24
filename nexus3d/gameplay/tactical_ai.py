from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Dict, Iterable, Optional, Sequence

from panda3d.core import Vec3


@dataclass
class TacticalState:
    role: str
    flank_sign: float
    decision_timer: float
    last_visible: float = 0.0
    cover_timer: float = 0.0
    preferred_range: float = 14.0


class TacticalAI:
    """Adds tactical steering and perception on top of the arcade mode rules.

    The individual game modes remain authoritative for damage, spawning and
    scoring.  This system adds perception, role selection, cover seeking,
    flanking and fair crowd attack scheduling without needing a navigation mesh.
    It deliberately uses the same box-collider representation as the modes so
    it remains deterministic and inexpensive.
    """

    def __init__(self) -> None:
        self._states: Dict[int, TacticalState] = {}
        self._rng = random.Random(0x4E45585553)
        self._cleanup_timer = 0.0

    def reset(self) -> None:
        self._states.clear()
        self._cleanup_timer = 0.0

    def update(self, dt: float, mode) -> None:
        if dt <= 0.0 or mode is None:
            return
        game_id = str(getattr(mode, "game_id", ""))
        if game_id == "neon_ops":
            self._update_neon_ops(dt, mode)
        elif game_id == "zombie_siege":
            self._update_zombie_siege(dt, mode)

        self._cleanup_timer += dt
        if self._cleanup_timer >= 3.0:
            self._cleanup_timer = 0.0
            self._cleanup(mode)

    # ------------------------------------------------------------------
    # Neon Ops
    # ------------------------------------------------------------------
    def _update_neon_ops(self, dt: float, mode) -> None:
        enemies = [e for e in getattr(mode, "enemies", []) if getattr(e, "alive", True)]
        if not enemies or not hasattr(mode, "player_pos"):
            return

        player = Vec3(mode.player_pos) + Vec3(0, 0, 0.85)
        wave = max(1, int(getattr(mode, "wave", 1)))

        for index, enemy in enumerate(enemies):
            if not hasattr(enemy, "rig") or enemy.rig.root.isEmpty():
                continue
            state = self._state_for(enemy, index, wave)
            state.decision_timer -= dt
            state.cover_timer = max(0.0, state.cover_timer - dt)

            pos = enemy.rig.get_pos()
            eye = pos + Vec3(0, 0, 1.45)
            to_player = player - eye
            distance = max(0.001, to_player.length())
            visible = self._line_of_sight(mode, eye, player)

            if visible:
                state.last_visible = 0.0
            else:
                state.last_visible += dt
                # Stop the original mode from firing through cover on a later
                # frame while preserving its own weapon cadence when visible.
                if hasattr(enemy, "fire_timer"):
                    enemy.fire_timer = max(float(enemy.fire_timer), 0.72)

            if state.decision_timer <= 0.0:
                self._choose_neon_role(state, enemy, distance, wave, visible)
                state.decision_timer = self._rng.uniform(0.55, 1.35)

            health_ratio = float(getattr(enemy, "health", 1.0)) / max(
                1.0, float(getattr(enemy, "max_health", 1.0))
            )
            if health_ratio < 0.38 and not bool(getattr(enemy, "elite", False)):
                state.role = "cover"

            steering = self._neon_steering(mode, enemy, state, player, distance, visible)
            if steering.lengthSquared() > 0.000001:
                speed = float(getattr(enemy, "speed", 4.0))
                strength = 0.36 if visible else 0.62
                delta = steering * speed * strength * dt
                self._move_actor(mode, enemy, delta)

            # Elite units are dangerous because they reposition faster, not
            # because they receive unfair perfect aim through walls.
            if bool(getattr(enemy, "elite", False)) and visible and distance > 13.0:
                flank = self._right_of(to_player) * state.flank_sign
                self._move_actor(mode, enemy, flank * dt * 0.55)

    def _choose_neon_role(
        self,
        state: TacticalState,
        enemy,
        distance: float,
        wave: int,
        visible: bool,
    ) -> None:
        elite = bool(getattr(enemy, "elite", False))
        roll = self._rng.random()

        if not visible:
            state.role = "hunt"
            state.preferred_range = 11.0
            return
        if elite and roll < 0.55:
            state.role = "flank"
            state.preferred_range = 12.5
        elif distance < 7.0:
            state.role = "retreat"
            state.preferred_range = 10.5
        elif roll < min(0.34, 0.18 + wave * 0.008):
            state.role = "flank"
            state.preferred_range = self._rng.uniform(10.5, 15.5)
        elif roll < 0.68:
            state.role = "suppress"
            state.preferred_range = self._rng.uniform(15.0, 23.0)
        else:
            state.role = "assault"
            state.preferred_range = self._rng.uniform(8.0, 13.0)

        if self._rng.random() < 0.18:
            state.flank_sign *= -1.0

    def _neon_steering(
        self,
        mode,
        enemy,
        state: TacticalState,
        player: Vec3,
        distance: float,
        visible: bool,
    ) -> Vec3:
        pos = enemy.rig.get_pos()
        flat_to_player = Vec3(player.x - pos.x, player.y - pos.y, 0.0)
        if flat_to_player.lengthSquared() < 0.00001:
            return Vec3(0)
        flat_to_player.normalize()
        right = Vec3(flat_to_player.y, -flat_to_player.x, 0.0)

        if state.role == "retreat":
            return -flat_to_player + right * state.flank_sign * 0.35
        if state.role == "flank":
            range_error = (distance - state.preferred_range) / max(4.0, state.preferred_range)
            return self._safe_normalize(right * state.flank_sign + flat_to_player * range_error * 0.75)
        if state.role == "suppress":
            range_error = distance - state.preferred_range
            forward_term = max(-0.55, min(0.55, range_error * 0.08))
            return self._safe_normalize(flat_to_player * forward_term + right * state.flank_sign * 0.20)
        if state.role == "cover":
            cover = self._best_cover_point(mode, pos, player)
            if cover is not None:
                direction = Vec3(cover.x - pos.x, cover.y - pos.y, 0.0)
                return self._safe_normalize(direction)
            return self._safe_normalize(-flat_to_player + right * state.flank_sign * 0.5)
        if state.role == "hunt" or not visible:
            probe = self._obstacle_avoidance(mode, pos, flat_to_player, 2.2)
            return self._safe_normalize(flat_to_player + probe * 1.35 + right * state.flank_sign * 0.12)

        # Assault role. Close distance, but keep a little lateral movement so
        # enemies do not form a single firing line.
        range_error = distance - state.preferred_range
        forward_term = max(-0.35, min(1.0, range_error * 0.11))
        return self._safe_normalize(flat_to_player * forward_term + right * state.flank_sign * 0.28)

    def _best_cover_point(self, mode, enemy_pos: Vec3, player: Vec3) -> Optional[Vec3]:
        colliders = getattr(mode, "colliders", None)
        if not colliders:
            return None
        best = None
        best_score = 1e9
        for collider in colliders[:80]:
            if str(getattr(collider, "tag", "solid")) != "solid":
                continue
            center = Vec3(collider.center)
            half = Vec3(collider.half)
            to_cover = center - player
            to_cover.z = 0
            if to_cover.lengthSquared() < 0.001:
                continue
            to_cover.normalize()
            clearance = max(half.x, half.y) + 1.15
            point = center + to_cover * clearance
            point.z = enemy_pos.z
            travel = (point - enemy_pos).length()
            if travel > 18.0:
                continue
            # Prefer points that actually put the collider between player and
            # candidate cover location.
            blocked = not self._line_of_sight(mode, point + Vec3(0, 0, 1.0), player)
            if not blocked:
                continue
            score = travel + (center - player).length() * 0.035
            if score < best_score:
                best_score = score
                best = point
        return best

    # ------------------------------------------------------------------
    # Zombie Siege
    # ------------------------------------------------------------------
    def _update_zombie_siege(self, dt: float, mode) -> None:
        zombies = [z for z in getattr(mode, "zombies", []) if getattr(z, "alive", True)]
        if not zombies or not hasattr(mode, "player_pos"):
            return

        player = Vec3(mode.player_pos)
        near_attackers = []
        count = len(zombies)
        player_health = float(getattr(mode, "health", 100.0))
        mercy = 0.72 if player_health < 25.0 else 1.0

        for index, zombie in enumerate(zombies[:64]):
            if not hasattr(zombie, "rig") or zombie.rig.root.isEmpty():
                continue
            pos = zombie.rig.get_pos()
            delta = player - pos
            delta.z = 0
            distance = max(0.001, delta.length())
            direction = self._safe_normalize(delta)
            kind = str(getattr(zombie, "kind", "walker"))

            # Assign an orbit slot around the survivor. This creates a horde
            # that surrounds the player instead of a single overlapping blob.
            slot_count = max(6, min(14, count))
            slot_angle = (index / slot_count) * math.tau
            if kind == "runner":
                slot_angle += math.sin(index * 2.17) * 0.8
                radius = 2.6
            elif kind == "brute":
                radius = 1.55
            else:
                radius = 2.0
            slot = player + Vec3(math.cos(slot_angle) * radius, math.sin(slot_angle) * radius, 0)
            slot_dir = Vec3(slot.x - pos.x, slot.y - pos.y, 0)

            if kind == "runner" and distance > 4.0:
                tangent = Vec3(direction.y, -direction.x, 0) * (1 if index % 2 == 0 else -1)
                steer = self._safe_normalize(slot_dir * 0.55 + tangent * 0.75)
                self._move_actor(mode, zombie, steer * float(getattr(zombie, "speed", 5.0)) * dt * 0.30)
            elif kind == "brute" and distance > 2.1:
                self._move_actor(mode, zombie, direction * float(getattr(zombie, "speed", 2.5)) * dt * 0.12)
            elif distance > 1.5:
                steer = self._safe_normalize(slot_dir)
                self._move_actor(mode, zombie, steer * float(getattr(zombie, "speed", 3.5)) * dt * 0.16)

            if distance < 1.9:
                near_attackers.append((distance, zombie))

            # When the player is nearly dead, slightly stagger the outer horde
            # rather than multiplying unavoidable simultaneous hits.
            if mercy < 1.0 and distance > 3.5 and hasattr(zombie, "attack_timer"):
                zombie.attack_timer = max(float(zombie.attack_timer), (1.0 - mercy) * 0.35)

        # Attack token system: only the closest few infected may resolve an
        # attack at exactly the same moment. This feels more cinematic and is
        # substantially fairer while still looking like a dense horde.
        near_attackers.sort(key=lambda item: item[0])
        allowed = 1 if player_health < 35.0 else 2 if len(near_attackers) < 8 else 3
        for _, zombie in near_attackers[allowed:]:
            if hasattr(zombie, "attack_timer"):
                zombie.attack_timer = max(float(zombie.attack_timer), 0.28 + self._rng.random() * 0.22)

    # ------------------------------------------------------------------
    # Geometry helpers
    # ------------------------------------------------------------------
    def _line_of_sight(self, mode, start: Vec3, end: Vec3) -> bool:
        colliders = getattr(mode, "colliders", None)
        if not colliders:
            return True
        for collider in colliders[:128]:
            if str(getattr(collider, "tag", "solid")) != "solid":
                continue
            if self._segment_aabb(start, end, Vec3(collider.center), Vec3(collider.half)):
                return False
        return True

    @staticmethod
    def _segment_aabb(start: Vec3, end: Vec3, center: Vec3, half: Vec3) -> bool:
        direction = end - start
        t_min = 0.0
        t_max = 1.0
        for axis in range(3):
            s = start[axis]
            d = direction[axis]
            lo = center[axis] - half[axis]
            hi = center[axis] + half[axis]
            if abs(d) < 1e-8:
                if s < lo or s > hi:
                    return False
                continue
            inv = 1.0 / d
            t1 = (lo - s) * inv
            t2 = (hi - s) * inv
            if t1 > t2:
                t1, t2 = t2, t1
            t_min = max(t_min, t1)
            t_max = min(t_max, t2)
            if t_min > t_max:
                return False
        return t_max >= 0.0 and t_min <= 1.0

    def _obstacle_avoidance(self, mode, pos: Vec3, direction: Vec3, distance: float) -> Vec3:
        colliders = getattr(mode, "colliders", None)
        if not colliders:
            return Vec3(0)
        probe = pos + direction * distance
        avoidance = Vec3(0)
        for collider in colliders[:96]:
            center = Vec3(collider.center)
            half = Vec3(collider.half) + Vec3(0.7, 0.7, 0.2)
            dx = probe.x - center.x
            dy = probe.y - center.y
            if abs(dx) <= half.x and abs(dy) <= half.y:
                away = Vec3(dx, dy, 0)
                if away.lengthSquared() < 0.001:
                    away = Vec3(direction.y, -direction.x, 0)
                avoidance += self._safe_normalize(away)
        return self._safe_normalize(avoidance)

    @staticmethod
    def _right_of(vector: Vec3) -> Vec3:
        flat = Vec3(vector.x, vector.y, 0)
        if flat.lengthSquared() < 0.00001:
            return Vec3(1, 0, 0)
        flat.normalize()
        return Vec3(flat.y, -flat.x, 0)

    @staticmethod
    def _safe_normalize(vector: Vec3) -> Vec3:
        result = Vec3(vector)
        if result.lengthSquared() > 0.000001:
            result.normalize()
        return result

    @staticmethod
    def _move_actor(mode, actor, delta: Vec3) -> None:
        if delta.lengthSquared() < 0.0000001:
            return
        pos = actor.rig.get_pos()
        radius = float(getattr(actor, "radius", 0.48))
        half = Vec3(max(0.25, radius * 0.75), max(0.25, radius * 0.75), 1.0)
        try:
            candidate = mode.move_with_collisions(pos, delta, half)
        except Exception:
            candidate = pos + delta
        actor.rig.set_pos(candidate)

    def _state_for(self, actor, index: int, wave: int) -> TacticalState:
        key = id(actor)
        state = self._states.get(key)
        if state is None:
            roles = ("assault", "flank", "suppress")
            role = roles[(index + wave) % len(roles)]
            state = TacticalState(
                role=role,
                flank_sign=-1.0 if (index + wave) % 2 else 1.0,
                decision_timer=self._rng.uniform(0.1, 0.8),
                preferred_range=self._rng.uniform(10.0, 18.0),
            )
            self._states[key] = state
        return state

    def _cleanup(self, mode) -> None:
        live_ids = set()
        for name in ("enemies", "zombies"):
            for actor in getattr(mode, name, []) or []:
                if getattr(actor, "alive", True):
                    live_ids.add(id(actor))
        stale = [key for key in self._states if key not in live_ids]
        for key in stale:
            self._states.pop(key, None)
