from __future__ import annotations

from typing import Dict, Optional

from panda3d.core import Vec3


class SweptProjectileSafety:
    """Continuous-collision fallback for fast projectiles.

    Mode collision callbacks remain authoritative. This layer only considers
    projectiles that survived the normal point test, then checks the segment
    travelled since the previous simulation step for thin geometry or targets.
    """

    def __init__(self) -> None:
        self.previous: Dict[int, Vec3] = {}
        self.mode_identity: Optional[int] = None

    def reset(self) -> None:
        self.previous.clear()
        self.mode_identity = None

    def update(self, dt: float, mode) -> None:
        if mode is None or not getattr(mode, "active", False):
            return
        if id(mode) != self.mode_identity:
            self.reset()
            self.mode_identity = id(mode)
        projectiles = list(getattr(mode, "projectiles", []) or [])
        if not projectiles:
            self.previous.clear()
            return

        live_ids = set()
        remove_ids: set[int] = set()
        game_id = str(getattr(mode, "game_id", ""))

        for projectile in projectiles:
            if projectile.node.isEmpty():
                continue
            key = id(projectile)
            live_ids.add(key)
            current = projectile.node.getPos(mode.root)
            previous = self.previous.get(key)
            self.previous[key] = Vec3(current)
            if previous is None:
                continue
            travel = current - previous
            if travel.lengthSquared() < 0.0004:
                continue

            wall_hit = self._segment_world(mode, previous, current)
            if wall_hit is not None:
                try:
                    mode.particles.sparks(wall_hit, projectile.color, 5)
                except Exception:
                    pass
                projectile.node.removeNode()
                remove_ids.add(key)
                continue

            if projectile.team == "enemy" and game_id in ("neon_ops", "orbital_wars"):
                center = Vec3(getattr(mode, "player_pos", Vec3(0)))
                radius = 0.86 if game_id == "orbital_wars" else 0.62
                if game_id == "neon_ops":
                    center += Vec3(0, 0, 0.8)
                hit = self._segment_sphere(previous, current, center, radius + float(projectile.radius))
                if hit is not None and hasattr(mode, "_damage_player"):
                    try:
                        mode._damage_player(projectile.damage)
                        mode.particles.sparks(hit, projectile.color, 7)
                    except Exception:
                        pass
                    if not projectile.node.isEmpty():
                        projectile.node.removeNode()
                    remove_ids.add(key)
                    continue

            if projectile.team == "player" and game_id == "orbital_wars":
                for enemy in list(getattr(mode, "enemies", []) or []):
                    if not getattr(enemy, "alive", True) or not hasattr(enemy, "rig") or enemy.rig.root.isEmpty():
                        continue
                    center = enemy.rig.root.getPos(mode.root)
                    radius = float(getattr(enemy, "radius", 0.8)) + float(projectile.radius)
                    hit = self._segment_sphere(previous, current, center, radius)
                    if hit is None:
                        continue
                    try:
                        mode._damage_enemy(enemy, projectile.damage)
                        mode.particles.sparks(hit, projectile.color, 8)
                    except Exception:
                        pass
                    if not projectile.node.isEmpty():
                        projectile.node.removeNode()
                    remove_ids.add(key)
                    break

        if remove_ids:
            mode.projectiles = [
                p for p in mode.projectiles
                if id(p) not in remove_ids and not p.node.isEmpty()
            ]
        for key in list(self.previous):
            if key not in live_ids or key in remove_ids:
                self.previous.pop(key, None)

    @staticmethod
    def _segment_sphere(start: Vec3, end: Vec3, center: Vec3, radius: float) -> Optional[Vec3]:
        segment = end - start
        length_sq = segment.lengthSquared()
        if length_sq < 1e-8:
            return Vec3(start) if (start - center).length() <= radius else None
        t = max(0.0, min(1.0, (center - start).dot(segment) / length_sq))
        closest = start + segment * t
        return closest if (closest - center).length() <= radius else None

    @staticmethod
    def _segment_world(mode, start: Vec3, end: Vec3) -> Optional[Vec3]:
        direction = end - start
        best_t: Optional[float] = None
        for collider in list(getattr(mode, "colliders", []) or [])[:220]:
            if str(getattr(collider, "tag", "solid")) != "solid":
                continue
            center = Vec3(collider.center)
            half = Vec3(collider.half)
            t_min = 0.0
            t_max = 1.0
            valid = True
            for axis in range(3):
                s = start[axis]
                d = direction[axis]
                lo = center[axis] - half[axis]
                hi = center[axis] + half[axis]
                if abs(d) < 1e-8:
                    if s < lo or s > hi:
                        valid = False
                        break
                    continue
                inv = 1.0 / d
                t1 = (lo - s) * inv
                t2 = (hi - s) * inv
                if t1 > t2:
                    t1, t2 = t2, t1
                t_min = max(t_min, t1)
                t_max = min(t_max, t2)
                if t_min > t_max:
                    valid = False
                    break
            if valid and 0.0 <= t_min <= 1.0 and (best_t is None or t_min < best_t):
                best_t = t_min
        return start + direction * best_t if best_t is not None else None
