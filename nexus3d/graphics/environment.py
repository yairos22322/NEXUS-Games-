from __future__ import annotations

import random
from typing import List

from panda3d.core import NodePath, Vec3

from .atmosphere import DistantCity, LensArtifacts, SkyDome, WaterSurface
from .quality import GraphicsQuality
from .visual_presets import choose_visual_preset
from .weather import WeatherField
from .weather_presets import choose_weather_preset


class CinematicEnvironment:
    def __init__(self, app, materials, profile_id: str, quality: GraphicsQuality, seed: int) -> None:
        self.app = app
        self.materials = materials
        self.profile_id = profile_id
        self.quality = quality
        self.seed = int(seed)
        self.root = app.render.attachNewNode(f"cinematic-environment-{profile_id}")
        self.visual = choose_visual_preset(profile_id, self.seed)
        self.weather_preset = choose_weather_preset(profile_id, self.seed + 991)
        self.sky = SkyDome(app, self.root, self.visual)
        self.city = None
        self.weather = None
        self.artifacts = None
        self.water: List[WaterSurface] = []
        self._build()

    def _build(self) -> None:
        profile = self.profile_id
        if profile != "orbital_wars":
            self.city = DistantCity(
                self.root,
                self.materials,
                self.visual,
                self.quality.distant_buildings,
                self.seed + 117,
            )
            self.artifacts = LensArtifacts(
                self.root,
                self.visual,
                6 + self.quality.environment_detail * 3,
                self.seed + 511,
            )

        if bool(self.app.save.setting("dynamic_weather", True)) and self.weather_preset.kind != "none":
            self.weather = WeatherField(
                self.app,
                self.root,
                self.weather_preset,
                int(self.quality.weather_particles * self.weather_preset.density),
                self.seed + 313,
            )

        if self.quality.water_quality > 0:
            self._build_water()

    def _build_water(self) -> None:
        c = self.visual.water_color
        q = self.quality.water_quality
        if self.profile_id == "menu":
            specs = [
                (Vec3(-14, 18, 0.025), (18, 6)),
                (Vec3(16, 36, 0.025), (20, 7)),
            ]
        elif self.profile_id == "street_rush":
            specs = [
                (Vec3(-10.2, 18, 0.03), (2.2, 58)),
                (Vec3(10.2, 42, 0.03), (2.2, 62)),
            ]
        elif self.profile_id == "neon_ops":
            specs = [
                (Vec3(-31, 24, 0.025), (10, 5)),
                (Vec3(30, -25, 0.025), (11, 4)),
            ]
        elif self.profile_id == "zombie_siege":
            specs = [
                (Vec3(-22, 20, 0.02), (9, 5)),
            ]
        elif self.profile_id == "cyber_runner":
            specs = [
                (Vec3(-35, 60, -1.0), (20, 50)),
                (Vec3(36, 95, -1.0), (24, 70)),
            ]
        else:
            specs = []
        for index, (position, size) in enumerate(specs):
            self.water.append(
                WaterSurface(self.root, position, size, c, q, self.seed + index * 47)
            )

    def update(self, dt: float) -> None:
        self.sky.update(dt)
        if self.city is not None:
            self.city.update(dt)
        if self.artifacts is not None:
            self.artifacts.update(dt)
        if self.weather is not None:
            self.weather.update(dt)
        camera_pos = self.app.camera.getPos(self.app.render)
        for surface in self.water:
            surface.update(dt, camera_pos)

    def destroy(self) -> None:
        if self.weather is not None:
            self.weather.destroy()
            self.weather = None
        for surface in self.water:
            surface.destroy()
        self.water.clear()
        if self.artifacts is not None:
            self.artifacts.destroy()
            self.artifacts = None
        if self.city is not None:
            self.city.destroy()
            self.city = None
        self.sky.destroy()
        if not self.root.isEmpty():
            self.root.removeNode()
