from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class GraphicsQuality:
    name: str
    shadow_map_size: int
    max_lights: int
    msaa_samples: int
    environment_detail: int
    weather_particles: int
    distant_buildings: int
    bloom_intensity: float
    ssao_samples: int
    ssao_strength: float
    water_quality: int
    sign_density: float
    enable_shadows: bool = True
    enable_postfx: bool = True


QUALITY_LEVELS: Dict[str, GraphicsQuality] = {
    "LOW": GraphicsQuality(
        name="LOW",
        shadow_map_size=512,
        max_lights=4,
        msaa_samples=2,
        environment_detail=1,
        weather_particles=28,
        distant_buildings=18,
        bloom_intensity=0.35,
        ssao_samples=8,
        ssao_strength=0.006,
        water_quality=1,
        sign_density=0.25,
    ),
    "MEDIUM": GraphicsQuality(
        name="MEDIUM",
        shadow_map_size=1024,
        max_lights=6,
        msaa_samples=4,
        environment_detail=2,
        weather_particles=52,
        distant_buildings=28,
        bloom_intensity=0.55,
        ssao_samples=12,
        ssao_strength=0.008,
        water_quality=2,
        sign_density=0.45,
    ),
    "HIGH": GraphicsQuality(
        name="HIGH",
        shadow_map_size=1536,
        max_lights=8,
        msaa_samples=4,
        environment_detail=3,
        weather_particles=82,
        distant_buildings=40,
        bloom_intensity=0.72,
        ssao_samples=16,
        ssao_strength=0.010,
        water_quality=3,
        sign_density=0.65,
    ),
    "ULTRA": GraphicsQuality(
        name="ULTRA",
        shadow_map_size=2048,
        max_lights=10,
        msaa_samples=8,
        environment_detail=4,
        weather_particles=118,
        distant_buildings=56,
        bloom_intensity=0.88,
        ssao_samples=20,
        ssao_strength=0.012,
        water_quality=4,
        sign_density=0.82,
    ),
    "CINEMATIC": GraphicsQuality(
        name="CINEMATIC",
        shadow_map_size=4096,
        max_lights=12,
        msaa_samples=8,
        environment_detail=5,
        weather_particles=160,
        distant_buildings=72,
        bloom_intensity=1.00,
        ssao_samples=24,
        ssao_strength=0.014,
        water_quality=5,
        sign_density=1.00,
    ),
}


def resolve_quality(value: str | None) -> GraphicsQuality:
    key = str(value or "ULTRA").upper()
    return QUALITY_LEVELS.get(key, QUALITY_LEVELS["ULTRA"])
