from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Dict, Optional

from panda3d.core import Vec3


@dataclass
class ReactionState:
    last_health: float
    impulse: Vec3
    roll: float = 0.0
    pitch: float = 0.0
    age: float = 0.0


class HitReactionDirector:
    """Adds short directional reactions when existing mode damage changes health."""

    def __init__(self) -> None:
        self.mode_identity: Optional[int] = None
        self.states: Dict[int, ReactionState] = {}

    def reset(self) -> None:
        self.mode_identity = None
        self.states.clear()

    def update(self, dt: float, mode) -> None:
        game_id = str(getattr(mode, "game_id", ""))
        if game_id not in ("neon_ops", "zombie_siege", "orbital_wars"):
            return
        if id(mode) != self.mode_identity:
            self.reset()
            self.mode_identity = id(mode)

        actors = list(getattr(mode, "enemies", []) or []) if game_id != "zombie_siege" else list(getattr(mode, "zombies", []) or [])
        live: set[int] = set()
        player = Vec3(getattr(mode, "player_pos", Vec3(0)))
        for actor in actors[:96]:
            if not getattr(actor, "alive", True) or not hasattr(actor, "rig") or actor.rig.root.isEmpty():
                continue
            key = id(actor)
            live.add(key)
            health = float(getattr(actor, "health", 1.0))
            state = self.states.get(key)
            if state is None:
                state = ReactionState(health, Vec3(0))
                self.states[key] = state
            elif health < state.last_health - 0.001:
                damage = max(0.0, state.last_health - health)
                self._on_hit(mode, actor, state, player, damage, game_id)
            state.last_health = health
            self._integrate(mode, actor, state, dt, game_id)

        for key in list(self.states):
            if key not in live:
                self.states.pop(key, None)

    def _on_hit(self, mode, actor, state: ReactionState, player: Vec3, damage: float, game_id: str) -> None:
        pos = actor.rig.get_pos()
        away = Vec3(pos.x - player.x, pos.y - player.y, pos.z - player.z)
        if away.lengthSquared() < 0.001:
            away = Vec3(0, 1, 0)
        away.normalize()
        normalized_damage = min(1.0, damage / max(20.0, float(getattr(actor, "max_health", 100.0)) * 0.35))

        if game_id == "zombie_siege":
            kind = str(getattr(actor, "kind", "walker"))
            if kind == "brute":
                force = 0.65 + normalized_damage * 0.55
                tilt = 4.0
            elif kind == "runner":
                force = 2.4 + normalized_damage * 2.0
                tilt = 13.0
            else:
                force = 1.55 + normalized_damage * 1.35
                tilt = 9.0
            state.impulse += Vec3(away.x, away.y, 0.08) * force
            state.roll += (-1.0 if key_sign(actor) < 0 else 1.0) * tilt
            state.pitch -= tilt * 0.35
            try:
                actor.stagger = max(float(getattr(actor, "stagger", 0.0)), 0.16 + normalized_damage * 0.20)
            except Exception:
                pass
        elif game_id == "orbital_wars":
            force = 1.8 + normalized_damage * 3.0
            state.impulse += away * force
            state.roll += (-1.0 if key_sign(actor) < 0 else 1.0) * (7.0 + normalized_damage * 15.0)
            state.pitch += (normalized_damage - 0.5) * 8.0
        else:
            elite = bool(getattr(actor, "elite", False))
            force = (0.65 if elite else 1.10) + normalized_damage * (0.65 if elite else 1.15)
            state.impulse += Vec3(away.x, away.y, 0.0) * force
            state.roll += (-1.0 if key_sign(actor) < 0 else 1.0) * (3.5 + normalized_damage * 5.5)
            state.pitch -= 2.0 + normalized_damage * 4.0

        state.age = 0.0

    def _integrate(self, mode, actor, state: ReactionState, dt: float, game_id: str) -> None:
        state.age += dt
        if state.impulse.lengthSquared() > 0.0001:
            pos = actor.rig.get_pos()
            delta = state.impulse * dt
            if game_id in ("neon_ops", "zombie_siege") and hasattr(mode, "move_with_collisions"):
                radius = float(getattr(actor, "radius", 0.48))
                try:
                    pos = mode.move_with_collisions(pos, delta, Vec3(radius*0.72, radius*0.72, 0.9))
                except Exception:
                    pos += delta
            else:
                pos += delta
            actor.rig.set_pos(pos)
            drag = math.exp(-7.0 * dt)
            state.impulse *= drag

        state.roll *= math.exp(-10.0 * dt)
        state.pitch *= math.exp(-11.0 * dt)
        try:
            actor.rig.root.setR(state.roll)
            # Keep pitch reaction conservative because ShipRig and procedural
            # characters use local pitch differently.
            if game_id != "orbital_wars":
                actor.rig.root.setP(state.pitch)
            else:
                actor.rig.root.setP(actor.rig.root.getP() + state.pitch * dt * 4.0)
        except Exception:
            pass


def key_sign(actor) -> int:
    """Stable left/right reaction direction without global random state."""
    return -1 if ((id(actor) >> 4) & 1) else 1
