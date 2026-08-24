from __future__ import annotations

import math
import random
from pathlib import Path
from typing import List

from panda3d.core import (
    CullFaceAttrib,
    NodePath,
    Shader,
    TransparencyAttrib,
    Vec3,
    Vec4,
)

from ..primitives import make_box, make_octahedron
from .geometry import make_subdivided_plane, make_uv_sphere
from .visual_presets import VisualPreset


class SkyDome:
    def __init__(self, app, root: NodePath, preset: VisualPreset) -> None:
        self.app = app
        self.root = root.attachNewNode("cinematic-sky-root")
        self.node = make_uv_sphere("cinematic-sky", 520.0, 64, 32)
        self.node.reparentTo(self.root)
        self.node.setTwoSided(True)
        self.node.setDepthWrite(False)
        self.node.setDepthTest(False)
        self.node.setBin("background", -100)
        self.node.setAttrib(CullFaceAttrib.make(CullFaceAttrib.MCullNone))
        shader_dir = Path(__file__).resolve().parent.parent / "shaders"
        try:
            shader = Shader.load(
                Shader.SL_GLSL,
                vertex=str(shader_dir / "sky.vert"),
                fragment=str(shader_dir / "sky.frag"),
            )
            self.node.setShader(shader, 100)
        except Exception:
            shader = None
        self.shader = shader
        self.apply_preset(preset)
        self.time = 0.0
        self.sun_phase = 0.0
        self.luminance = 0.5

    def apply_preset(self, preset: VisualPreset) -> None:
        self.preset = preset
        self.node.setShaderInput("u_top_color", Vec4(*preset.sky_top))
        self.node.setShaderInput("u_horizon_color", Vec4(*preset.sky_horizon))
        self.node.setShaderInput("u_bottom_color", Vec4(*preset.sky_bottom))
        self.node.setShaderInput("u_sun_color", Vec4(*preset.sun_color))
        self.node.setShaderInput("u_sun_dir", Vec4(*preset.sun_direction, 0.0))
        self.node.setShaderInput("u_star_strength", float(preset.star_strength))
        self.node.setShaderInput("u_cloud_strength", float(preset.cloud_strength))
        self.node.setShaderInput("u_cloud_speed", 1.0)
        self.node.setShaderInput("u_haze_strength", 0.55)

    def update(self, dt: float) -> None:
        self.time += dt
        self.root.setPos(self.app.camera.getPos(self.app.render))
        self.node.setShaderInput("u_time", self.time)

        base = Vec3(*self.preset.sun_direction)
        if bool(self.app.save.setting("cinematic_sky_motion", True)):
            self.sun_phase += dt * 0.0065
            angle = self.sun_phase
            # Very slow cinematic drift, not a fast fake day/night cycle.
            rotated = Vec3(
                base.x * math.cos(angle) - base.y * math.sin(angle),
                base.x * math.sin(angle) + base.y * math.cos(angle),
                max(-0.35, min(0.95, base.z + math.sin(angle * 0.63) * 0.12)),
            )
            if rotated.lengthSquared() > 0.0001:
                rotated.normalize()
            self.node.setShaderInput("u_sun_dir", Vec4(rotated.x, rotated.y, rotated.z, 0.0))
            self.luminance = max(0.10, min(1.0, 0.52 + rotated.z * 0.36))
        else:
            self.luminance = max(0.10, min(1.0, 0.52 + base.z * 0.36))

        # Clouds breathe almost imperceptibly so repeated scenes do not look frozen.
        cloud_speed = 0.78 + math.sin(self.time * 0.027) * 0.16
        haze = 0.44 + math.sin(self.time * 0.019 + 1.2) * 0.10
        self.node.setShaderInput("u_cloud_speed", cloud_speed)
        self.node.setShaderInput("u_haze_strength", haze)

    def destroy(self) -> None:
        if not self.root.isEmpty():
            self.root.removeNode()


class WaterSurface:
    def __init__(
        self,
        root: NodePath,
        position: Vec3,
        size: tuple[float, float],
        color: tuple[float, float, float, float],
        quality: int,
        seed: int,
    ) -> None:
        segments = 10 + quality * 8
        self.node = make_subdivided_plane("cinematic-water", size[0], size[1], segments, max(6, segments // 2))
        self.node.reparentTo(root)
        self.node.setPos(position)
        self.node.setTransparency(TransparencyAttrib.MAlpha)
        self.node.setDepthWrite(False)
        self.node.setBin("transparent", 20)
        shader_dir = Path(__file__).resolve().parent.parent / "shaders"
        try:
            shader = Shader.load(
                Shader.SL_GLSL,
                vertex=str(shader_dir / "water.vert"),
                fragment=str(shader_dir / "water.frag"),
            )
            self.node.setShader(shader, 110)
        except Exception:
            shader = None
        self.shader = shader
        self.node.setShaderInput("u_water_color", Vec4(*color))
        self.node.setShaderInput("u_seed", float(seed % 1024) / 1024.0)
        self.node.setShaderInput("u_reflection_strength", 0.85)
        self.time = random.random() * 50.0

    def update(self, dt: float, camera_pos: Vec3) -> None:
        self.time += dt
        self.node.setShaderInput("u_time", self.time)
        self.node.setShaderInput("u_camera_pos", Vec4(camera_pos.x, camera_pos.y, camera_pos.z, 1.0))

    def destroy(self) -> None:
        if not self.node.isEmpty():
            self.node.removeNode()


class DistantCity:
    """Procedural skyline with runtime density scaling."""

    def __init__(self, root: NodePath, materials, preset: VisualPreset, count: int, seed: int) -> None:
        self.root = root.attachNewNode("distant-city")
        self.materials = materials
        self.preset = preset
        self.rng = random.Random(seed)
        self.nodes: List[NodePath] = []
        self.runtime_scale = 1.0
        self._build(count)

    def _build(self, count: int) -> None:
        for index in range(max(0, count)):
            angle = self.rng.uniform(0.0, math.tau)
            radius = self.rng.uniform(92.0, 215.0)
            x = math.cos(angle) * radius
            y = math.sin(angle) * radius
            width = self.rng.uniform(5.0, 15.0)
            depth = self.rng.uniform(5.0, 15.0)
            height = self.rng.uniform(18.0, 78.0)
            base = self.preset.architecture_tint
            variation = self.rng.uniform(0.72, 1.15)
            color = (
                min(1.0, base[0] * variation),
                min(1.0, base[1] * variation),
                min(1.0, base[2] * variation),
                1.0,
            )
            tower = make_box(
                f"distant-tower-{index}",
                (width, depth, height),
                color,
                self.root,
                (x, y, height * 0.5 - 1.0),
                (self.rng.uniform(-8, 8), 0, 0),
            )
            self.materials.apply(tower, "concrete", f"tower-{index}", color)
            self.nodes.append(tower)

            if index % 2 == 0:
                accent = self.preset.neon_primary if index % 4 == 0 else self.preset.neon_secondary
                sign = make_box(
                    f"distant-sign-{index}",
                    (max(1.2, width * 0.55), 0.12, self.rng.uniform(0.35, 0.90)),
                    accent,
                    tower,
                    (0, -depth * 0.51, self.rng.uniform(-height * 0.15, height * 0.25)),
                )
                self.materials.apply(sign, "emissive", f"sign-{index}", accent, 1.8)

    def set_runtime_scale(self, scale: float) -> None:
        self.runtime_scale = max(0.35, min(1.0, float(scale)))
        if not self.nodes:
            return
        keep = max(8, int(len(self.nodes) * self.runtime_scale))
        for index, node in enumerate(self.nodes):
            if index < keep:
                node.show()
            else:
                node.hide()

    def update(self, dt: float) -> None:
        return

    def destroy(self) -> None:
        if not self.root.isEmpty():
            self.root.removeNode()


class LensArtifacts:
    """Small emissive sprites that mimic distant lens scatter without post FX."""

    def __init__(self, root: NodePath, preset: VisualPreset, count: int, seed: int) -> None:
        self.root = root.attachNewNode("lens-artifacts")
        rng = random.Random(seed ^ 0xA811CE)
        self.nodes: List[NodePath] = []
        self.runtime_scale = 1.0
        for index in range(max(0, count)):
            node = make_octahedron(
                f"light-speck-{index}",
                rng.uniform(0.04, 0.16),
                preset.neon_primary if index % 2 == 0 else preset.neon_secondary,
                self.root,
            )
            angle = rng.uniform(0, math.tau)
            radius = rng.uniform(45, 110)
            node.setPos(math.cos(angle) * radius, math.sin(angle) * radius, rng.uniform(2, 28))
            node.setTransparency(TransparencyAttrib.MAlpha)
            node.setLightOff(10)
            self.nodes.append(node)

    def set_runtime_scale(self, scale: float) -> None:
        self.runtime_scale = max(0.25, min(1.0, float(scale)))
        keep = max(2, int(len(self.nodes) * self.runtime_scale)) if self.nodes else 0
        for index, node in enumerate(self.nodes):
            if index < keep:
                node.show()
            else:
                node.hide()

    def update(self, dt: float) -> None:
        for index, node in enumerate(self.nodes):
            if not node.isEmpty() and not node.isHidden():
                node.setH(node.getH() + dt * (8 + index % 7))

    def destroy(self) -> None:
        if not self.root.isEmpty():
            self.root.removeNode()
