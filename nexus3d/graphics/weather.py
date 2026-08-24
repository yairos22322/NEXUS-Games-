from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List

from panda3d.core import NodePath, TransparencyAttrib, Vec3

from ..primitives import make_box, make_octahedron
from .weather_presets import WeatherPreset


@dataclass
class WeatherParticle:
    node: NodePath
    offset: Vec3
    velocity: Vec3
    spin: float
    phase: float


class WeatherField:
    """Camera-centred weather volume with reusable geometry.

    Particles are deliberately simulated in a local volume around the camera,
    so a large-looking storm does not need thousands of persistent world
    objects.  The system reuses nodes and wraps them when they leave the volume.
    """

    def __init__(self, app, root: NodePath, preset: WeatherPreset, count: int, seed: int) -> None:
        self.app = app
        self.root = root.attachNewNode("weather-field")
        self.preset = preset
        self.rng = random.Random(seed ^ 0x57EA7E)
        self.particles: List[WeatherParticle] = []
        self.time = 0.0
        self.flash = 0.0
        self._create(max(0, count))

    def _random_offset(self) -> Vec3:
        radius = self.preset.radius
        return Vec3(
            self.rng.uniform(-radius, radius),
            self.rng.uniform(-radius, radius),
            self.rng.uniform(-self.preset.vertical_range * 0.35, self.preset.vertical_range),
        )

    def _create(self, count: int) -> None:
        kind = self.preset.kind
        for index in range(count):
            if kind in ("rain", "storm"):
                node = make_box(
                    f"rain-{index}",
                    (0.018, 0.018, self.rng.uniform(0.35, 0.85)),
                    self.preset.color,
                    self.root,
                )
            elif kind in ("ash", "dust", "snow"):
                node = make_octahedron(
                    f"weather-{index}",
                    self.rng.uniform(0.025, 0.075),
                    self.preset.color,
                    self.root,
                )
            else:
                node = make_octahedron(
                    f"spark-{index}",
                    self.rng.uniform(0.015, 0.045),
                    self.preset.color,
                    self.root,
                )
            node.setTransparency(TransparencyAttrib.MAlpha)
            node.setLightOff(4)
            offset = self._random_offset()
            node.setPos(offset)
            velocity = Vec3(
                self.preset.wind_x + self.rng.uniform(-0.8, 0.8),
                self.preset.wind_y + self.rng.uniform(-0.8, 0.8),
                -abs(self.preset.fall_speed) * self.rng.uniform(0.80, 1.25),
            )
            self.particles.append(
                WeatherParticle(node, offset, velocity, self.rng.uniform(-90, 90), self.rng.uniform(0, math.tau))
            )

    def update(self, dt: float) -> None:
        self.time += dt
        camera_world = self.app.camera.getPos(self.app.render)
        self.root.setPos(camera_world)
        radius = self.preset.radius
        low = -self.preset.vertical_range * 0.45
        high = self.preset.vertical_range

        for particle in self.particles:
            particle.phase += dt
            particle.offset += particle.velocity * dt
            if self.preset.kind in ("ash", "dust", "snow"):
                particle.offset.x += math.sin(particle.phase * 1.7) * self.preset.turbulence * dt
                particle.offset.y += math.cos(particle.phase * 1.2) * self.preset.turbulence * dt
                particle.node.setH(particle.node.getH() + particle.spin * dt)
            if (
                particle.offset.z < low
                or abs(particle.offset.x) > radius
                or abs(particle.offset.y) > radius
            ):
                particle.offset = self._random_offset()
                particle.offset.z = high
            particle.node.setPos(particle.offset)

        if self.preset.lightning_chance > 0.0:
            if self.rng.random() < dt * self.preset.lightning_chance:
                self.flash = 1.0
            self.flash = max(0.0, self.flash - dt * 4.0)
            if self.flash > 0.0:
                boost = 1.0 + self.flash * 1.35
                self.root.setColorScale(boost, boost, boost * 1.08, 1.0)
            else:
                self.root.clearColorScale()

    def destroy(self) -> None:
        if not self.root.isEmpty():
            self.root.removeNode()
