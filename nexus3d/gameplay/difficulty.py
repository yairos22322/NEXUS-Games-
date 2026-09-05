from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional


@dataclass
class PerformanceWindow:
    score: float = 0.0
    score_rate: float = 0.0
    health: float = 100.0
    damage_rate: float = 0.0
    time_alive: float = 0.0
    intensity: float = 1.0


class AdaptiveDifficultyDirector:
    """Soft, reversible difficulty around the player's selected preset.

    V4 removes the V3 behaviour where some player max-speed / fire-rate values
    could ratchet upward permanently during a run. Only future encounter pressure
    is adjusted. Player power remains the product of chosen difficulty, upgrades
    and perks, not hidden one-way DDA mutations.
    """

    def __init__(self) -> None:
        self.window = PerformanceWindow()
        self._base_scale: Optional[float] = None
        self._last_score = 0.0
        self._last_health: Optional[float] = None
        self._sample_timer = 0.0
        self._damage_memory = 0.0
        self._score_memory = 0.0

    def reset(self) -> None:
        self.window = PerformanceWindow()
        self._base_scale = None
        self._last_score = 0.0
        self._last_health = None
        self._sample_timer = 0.0
        self._damage_memory = 0.0
        self._score_memory = 0.0

    def update(self, dt: float, mode) -> None:
        if dt <= 0.0 or mode is None or not getattr(mode, "active", False):
            return
        if getattr(mode, "paused", False) or getattr(mode, "game_over", False):
            return

        if self._base_scale is None:
            self._base_scale = float(getattr(mode, "difficulty_scale", 1.0))
            self._last_score = float(getattr(mode, "score", 0.0))
            self._last_health = self._health_value(mode)
            self.window.intensity = 1.0

        self.window.time_alive += dt
        self._sample_timer += dt
        self._damage_memory *= math.exp(-dt * 0.75)
        self._score_memory *= math.exp(-dt * 0.42)

        score = float(getattr(mode, "score", 0.0))
        score_gain = max(0.0, score - self._last_score)
        self._score_memory += score_gain
        self._last_score = score

        health = self._health_value(mode)
        if health is not None:
            if self._last_health is not None and health < self._last_health:
                self._damage_memory += self._last_health - health
            self._last_health = health
            self.window.health = health

        if self._sample_timer < 0.25:
            return
        step = self._sample_timer
        self._sample_timer = 0.0

        self.window.score = score
        self.window.score_rate = self._score_memory * 0.42
        self.window.damage_rate = self._damage_memory * 0.75

        target = self._target_intensity(mode)
        sharpness = 0.22 if target > self.window.intensity else 0.62
        blend = 1.0 - math.exp(-sharpness * step)
        self.window.intensity += (target - self.window.intensity) * blend
        self.window.intensity = max(0.88, min(1.16, self.window.intensity))

        if self._base_scale is not None:
            mode.difficulty_scale = self._base_scale * self.window.intensity

        self._apply_mode_pressure(mode)

    def _target_intensity(self, mode) -> float:
        game_id = str(getattr(mode, "game_id", ""))
        score_rate = self.window.score_rate
        damage = self.window.damage_rate
        health = self.window.health
        alive = self.window.time_alive

        score_thresholds = {
            "neon_ops": 110.0,
            "street_rush": 95.0,
            "zombie_siege": 90.0,
            "orbital_wars": 120.0,
            "cyber_runner": 85.0,
        }
        threshold = score_thresholds.get(game_id, 100.0)
        performance = max(
            -1.0,
            min(1.0, (score_rate - threshold) / max(40.0, threshold)),
        )

        target = 1.0 + performance * 0.09
        if health < 32.0:
            target -= 0.10
        elif health < 52.0:
            target -= 0.045
        elif health > 82.0 and alive > 45.0:
            target += 0.025

        if damage > 22.0:
            target -= 0.08
        elif damage > 10.0:
            target -= 0.035

        target += min(0.04, max(0.0, alive - 80.0) / 3600.0)
        return max(0.88, min(1.16, target))

    def _apply_mode_pressure(self, mode) -> None:
        intensity = self.window.intensity
        game_id = str(getattr(mode, "game_id", ""))
        mode.v4_encounter_intensity = intensity

        if game_id == "neon_ops" and hasattr(mode, "spawn_interval"):
            mode.spawn_interval = max(0.26, 0.42 / max(0.92, intensity))
        elif game_id == "zombie_siege" and hasattr(mode, "wave_break"):
            if getattr(mode, "spawn_remaining", 1) <= 0 and not getattr(mode, "zombies", []):
                desired = 1.4 / max(0.92, intensity)
                mode.wave_break = max(0.85, min(float(mode.wave_break), desired))

    @staticmethod
    def _health_value(mode) -> Optional[float]:
        if hasattr(mode, "health"):
            try:
                return max(0.0, min(100.0, float(mode.health)))
            except Exception:
                return None
        return None
