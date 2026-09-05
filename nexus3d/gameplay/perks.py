from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Callable, List, Optional

from direct.gui.DirectGui import DGG, DirectButton, DirectFrame, DirectLabel


@dataclass(frozen=True)
class Perk:
    name: str
    description: str
    apply: Callable[[object], None]


class PerkDirector:
    """V4 roguelite upgrade draft with keyboard and mouse selection."""

    def __init__(self, app) -> None:
        self.app = app
        self.mode_identity: Optional[int] = None
        self.last_wave = 0
        self.next_offer_wave = 2
        self.offer: List[Perk] = []
        self.panel: Optional[DirectFrame] = None
        self.key_down = {"z": False, "x": False, "c": False}
        self.rng = random.Random(0x5045524B5634)
        self.picks = 0

    @property
    def active(self) -> bool:
        return bool(self.offer)

    def reset(self) -> None:
        self._destroy_ui()
        self.mode_identity = None
        self.last_wave = 0
        self.next_offer_wave = 2
        self.offer.clear()
        self.key_down = {"z": False, "x": False, "c": False}
        self.picks = 0

    def update(self, dt: float, mode) -> None:
        game_id = str(getattr(mode, "game_id", ""))
        if game_id not in ("neon_ops", "zombie_siege", "orbital_wars"):
            return
        if id(mode) != self.mode_identity:
            self._attach(mode)

        if self.active:
            mode.paused = True
            try:
                mode.set_mouse_capture(False)
            except Exception:
                pass
            self._read_choice(mode)
            return

        wave = int(getattr(mode, "wave", 0))
        if wave != self.last_wave:
            self.last_wave = wave
            if wave >= self.next_offer_wave and not getattr(mode, "game_over", False):
                self._open_offer(mode)
                self.next_offer_wave = wave + 2

    def _attach(self, mode) -> None:
        self.reset()
        self.mode_identity = id(mode)
        self.last_wave = int(getattr(mode, "wave", 0))
        self.next_offer_wave = max(2, self.last_wave + 2)
        for key in ("z", "x", "c"):
            try:
                mode.key.bind(key)
            except Exception:
                pass

        # Shared modifier attributes. RunModifierDirector consumes these.
        mode.heal_on_kill = 0.0
        mode.armor_on_kill = 0.0
        mode.shield_on_kill = 0.0
        mode.energy_on_kill = 0.0
        mode.ammo_on_kill = 0
        mode.low_health_damage_bonus = 0.0
        mode.dash_reload_fraction = 0.0

        game_id = str(getattr(mode, "game_id", ""))
        if game_id == "neon_ops":
            mode.weapon_damage_multiplier = 1.0
            mode.weapon_reload_multiplier = 1.0
            mode.weapon_fire_rate_multiplier = 1.0
            mode.weapon_mag_bonus = 0
        elif game_id == "zombie_siege":
            mode.zombie_damage_multiplier = 1.0

    def _open_offer(self, mode) -> None:
        pool = self._pool_for(mode)
        if len(pool) < 3:
            return
        self.offer = self.rng.sample(pool, 3)
        mode.paused = True
        try:
            mode.set_mouse_capture(False)
        except Exception:
            pass

        self.panel = DirectFrame(
            parent=mode.base.aspect2d,
            frameColor=(0.006, 0.010, 0.018, 0.96),
            frameSize=(-1.78, 1.78, -1.02, 1.02),
            sortOrder=120,
        )
        DirectLabel(
            parent=self.panel,
            text="TACTICAL UPGRADE",
            text_fg=(0.95, 0.97, 1.0, 1.0),
            text_scale=0.085,
            frameColor=(0, 0, 0, 0),
            pos=(0, 0, 0.56),
        )
        DirectLabel(
            parent=self.panel,
            text="CHOOSE ONE // CLICK A CARD OR PRESS Z / X / C",
            text_fg=(0.48, 0.62, 0.76, 1.0),
            text_scale=0.031,
            frameColor=(0, 0, 0, 0),
            pos=(0, 0, 0.43),
        )

        keys = ("Z", "X", "C")
        accents = (
            (0.05, 0.90, 1.0, 1.0),
            (0.62, 0.22, 1.0, 1.0),
            (1.0, 0.42, 0.08, 1.0),
        )
        for index, perk in enumerate(self.offer):
            x = -0.92 + index * 0.92
            accent = accents[index]
            card = DirectButton(
                parent=self.panel,
                text="",
                frameColor=(0.035, 0.055, 0.085, 0.96),
                frameSize=(-0.38, 0.38, -0.30, 0.30),
                pos=(x, 0, 0.02),
                command=self._choose,
                extraArgs=[mode, index],
                relief=DGG.FLAT,
            )
            DirectFrame(parent=card, frameColor=accent, frameSize=(-0.38, 0.38, 0.275, 0.30))
            DirectLabel(
                parent=card,
                text=keys[index],
                text_fg=accent,
                text_scale=0.065,
                frameColor=(0, 0, 0, 0),
                pos=(0, 0, 0.18),
            )
            DirectLabel(
                parent=card,
                text=perk.name,
                text_fg=(0.96, 0.98, 1.0, 1.0),
                text_scale=0.041,
                text_wordwrap=17,
                frameColor=(0, 0, 0, 0),
                pos=(0, 0, 0.07),
            )
            DirectLabel(
                parent=card,
                text=perk.description,
                text_fg=(0.62, 0.70, 0.80, 1.0),
                text_scale=0.027,
                text_wordwrap=23,
                frameColor=(0, 0, 0, 0),
                pos=(0, 0, -0.10),
            )
        try:
            self.app.audio.play("menu_open", self.app.sfx_volume() * 0.70, 0.82)
        except Exception:
            pass

    def _read_choice(self, mode) -> None:
        for index, key in enumerate(("z", "x", "c")):
            down = bool(mode.key[key])
            if down and not self.key_down[key]:
                self._choose(mode, index)
                self.key_down[key] = down
                return
            self.key_down[key] = down

    def _choose(self, mode, index: int) -> None:
        if index < 0 or index >= len(self.offer):
            return
        perk = self.offer[index]
        try:
            perk.apply(mode)
        except Exception:
            pass
        self.picks += 1
        self.offer.clear()
        self._destroy_ui()
        mode.paused = False
        try:
            mode.spawn_floating_text(
                f"UPGRADE: {perk.name}",
                (0.0, 0.28),
                (0.18, 1.0, 0.62, 1.0),
                0.040,
                1.0,
            )
            mode.on_resume()
            self.app.audio.play("pickup", self.app.sfx_volume() * 0.74, 1.18)
        except Exception:
            pass

    def _pool_for(self, mode) -> List[Perk]:
        game_id = str(getattr(mode, "game_id", ""))
        if game_id == "neon_ops":
            return [
                Perk(
                    "HOLLOW POINTS",
                    "+14% weapon damage",
                    lambda m: setattr(
                        m,
                        "weapon_damage_multiplier",
                        float(getattr(m, "weapon_damage_multiplier", 1.0)) * 1.14,
                    ),
                ),
                Perk("EXTENDED MAGS", "+8 rounds to every magazine", self._neon_mag),
                Perk(
                    "FAST HANDS",
                    "Reload time reduced by 14%",
                    lambda m: setattr(
                        m,
                        "weapon_reload_multiplier",
                        float(getattr(m, "weapon_reload_multiplier", 1.0)) * 0.86,
                    ),
                ),
                Perk(
                    "OVERCLOCK",
                    "Fire rate +12%",
                    lambda m: setattr(
                        m,
                        "weapon_fire_rate_multiplier",
                        float(getattr(m, "weapon_fire_rate_multiplier", 1.0)) * 0.88,
                    ),
                ),
                Perk(
                    "BLOOD CIRCUIT",
                    "Every kill restores 3 health",
                    lambda m: setattr(m, "heal_on_kill", float(getattr(m, "heal_on_kill", 0.0)) + 3.0),
                ),
                Perk(
                    "DASH FEED",
                    "Dashing instantly refills 28% of the magazine",
                    lambda m: setattr(
                        m,
                        "dash_reload_fraction",
                        max(float(getattr(m, "dash_reload_fraction", 0.0)), 0.28),
                    ),
                ),
                Perk(
                    "ADRENAL CORE",
                    "+35% damage while under 35 HP",
                    lambda m: setattr(
                        m,
                        "low_health_damage_bonus",
                        float(getattr(m, "low_health_damage_bonus", 0.0)) + 0.35,
                    ),
                ),
                Perk(
                    "EXECUTION CACHE",
                    "Every kill generates 3 reserve rounds",
                    lambda m: setattr(m, "ammo_on_kill", int(getattr(m, "ammo_on_kill", 0)) + 3),
                ),
                Perk("COMBAT BOOTS", "+10% walk and sprint speed", self._neon_mobility),
                Perk(
                    "ARMOR TAP",
                    "Every kill restores 2 armor",
                    lambda m: setattr(m, "armor_on_kill", float(getattr(m, "armor_on_kill", 0.0)) + 2.0),
                ),
            ]

        if game_id == "zombie_siege":
            return [
                Perk(
                    "HEAVY PELLETS",
                    "+16% shotgun damage",
                    lambda m: setattr(
                        m,
                        "zombie_damage_multiplier",
                        float(getattr(m, "zombie_damage_multiplier", 1.0)) * 1.16,
                    ),
                ),
                Perk("TUBE EXTENDER", "+2 shell capacity", self._zombie_mag),
                Perk(
                    "FAST HANDS",
                    "Reload time reduced by 16%",
                    lambda m: setattr(m, "reload_time", max(0.70, float(getattr(m, "reload_time", 1.65)) * 0.84)),
                ),
                Perk(
                    "NECRO SIPHON",
                    "Every infected kill restores 2.5 health",
                    lambda m: setattr(m, "heal_on_kill", float(getattr(m, "heal_on_kill", 0.0)) + 2.5),
                ),
                Perk(
                    "SCRAP PLATING",
                    "Every kill restores 1.5 armor",
                    lambda m: setattr(m, "armor_on_kill", float(getattr(m, "armor_on_kill", 0.0)) + 1.5),
                ),
                Perk(
                    "SHELL FORGE",
                    "Every kill generates 1 reserve shell",
                    lambda m: setattr(m, "ammo_on_kill", int(getattr(m, "ammo_on_kill", 0)) + 1),
                ),
                Perk(
                    "LAST STAND",
                    "+40% damage while under 35 HP",
                    lambda m: setattr(
                        m,
                        "low_health_damage_bonus",
                        float(getattr(m, "low_health_damage_bonus", 0.0)) + 0.40,
                    ),
                ),
                Perk(
                    "TRAUMA KIT",
                    "+35 health immediately",
                    lambda m: setattr(m, "health", min(100.0, float(getattr(m, "health", 0.0)) + 35.0)),
                ),
            ]

        return [
            Perk(
                "LASER CYCLER",
                "Laser fire rate +14%",
                lambda m: setattr(m, "laser_interval", max(0.055, float(getattr(m, "laser_interval", 0.12)) * 0.86)),
            ),
            Perk(
                "MISSILE RACK",
                "+3 missiles",
                lambda m: setattr(m, "missiles", min(16, int(getattr(m, "missiles", 0)) + 3)),
            ),
            Perk(
                "SHIELD CELL",
                "+40 shield immediately",
                lambda m: setattr(m, "shield", min(100.0, float(getattr(m, "shield", 0.0)) + 40.0)),
            ),
            Perk(
                "VOID SIPHON",
                "Every kill restores 4 shield",
                lambda m: setattr(m, "shield_on_kill", float(getattr(m, "shield_on_kill", 0.0)) + 4.0),
            ),
            Perk(
                "REACTOR FEED",
                "Every kill restores 5 energy",
                lambda m: setattr(m, "energy_on_kill", float(getattr(m, "energy_on_kill", 0.0)) + 5.0),
            ),
            Perk(
                "HULL REPAIR",
                "+35 hull immediately",
                lambda m: setattr(m, "health", min(100.0, float(getattr(m, "health", 0.0)) + 35.0)),
            ),
            Perk(
                "ENERGY CELL",
                "+55 energy immediately",
                lambda m: setattr(m, "energy", min(100.0, float(getattr(m, "energy", 0.0)) + 55.0)),
            ),
            Perk(
                "PULSE RESET",
                "Pulse cooldown immediately cleared",
                lambda m: setattr(m, "pulse_cooldown", 0.0),
            ),
        ]

    @staticmethod
    def _neon_mag(mode) -> None:
        mode.weapon_mag_bonus = int(getattr(mode, "weapon_mag_bonus", 0)) + 8
        mode.magazine_size = int(getattr(mode, "magazine_size", 30)) + 8
        mode.ammo = min(mode.magazine_size, int(getattr(mode, "ammo", 0)) + 8)

    @staticmethod
    def _neon_mobility(mode) -> None:
        mode.walk_speed = float(getattr(mode, "walk_speed", 8.5)) * 1.10
        mode.sprint_speed = float(getattr(mode, "sprint_speed", 12.8)) * 1.10

    @staticmethod
    def _zombie_mag(mode) -> None:
        mode.mag_size = int(getattr(mode, "mag_size", 8)) + 2
        mode.ammo = min(mode.mag_size, int(getattr(mode, "ammo", 0)) + 2)

    def _destroy_ui(self) -> None:
        if self.panel is not None:
            try:
                self.panel.destroy()
            except Exception:
                pass
        self.panel = None

    def destroy(self) -> None:
        self.reset()
