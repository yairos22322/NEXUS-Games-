from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional

from panda3d.core import Vec3, Vec4


@dataclass
class LightingBaseline:
    ambient: Vec4
    sun: Vec4


class WorldLightingDirector:
    """Slow cinematic light evolution shared by the playable modes."""

    def __init__(self, app) -> None:
        self.app = app
        self.mode_identity: Optional[int] = None
        self.baseline: Optional[LightingBaseline] = None
        self.time = 0.0
        self.intensity = 1.0

    def reset(self) -> None:
        self.mode_identity = None
        self.baseline = None
        self.time = 0.0
        self.intensity = 1.0

    def update(self, dt: float, mode) -> None:
        if mode is None or not getattr(mode, "active", False):
            return
        if id(mode) != self.mode_identity:
            self._attach(mode)
        self.time += max(0.0, dt)
        game_id = str(getattr(mode, "game_id", ""))

        if game_id == "orbital_wars":
            self._space_light(mode)
            return

        cycle_speed = {
            "neon_ops": 1.0 / 260.0,
            "street_rush": 1.0 / 210.0,
            "zombie_siege": 1.0 / 320.0,
            "cyber_runner": 1.0 / 190.0,
        }.get(game_id, 1.0 / 240.0)
        phase = (self.time * cycle_speed) % 1.0

        # These games are stylized, so the cycle covers a cinematic slice of a
        # day instead of forcing every run through noon and midnight.
        if game_id == "zombie_siege":
            elevation = -18.0 + math.sin(phase * math.tau) * 8.0
            brightness = 0.55 + 0.10 * math.sin(phase * math.tau)
            warmth = 0.72
        elif game_id == "street_rush":
            elevation = -6.0 + math.sin(phase * math.tau) * 11.0
            brightness = 0.68 + 0.15 * math.sin(phase * math.tau + 0.5)
            warmth = 0.85
        elif game_id == "cyber_runner":
            elevation = 8.0 + math.sin(phase * math.tau) * 18.0
            brightness = 0.82 + 0.18 * math.sin(phase * math.tau + 0.3)
            warmth = 1.08
        else:
            elevation = 15.0 + math.sin(phase * math.tau) * 20.0
            brightness = 0.88 + 0.12 * math.sin(phase * math.tau + 0.2)
            warmth = 0.98

        azimuth = -48.0 + phase * 58.0
        self.intensity += (brightness - self.intensity) * min(1.0, dt * 0.6)
        self._apply_mode_lights(mode, azimuth, elevation, self.intensity, warmth)
        self._apply_sky_direction(azimuth, elevation)
        setattr(mode, "world_light_intensity", self.intensity)

    def _attach(self, mode) -> None:
        self.mode_identity = id(mode)
        self.time = 0.0
        ambient_color = Vec4(0.18, 0.21, 0.30, 1.0)
        sun_color = Vec4(0.88, 0.92, 1.0, 1.0)
        try:
            if getattr(mode, "_ambient", None) is not None:
                ambient_color = Vec4(mode._ambient.node().getColor())
        except Exception:
            pass
        try:
            if getattr(mode, "_sun", None) is not None:
                sun_color = Vec4(mode._sun.node().getColor())
        except Exception:
            pass
        self.baseline = LightingBaseline(ambient=ambient_color, sun=sun_color)

    def _apply_mode_lights(self, mode, azimuth: float, elevation: float, brightness: float, warmth: float) -> None:
        if self.baseline is None:
            return
        sun_node = getattr(mode, "_sun", None)
        ambient_node = getattr(mode, "_ambient", None)
        if sun_node is not None:
            try:
                sun_node.setHpr(azimuth, -45.0 - elevation * 0.45, 0.0)
                base = self.baseline.sun
                sun = Vec4(
                    min(1.25, base.x * brightness * warmth),
                    min(1.20, base.y * brightness),
                    min(1.25, base.z * brightness * (2.0 - warmth)),
                    1.0,
                )
                sun_node.node().setColor(sun)
            except Exception:
                pass
        if ambient_node is not None:
            try:
                base = self.baseline.ambient
                ambient_scale = 0.72 + brightness * 0.28
                ambient_node.node().setColor(
                    Vec4(
                        base.x * ambient_scale,
                        base.y * ambient_scale,
                        base.z * ambient_scale,
                        1.0,
                    )
                )
            except Exception:
                pass

    def _apply_sky_direction(self, azimuth: float, elevation: float) -> None:
        try:
            sky = self.app.graphics.environment.sky
            az = math.radians(azimuth)
            el = math.radians(elevation)
            direction = Vec3(
                math.sin(az) * math.cos(el),
                math.cos(az) * math.cos(el),
                math.sin(el),
            )
            direction.normalize()
            sky.node.setShaderInput("u_sun_dir", Vec4(direction.x, direction.y, direction.z, 0.0))
        except Exception:
            pass

    def _space_light(self, mode) -> None:
        # Slow moving key light gives ships readable changing highlights while
        # keeping the star field itself visually stable.
        azimuth = -24.0 + math.sin(self.time * 0.035) * 22.0
        elevation = 24.0 + math.sin(self.time * 0.021) * 9.0
        self._apply_mode_lights(mode, azimuth, elevation, 0.92, 0.92)
