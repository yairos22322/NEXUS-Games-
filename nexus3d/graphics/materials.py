from __future__ import annotations

import hashlib
from typing import Dict, Optional, Tuple

from panda3d.core import Material, NodePath, Vec4

from .material_presets import MaterialPreset, choose_material_preset

Color = Tuple[float, float, float, float]


class MaterialLibrary:
    """Applies PBR-friendly Panda3D materials to procedural geometry.

    The original build used only vertex colours. That makes scenes readable,
    but it gives the renderer almost no information about whether a surface is
    metal, paint, wet asphalt, fabric, glass, concrete or an emissive sign.
    """

    def __init__(self) -> None:
        self._cache: Dict[tuple, Material] = {}

    @staticmethod
    def _stable_seed(name: str) -> int:
        digest = hashlib.sha1(name.encode("utf-8", "ignore")).digest()
        return int.from_bytes(digest[:4], "little")

    def material_for(
        self,
        category: str,
        name: str,
        base_color: Optional[Color] = None,
        emission_scale: float = 1.0,
    ) -> Material:
        seed = self._stable_seed(name)
        preset = choose_material_preset(category, seed)
        color = tuple(base_color or preset.base_color)
        cache_key = (
            category,
            round(color[0], 3),
            round(color[1], 3),
            round(color[2], 3),
            round(color[3], 3),
            round(preset.metallic, 3),
            round(preset.roughness, 3),
            round(preset.emission * emission_scale, 3),
        )
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        material = Material(f"mat-{category}-{len(self._cache)}")
        material.setBaseColor(Vec4(1.0, 1.0, 1.0, color[3]))
        material.setMetallic(max(0.0, min(1.0, preset.metallic)))
        material.setRoughness(max(0.02, min(1.0, preset.roughness)))
        material.setRefractiveIndex(max(1.0, preset.ior))

        if preset.emission > 0.0001:
            strength = preset.emission * max(0.0, emission_scale)
            material.setEmission(
                Vec4(
                    color[0] * strength,
                    color[1] * strength,
                    color[2] * strength,
                    color[3],
                )
            )

        self._cache[cache_key] = material
        return material

    def apply(
        self,
        node: NodePath,
        category: str,
        name: str = "surface",
        base_color: Optional[Color] = None,
        emission_scale: float = 1.0,
        priority: int = 1,
    ) -> NodePath:
        material = self.material_for(category, name, base_color, emission_scale)
        node.setMaterial(material, priority)
        return node

    def apply_by_name(self, node: NodePath, name: str, color: Optional[Color] = None) -> NodePath:
        lowered = name.lower()
        if "emissive" in lowered or any(word in lowered for word in ("neon", "glow", "light", "muzzle", "laser", "window", "accent")):
            category = "emissive"
        elif any(word in lowered for word in ("weapon", "rifle", "barrel", "gun", "blade")):
            category = "weapon_metal"
        elif any(word in lowered for word in ("car", "vehicle", "hood", "spoiler")):
            category = "vehicle_paint"
        elif any(word in lowered for word in ("tire", "rubber")):
            category = "rubber"
        elif any(word in lowered for word in ("asphalt", "road")):
            category = "wet_asphalt"
        elif any(word in lowered for word in ("glass", "visor")):
            category = "glass"
        elif any(word in lowered for word in ("skin", "head", "face")):
            category = "skin"
        elif any(word in lowered for word in ("wall", "tower", "building", "concrete", "curb")):
            category = "concrete"
        elif any(word in lowered for word in ("ship", "hull", "drone", "orbital")):
            category = "space_hull"
        else:
            category = "painted_metal"
        return self.apply(node, category, name, color)
