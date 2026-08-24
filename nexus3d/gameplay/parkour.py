from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional

from panda3d.core import Vec3


@dataclass
class ParkourState:
    coyote: float = 0.0
    jump_buffer: float = 0.0
    wall_run: float = 0.0
    wall_side: float = 0.0
    vault_cooldown: float = 0.0
    last_grounded: bool = True
    last_vertical_speed: float = 0.0
    last_jump_down: bool = False
    last_slide_down: bool = False


class ParkourDirector:
    """Adds forgiving modern movement mechanics to Cyber Runner.

    Coyote time and jump buffering improve responsiveness.  Wall-running and
    context-sensitive vault assists add depth without changing the base mode's
    obstacle generation or scoring contract.
    """

    def __init__(self) -> None:
        self.state = ParkourState()

    def reset(self) -> None:
        self.state = ParkourState()

    def update(self, dt: float, mode) -> None:
        if dt <= 0.0 or str(getattr(mode, "game_id", "")) != "cyber_runner":
            return
        if not hasattr(mode, "player_pos") or not hasattr(mode, "player_velocity"):
            return

        state = self.state
        key = getattr(mode, "key", None)
        if key is None:
            return

        grounded = bool(getattr(mode, "grounded", False))
        jump_down = bool(key["space"])
        slide_down = bool(key["control"])
        jump_pressed = jump_down and not state.last_jump_down
        slide_pressed = slide_down and not state.last_slide_down

        state.vault_cooldown = max(0.0, state.vault_cooldown - dt)
        state.jump_buffer = max(0.0, state.jump_buffer - dt)
        state.coyote = max(0.0, state.coyote - dt)
        state.wall_run = max(0.0, state.wall_run - dt)

        if grounded:
            state.coyote = 0.115
        if jump_pressed:
            state.jump_buffer = 0.14

        # If the base mode saw the button slightly too late/early, resolve it
        # here on the next frame. This is standard coyote/buffer behaviour.
        if state.jump_buffer > 0.0 and (grounded or state.coyote > 0.0):
            if float(mode.player_velocity.z) <= 1.0:
                mode.player_velocity.z = max(9.4, float(mode.player_velocity.z))
                mode.grounded = False
                state.jump_buffer = 0.0
                state.coyote = 0.0
                try:
                    mode.app.audio.play("dash", mode.app.sfx_volume() * 0.18, 1.45)
                except Exception:
                    pass

        self._vault_assist(dt, mode, jump_pressed)
        self._wall_run(dt, mode)
        self._landing_feedback(mode, grounded)

        # Sliding gets a mild momentum conversion instead of only changing the
        # character scale. This makes a well-timed slide useful but not mandatory.
        if slide_pressed and grounded and float(getattr(mode, "speed", 0.0)) > 18.0:
            mode.speed = min(float(getattr(mode, "max_speed", 32.0)) + 3.0, float(mode.speed) + 1.8)
            mode.energy = min(100.0, float(getattr(mode, "energy", 100.0)) + 3.0)

        state.last_vertical_speed = float(mode.player_velocity.z)
        state.last_grounded = bool(getattr(mode, "grounded", False))
        state.last_jump_down = jump_down
        state.last_slide_down = slide_down

    def _vault_assist(self, dt: float, mode, jump_pressed: bool) -> None:
        state = self.state
        if state.vault_cooldown > 0.0:
            return
        if not bool(getattr(mode, "grounded", False)):
            return
        speed = float(getattr(mode, "speed", 0.0))
        if speed < 14.0:
            return

        player_x = float(mode.player_pos.x)
        obstacles = getattr(mode, "obstacles", []) or []
        best = None
        best_y = 99.0
        for obstacle in obstacles[:64]:
            kind = str(getattr(obstacle, "kind", ""))
            if kind not in ("barrier", "wall"):
                continue
            pos = getattr(obstacle, "pos", None)
            half = getattr(obstacle, "half", None)
            if pos is None or half is None:
                continue
            y = float(pos.y)
            if y < 0.65 or y > 3.4:
                continue
            if abs(float(pos.x) - player_x) > float(half.x) + 0.42:
                continue
            height = float(half.z) * 2.0
            if height > 1.75:
                continue
            if y < best_y:
                best = obstacle
                best_y = y

        if best is None:
            return

        # High-speed runners auto-step very low cover. Taller objects require
        # jump intent, preventing the system from playing the game automatically.
        height = float(best.half.z) * 2.0
        if height > 1.1 and not jump_pressed:
            return

        mode.player_velocity.z = max(float(mode.player_velocity.z), 7.3 + height * 0.8)
        mode.player_pos.z += 0.08
        mode.grounded = False
        state.vault_cooldown = 0.55
        state.jump_buffer = 0.0
        try:
            mode.score += 35.0 * max(1, int(getattr(mode, "multiplier", 1)))
            mode.energy = min(100.0, float(mode.energy) + 4.0)
            mode.spawn_floating_text("VAULT", (0.0, 0.14), mode.meta.accent, 0.031, 0.45)
        except Exception:
            pass

    def _wall_run(self, dt: float, mode) -> None:
        state = self.state
        if bool(getattr(mode, "grounded", False)):
            state.wall_run = 0.0
            return
        if bool(getattr(mode, "sliding", False)):
            return

        x = float(mode.player_pos.x)
        vx_input = (1 if mode.key["d"] else 0) - (1 if mode.key["a"] else 0)
        touching_left = x <= -5.35 and vx_input < 0
        touching_right = x >= 5.35 and vx_input > 0
        wants_wall = touching_left or touching_right
        energy = float(getattr(mode, "energy", 0.0))

        if wants_wall and energy > 2.0 and float(mode.player_velocity.z) < 2.5:
            state.wall_side = -1.0 if touching_left else 1.0
            state.wall_run = min(0.72, state.wall_run + dt * 2.5)
            mode.player_velocity.z = max(float(mode.player_velocity.z), -1.25)
            mode.energy = max(0.0, energy - 10.0 * dt)
            mode.speed = min(float(getattr(mode, "max_speed", 32.0)) + 4.0, float(mode.speed) + 0.8 * dt)
            try:
                mode.player.root.setR(state.wall_side * 13.0)
            except Exception:
                pass

            # Jumping away from a wall gives a small lateral pop and preserves
            # flow. The base track is wide enough for this to remain controllable.
            if bool(mode.key["space"]) and not state.last_jump_down:
                mode.player_velocity.z = 8.2
                mode.player_pos.x -= state.wall_side * 0.65
                mode.energy = max(0.0, float(mode.energy) - 6.0)
                state.wall_run = 0.0
                state.jump_buffer = 0.0
        else:
            state.wall_run = max(0.0, state.wall_run - dt * 3.0)

    def _landing_feedback(self, mode, grounded_before_update: bool) -> None:
        state = self.state
        now_grounded = bool(getattr(mode, "grounded", False))
        if not state.last_grounded and now_grounded:
            impact = abs(min(0.0, state.last_vertical_speed))
            if impact > 5.5:
                try:
                    mode.camera_shake.add(min(0.22, impact * 0.012))
                except Exception:
                    pass
            if 3.0 < impact < 10.5:
                # Clean landings maintain the rhythm loop without adding a new
                # mandatory resource system.
                try:
                    mode.energy = min(100.0, float(mode.energy) + 2.5)
                    mode.multiplier_timer = max(float(getattr(mode, "multiplier_timer", 0.0)), 0.5)
                except Exception:
                    pass
