from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from direct.gui.DirectGui import DirectLabel
from panda3d.core import TextNode


@dataclass(frozen=True)
class WeaponSpec:
    weapon_id: str
    name: str
    damage: float
    fire_interval: float
    spread: float
    magazine: int
    reserve: int
    reload_time: float
    visual_scale: tuple[float, float, float]
    accent: tuple[float, float, float, float]


@dataclass
class WeaponRuntime:
    spec: WeaponSpec
    ammo: int
    reserve: int


class WeaponLoadoutDirector:
    """Runtime three-weapon loadout with persistent + run modifier stacking."""

    SPECS = (
        WeaponSpec("ar", "VX-7 ASSAULT", 29.0, 0.095, 0.014, 30, 150, 1.52, (1.0, 1.0, 1.0), (0.05, 0.90, 1.0, 1.0)),
        WeaponSpec("smg", "KITE-9 SMG", 18.5, 0.060, 0.024, 42, 210, 1.28, (0.94, 0.82, 0.92), (0.60, 0.24, 1.0, 1.0)),
        WeaponSpec("dmr", "SENTINEL DMR", 52.0, 0.235, 0.006, 12, 72, 1.78, (1.02, 1.22, 0.96), (1.0, 0.42, 0.08, 1.0)),
    )

    def __init__(self, app) -> None:
        self.app = app
        self.mode_identity: Optional[int] = None
        self.weapons: Dict[int, WeaponRuntime] = {}
        self.active_slot = 1
        self.key_was_down = {1: False, 2: False, 3: False}
        self.switch_cooldown = 0.0
        self.label: Optional[DirectLabel] = None

    def reset(self) -> None:
        if self.label is not None:
            try:
                self.label.destroy()
            except Exception:
                pass
        self.label = None
        self.mode_identity = None
        self.weapons.clear()
        self.active_slot = 1
        self.key_was_down = {1: False, 2: False, 3: False}
        self.switch_cooldown = 0.0

    def update(self, dt: float, mode) -> None:
        if str(getattr(mode, "game_id", "")) != "neon_ops":
            return
        if id(mode) != self.mode_identity:
            self._attach(mode)
        self.switch_cooldown = max(0.0, self.switch_cooldown - max(0.0, dt))
        for slot in (1, 2, 3):
            down = bool(mode.key[str(slot)])
            if down and not self.key_was_down[slot] and self.switch_cooldown <= 0.0:
                self._switch(mode, slot)
            self.key_was_down[slot] = down
        self._refresh_active_stats(mode)
        self._update_label(mode)

    def _attach(self, mode) -> None:
        self.reset()
        self.mode_identity = id(mode)
        for slot in (1, 2, 3):
            try:
                mode.key.bind(str(slot))
            except Exception:
                pass

        level = int(self.app.save.profile.get("level", 1))
        level_bonus = min(0.16, max(0, level - 1) * 0.004)
        reserve_mult = 1.0
        progression = getattr(self.app, "progression", None)
        if progression is not None:
            try:
                reserve_mult = float(progression.reserve_multiplier())
            except Exception:
                reserve_mult = 1.0

        for slot, spec in enumerate(self.SPECS, start=1):
            scaled_spec = WeaponSpec(
                spec.weapon_id,
                spec.name,
                spec.damage * (1.0 + level_bonus),
                spec.fire_interval,
                spec.spread,
                spec.magazine,
                max(spec.magazine, int(round(spec.reserve * reserve_mult))),
                spec.reload_time,
                spec.visual_scale,
                spec.accent,
            )
            self.weapons[slot] = WeaponRuntime(
                scaled_spec,
                scaled_spec.magazine,
                scaled_spec.reserve,
            )

        self.weapons[1].ammo = int(getattr(mode, "ammo", self.weapons[1].ammo))
        self.weapons[1].reserve = int(getattr(mode, "reserve_ammo", self.weapons[1].reserve))
        self.active_slot = 1
        self._apply(mode, self.weapons[1])

        self.label = DirectLabel(
            parent=mode.hud_root,
            text="",
            text_fg=(0.70, 0.78, 0.88, 1.0),
            text_scale=0.024,
            text_align=TextNode.ACenter,
            frameColor=(0.015, 0.025, 0.04, 0.70),
            frameSize=(-0.56, 0.56, -0.040, 0.040),
            pos=(0.0, 0, -0.90),
        )
        self._update_label(mode)

    def _switch(self, mode, slot: int) -> None:
        if slot == self.active_slot or slot not in self.weapons:
            return
        current = self.weapons[self.active_slot]
        current.ammo = int(getattr(mode, "ammo", current.ammo))
        current.reserve = int(getattr(mode, "reserve_ammo", current.reserve))
        self.active_slot = slot
        target = self.weapons[slot]
        self._apply(mode, target)
        self.switch_cooldown = 0.22
        try:
            mode.reloading = False
            mode.reload_timer = 0.0
            mode.fire_timer = max(float(getattr(mode, "fire_timer", 0.0)), 0.12)
            mode.spawn_floating_text(target.spec.name, (0.0, -0.12), target.spec.accent, 0.030, 0.55)
            self.app.audio.play("reload", self.app.sfx_volume() * 0.22, 1.45)
        except Exception:
            pass

    def _refresh_active_stats(self, mode) -> None:
        runtime = self.weapons.get(self.active_slot)
        if runtime is None:
            return
        runtime.ammo = int(getattr(mode, "ammo", runtime.ammo))
        runtime.reserve = int(getattr(mode, "reserve_ammo", runtime.reserve))
        self._apply_perk_stats(mode, runtime.spec)

    def _apply(self, mode, runtime: WeaponRuntime) -> None:
        spec = runtime.spec
        mode.weapon_name = spec.name
        self._apply_perk_stats(mode, spec)
        mode.weapon_spread = spec.spread
        mode.ammo = runtime.ammo
        mode.reserve_ammo = runtime.reserve
        try:
            mode.weapon_body.setScale(*spec.visual_scale)
            mode.weapon_barrel.setScale(1.0, spec.visual_scale[1], 1.0)
            mode.weapon_accent.setColor(spec.accent)
        except Exception:
            pass
        if hasattr(mode, "weapon_label"):
            try:
                mode.weapon_label["text"] = f"{spec.name} // SLOT {self.active_slot}"
                mode.weapon_label["text_fg"] = spec.accent
            except Exception:
                pass

    @staticmethod
    def _apply_perk_stats(mode, spec: WeaponSpec) -> None:
        run_damage = max(0.25, float(getattr(mode, "weapon_damage_multiplier", 1.0) or 1.0))
        permanent_damage = max(0.25, float(getattr(mode, "permanent_damage_multiplier", 1.0) or 1.0))
        conditional_damage = max(0.25, float(getattr(mode, "conditional_damage_multiplier", 1.0) or 1.0))
        run_reload = max(0.45, float(getattr(mode, "weapon_reload_multiplier", 1.0) or 1.0))
        permanent_reload = max(0.45, float(getattr(mode, "permanent_reload_multiplier", 1.0) or 1.0))
        fire_rate_mult = max(0.55, float(getattr(mode, "weapon_fire_rate_multiplier", 1.0) or 1.0))
        mag_bonus = max(0, int(getattr(mode, "weapon_mag_bonus", 0)))

        mode.weapon_damage = spec.damage * run_damage * permanent_damage * conditional_damage
        mode.fire_interval = max(0.035, spec.fire_interval * fire_rate_mult)
        mode.magazine_size = spec.magazine + mag_bonus
        mode.reload_time = max(0.55, spec.reload_time * run_reload * permanent_reload)

    def _update_label(self, mode) -> None:
        if self.label is None:
            return
        parts = []
        for slot in (1, 2, 3):
            runtime = self.weapons.get(slot)
            if runtime is None:
                continue
            spec = runtime.spec
            short = "AR" if spec.weapon_id == "ar" else "SMG" if spec.weapon_id == "smg" else "DMR"
            marker = "[" if slot == self.active_slot else " "
            end = "]" if slot == self.active_slot else " "
            parts.append(f"{marker}{slot} {short}{end}")
        self.label["text"] = "   ".join(parts)
