from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Dict, Optional, Tuple

from direct.gui.DirectGui import DirectFrame, DirectLabel
from panda3d.core import TextNode

Color = Tuple[float, float, float, float]


@dataclass(frozen=True)
class OperationStage:
    label: str
    metric: str
    target: float
    relative: bool = True


@dataclass(frozen=True)
class OperationTemplate:
    codename: str
    stages: Tuple[OperationStage, ...]
    reward_score: int
    reward_xp: int
    reward_credits: int


OPERATION_BOOK: Dict[str, Tuple[OperationTemplate, ...]] = {
    "neon_ops": (
        OperationTemplate(
            "GLASS CIRCUIT",
            (
                OperationStage("Neutralize 8 hostiles", "kills", 8),
                OperationStage("Clear 2 additional waves", "wave", 2),
                OperationStage("Earn 3,200 additional score", "score", 3200),
            ),
            2500, 260, 135,
        ),
        OperationTemplate(
            "BLACK ICE",
            (
                OperationStage("Build a x6 combat combo", "combo", 6, False),
                OperationStage("Neutralize 12 hostiles", "kills", 12),
                OperationStage("Clear 3 additional waves", "wave", 3),
            ),
            3100, 300, 165,
        ),
    ),
    "street_rush": (
        OperationTemplate(
            "MIDNIGHT VECTOR",
            (
                OperationStage("Drive 850 m", "distance", 850),
                OperationStage("Earn 3,000 additional score", "score", 3000),
                OperationStage("Build a x5 close-call chain", "combo", 5, False),
            ),
            2300, 230, 125,
        ),
        OperationTemplate(
            "REDLINE GHOST",
            (
                OperationStage("Drive 1,100 m", "distance", 1100),
                OperationStage("Build a x7 close-call chain", "combo", 7, False),
                OperationStage("Earn 4,200 additional score", "score", 4200),
            ),
            3000, 280, 155,
        ),
    ),
    "zombie_siege": (
        OperationTemplate(
            "LAST LIGHT",
            (
                OperationStage("Eliminate 14 infected", "kills", 14),
                OperationStage("Survive 45 additional seconds", "survival", 45),
                OperationStage("Clear 2 additional nights", "wave", 2),
            ),
            2600, 270, 140,
        ),
        OperationTemplate(
            "DEAD SIGNAL",
            (
                OperationStage("Build a x6 elimination combo", "combo", 6, False),
                OperationStage("Eliminate 20 infected", "kills", 20),
                OperationStage("Clear 3 additional nights", "wave", 3),
            ),
            3300, 320, 175,
        ),
    ),
    "orbital_wars": (
        OperationTemplate(
            "VOID LANCE",
            (
                OperationStage("Destroy 10 hostiles", "kills", 10),
                OperationStage("Clear 2 additional sectors", "wave", 2),
                OperationStage("Earn 4,000 additional score", "score", 4000),
            ),
            2900, 280, 150,
        ),
        OperationTemplate(
            "STARBREAKER",
            (
                OperationStage("Build a x6 combat chain", "combo", 6, False),
                OperationStage("Destroy 15 hostiles", "kills", 15),
                OperationStage("Clear 3 additional sectors", "wave", 3),
            ),
            3500, 330, 185,
        ),
    ),
    "cyber_runner": (
        OperationTemplate(
            "SKYLINE ZERO",
            (
                OperationStage("Run 900 m", "distance", 900),
                OperationStage("Reach x4 flow", "multiplier", 4, False),
                OperationStage("Earn 3,500 additional score", "score", 3500),
            ),
            2400, 240, 130,
        ),
        OperationTemplate(
            "VERTIGO",
            (
                OperationStage("Run 1,250 m", "distance", 1250),
                OperationStage("Reach x6 flow", "multiplier", 6, False),
                OperationStage("Earn 5,000 additional score", "score", 5000),
            ),
            3150, 300, 165,
        ),
    ),
}


class MissionDirector:
    """Three-stage authored operations layered over the endless arcade loops.

    Completing an operation records a real win, pays persistent rewards and then
    rolls a harder follow-up operation without ending the run.
    """

    def __init__(self, app) -> None:
        self.app = app
        self.mode_identity: Optional[int] = None
        self.operation: Optional[OperationTemplate] = None
        self.stage_index = 0
        self.stage_start_value = 0.0
        self.tier = 0
        self.run_streak = 0
        self.cooldown = 0.0
        self.panel: Optional[DirectFrame] = None
        self.title_label: Optional[DirectLabel] = None
        self.stage_label: Optional[DirectLabel] = None
        self.progress_label: Optional[DirectLabel] = None
        self.bar: Optional[DirectFrame] = None
        self.flash = 0.0

    def reset(self) -> None:
        self._destroy_ui()
        self.mode_identity = None
        self.operation = None
        self.stage_index = 0
        self.stage_start_value = 0.0
        self.tier = 0
        self.run_streak = 0
        self.cooldown = 0.0
        self.flash = 0.0

    def update(self, dt: float, mode) -> None:
        if mode is None or not getattr(mode, "active", False):
            return
        if id(mode) != self.mode_identity:
            self._attach(mode)
        if not bool(self.app.save.setting("missions", True)):
            return
        if self.operation is None or getattr(mode, "game_over", False):
            return
        if getattr(mode, "paused", False):
            return

        dt = max(0.0, float(dt))
        if self.cooldown > 0.0:
            self.cooldown = max(0.0, self.cooldown - dt)
            if self.cooldown <= 0.0:
                self._roll_next(mode)
            return

        stage = self.operation.stages[self.stage_index]
        value = self._metric_value(mode, stage.metric)
        progress = value - self.stage_start_value if stage.relative else value
        ratio = max(0.0, min(1.0, progress / max(0.001, stage.target)))
        self._update_ui(progress, ratio)

        if ratio >= 1.0:
            self._complete_stage(mode)

        self.flash = max(0.0, self.flash - dt * 2.0)
        if self.panel is not None:
            if self.flash > 0.0:
                pulse = 0.90 + math.sin(self.flash * 22.0) * 0.08
                self.panel.setColorScale(pulse, 1.0, pulse, 1.0)
            else:
                self.panel.clearColorScale()

    def _attach(self, mode) -> None:
        self.reset()
        self.mode_identity = id(mode)
        game_id = str(getattr(mode, "game_id", ""))
        wins = int(self.app.save.data.get("stats", {}).get(game_id, {}).get("wins", 0))
        templates = OPERATION_BOOK.get(game_id)
        if not templates:
            return
        self.tier = max(0, wins // max(1, len(templates)))
        self.operation = self._scaled_template(templates[wins % len(templates)], self.tier)
        self.stage_index = 0
        self.stage_start_value = self._metric_value(mode, self.operation.stages[0].metric)
        if bool(self.app.save.setting("missions", True)):
            self._build_ui(mode)
            self._update_ui(0.0, 0.0)

    @staticmethod
    def _scaled_template(template: OperationTemplate, tier: int) -> OperationTemplate:
        tier = max(0, int(tier))
        target_scale = 1.0 + min(0.75, tier * 0.10)
        reward_scale = 1.0 + min(1.25, tier * 0.14)
        scaled_stages = []
        for stage in template.stages:
            target = (
                stage.target * target_scale
                if stage.relative and stage.metric not in ("wave",)
                else stage.target
            )
            label = stage.label
            if abs(target - stage.target) > 0.001:
                label = re.sub(r"\d[\d,]*", f"{int(round(target)):,}", label, count=1)
            scaled_stages.append(OperationStage(label, stage.metric, target, stage.relative))
        stages = tuple(scaled_stages)
        return OperationTemplate(
            codename=template.codename,
            stages=stages,
            reward_score=int(template.reward_score * reward_scale),
            reward_xp=int(template.reward_xp * reward_scale),
            reward_credits=int(template.reward_credits * reward_scale),
        )

    def _build_ui(self, mode) -> None:
        self._destroy_ui()
        accent = getattr(getattr(mode, "meta", None), "accent", (0.05, 0.90, 1.0, 1.0))
        self.panel = DirectFrame(
            parent=mode.hud_root,
            frameColor=(0.010, 0.018, 0.032, 0.88),
            frameSize=(-0.58, 0.58, -0.105, 0.105),
            pos=(0.0, 0, 0.82),
        )
        DirectFrame(
            parent=self.panel,
            frameColor=accent,
            frameSize=(-0.58, 0.58, 0.088, 0.105),
        )
        self.title_label = DirectLabel(
            parent=self.panel,
            text="",
            text_fg=(0.95, 0.97, 1.0, 1.0),
            text_scale=0.027,
            text_align=TextNode.ALeft,
            frameColor=(0, 0, 0, 0),
            pos=(-0.53, 0, 0.043),
        )
        self.stage_label = DirectLabel(
            parent=self.panel,
            text="",
            text_fg=(0.60, 0.69, 0.80, 1.0),
            text_scale=0.021,
            text_align=TextNode.ALeft,
            frameColor=(0, 0, 0, 0),
            pos=(-0.53, 0, -0.010),
        )
        self.progress_label = DirectLabel(
            parent=self.panel,
            text="",
            text_fg=accent,
            text_scale=0.021,
            text_align=TextNode.ARight,
            frameColor=(0, 0, 0, 0),
            pos=(0.52, 0, -0.010),
        )
        DirectFrame(
            parent=self.panel,
            frameColor=(0.07, 0.09, 0.13, 0.95),
            frameSize=(-0.53, 0.53, -0.078, -0.059),
        )
        self.bar = DirectFrame(
            parent=self.panel,
            frameColor=accent,
            frameSize=(-0.53, -0.53, -0.078, -0.059),
        )

    def _complete_stage(self, mode) -> None:
        if self.operation is None:
            return
        self.flash = 1.0
        try:
            self.app.audio.play("pickup", self.app.sfx_volume() * 0.64, 1.08)
        except Exception:
            pass
        try:
            mode.spawn_floating_text(
                f"OBJECTIVE {self.stage_index + 1}/3 COMPLETE",
                (0.0, 0.24),
                getattr(mode.meta, "accent", (0.1, 0.9, 1.0, 1.0)),
                0.035,
                0.8,
            )
        except Exception:
            pass

        self.stage_index += 1
        if self.stage_index >= len(self.operation.stages):
            self._complete_operation(mode)
            return

        next_stage = self.operation.stages[self.stage_index]
        self.stage_start_value = self._metric_value(mode, next_stage.metric)
        self._update_ui(0.0, 0.0)

    def _complete_operation(self, mode) -> None:
        operation = self.operation
        if operation is None:
            return
        self.run_streak += 1
        credit_mult = 1.0
        progression = getattr(self.app, "progression", None)
        if progression is not None:
            try:
                credit_mult = float(progression.credit_multiplier())
            except Exception:
                credit_mult = 1.0
        credits = max(1, int(round(operation.reward_credits * credit_mult)))
        mode.score = float(getattr(mode, "score", 0.0)) + operation.reward_score
        self.app.save.add_credits(credits, save=False)
        self.app.save.add_xp(operation.reward_xp)
        self.app.save.record_mission_complete(str(getattr(mode, "game_id", "")), self.run_streak)
        self.app.save.save()
        try:
            mode.spawn_floating_text(
                f"OPERATION COMPLETE  +{credits} CR",
                (0.0, 0.30),
                (0.18, 1.0, 0.58, 1.0),
                0.044,
                1.35,
            )
            self.app.audio.play("menu_open", self.app.sfx_volume() * 0.75, 1.12)
        except Exception:
            pass
        if self.title_label is not None:
            self.title_label["text"] = f"OPERATION {operation.codename} // COMPLETE"
        if self.stage_label is not None:
            self.stage_label["text"] = "Follow-up operation incoming"
        if self.progress_label is not None:
            self.progress_label["text"] = f"+{operation.reward_xp} XP  +{credits} CR"
        if self.bar is not None:
            self.bar["frameSize"] = (-0.53, 0.53, -0.078, -0.059)
        self.cooldown = 3.0

    def _roll_next(self, mode) -> None:
        game_id = str(getattr(mode, "game_id", ""))
        templates = OPERATION_BOOK.get(game_id)
        if not templates:
            self.operation = None
            return
        wins = int(self.app.save.data.get("stats", {}).get(game_id, {}).get("wins", 0))
        self.tier = max(0, wins // max(1, len(templates)))
        self.operation = self._scaled_template(templates[wins % len(templates)], self.tier)
        self.stage_index = 0
        first = self.operation.stages[0]
        self.stage_start_value = self._metric_value(mode, first.metric)
        self._update_ui(0.0, 0.0)

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
        if metric == "combo":
            return float(getattr(mode, "combo", 0.0))
        if metric == "multiplier":
            return float(getattr(mode, "multiplier", 1.0))
        return 0.0

    def _update_ui(self, progress: float, ratio: float) -> None:
        if self.operation is None:
            return
        stage = self.operation.stages[self.stage_index]
        if self.title_label is not None:
            self.title_label["text"] = (
                f"OPERATION {self.operation.codename}  //  {self.stage_index + 1}/{len(self.operation.stages)}"
            )
        if self.stage_label is not None:
            self.stage_label["text"] = stage.label
        if self.progress_label is not None:
            if stage.target >= 100:
                self.progress_label["text"] = f"{int(progress):,} / {int(stage.target):,}"
            else:
                self.progress_label["text"] = f"{progress:.0f} / {stage.target:.0f}"
        if self.bar is not None:
            self.bar["frameSize"] = (-0.53, -0.53 + 1.06 * ratio, -0.078, -0.059)

    def _destroy_ui(self) -> None:
        if self.panel is not None:
            try:
                self.panel.destroy()
            except Exception:
                pass
        self.panel = None
        self.title_label = None
        self.stage_label = None
        self.progress_label = None
        self.bar = None

    def destroy(self) -> None:
        self.reset()
