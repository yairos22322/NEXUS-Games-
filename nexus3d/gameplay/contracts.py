from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional

from direct.gui.DirectGui import DirectFrame, DirectLabel
from panda3d.core import TextNode


@dataclass
class Contract:
    title: str
    label: str
    metric: str
    target: float
    start_value: float
    reward_score: int
    reward_xp: int
    reward_credits: int


class ContractDirector:
    """Creates short optional objectives that make each run feel authored.

    Contracts never block the core mode. They observe existing mode state,
    reward successful play and immediately roll into a harder follow-up goal.
    """

    def __init__(self, app) -> None:
        self.app = app
        self.mode_identity: Optional[int] = None
        self.contract: Optional[Contract] = None
        self.tier = 0
        self.panel: Optional[DirectFrame] = None
        self.title_label: Optional[DirectLabel] = None
        self.progress_label: Optional[DirectLabel] = None
        self.bar_bg: Optional[DirectFrame] = None
        self.bar: Optional[DirectFrame] = None
        self.flash = 0.0

    def reset(self) -> None:
        self._destroy_ui()
        self.mode_identity = None
        self.contract = None
        self.tier = 0
        self.flash = 0.0

    def update(self, dt: float, mode) -> None:
        if mode is None or not getattr(mode, "active", False):
            return
        if id(mode) != self.mode_identity:
            self._attach(mode)
        if self.contract is None or getattr(mode, "game_over", False):
            return

        value = self._metric_value(mode, self.contract.metric)
        progress = max(0.0, value - self.contract.start_value)
        ratio = max(0.0, min(1.0, progress / max(0.001, self.contract.target)))
        self._update_ui(progress, ratio)

        if ratio >= 1.0:
            self._complete(mode)

        self.flash = max(0.0, self.flash - max(0.0, dt) * 2.4)
        if self.panel is not None and self.flash > 0.0:
            glow = 0.86 + math.sin(self.flash * 18.0) * 0.10
            self.panel.setColorScale(glow, 1.0, glow, 1.0)
        elif self.panel is not None:
            self.panel.clearColorScale()

    def _attach(self, mode) -> None:
        self._destroy_ui()
        self.mode_identity = id(mode)
        self.tier = 0
        self.contract = self._make_contract(mode)
        if not bool(self.app.save.setting("contracts", True)):
            return
        self.panel = DirectFrame(
            parent=mode.hud_root,
            frameColor=(0.015, 0.025, 0.040, 0.84),
            frameSize=(-0.02, 0.76, -0.13, 0.13),
            pos=(-1.62, 0, 0.63),
        )
        self.title_label = DirectLabel(
            parent=self.panel,
            text="FIELD CONTRACT",
            text_fg=(0.55, 0.90, 1.0, 1.0),
            text_scale=0.026,
            text_align=TextNode.ALeft,
            frameColor=(0, 0, 0, 0),
            pos=(0.02, 0, 0.072),
        )
        self.progress_label = DirectLabel(
            parent=self.panel,
            text="",
            text_fg=(0.94, 0.97, 1.0, 1.0),
            text_scale=0.028,
            text_align=TextNode.ALeft,
            frameColor=(0, 0, 0, 0),
            pos=(0.02, 0, 0.012),
        )
        self.bar_bg = DirectFrame(
            parent=self.panel,
            frameColor=(0.08, 0.10, 0.14, 0.94),
            frameSize=(0.02, 0.71, -0.080, -0.058),
        )
        self.bar = DirectFrame(
            parent=self.panel,
            frameColor=(0.08, 0.82, 1.0, 0.95),
            frameSize=(0.02, 0.02, -0.080, -0.058),
        )
        self._update_ui(0.0, 0.0)

    def _make_contract(self, mode) -> Contract:
        game_id = str(getattr(mode, "game_id", ""))
        tier = self.tier
        score_reward = 650 + tier * 220
        xp_reward = 70 + tier * 20
        credits_reward = 20 + tier * 5

        if game_id == "neon_ops":
            metric = "kills" if tier % 2 == 0 else "wave"
            if metric == "kills":
                target = 6 + tier * 2
                label = f"Eliminate {int(target)} hostiles"
            else:
                target = 2
                label = "Clear 2 combat waves"
            start = self._metric_value(mode, metric)
        elif game_id == "street_rush":
            metric = "distance" if tier % 2 == 0 else "score"
            if metric == "distance":
                target = 650.0 + tier * 160.0
                label = f"Drive {int(target)} m"
            else:
                target = 2200.0 + tier * 500.0
                label = f"Earn {int(target):,} score"
            start = self._metric_value(mode, metric)
        elif game_id == "zombie_siege":
            metric = "wave" if tier % 2 == 0 else "survival"
            if metric == "wave":
                target = 2
                label = "Survive 2 nights"
            else:
                target = 38.0 + tier * 8.0
                label = f"Stay alive {int(target)} sec"
            start = self._metric_value(mode, metric)
        elif game_id == "orbital_wars":
            metric = "kills" if tier % 2 == 0 else "wave"
            if metric == "kills":
                target = 7 + tier * 2
                label = f"Destroy {int(target)} hostiles"
            else:
                target = 2
                label = "Clear 2 sectors"
            start = self._metric_value(mode, metric)
        else:
            metric = "distance" if tier % 2 == 0 else "multiplier"
            if metric == "distance":
                target = 720.0 + tier * 180.0
                label = f"Run {int(target)} m"
            else:
                target = 4 + min(5, tier)
                label = f"Reach x{int(target)} flow"
            start = 0.0 if metric == "multiplier" else self._metric_value(mode, metric)

        return Contract(
            title="FIELD CONTRACT",
            label=label,
            metric=metric,
            target=float(target),
            start_value=float(start),
            reward_score=score_reward,
            reward_xp=xp_reward,
            reward_credits=credits_reward,
        )

    def _metric_value(self, mode, metric: str) -> float:
        game_id = str(getattr(mode, "game_id", ""))
        if metric == "kills":
            try:
                return float(self.app.save.data["stats"][game_id].get("kills", 0))
            except Exception:
                return 0.0
        if metric == "wave":
            return float(getattr(mode, "wave", 0))
        if metric == "distance":
            return float(getattr(mode, "distance", 0.0))
        if metric == "score":
            return float(getattr(mode, "score", 0.0))
        if metric == "survival":
            return float(getattr(mode, "elapsed", 0.0))
        if metric == "multiplier":
            return float(getattr(mode, "multiplier", 1.0))
        return 0.0

    def _update_ui(self, progress: float, ratio: float) -> None:
        if self.contract is None or self.progress_label is None:
            return
        self.progress_label["text"] = self.contract.label
        if self.title_label is not None:
            self.title_label["text"] = (
                f"FIELD CONTRACT  //  {int(progress):d}/{int(self.contract.target):d}"
                if self.contract.target >= 2
                else "FIELD CONTRACT"
            )
        if self.bar is not None:
            self.bar["frameSize"] = (0.02, 0.02 + 0.69 * ratio, -0.080, -0.058)

    def _complete(self, mode) -> None:
        contract = self.contract
        if contract is None:
            return
        mode.score = float(getattr(mode, "score", 0.0)) + contract.reward_score
        try:
            self.app.save.profile["credits"] = int(self.app.save.profile.get("credits", 0)) + contract.reward_credits
            self.app.save.add_xp(contract.reward_xp)
        except Exception:
            pass
        try:
            mode.spawn_floating_text(
                f"CONTRACT COMPLETE  +{contract.reward_score} SCORE",
                (0.0, 0.30),
                (0.15, 1.0, 0.55, 1.0),
                0.040,
                1.15,
            )
            self.app.audio.play("pickup", self.app.sfx_volume() * 0.72, 1.08)
        except Exception:
            pass
        self.flash = 1.0
        self.tier += 1
        self.contract = self._make_contract(mode)

    def _destroy_ui(self) -> None:
        if self.panel is not None:
            try:
                self.panel.destroy()
            except Exception:
                pass
        self.panel = None
        self.title_label = None
        self.progress_label = None
        self.bar_bg = None
        self.bar = None
