from __future__ import annotations

import math
import random
from typing import Iterable, Tuple

from panda3d.core import Vec2, Vec3


def clamp(value: float, low: float, high: float) -> float:
    return low if value < low else high if value > high else value


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * clamp(t, 0.0, 1.0)


def lerp_vec3(a: Vec3, b: Vec3, t: float) -> Vec3:
    t = clamp(t, 0.0, 1.0)
    return a + (b - a) * t


def ease_out_cubic(t: float) -> float:
    t = clamp(t, 0.0, 1.0)
    return 1.0 - pow(1.0 - t, 3)


def ease_in_out_quint(t: float) -> float:
    t = clamp(t, 0.0, 1.0)
    if t < 0.5:
        return 16.0 * t * t * t * t * t
    return 1.0 - pow(-2.0 * t + 2.0, 5) / 2.0


def damp(current: float, target: float, smoothing: float, dt: float) -> float:
    if smoothing <= 0:
        return target
    return lerp(current, target, 1.0 - math.exp(-smoothing * dt))


def damp_vec3(current: Vec3, target: Vec3, smoothing: float, dt: float) -> Vec3:
    if smoothing <= 0:
        return Vec3(target)
    t = 1.0 - math.exp(-smoothing * dt)
    return lerp_vec3(current, target, t)


def heading_vector(heading_degrees: float) -> Vec3:
    radians = math.radians(heading_degrees)
    return Vec3(math.sin(radians), math.cos(radians), 0.0)


def right_vector(heading_degrees: float) -> Vec3:
    radians = math.radians(heading_degrees)
    return Vec3(math.cos(radians), -math.sin(radians), 0.0)


def yaw_pitch_forward(yaw: float, pitch: float) -> Vec3:
    yaw_r = math.radians(yaw)
    pitch_r = math.radians(pitch)
    cp = math.cos(pitch_r)
    return Vec3(
        math.sin(yaw_r) * cp,
        math.cos(yaw_r) * cp,
        math.sin(pitch_r),
    ).normalized()


def flatten(vector: Vec3) -> Vec3:
    result = Vec3(vector.x, vector.y, 0.0)
    if result.lengthSquared() > 0.0001:
        result.normalize()
    return result


def random_point_ring(min_radius: float, max_radius: float, z: float = 0.0) -> Vec3:
    angle = random.uniform(0.0, math.tau)
    radius = random.uniform(min_radius, max_radius)
    return Vec3(math.cos(angle) * radius, math.sin(angle) * radius, z)


def distance_2d(a: Vec3, b: Vec3) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def aabb_overlap(
    pos_a: Vec3,
    half_a: Vec3,
    pos_b: Vec3,
    half_b: Vec3,
) -> bool:
    return (
        abs(pos_a.x - pos_b.x) <= half_a.x + half_b.x
        and abs(pos_a.y - pos_b.y) <= half_a.y + half_b.y
        and abs(pos_a.z - pos_b.z) <= half_a.z + half_b.z
    )


def circle_overlap_2d(a: Vec3, radius_a: float, b: Vec3, radius_b: float) -> bool:
    dx = a.x - b.x
    dy = a.y - b.y
    radius = radius_a + radius_b
    return dx * dx + dy * dy <= radius * radius


def segment_point_distance(origin: Vec3, direction: Vec3, point: Vec3) -> Tuple[float, float]:
    direction = Vec3(direction)
    if direction.lengthSquared() <= 0.0001:
        return (point - origin).length(), 0.0
    direction.normalize()
    relative = point - origin
    along = relative.dot(direction)
    closest = origin + direction * max(0.0, along)
    return (point - closest).length(), along


def format_time(seconds: float) -> str:
    seconds = max(0, int(seconds))
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def weighted_choice(items: Iterable[Tuple[object, float]]):
    pool = list(items)
    if not pool:
        raise ValueError("weighted_choice requires at least one item")
    total = sum(max(0.0, weight) for _, weight in pool)
    if total <= 0.0:
        return pool[-1][0]
    roll = random.uniform(0.0, total)
    upto = 0.0
    for item, weight in pool:
        upto += max(0.0, weight)
        if roll <= upto:
            return item
    return pool[-1][0]
