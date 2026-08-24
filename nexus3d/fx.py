from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List, Tuple

from panda3d.core import NodePath, Vec3, Vec4

from .math3d import damp_vec3
from .primitives import make_box, make_octahedron, make_ring

Color = Tuple[float, float, float, float]


@dataclass
class Particle:
    node: NodePath
    velocity: Vec3
    gravity: Vec3
    age: float
    lifetime: float
    start_scale: float
    end_scale: float
    spin: Vec3


class ParticleSystem:
    def __init__(self, parent: NodePath) -> None:
        self.root = parent.attachNewNode("particle-root")
        self.particles: List[Particle] = []
        self.enabled = True

    def burst(
        self,
        position: Vec3,
        color: Color,
        count: int = 16,
        speed: float = 5.0,
        lifetime: float = 0.55,
        size: float = 0.06,
        gravity: float = 3.0,
    ) -> None:
        if not self.enabled:
            return
        for index in range(max(0, count)):
            node = make_box(
                f"particle-{index}",
                (size, size, size),
                color,
                self.root,
                tuple(position),
            )
            direction = Vec3(
                random.uniform(-1, 1),
                random.uniform(-1, 1),
                random.uniform(-0.25, 1.0),
            )
            if direction.lengthSquared() < 0.01:
                direction = Vec3(0, 0, 1)
            direction.normalize()
            velocity = direction * random.uniform(speed * 0.35, speed)
            self.particles.append(
                Particle(
                    node=node,
                    velocity=velocity,
                    gravity=Vec3(0, 0, -gravity),
                    age=0.0,
                    lifetime=random.uniform(lifetime * 0.65, lifetime * 1.25),
                    start_scale=random.uniform(0.75, 1.35),
                    end_scale=0.01,
                    spin=Vec3(
                        random.uniform(-240, 240),
                        random.uniform(-240, 240),
                        random.uniform(-240, 240),
                    ),
                )
            )

    def sparks(self, position: Vec3, color: Color, count: int = 12) -> None:
        self.burst(position, color, count=count, speed=10.0, lifetime=0.35, size=0.035, gravity=7.0)

    def explosion(self, position: Vec3, primary: Color, secondary: Color) -> None:
        self.burst(position, primary, count=28, speed=11.0, lifetime=0.7, size=0.10, gravity=4.5)
        self.burst(position, secondary, count=20, speed=7.0, lifetime=0.9, size=0.13, gravity=2.0)

    def pickup(self, position: Vec3, color: Color) -> None:
        self.burst(position, color, count=18, speed=5.0, lifetime=0.8, size=0.045, gravity=-0.5)

    def update(self, dt: float) -> None:
        alive: List[Particle] = []
        for particle in self.particles:
            particle.age += dt
            if particle.age >= particle.lifetime or particle.node.isEmpty():
                if not particle.node.isEmpty():
                    particle.node.removeNode()
                continue
            progress = particle.age / particle.lifetime
            particle.velocity += particle.gravity * dt
            particle.node.setPos(particle.node.getPos() + particle.velocity * dt)
            particle.node.setHpr(
                particle.node.getH() + particle.spin.x * dt,
                particle.node.getP() + particle.spin.y * dt,
                particle.node.getR() + particle.spin.z * dt,
            )
            scale = particle.start_scale + (particle.end_scale - particle.start_scale) * progress
            particle.node.setScale(max(0.001, scale))
            alive.append(particle)
        self.particles = alive

    def clear(self) -> None:
        for particle in self.particles:
            if not particle.node.isEmpty():
                particle.node.removeNode()
        self.particles.clear()
        self.root.removeNode()


@dataclass
class PulseRing:
    node: NodePath
    age: float
    lifetime: float
    start_scale: float
    end_scale: float


class PulseSystem:
    def __init__(self, parent: NodePath) -> None:
        self.root = parent.attachNewNode("pulse-root")
        self.rings: List[PulseRing] = []

    def emit(self, position: Vec3, color: Color, start: float = 0.5, end: float = 6.0, lifetime: float = 0.55) -> None:
        ring = make_ring("pulse", 0.84, 1.0, 36, color, self.root)
        ring.setPos(position)
        ring.setP(90)
        ring.setScale(start)
        self.rings.append(PulseRing(ring, 0.0, lifetime, start, end))

    def update(self, dt: float) -> None:
        alive: List[PulseRing] = []
        for ring in self.rings:
            ring.age += dt
            if ring.age >= ring.lifetime or ring.node.isEmpty():
                if not ring.node.isEmpty():
                    ring.node.removeNode()
                continue
            t = ring.age / ring.lifetime
            scale = ring.start_scale + (ring.end_scale - ring.start_scale) * (1.0 - (1.0 - t) ** 3)
            ring.node.setScale(scale)
            ring.node.setColorScale(1, 1, 1, max(0.0, 1.0 - t))
            alive.append(ring)
        self.rings = alive

    def clear(self) -> None:
        self.root.removeNode()
        self.rings.clear()


class CameraShake:
    def __init__(self, camera: NodePath) -> None:
        self.camera = camera
        self.trauma = 0.0
        self.max_translation = Vec3(0.18, 0.08, 0.14)
        self.max_rotation = Vec3(1.4, 1.0, 1.3)
        self.frequency = 28.0
        self.time = 0.0
        self.offset_pos = Vec3(0, 0, 0)
        self.offset_hpr = Vec3(0, 0, 0)
        self.enabled = True

    def add(self, amount: float) -> None:
        if self.enabled:
            self.trauma = min(1.0, self.trauma + max(0.0, amount))

    def update(self, dt: float) -> Tuple[Vec3, Vec3]:
        self.time += dt
        self.trauma = max(0.0, self.trauma - dt * 1.45)
        if self.trauma <= 0.001 or not self.enabled:
            self.offset_pos = damp_vec3(self.offset_pos, Vec3(0), 18.0, dt)
            self.offset_hpr = damp_vec3(self.offset_hpr, Vec3(0), 18.0, dt)
            return self.offset_pos, self.offset_hpr

        strength = self.trauma * self.trauma
        sx = math.sin(self.time * self.frequency * 1.00 + 0.4)
        sy = math.sin(self.time * self.frequency * 1.31 + 1.8)
        sz = math.sin(self.time * self.frequency * 1.77 + 3.1)
        target_pos = Vec3(
            sx * self.max_translation.x,
            sy * self.max_translation.y,
            sz * self.max_translation.z,
        ) * strength
        target_hpr = Vec3(
            sy * self.max_rotation.x,
            sz * self.max_rotation.y,
            sx * self.max_rotation.z,
        ) * strength
        self.offset_pos = damp_vec3(self.offset_pos, target_pos, 24.0, dt)
        self.offset_hpr = damp_vec3(self.offset_hpr, target_hpr, 24.0, dt)
        return self.offset_pos, self.offset_hpr
