from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import List, Tuple

Color = Tuple[float, float, float, float]


@dataclass(frozen=True)
class WeaponProfile:
    name: str
    damage: float
    magazine: int
    reserve: int
    fire_interval: float
    reload_time: float
    spread: float
    recoil: float
    accent: Color


@dataclass(frozen=True)
class EnemyProfile:
    name: str
    health: float
    speed: float
    damage: float
    fire_interval: float
    scale: float
    primary: Color
    secondary: Color


@dataclass(frozen=True)
class VehicleProfile:
    name: str
    cruise_speed: float
    aggression: float
    width: float
    length: float
    primary: Color
    secondary: Color


@dataclass(frozen=True)
class RunnerPattern:
    name: str
    difficulty: int
    spacing: float
    lanes: Tuple[int, ...]
    obstacle_types: Tuple[str, ...]
    shard_count: int
    drone_chance: float


@dataclass(frozen=True)
class SpaceFormation:
    name: str
    difficulty: int
    offsets: Tuple[Tuple[float, float, float], ...]
    kinds: Tuple[str, ...]
    speed_multiplier: float
    fire_multiplier: float


@dataclass(frozen=True)
class ArenaLayout:
    name: str
    obstacles: Tuple[Tuple[float, float, float, float, float], ...]
    spawn_points: Tuple[Tuple[float, float, float], ...]
    light_points: Tuple[Tuple[float, float, float], ...]


_WEAPON_NAMES = ("RAPTOR", "SPECTRE", "NOVA", "WRAITH", "TEMPEST")
_ENEMY_NAMES = ("RAIDER", "BREACHER", "HUNTER", "WARDEN", "PHANTOM")
_TRAFFIC_NAMES = ("VECTOR", "COMET", "APEX", "PHASE", "VOLT")
_ZOMBIE_NAMES = ("ROAMER", "RAVAGER", "HOLLOW", "FERAL", "ROTTER")


def _seed(value: int | float, salt: int) -> int:
    try:
        base = int(float(value) * 1000.0)
    except (TypeError, ValueError, OverflowError):
        base = 0
    return (base * 0x9E3779B1 + salt * 0x85EBCA77) & 0xFFFFFFFF


def _accent(tier: int, phase: float = 0.0) -> Color:
    angle = (tier * 0.73 + phase) % math.tau
    r = 0.25 + 0.42 * (0.5 + 0.5 * math.sin(angle))
    g = 0.30 + 0.55 * (0.5 + 0.5 * math.sin(angle + 2.1))
    b = 0.35 + 0.52 * (0.5 + 0.5 * math.sin(angle + 4.2))
    return (min(1.0, r), min(1.0, g), min(1.0, b), 1.0)


def weapon_for_level(level: int) -> WeaponProfile:
    """Generate a balanced deterministic starter profile for any profile level.

    V3 shipped thousands of literal preset rows. V4 uses compact rules, so
    content scales indefinitely without inflating import time or repository size.
    """
    level = max(1, int(level))
    tier = min(60, level - 1)
    family = _WEAPON_NAMES[tier % len(_WEAPON_NAMES)]
    rng = random.Random(_seed(level, 11))
    damage = 25.0 + tier * 0.62 + rng.uniform(-0.8, 0.8)
    magazine = 28 + (tier % 4) * 3
    reserve = magazine * (4 + (tier % 3))
    fire_interval = max(0.078, 0.118 - tier * 0.0008 + rng.uniform(-0.003, 0.003))
    reload_time = max(1.05, 1.52 - min(0.30, tier * 0.006) + rng.uniform(-0.04, 0.04))
    spread = max(0.0055, min(0.020, 0.010 + rng.uniform(-0.0025, 0.0025) + tier * 0.00004))
    recoil = 0.055 + (tier % 5) * 0.009
    return WeaponProfile(
        name=f"VX-{400 + level:03d} {family}",
        damage=round(damage, 3),
        magazine=magazine,
        reserve=reserve,
        fire_interval=round(fire_interval, 4),
        reload_time=round(reload_time, 3),
        spread=round(spread, 5),
        recoil=round(recoil, 3),
        accent=_accent(tier, 0.4),
    )


def neon_enemy_for_wave(wave: int, elite: bool = False) -> EnemyProfile:
    wave = max(1, int(wave))
    tier = wave - 1
    rng = random.Random(_seed(wave, 23) ^ (0xA11CE if elite else 0))
    archetype = tier % len(_ENEMY_NAMES)
    health = 58.0 + tier * 8.0 + rng.uniform(-4.0, 5.0)
    speed = 4.5 + min(3.1, tier * 0.07) + rng.uniform(-0.18, 0.18)
    damage = 6.8 + tier * 0.34 + rng.uniform(-0.35, 0.35)
    fire_interval = max(0.48, 1.25 - tier * 0.014 + rng.uniform(-0.05, 0.05))
    scale = 0.96 + (archetype % 3) * 0.035
    if elite:
        health *= 1.22
        speed *= 1.06
        damage *= 1.12
        fire_interval *= 0.90
        scale *= 1.08
    return EnemyProfile(
        name=("ELITE " if elite else "") + _ENEMY_NAMES[archetype],
        health=round(health, 3),
        speed=round(speed, 3),
        damage=round(damage, 3),
        fire_interval=round(fire_interval, 3),
        scale=round(scale, 3),
        primary=_accent(tier, 0.0),
        secondary=_accent(tier, 1.7),
    )


def traffic_for_distance(distance: float) -> VehicleProfile:
    distance = max(0.0, float(distance))
    tier = min(80, int(distance // 550.0))
    rng = random.Random(_seed(distance // 120.0, 31))
    cruise = 24.0 + min(38.0, tier * 0.55) + rng.uniform(-3.5, 3.5)
    aggression = min(1.0, 0.20 + tier * 0.012 + rng.uniform(0.0, 0.15))
    width = rng.uniform(1.65, 1.95)
    length = rng.uniform(3.7, 4.6)
    return VehicleProfile(
        name=f"{_TRAFFIC_NAMES[tier % len(_TRAFFIC_NAMES)]}-{tier:02d}",
        cruise_speed=round(cruise, 3),
        aggression=round(aggression, 3),
        width=round(width, 3),
        length=round(length, 3),
        primary=_accent(tier, 2.4),
        secondary=_accent(tier, 4.0),
    )


def zombie_for_wave(wave: int) -> EnemyProfile:
    wave = max(1, int(wave))
    tier = wave - 1
    rng = random.Random(_seed(wave, 47))
    health = 54.0 + tier * 9.2 + rng.uniform(-5.0, 6.0)
    speed = 2.6 + min(2.2, tier * 0.045) + rng.uniform(-0.12, 0.12)
    damage = 7.0 + tier * 0.32 + rng.uniform(-0.30, 0.30)
    return EnemyProfile(
        name=f"{_ZOMBIE_NAMES[tier % len(_ZOMBIE_NAMES)]}-{wave:02d}",
        health=round(health, 3),
        speed=round(speed, 3),
        damage=round(damage, 3),
        fire_interval=1.0,
        scale=round(0.96 + (tier % 4) * 0.018, 3),
        primary=(0.08 + (tier % 3) * 0.018, 0.14 + (tier % 4) * 0.012, 0.075, 1.0),
        secondary=(0.25, 0.31 + (tier % 3) * 0.025, 0.16, 1.0),
    )


def runner_pattern_for_distance(distance: float) -> RunnerPattern:
    distance = max(0.0, float(distance))
    tier = min(999, int(distance // 180.0))
    rng = random.Random(_seed(tier, 59))
    index = rng.randrange(0, 14)
    families = (
        ("barrier", "barrier", "shard"),
        ("wall", "wall", "shard"),
        ("laser_low", "shard", "shard"),
        ("laser_high", "barrier", "shard"),
        ("shard", "shard", "shard"),
        ("barrier", "laser_high", "barrier"),
        ("drone", "shard", "barrier"),
    )
    obstacle_types = families[index % len(families)]
    return RunnerPattern(
        name=f"RUNNER_PATTERN_{index:03d}",
        difficulty=1 + min(10, tier // 3),
        spacing=max(7.5, 15.0 - min(6.5, tier * 0.10)),
        lanes=(-2, -1, 0, 1, 2),
        obstacle_types=obstacle_types,
        shard_count=3 + (index % 5),
        drone_chance=min(0.65, 0.08 + tier * 0.012),
    )


def space_formation_for_wave(wave: int) -> SpaceFormation:
    wave = max(1, int(wave))
    tier = wave - 1
    rng = random.Random(_seed(wave, 71))
    count = 3 + min(5, tier // 2)
    offsets: List[Tuple[float, float, float]] = []
    kinds: List[str] = []
    for index in range(count):
        row = index // 3
        column = index % 3 - 1
        jitter = rng.uniform(-0.8, 0.8)
        offsets.append((column * (5.0 + row * 0.4) + jitter, row * 5.5, rng.uniform(-2.5, 2.5)))
        roll = rng.random()
        if tier >= 4 and roll < 0.18:
            kinds.append("bomber")
        elif tier >= 2 and roll < 0.48:
            kinds.append("interceptor")
        else:
            kinds.append("fighter")
    return SpaceFormation(
        name=f"VOID_FORMATION_{wave:03d}",
        difficulty=1 + min(10, tier // 2),
        offsets=tuple(offsets),
        kinds=tuple(kinds),
        speed_multiplier=1.0 + min(0.35, tier * 0.012),
        fire_multiplier=max(0.72, 1.0 - tier * 0.008),
    )


def arena_for_seed(seed: int) -> ArenaLayout:
    """Generate a deterministic combat arena with separation constraints."""
    seed = int(seed)
    rng = random.Random(_seed(seed, 97))
    obstacle_count = 9 + rng.randrange(0, 5)
    obstacles: List[Tuple[float, float, float, float, float]] = []
    attempts = 0

    while len(obstacles) < obstacle_count and attempts < 240:
        attempts += 1
        x = rng.uniform(-29.0, 29.0)
        y = rng.uniform(-28.0, 29.0)
        sx = rng.uniform(2.2, 7.2)
        sy = rng.uniform(2.0, 6.4)
        sz = rng.uniform(1.8, 4.2)

        # Preserve a useful spawn/movement pocket around the player start.
        if abs(x) < 8.0 and y < -10.0:
            continue
        if math.hypot(x, y) < 6.0:
            continue

        overlap = False
        for ox, oy, osx, osy, _ in obstacles:
            if abs(x - ox) < (sx + osx) * 0.5 + 1.4 and abs(y - oy) < (sy + osy) * 0.5 + 1.4:
                overlap = True
                break
        if overlap:
            continue
        obstacles.append((round(x, 2), round(y, 2), round(sx, 2), round(sy, 2), round(sz, 2)))

    spawn_points = (
        (-34.0, -32.0, 0.0),
        (0.0, -37.0, 0.0),
        (33.0, -31.0, 0.0),
        (-36.0, 0.0, 0.0),
        (36.0, 0.0, 0.0),
        (-33.0, 31.0, 0.0),
        (0.0, 36.0, 0.0),
        (33.0, 31.0, 0.0),
    )
    light_points = tuple(
        (
            round(rng.uniform(-24.0, 24.0), 2),
            round(rng.uniform(-22.0, 24.0), 2),
            round(rng.uniform(5.5, 9.0), 2),
        )
        for _ in range(3)
    )
    return ArenaLayout(
        name=f"NEON_ARENA_{abs(seed) % 100000:05d}",
        obstacles=tuple(obstacles),
        spawn_points=spawn_points,
        light_points=light_points,
    )
