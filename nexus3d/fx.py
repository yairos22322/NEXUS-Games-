from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List, Tuple

from panda3d.core import NodePath, TransparencyAttrib, Vec3

from .math3d import damp_vec3
from .primitives import make_box, make_ring

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
    color: Color
    drag: float
    active: bool = False


class ParticleSystem:
    """Pooled lightweight particles used by every game mode.

    Earlier builds allocated a new Panda3D node for every spark and deleted it
    less than a second later. Fast weapons and chain explosions could therefore
    create avoidable garbage-collection and scene-graph spikes. This version
    preallocates a fixed pool and only mutates transforms while playing.
    """

    DEFAULT_POOL = 156

    def __init__(self, parent: NodePath, pool_size: int = DEFAULT_POOL) -> None:
        self.root = parent.attachNewNode("particle-root")
        self.enabled = True
        self.pool: List[Particle] = []
        self.active: List[Particle] = []
        self._cursor = 0
        self._build_pool(max(48, int(pool_size)))

    @property
    def particles(self) -> List[Particle]:
        # Compatibility with older debug code that accessed `.particles`.
        return self.active

    def _build_pool(self, count: int) -> None:
        for index in range(count):
            node = make_box(
                f"pooled-particle-{index}",
                (1.0, 1.0, 1.0),
                (1, 1, 1, 1),
                self.root,
            )
            node.setTransparency(TransparencyAttrib.MAlpha)
            node.setDepthWrite(False)
            node.setBin("transparent", 24)
            node.hide()
            self.pool.append(
                Particle(
                    node=node,
                    velocity=Vec3(0),
                    gravity=Vec3(0),
                    age=0.0,
                    lifetime=0.5,
                    start_scale=0.05,
                    end_scale=0.001,
                    spin=Vec3(0),
                    color=(1, 1, 1, 1),
                    drag=0.0,
                    active=False,
                )
            )

    def _acquire(self) -> Particle:
        for _ in range(len(self.pool)):
            particle = self.pool[self._cursor]
            self._cursor = (self._cursor + 1) % len(self.pool)
            if not particle.active:
                return particle

        # Pool saturation is rare. Recycle the oldest visible particle rather
        # than allocating a new scene node in the hot path.
        oldest = max(self.active, key=lambda item: item.age / max(0.001, item.lifetime))
        self._release(oldest)
        return oldest

    def _release(self, particle: Particle) -> None:
        particle.active = False
        particle.node.hide()
        particle.node.clearColorScale()
        if particle in self.active:
            self.active.remove(particle)

    def burst(
        self,
        position: Vec3,
        color: Color,
        count: int = 16,
        speed: float = 5.0,
        lifetime: float = 0.55,
        size: float = 0.06,
        gravity: float = 3.0,
        drag: float = 0.12,
        vertical_bias: float = 0.18,
    ) -> None:
        if not self.enabled:
            return
        for _ in range(max(0, min(int(count), len(self.pool)))):
            particle = self._acquire()
            direction = Vec3(
                random.uniform(-1, 1),
                random.uniform(-1, 1),
                random.uniform(-0.25 + vertical_bias, 1.0 + vertical_bias),
            )
            if direction.lengthSquared() < 0.01:
                direction = Vec3(0, 0, 1)
            direction.normalize()

            particle.velocity = direction * random.uniform(speed * 0.35, speed)
            particle.gravity = Vec3(0, 0, -gravity)
            particle.age = 0.0
            particle.lifetime = random.uniform(lifetime * 0.65, lifetime * 1.25)
            particle.start_scale = size * random.uniform(0.72, 1.38)
            particle.end_scale = max(0.001, size * random.uniform(0.02, 0.14))
            particle.spin = Vec3(
                random.uniform(-260, 260),
                random.uniform(-260, 260),
                random.uniform(-260, 260),
            )
            particle.color = color
            particle.drag = max(0.0, drag)
            particle.active = True
            particle.node.setPos(position)
            particle.node.setScale(particle.start_scale)
            particle.node.setHpr(random.uniform(0, 360), random.uniform(0, 360), random.uniform(0, 360))
            particle.node.setColorScale(*color)
            particle.node.show()
            if particle not in self.active:
                self.active.append(particle)

    def sparks(self, position: Vec3, color: Color, count: int = 12) -> None:
        self.burst(
            position,
            color,
            count=count,
            speed=12.0,
            lifetime=0.32,
            size=0.030,
            gravity=8.0,
            drag=0.06,
            vertical_bias=0.10,
        )

    def explosion(self, position: Vec3, primary: Color, secondary: Color) -> None:
        # Fast bright core.
        self.burst(position, primary, count=24, speed=13.0, lifetime=0.46, size=0.085, gravity=4.5, drag=0.10)
        # Slower hot debris.
        self.burst(position, secondary, count=18, speed=8.0, lifetime=0.82, size=0.115, gravity=3.2, drag=0.18)
        # Darker expanding smoke/debris approximation using the same pool.
        smoke = (
            primary[0] * 0.22 + 0.06,
            primary[1] * 0.18 + 0.055,
            primary[2] * 0.16 + 0.05,
            min(0.72, primary[3] if len(primary) > 3 else 0.65),
        )
        self.burst(position + Vec3(0, 0, 0.25), smoke, count=13, speed=3.8, lifetime=1.15, size=0.16, gravity=-0.35, drag=0.55, vertical_bias=0.45)

    def pickup(self, position: Vec3, color: Color) -> None:
        self.burst(position, color, count=18, speed=5.0, lifetime=0.8, size=0.042, gravity=-0.5, drag=0.20, vertical_bias=0.4)

    def update(self, dt: float) -> None:
        if dt <= 0.0:
            return
        for particle in list(self.active):
            particle.age += dt
            if particle.age >= particle.lifetime or particle.node.isEmpty():
                self._release(particle)
                continue

            progress = max(0.0, min(1.0, particle.age / max(0.001, particle.lifetime)))
            particle.velocity += particle.gravity * dt
            if particle.drag > 0.0:
                particle.velocity *= math.exp(-particle.drag * dt)
            particle.node.setPos(particle.node.getPos() + particle.velocity * dt)
            particle.node.setHpr(
                particle.node.getH() + particle.spin.x * dt,
                particle.node.getP() + particle.spin.y * dt,
                particle.node.getR() + particle.spin.z * dt,
            )

            # Cubic decay keeps the first part of a spark readable before it
            # shrinks and fades quickly at the end of its life.
            eased = 1.0 - (1.0 - progress) ** 3
            scale = particle.start_scale + (particle.end_scale - particle.start_scale) * eased
            particle.node.setScale(max(0.001, scale))
            alpha = particle.color[3] * max(0.0, (1.0 - progress) ** 1.45)
            particle.node.setColorScale(particle.color[0], particle.color[1], particle.color[2], alpha)

    def clear(self) -> None:
        for particle in list(self.active):
            self._release(particle)
        self.active.clear()
        if not self.root.isEmpty():
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
        ring.setTransparency(TransparencyAttrib.MAlpha)
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
            ring.node.setColorScale(1, 1, 1, max(0.0, (1.0 - t) ** 1.3))
            alive.append(ring)
        self.rings = alive

    def clear(self) -> None:
        if not self.root.isEmpty():
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
        # Multiple incommensurate frequencies produce a less mechanical shake
        # while remaining deterministic and cheap.
        sx = math.sin(self.time * self.frequency * 1.00 + 0.4) + math.sin(self.time * self.frequency * 0.47 + 2.1) * 0.35
        sy = math.sin(self.time * self.frequency * 1.31 + 1.8) + math.sin(self.time * self.frequency * 0.61 + 0.7) * 0.28
        sz = math.sin(self.time * self.frequency * 1.77 + 3.1) + math.sin(self.time * self.frequency * 0.83 + 4.0) * 0.22
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
