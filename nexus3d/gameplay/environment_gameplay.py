from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Dict, Optional

from panda3d.core import Vec3


@dataclass
class ModeBaseline:
    lateral_speed: Optional[float] = None
    brake: Optional[float] = None
    accel: Optional[float] = None
    sprint_speed: Optional[float] = None


class EnvironmentGameplayDirector:
    """Connects cinematic weather to gameplay without making it punitive.

    Visual weather previously had no effect on simulation. This director adds
    restrained, readable consequences: rain reduces peak road grip, dust/fog
    limits long-range enemy firing confidence, and strong wind slightly affects
    airborne parkour. Values are intentionally small so player skill remains
    more important than a random preset.
    """

    def __init__(self, app) -> None:
        self.app = app
        self.mode_id: Optional[int] = None
        self.baseline: Optional[ModeBaseline] = None
        self.wetness = 0.0
        self.visibility = 1.0
        self.wind = Vec3(0)
        self.kind = "none"
        self._time = 0.0

    def reset(self) -> None:
        self.mode_id = None
        self.baseline = None
        self.wetness = 0.0
        self.visibility = 1.0
        self.wind = Vec3(0)
        self.kind = "none"
        self._time = 0.0

    def update(self, dt: float, mode) -> None:
        if mode is None or not getattr(mode, "active", False):
            return
        self._time += max(0.0, dt)
        self._ensure_baseline(mode)
        preset = self._weather_preset()
        if preset is None:
            self.kind = "none"
            target_wetness = 0.0
            target_visibility = 1.0
            wind = Vec3(0)
        else:
            self.kind = str(getattr(preset, "kind", "none"))
            density = max(0.0, min(1.5, float(getattr(preset, "density", 0.0))))
            target_wetness = self._wetness_for(self.kind, density)
            target_visibility = self._visibility_for(self.kind, density)
            wind = Vec3(
                float(getattr(preset, "wind_x", 0.0)),
                float(getattr(preset, "wind_y", 0.0)),
                0.0,
            )

        blend = 1.0 - math.exp(-max(0.0, dt) * 0.9)
        self.wetness += (target_wetness - self.wetness) * blend
        self.visibility += (target_visibility - self.visibility) * blend
        self.wind += (wind - self.wind) * blend

        setattr(mode, "world_wetness", self.wetness)
        setattr(mode, "world_visibility", self.visibility)
        setattr(mode, "world_wind", Vec3(self.wind))
        setattr(mode, "world_weather_kind", self.kind)

        game_id = str(getattr(mode, "game_id", ""))
        if game_id == "street_rush":
            self._apply_driving(mode)
        elif game_id == "neon_ops":
            self._apply_combat_visibility(mode, dt)
        elif game_id == "cyber_runner":
            self._apply_runner_wind(mode, dt)
        elif game_id == "zombie_siege":
            self._apply_horde_weather(mode, dt)

    def _ensure_baseline(self, mode) -> None:
        identity = id(mode)
        if identity == self.mode_id and self.baseline is not None:
            return
        self.mode_id = identity
        self.baseline = ModeBaseline(
            lateral_speed=float(mode.lateral_speed) if hasattr(mode, "lateral_speed") else None,
            brake=float(mode.brake) if hasattr(mode, "brake") else None,
            accel=float(mode.accel) if hasattr(mode, "accel") else None,
            sprint_speed=float(mode.sprint_speed) if hasattr(mode, "sprint_speed") else None,
        )

    def _weather_preset(self):
        try:
            environment = self.app.graphics.environment
            return getattr(environment, "weather_preset", None)
        except Exception:
            return None

    @staticmethod
    def _wetness_for(kind: str, density: float) -> float:
        if kind == "storm":
            return min(1.0, 0.65 + density * 0.25)
        if kind == "rain":
            return min(0.82, 0.35 + density * 0.34)
        if kind == "snow":
            return min(0.68, 0.28 + density * 0.30)
        return 0.0

    @staticmethod
    def _visibility_for(kind: str, density: float) -> float:
        if kind == "storm":
            return max(0.60, 0.82 - density * 0.15)
        if kind == "dust":
            return max(0.52, 0.78 - density * 0.20)
        if kind == "ash":
            return max(0.62, 0.84 - density * 0.16)
        if kind == "snow":
            return max(0.72, 0.91 - density * 0.10)
        if kind == "rain":
            return max(0.78, 0.94 - density * 0.08)
        return 1.0

    def _apply_driving(self, mode) -> None:
        if self.baseline is None:
            return
        # Wet roads reduce lateral authority more than acceleration. Braking
        # becomes slightly less sharp, but never so weak that a run feels random.
        if self.baseline.lateral_speed is not None:
            mode.lateral_speed = self.baseline.lateral_speed * (1.0 - self.wetness * 0.14)
        if self.baseline.brake is not None:
            mode.brake = self.baseline.brake * (1.0 - self.wetness * 0.11)
        if self.baseline.accel is not None:
            mode.accel = self.baseline.accel * (1.0 - self.wetness * 0.035)
        setattr(mode, "road_grip", max(0.72, 1.0 - self.wetness * 0.24))

    def _apply_combat_visibility(self, mode, dt: float) -> None:
        if self.visibility >= 0.97:
            return
        player = Vec3(getattr(mode, "player_pos", Vec3(0)))
        max_confident_range = 36.0 * self.visibility
        for enemy in list(getattr(mode, "enemies", []) or [])[:64]:
            if not getattr(enemy, "alive", True) or not hasattr(enemy, "rig"):
                continue
            distance = (enemy.rig.get_pos() - player).length()
            if distance <= max_confident_range:
                continue
            if hasattr(enemy, "fire_timer"):
                penalty = (distance - max_confident_range) / max(8.0, max_confident_range)
                enemy.fire_timer = max(float(enemy.fire_timer), min(0.9, 0.15 + penalty * 0.55))

    def _apply_runner_wind(self, mode, dt: float) -> None:
        if bool(getattr(mode, "grounded", True)):
            return
        if self.wind.lengthSquared() < 0.04:
            return
        # Side wind is deliberately tiny. It communicates weather without
        # taking control away from the player during precision jumps.
        push = max(-0.55, min(0.55, self.wind.x * 0.08))
        if hasattr(mode, "player_pos"):
            mode.player_pos.x = max(-5.7, min(5.7, float(mode.player_pos.x) + push * dt))

    def _apply_horde_weather(self, mode, dt: float) -> None:
        # Heavy storms mask sound and make the horde slightly less synchronized.
        if self.kind not in ("storm", "rain") or self.visibility > 0.9:
            return
        for index, zombie in enumerate(list(getattr(mode, "zombies", []) or [])[:72]):
            if index % 3 != 0 or not hasattr(zombie, "attack_timer"):
                continue
            zombie.attack_timer = max(float(zombie.attack_timer), (1.0 - self.visibility) * 0.22)
