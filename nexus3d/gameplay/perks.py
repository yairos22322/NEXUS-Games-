from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Callable, List, Optional

from direct.gui.DirectGui import DirectFrame, DirectLabel


@dataclass(frozen=True)
class Perk:
    name: str
    description: str
    apply: Callable[[object], None]


class PerkDirector:
    """Roguelite-style upgrade choices every few combat waves."""

    def __init__(self, app) -> None:
        self.app = app
        self.mode_identity: Optional[int] = None
        self.last_wave = 0
        self.next_offer_wave = 2
        self.offer: List[Perk] = []
        self.panel: Optional[DirectFrame] = None
        self.key_down = {"z": False, "x": False, "c": False}
        self.rng = random.Random(0x5045524B5633)
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
            # Escape is owned by BaseMode. If it toggles pause while this overlay
            # is open, immediately restore the modal state so gameplay can never
            # continue invisibly behind the perk cards.
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
        if str(getattr(mode, "game_id", "")) == "neon_ops":
            mode.weapon_damage_multiplier = 1.0
            mode.weapon_reload_multiplier = 1.0
            mode.weapon_mag_bonus = 0

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
        DirectLabel(parent=self.panel,text="TACTICAL UPGRADE",text_fg=(0.95,0.97,1.0,1.0),text_scale=0.085,frameColor=(0,0,0,0),pos=(0,0,0.56))
        DirectLabel(parent=self.panel,text="CHOOSE ONE UPGRADE FOR THIS RUN",text_fg=(0.48,0.62,0.76,1.0),text_scale=0.031,frameColor=(0,0,0,0),pos=(0,0,0.43))
        keys = ("Z", "X", "C")
        accents = ((0.05,0.90,1.0,1.0), (0.62,0.22,1.0,1.0), (1.0,0.42,0.08,1.0))
        for index, perk in enumerate(self.offer):
            x = -0.92 + index * 0.92
            card = DirectFrame(parent=self.panel,frameColor=(0.035,0.055,0.085,0.94),frameSize=(-0.38,0.38,-0.30,0.30),pos=(x,0,0.02))
            DirectFrame(parent=card,frameColor=accents[index],frameSize=(-0.38,0.38,0.275,0.30))
            DirectLabel(parent=card,text=keys[index],text_fg=accents[index],text_scale=0.065,frameColor=(0,0,0,0),pos=(0,0,0.18))
            DirectLabel(parent=card,text=perk.name,text_fg=(0.96,0.98,1.0,1.0),text_scale=0.041,text_wordwrap=17,frameColor=(0,0,0,0),pos=(0,0,0.07))
            DirectLabel(parent=card,text=perk.description,text_fg=(0.62,0.70,0.80,1.0),text_scale=0.027,text_wordwrap=23,frameColor=(0,0,0,0),pos=(0,0,-0.10))
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
            mode.spawn_floating_text(f"UPGRADE: {perk.name}",(0.0,0.28),(0.18,1.0,0.62,1.0),0.040,1.0)
            mode.on_resume()
            self.app.audio.play("pickup", self.app.sfx_volume() * 0.74, 1.18)
        except Exception:
            pass

    def _pool_for(self, mode) -> List[Perk]:
        game_id = str(getattr(mode, "game_id", ""))
        if game_id == "neon_ops":
            return [
                Perk("HOLLOW POINTS", "+12% weapon damage", lambda m: setattr(m,"weapon_damage_multiplier",float(getattr(m,"weapon_damage_multiplier",1.0))*1.12)),
                Perk("EXTENDED MAGS", "+6 rounds to every magazine", self._neon_mag),
                Perk("FAST HANDS", "Reload time reduced by 12%", lambda m: setattr(m,"weapon_reload_multiplier",float(getattr(m,"weapon_reload_multiplier",1.0))*0.88)),
                Perk("ARMOR PLATES", "+30 armor immediately", lambda m: setattr(m,"armor",min(100.0,float(getattr(m,"armor",0.0))+30.0))),
                Perk("COMBAT BOOTS", "+8% walk and sprint speed", self._neon_mobility),
                Perk("FIELD AMMO", "+90 reserve ammo", lambda m: setattr(m,"reserve_ammo",int(getattr(m,"reserve_ammo",0))+90)),
            ]
        if game_id == "zombie_siege":
            return [
                Perk("HEAVY PELLETS", "+14% shotgun damage", lambda m: setattr(m,"damage",float(getattr(m,"damage",46.0))*1.14)),
                Perk("TUBE EXTENDER", "+2 shell capacity", self._zombie_mag),
                Perk("FAST HANDS", "Reload time reduced by 14%", lambda m: setattr(m,"reload_time",max(0.75,float(getattr(m,"reload_time",1.65))*0.86))),
                Perk("TRAUMA KIT", "+35 health now", lambda m: setattr(m,"health",min(100.0,float(getattr(m,"health",0.0))+35.0))),
                Perk("PLATE CARRIER", "+35 armor now", lambda m: setattr(m,"armor",min(100.0,float(getattr(m,"armor",0.0))+35.0))),
                Perk("SHELL CACHE", "+30 reserve shells", lambda m: setattr(m,"reserve",int(getattr(m,"reserve",0))+30)),
            ]
        return [
            Perk("LASER CYCLER", "Laser fire rate +12%", lambda m: setattr(m,"laser_interval",max(0.055,float(getattr(m,"laser_interval",0.12))*0.88))),
            Perk("MISSILE RACK", "+3 missiles", lambda m: setattr(m,"missiles",min(12,int(getattr(m,"missiles",0))+3))),
            Perk("SHIELD CELL", "+40 shield immediately", lambda m: setattr(m,"shield",min(100.0,float(getattr(m,"shield",0.0))+40.0))),
            Perk("HULL REPAIR", "+35 hull immediately", lambda m: setattr(m,"health",min(100.0,float(getattr(m,"health",0.0))+35.0))),
            Perk("ENERGY CELL", "+55 energy immediately", lambda m: setattr(m,"energy",min(100.0,float(getattr(m,"energy",0.0))+55.0))),
            Perk("PULSE RESET", "Pulse cooldown immediately cleared", lambda m: setattr(m,"pulse_cooldown",0.0)),
        ]

    @staticmethod
    def _neon_mag(mode) -> None:
        mode.weapon_mag_bonus = int(getattr(mode, "weapon_mag_bonus", 0)) + 6
        mode.magazine_size = int(getattr(mode, "magazine_size", 30)) + 6
        mode.ammo = min(mode.magazine_size, int(getattr(mode, "ammo", 0)) + 6)

    @staticmethod
    def _neon_mobility(mode) -> None:
        mode.walk_speed = float(getattr(mode, "walk_speed", 8.5)) * 1.08
        mode.sprint_speed = float(getattr(mode, "sprint_speed", 12.8)) * 1.08

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
