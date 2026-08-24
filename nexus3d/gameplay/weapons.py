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
    """Runtime three-weapon loadout layered over the existing FPS rules."""

    SPECS = (
        WeaponSpec(
            weapon_id="ar",
            name="VX-7 ASSAULT",
            damage=29.0,
            fire_interval=0.095,
            spread=0.014,
            magazine=30,
            reserve=150,
            reload_time=1.52,
            visual_scale=(1.0, 1.0, 1.0),
            accent=(0.05, 0.90, 1.0, 1.0),
        ),
        WeaponSpec(
            weapon_id="smg",
            name="KITE-9 SMG",
            damage=18.5,
            fire_interval=0.060,
            spread=0.024,
            magazine=42,
            reserve=210,
            reload_time=1.28,
            visual_scale=(0.94, 0.82, 0.92),
            accent=(0.60, 0.24, 1.0, 1.0),
        ),
        WeaponSpec(
            weapon_id="dmr",
            name="SENTINEL DMR",
            damage=52.0,
            fire_interval=0.235,
            spread=0.006,
            magazine=12,
            reserve=72,
            reload_time=1.78,
            visual_scale=(1.02, 1.22, 0.96),
            accent=(1.0, 0.42, 0.08, 1.0),
        ),
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
        damage_bonus = min(0.18, max(0, level - 1) * 0.006)
        for slot, spec in enumerate(self.SPECS, start=1):
            scaled_spec = WeaponSpec(
                weapon_id=spec.weapon_id,
                name=spec.name,
                damage=spec.damage * (1.0 + damage_bonus),
                fire_interval=spec.fire_interval,
                spread=spec.spread,
                magazine=spec.magazine,
                reserve=spec.reserve,
                reload_time=spec.reload_time,
                visual_scale=spec.visual_scale,
                accent=spec.accent,
            )
            self.weapons[slot] = WeaponRuntime(scaled_spec, scaled_spec.magazine, scaled_spec.reserve)

        # Preserve the base-mode starting ammo in the assault slot when possible.
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
        self.switch_cooldown = 0.26
        try:
            mode.reloading = False
            mode.reload_timer = 0.0
            mode.fire_timer = max(float(getattr(mode, "fire_timer", 0.0)), 0.16)
            mode.spawn_floating_text(
                target.spec.name,
                (0.0, -0.12),
                target.spec.accent,
                0.030,
                0.55,
            )
            self.app.audio.play("reload", self.app.sfx_volume() * 0.22, 1.45)
        except Exception:
            pass

    def _apply(self, mode, runtime: WeaponRuntime) -> None:
        spec = runtime.spec
        mode.weapon_name = spec.name
        mode.weapon_damage = spec.damage
        mode.fire_interval = spec.fire_interval
        mode.weapon_spread = spec.spread
        mode.magazine_size = spec.magazine
        mode.reload_time = spec.reload_time
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

    def _update_label(self, mode) -> None:
        if self.label is None:
            return
        parts = []
        for slot in (1, 2, 3):
            spec = self.weapons[slot].spec
            short = "AR" if spec.weapon_id == "ar" else "SMG" if spec.weapon_id == "smg" else "DMR"
            marker = "[" if slot == self.active_slot else " "
            end = "]" if slot == self.active_slot else " "
            parts.append(f"{marker}{slot} {short}{end}")
        self.label["text"] = "   ".join(parts)
