from __future__ import annotations

from typing import Optional


class RunModifierDirector:
    """Executes the behavioural side of V4 roguelite perks.

    PerkDirector only declares attributes on the mode. This director turns those
    attributes into kill siphons, ammo generation, low-health damage bonuses and
    dash reloads without hard-coding those behaviours into every game mode.
    """

    def __init__(self, app) -> None:
        self.app = app
        self.mode_identity: Optional[int] = None
        self.last_kills = 0
        self.last_dash_active = False
        self.zombie_base_damage: Optional[float] = None

    def reset(self) -> None:
        self.mode_identity = None
        self.last_kills = 0
        self.last_dash_active = False
        self.zombie_base_damage = None

    def update(self, dt: float, mode) -> None:
        if mode is None or not getattr(mode, "active", False):
            return
        if id(mode) != self.mode_identity:
            self._attach(mode)
        if getattr(mode, "paused", False) or getattr(mode, "game_over", False):
            return

        current_kills = self._kills_for(mode)
        gained = max(0, current_kills - self.last_kills)
        if gained > 0:
            for _ in range(min(50, gained)):
                self._on_kill(mode)
            self.last_kills = current_kills

        health = self._health(mode)
        low_bonus = max(0.0, float(getattr(mode, "low_health_damage_bonus", 0.0) or 0.0))
        conditional = 1.0 + (low_bonus if health is not None and health <= 35.0 else 0.0)
        mode.conditional_damage_multiplier = conditional

        if str(getattr(mode, "game_id", "")) == "zombie_siege" and self.zombie_base_damage is not None:
            perk_mult = max(0.25, float(getattr(mode, "zombie_damage_multiplier", 1.0) or 1.0))
            permanent = max(0.25, float(getattr(mode, "permanent_damage_multiplier", 1.0) or 1.0))
            mode.damage = self.zombie_base_damage * perk_mult * permanent * conditional

        dash_active = float(getattr(mode, "dash_timer", 0.0) or 0.0) > 0.0
        if dash_active and not self.last_dash_active:
            self._on_dash(mode)
        self.last_dash_active = dash_active

    def _attach(self, mode) -> None:
        self.mode_identity = id(mode)
        self.last_kills = self._kills_for(mode)
        self.last_dash_active = float(getattr(mode, "dash_timer", 0.0) or 0.0) > 0.0
        self.zombie_base_damage = None
        if str(getattr(mode, "game_id", "")) == "zombie_siege" and hasattr(mode, "damage"):
            # Progression may already have scaled damage before this system attaches.
            permanent = max(0.25, float(getattr(mode, "permanent_damage_multiplier", 1.0) or 1.0))
            self.zombie_base_damage = float(mode.damage) / permanent
        mode.conditional_damage_multiplier = 1.0

    def _on_kill(self, mode) -> None:
        heal = max(0.0, float(getattr(mode, "heal_on_kill", 0.0) or 0.0))
        if heal > 0.0 and hasattr(mode, "health"):
            try:
                mode.health = min(100.0, float(mode.health) + heal)
            except Exception:
                pass

        armor = max(0.0, float(getattr(mode, "armor_on_kill", 0.0) or 0.0))
        if armor > 0.0 and hasattr(mode, "armor"):
            try:
                mode.armor = min(100.0, float(mode.armor) + armor)
            except Exception:
                pass

        shield = max(0.0, float(getattr(mode, "shield_on_kill", 0.0) or 0.0))
        if shield > 0.0 and hasattr(mode, "shield"):
            try:
                mode.shield = min(100.0, float(mode.shield) + shield)
            except Exception:
                pass

        energy = max(0.0, float(getattr(mode, "energy_on_kill", 0.0) or 0.0))
        if energy > 0.0 and hasattr(mode, "energy"):
            try:
                mode.energy = min(100.0, float(mode.energy) + energy)
            except Exception:
                pass

        ammo = max(0, int(getattr(mode, "ammo_on_kill", 0) or 0))
        if ammo > 0:
            if hasattr(mode, "reserve_ammo"):
                try:
                    mode.reserve_ammo = int(mode.reserve_ammo) + ammo
                except Exception:
                    pass
            elif hasattr(mode, "reserve"):
                try:
                    mode.reserve = int(mode.reserve) + ammo
                except Exception:
                    pass

    def _on_dash(self, mode) -> None:
        fraction = max(0.0, min(1.0, float(getattr(mode, "dash_reload_fraction", 0.0) or 0.0)))
        if fraction <= 0.0 or not hasattr(mode, "ammo"):
            return
        mag = int(getattr(mode, "magazine_size", getattr(mode, "mag_size", 0)) or 0)
        if mag <= 0:
            return
        rounds = max(1, int(round(mag * fraction)))
        missing = max(0, mag - int(mode.ammo))
        loaded = min(missing, rounds)
        if loaded <= 0:
            return
        # Dash reload is free by design: it is a build-defining perk, not a normal reload.
        mode.ammo = int(mode.ammo) + loaded

    def _kills_for(self, mode) -> int:
        game_id = str(getattr(mode, "game_id", ""))
        try:
            return int(self.app.save.data["stats"][game_id].get("kills", 0))
        except Exception:
            return 0

    @staticmethod
    def _health(mode) -> Optional[float]:
        if not hasattr(mode, "health"):
            return None
        try:
            return max(0.0, min(100.0, float(mode.health)))
        except Exception:
            return None
