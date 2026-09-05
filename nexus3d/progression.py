from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable, Dict, Optional, Tuple

from direct.gui.DirectGui import DGG, DirectButton, DirectFrame, DirectLabel
from panda3d.core import TextNode

from .config import CYAN, GREEN, MAGENTA, MUTED, ORANGE, PURPLE, WHITE, YELLOW

Color = Tuple[float, float, float, float]


@dataclass(frozen=True)
class UpgradeSpec:
    key: str
    name: str
    description: str
    max_rank: int
    base_cost: int
    cost_growth: float
    accent: Color

    def cost_for(self, rank: int) -> int:
        rank = max(0, int(rank))
        return int(round(self.base_cost * (self.cost_growth ** rank) / 5.0) * 5)


UPGRADES = (
    UpgradeSpec("firepower", "BALLISTIC CORE", "+4% combat damage per rank.", 8, 180, 1.42, CYAN),
    UpgradeSpec("handling", "REFLEX LINK", "-4% reload / weapon cycle time per rank.", 8, 160, 1.40, MAGENTA),
    UpgradeSpec("mobility", "KINETIC FRAME", "+3% movement and handling per rank.", 8, 150, 1.38, ORANGE),
    UpgradeSpec("reserves", "FIELD CACHE", "+8% starting ammo, energy and utility per rank.", 8, 140, 1.36, GREEN),
    UpgradeSpec("plating", "AEGIS PLATING", "+8 starting armor, or extra energy when armor is unavailable.", 8, 175, 1.41, PURPLE),
    UpgradeSpec("fortune", "SALVAGE PROTOCOL", "+6% credits from operations, contracts and run payouts.", 8, 210, 1.45, YELLOW),
)
UPGRADE_BY_KEY: Dict[str, UpgradeSpec] = {spec.key: spec for spec in UPGRADES}


@dataclass(frozen=True)
class AchievementSpec:
    key: str
    name: str
    description: str
    reward_credits: int
    reward_xp: int
    predicate: Callable[[object], bool]


def _total_stat(save, key: str) -> float:
    total = 0.0
    for row in save.data.get("stats", {}).values():
        try:
            total += float(row.get(key, 0))
        except (TypeError, ValueError):
            continue
    return total


ACHIEVEMENTS = (
    AchievementSpec(
        "first_deploy",
        "FIRST DEPLOY",
        "Complete your first run.",
        120,
        80,
        lambda s: int(s.profile.get("games_played", 0)) >= 1,
    ),
    AchievementSpec(
        "hunter_100",
        "HUNTER // 100",
        "Eliminate 100 enemies across combat modes.",
        300,
        180,
        lambda s: _total_stat(s, "kills") >= 100,
    ),
    AchievementSpec(
        "operation_5",
        "OPERATOR",
        "Complete 5 V4 operations.",
        450,
        260,
        lambda s: int(s.progression.get("missions_completed", 0)) >= 5,
    ),
    AchievementSpec(
        "road_10k",
        "TEN KILOMETERS",
        "Travel 10 km across movement modes.",
        350,
        220,
        lambda s: _total_stat(s, "distance") >= 10_000,
    ),
    AchievementSpec(
        "combo_12",
        "FLOW STATE",
        "Record a combo of 12 or higher.",
        400,
        250,
        lambda s: max(
            [int(row.get("best_combo", 0)) for row in s.data.get("stats", {}).values()] or [0]
        ) >= 12,
    ),
    AchievementSpec(
        "level_5",
        "NEXUS VETERAN",
        "Reach profile level 5.",
        600,
        350,
        lambda s: int(s.profile.get("level", 1)) >= 5,
    ),
)


class MetaProgressionDirector:
    """Persistent V4 economy, upgrade lab, achievements and run payouts."""

    def __init__(self, app) -> None:
        self.app = app
        self.lab_root: Optional[DirectFrame] = None
        self.menu_patch: Optional[DirectFrame] = None
        self.menu_hint: Optional[DirectLabel] = None
        self.toast_root: Optional[DirectFrame] = None
        self.toast_timer = 0.0
        self._achievement_timer = 0.0
        self._mode_identity: Optional[int] = None
        self._payout_mode_identity: Optional[int] = None
        self._last_lab_message = ""
        self.app.accept("f2", self.toggle_lab)

    def rank(self, key: str) -> int:
        return self.app.save.upgrade_rank(key)

    def credit_multiplier(self) -> float:
        return 1.0 + self.rank("fortune") * 0.06

    def damage_multiplier(self) -> float:
        return 1.0 + self.rank("firepower") * 0.04

    def reload_multiplier(self) -> float:
        return max(0.62, 1.0 - self.rank("handling") * 0.04)

    def movement_multiplier(self) -> float:
        return 1.0 + self.rank("mobility") * 0.03

    def reserve_multiplier(self) -> float:
        return 1.0 + self.rank("reserves") * 0.08

    def on_menu_open(self) -> None:
        self.close_lab()
        self._destroy_menu_decor()
        # Cover the old V2/ONLINE copy without forcing a risky rewrite of the
        # existing menu file. This keeps the overlay self-contained and truthful.
        self.menu_patch = DirectFrame(
            parent=self.app.aspect2d,
            frameColor=(0.012, 0.017, 0.031, 0.98),
            frameSize=(-1.67, -0.54, 0.575, 0.655),
            sortOrder=28,
        )
        DirectLabel(
            parent=self.menu_patch,
            text="BUILD 04.00   LOCAL PROFILE",
            text_fg=CYAN,
            text_scale=0.024,
            text_align=TextNode.ALeft,
            frameColor=(0, 0, 0, 0),
            pos=(-0.01, 0, 0.01),
        )
        self.menu_hint = DirectLabel(
            parent=self.app.aspect2d,
            text=self._hint_text(),
            text_fg=WHITE,
            text_scale=0.026,
            text_align=TextNode.ARight,
            frameColor=(0.018, 0.026, 0.043, 0.92),
            frameSize=(-0.82, 0.02, -0.045, 0.045),
            pos=(1.66, 0, -0.94),
            sortOrder=30,
        )

    def on_game_start(self) -> None:
        self.close_lab()
        self._destroy_menu_decor()
        self._mode_identity = None
        self._payout_mode_identity = None

    def _hint_text(self) -> str:
        credits = int(self.app.save.profile.get("credits", 0))
        return f"F2  NEXUS LAB   //   {credits:,} CR"

    def update(self, dt: float, mode) -> None:
        dt = max(0.0, float(dt))
        if mode is not None and getattr(mode, "active", False):
            if id(mode) != self._mode_identity:
                self._mode_identity = id(mode)
                self.apply_to_mode(mode)
            if getattr(mode, "game_over", False):
                self._award_run_payout(mode)
        else:
            self._mode_identity = None

        self._achievement_timer += dt
        if self._achievement_timer >= 0.75:
            self._achievement_timer = 0.0
            self._evaluate_achievements()

        if self.toast_root is not None:
            self.toast_timer = max(0.0, self.toast_timer - dt)
            if self.toast_timer <= 0.0:
                self.toast_root.destroy()
                self.toast_root = None
            else:
                alpha = min(1.0, self.toast_timer * 2.0)
                try:
                    self.toast_root.setColorScale(1, 1, 1, alpha)
                except Exception:
                    pass

        if self.menu_hint is not None:
            try:
                self.menu_hint["text"] = self._hint_text()
            except Exception:
                pass

    def apply_to_mode(self, mode) -> None:
        if not bool(self.app.save.setting("meta_progression", True)):
            return
        if bool(getattr(mode, "_v4_progression_applied", False)):
            return
        mode._v4_progression_applied = True
        mode.permanent_damage_multiplier = self.damage_multiplier()
        mode.permanent_reload_multiplier = self.reload_multiplier()
        mode.reward_credit_multiplier = self.credit_multiplier()

        movement = self.movement_multiplier()
        for attr in ("walk_speed", "sprint_speed", "lateral_speed", "accel", "brake", "max_speed"):
            value = getattr(mode, attr, None)
            if isinstance(value, (int, float)):
                setattr(mode, attr, float(value) * movement)

        reserve_multiplier = self.reserve_multiplier()
        for attr in ("reserve_ammo", "reserve", "nitro", "energy"):
            value = getattr(mode, attr, None)
            if isinstance(value, (int, float)):
                scaled = float(value) * reserve_multiplier
                setattr(mode, attr, int(round(scaled)) if isinstance(value, int) else scaled)
        if hasattr(mode, "missiles"):
            try:
                mode.missiles = int(mode.missiles) + self.rank("reserves") // 2
            except Exception:
                pass

        plating = self.rank("plating")
        if plating > 0:
            if hasattr(mode, "armor"):
                try:
                    mode.armor = min(100.0, float(mode.armor) + plating * 8.0)
                except Exception:
                    pass
            elif hasattr(mode, "shield"):
                try:
                    mode.shield = min(100.0, float(mode.shield) + plating * 6.0)
                except Exception:
                    pass
            elif hasattr(mode, "energy"):
                try:
                    mode.energy = min(140.0, float(mode.energy) + plating * 5.0)
                except Exception:
                    pass

        # Non-loadout combat modes consume these values directly.
        if str(getattr(mode, "game_id", "")) == "zombie_siege" and hasattr(mode, "damage"):
            try:
                mode.damage = float(mode.damage) * self.damage_multiplier()
            except Exception:
                pass
        if str(getattr(mode, "game_id", "")) == "orbital_wars" and hasattr(mode, "laser_interval"):
            try:
                rate_bonus = 1.0 - self.rank("firepower") * 0.018
                mode.laser_interval = max(0.065, float(mode.laser_interval) * max(0.78, rate_bonus))
            except Exception:
                pass

    def _award_run_payout(self, mode) -> None:
        if not bool(self.app.save.setting("run_payouts", True)):
            return
        identity = id(mode)
        if identity == self._payout_mode_identity:
            return
        self._payout_mode_identity = identity
        score = max(0.0, float(getattr(mode, "score", 0.0)))
        wave = max(0, int(getattr(mode, "wave", 0)))
        distance = max(0.0, float(getattr(mode, "distance", 0.0)))
        raw = 20 + min(180, int(score / 850.0)) + min(70, wave * 3) + min(60, int(distance / 500.0))
        payout = max(20, int(round(raw * self.credit_multiplier())))
        self.app.save.add_credits(payout)
        self._show_toast("RUN PAYOUT", f"+{payout:,} CR deposited", GREEN)

    def toggle_lab(self) -> None:
        if self.lab_root is not None:
            self.close_lab()
            return
        if getattr(self.app, "mode", None) is not None or getattr(self.app, "menu", None) is None:
            return
        self._build_lab()

    def close_lab(self) -> None:
        if self.lab_root is not None:
            try:
                self.lab_root.destroy()
            except Exception:
                pass
            self.lab_root = None

    def _build_lab(self) -> None:
        self.close_lab()
        self.lab_root = DirectFrame(
            parent=self.app.aspect2d,
            frameColor=(0.006, 0.010, 0.018, 0.985),
            frameSize=(-1.78, 1.78, -1.02, 1.02),
            sortOrder=160,
        )
        DirectLabel(
            parent=self.lab_root,
            text="NEXUS LAB // PERMANENT R&D",
            text_fg=CYAN,
            text_scale=0.070,
            text_align=TextNode.ALeft,
            frameColor=(0, 0, 0, 0),
            pos=(-1.52, 0, 0.82),
        )
        credits = int(self.app.save.profile.get("credits", 0))
        DirectLabel(
            parent=self.lab_root,
            text=f"{credits:,} CREDITS",
            text_fg=GREEN,
            text_scale=0.040,
            text_align=TextNode.ARight,
            frameColor=(0, 0, 0, 0),
            pos=(1.52, 0, 0.82),
        )
        DirectLabel(
            parent=self.lab_root,
            text="Spend credits on account-wide upgrades. F2 closes the lab.",
            text_fg=MUTED,
            text_scale=0.027,
            text_align=TextNode.ALeft,
            frameColor=(0, 0, 0, 0),
            pos=(-1.50, 0, 0.70),
        )

        for index, spec in enumerate(UPGRADES):
            row = index // 2
            col = index % 2
            x = -0.78 + col * 1.58
            z = 0.43 - row * 0.39
            rank = self.rank(spec.key)
            maxed = rank >= spec.max_rank
            cost = 0 if maxed else spec.cost_for(rank)
            card = DirectFrame(
                parent=self.lab_root,
                frameColor=(0.035, 0.050, 0.078, 0.96),
                frameSize=(-0.67, 0.67, -0.155, 0.155),
                pos=(x, 0, z),
            )
            DirectFrame(
                parent=card,
                frameColor=spec.accent,
                frameSize=(-0.67, -0.645, -0.155, 0.155),
            )
            DirectLabel(
                parent=card,
                text=spec.name,
                text_fg=WHITE,
                text_scale=0.034,
                text_align=TextNode.ALeft,
                frameColor=(0, 0, 0, 0),
                pos=(-0.57, 0, 0.070),
            )
            DirectLabel(
                parent=card,
                text=f"RANK {rank}/{spec.max_rank}",
                text_fg=spec.accent,
                text_scale=0.027,
                text_align=TextNode.ARight,
                frameColor=(0, 0, 0, 0),
                pos=(0.56, 0, 0.070),
            )
            DirectLabel(
                parent=card,
                text=spec.description,
                text_fg=MUTED,
                text_scale=0.023,
                text_align=TextNode.ALeft,
                text_wordwrap=34,
                frameColor=(0, 0, 0, 0),
                pos=(-0.57, 0, -0.005),
            )
            DirectButton(
                parent=card,
                text="MAXED" if maxed else f"UPGRADE  {cost:,} CR",
                text_fg=WHITE if not maxed else MUTED,
                text_scale=0.025,
                frameColor=(spec.accent[0] * 0.30, spec.accent[1] * 0.30, spec.accent[2] * 0.30, 0.95),
                frameSize=(-0.29, 0.29, -0.042, 0.042),
                pos=(0.27, 0, -0.098),
                command=self.purchase,
                extraArgs=[spec.key],
                state=DGG.DISABLED if maxed else DGG.NORMAL,
                relief=DGG.FLAT,
            )

        if self._last_lab_message:
            DirectLabel(
                parent=self.lab_root,
                text=self._last_lab_message,
                text_fg=YELLOW,
                text_scale=0.026,
                frameColor=(0, 0, 0, 0),
                pos=(0, 0, -0.80),
            )

    def purchase(self, key: str) -> None:
        spec = UPGRADE_BY_KEY.get(key)
        if spec is None:
            return
        rank = self.rank(key)
        if rank >= spec.max_rank:
            self._last_lab_message = f"{spec.name} is already max rank."
            self._build_lab()
            return
        cost = spec.cost_for(rank)
        if not self.app.save.spend_credits(cost):
            self._last_lab_message = f"Need {cost:,} CR for {spec.name}."
            self._build_lab()
            return
        self.app.save.set_upgrade_rank(key, rank + 1)
        self._last_lab_message = f"{spec.name} upgraded to rank {rank + 1}."
        try:
            self.app.audio.play("pickup", self.app.sfx_volume() * 0.72, 1.12)
        except Exception:
            pass
        self._build_lab()

    def _evaluate_achievements(self) -> None:
        unlocked = self.app.save.progression.setdefault("achievements", {})
        for spec in ACHIEVEMENTS:
            if bool(unlocked.get(spec.key, False)):
                continue
            try:
                complete = bool(spec.predicate(self.app.save))
            except Exception:
                complete = False
            if not complete:
                continue
            unlocked[spec.key] = True
            self.app.save.add_credits(spec.reward_credits, save=False)
            self.app.save.add_xp(spec.reward_xp)
            self.app.save.save()
            if bool(self.app.save.setting("achievement_toasts", True)):
                self._show_toast(
                    f"ACHIEVEMENT // {spec.name}",
                    f"{spec.description}  +{spec.reward_credits} CR",
                    YELLOW,
                )

    def _show_toast(self, title: str, body: str, accent: Color) -> None:
        if self.toast_root is not None:
            try:
                self.toast_root.destroy()
            except Exception:
                pass
        self.toast_root = DirectFrame(
            parent=self.app.aspect2d,
            frameColor=(0.012, 0.020, 0.034, 0.96),
            frameSize=(-0.62, 0.62, -0.10, 0.10),
            pos=(0, 0, 0.78),
            sortOrder=190,
        )
        DirectFrame(
            parent=self.toast_root,
            frameColor=accent,
            frameSize=(-0.62, 0.62, 0.083, 0.10),
        )
        DirectLabel(
            parent=self.toast_root,
            text=title,
            text_fg=WHITE,
            text_scale=0.030,
            frameColor=(0, 0, 0, 0),
            pos=(0, 0, 0.025),
        )
        DirectLabel(
            parent=self.toast_root,
            text=body,
            text_fg=MUTED,
            text_scale=0.022,
            frameColor=(0, 0, 0, 0),
            pos=(0, 0, -0.040),
        )
        self.toast_timer = 2.8

    def _destroy_menu_decor(self) -> None:
        if self.menu_patch is not None:
            try:
                self.menu_patch.destroy()
            except Exception:
                pass
            self.menu_patch = None
        if self.menu_hint is not None:
            try:
                self.menu_hint.destroy()
            except Exception:
                pass
            self.menu_hint = None

    def destroy(self) -> None:
        self.close_lab()
        self._destroy_menu_decor()
        if self.toast_root is not None:
            try:
                self.toast_root.destroy()
            except Exception:
                pass
            self.toast_root = None
