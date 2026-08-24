from __future__ import annotations

import math
from typing import Iterable, List, Sequence, Tuple

from panda3d.core import (
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    LineSegs,
    Material,
    NodePath,
    TransparencyAttrib,
    Vec3,
    Vec4,
)

Color = Tuple[float, float, float, float]


def _apply_default_material(node: NodePath, name: str, color: Color) -> None:
    """Give every generated primitive basic PBR surface properties.

    Vertex colours remain the source of tint.  The material therefore stays
    white and only supplies roughness, metallic response and emission.
    """
    lowered = name.lower()
    metallic = 0.0
    roughness = 0.62
    emission = 0.0

    if any(word in lowered for word in ("neon", "glow", "light", "laser", "muzzle", "window", "accent", "projectile")):
        metallic = 0.05
        roughness = 0.22
        emission = 2.2
    elif any(word in lowered for word in ("weapon", "rifle", "barrel", "gun", "blade", "hull", "ship", "drone")):
        metallic = 0.92
        roughness = 0.24
    elif any(word in lowered for word in ("car", "vehicle", "hood", "spoiler")):
        metallic = 0.68
        roughness = 0.16
    elif any(word in lowered for word in ("asphalt", "road")):
        metallic = 0.03
        roughness = 0.24
    elif any(word in lowered for word in ("glass", "visor")):
        metallic = 0.0
        roughness = 0.06
    elif any(word in lowered for word in ("tire", "rubber")):
        roughness = 0.92
    elif any(word in lowered for word in ("wall", "tower", "building", "concrete", "curb", "ground")):
        roughness = 0.78
    elif any(word in lowered for word in ("skin", "head", "face")):
        roughness = 0.66

    material = Material(f"{name}-material")
    material.setBaseColor(Vec4(1.0, 1.0, 1.0, color[3]))
    material.setMetallic(metallic)
    material.setRoughness(roughness)
    material.setRefractiveIndex(1.5)
    if emission > 0.0:
        material.setEmission(Vec4(color[0] * emission, color[1] * emission, color[2] * emission, color[3]))
    node.setMaterial(material, 1)


def _build_mesh(
    name: str,
    vertices: Sequence[Tuple[float, float, float]],
    triangles: Sequence[Tuple[int, int, int]],
    color: Color,
) -> NodePath:
    fmt = GeomVertexFormat.getV3n3c4()
    data = GeomVertexData(name, fmt, Geom.UHStatic)
    data.setNumRows(len(vertices))

    vw = GeomVertexWriter(data, "vertex")
    nw = GeomVertexWriter(data, "normal")
    cw = GeomVertexWriter(data, "color")

    normals: List[Vec3] = [Vec3(0, 0, 0) for _ in vertices]
    for a, b, c in triangles:
        va = Vec3(*vertices[a])
        vb = Vec3(*vertices[b])
        vc = Vec3(*vertices[c])
        normal = (vb - va).cross(vc - va)
        if normal.lengthSquared() > 0.000001:
            normal.normalize()
        normals[a] += normal
        normals[b] += normal
        normals[c] += normal

    for index, vertex in enumerate(vertices):
        vw.addData3f(*vertex)
        normal = normals[index]
        if normal.lengthSquared() > 0.000001:
            normal.normalize()
        else:
            normal = Vec3(0, 0, 1)
        nw.addData3f(normal)
        cw.addData4f(*color)

    primitive = GeomTriangles(Geom.UHStatic)
    for a, b, c in triangles:
        primitive.addVertices(a, b, c)
    primitive.closePrimitive()

    geom = Geom(data)
    geom.addPrimitive(primitive)
    node = GeomNode(name)
    node.addGeom(geom)
    return NodePath(node)


def make_box(
    name: str,
    size: Tuple[float, float, float] = (1.0, 1.0, 1.0),
    color: Color = (1, 1, 1, 1),
    parent: NodePath | None = None,
    pos: Tuple[float, float, float] = (0, 0, 0),
    hpr: Tuple[float, float, float] = (0, 0, 0),
) -> NodePath:
    sx, sy, sz = (max(0.001, float(v)) * 0.5 for v in size)
    # 24 vertices rather than 8 so every face keeps a flat normal.
    # This matters a lot once per-pixel PBR lighting and shadowing are enabled.
    vertices = [
        (-sx, -sy, -sz), (sx, -sy, -sz), (sx, sy, -sz), (-sx, sy, -sz),
        (-sx, -sy, sz), (sx, -sy, sz), (sx, sy, sz), (-sx, sy, sz),
        (-sx, -sy, -sz), (sx, -sy, -sz), (sx, -sy, sz), (-sx, -sy, sz),
        (sx, -sy, -sz), (sx, sy, -sz), (sx, sy, sz), (sx, -sy, sz),
        (sx, sy, -sz), (-sx, sy, -sz), (-sx, sy, sz), (sx, sy, sz),
        (-sx, sy, -sz), (-sx, -sy, -sz), (-sx, -sy, sz), (-sx, sy, sz),
    ]
    triangles = [
        (0, 2, 1), (0, 3, 2),
        (4, 5, 6), (4, 6, 7),
        (8, 9, 10), (8, 10, 11),
        (12, 13, 14), (12, 14, 15),
        (16, 17, 18), (16, 18, 19),
        (20, 21, 22), (20, 22, 23),
    ]
    node = _build_mesh(name, vertices, triangles, color)
    _apply_default_material(node, name, color)
    if parent is not None:
        node.reparentTo(parent)
    node.setPos(*pos)
    node.setHpr(*hpr)
    if color[3] < 0.999:
        node.setTransparency(TransparencyAttrib.MAlpha)
    return node


def make_plane(
    name: str,
    width: float,
    depth: float,
    color: Color,
    parent: NodePath | None = None,
    z: float = 0.0,
) -> NodePath:
    hw = width * 0.5
    hd = depth * 0.5
    vertices = [
        (-hw, -hd, 0.0),
        (hw, -hd, 0.0),
        (hw, hd, 0.0),
        (-hw, hd, 0.0),
    ]
    triangles = [(0, 1, 2), (0, 2, 3)]
    node = _build_mesh(name, vertices, triangles, color)
    _apply_default_material(node, name, color)
    if parent is not None:
        node.reparentTo(parent)
    node.setZ(z)
    if color[3] < 0.999:
        node.setTransparency(TransparencyAttrib.MAlpha)
    return node


def make_wedge(
    name: str,
    width: float,
    depth: float,
    height: float,
    color: Color,
    parent: NodePath | None = None,
) -> NodePath:
    w = width * 0.5
    d = depth * 0.5
    vertices = [
        (-w, -d, 0),
        (w, -d, 0),
        (w, d, 0),
        (-w, d, 0),
        (-w, d, height),
        (w, d, height),
    ]
    triangles = [
        (0, 1, 2), (0, 2, 3),
        (3, 2, 5), (3, 5, 4),
        (0, 4, 5), (0, 5, 1),
        (0, 3, 4),
        (1, 5, 2),
    ]
    node = _build_mesh(name, vertices, triangles, color)
    _apply_default_material(node, name, color)
    if parent is not None:
        node.reparentTo(parent)
    return node


def make_octahedron(
    name: str,
    radius: float,
    color: Color,
    parent: NodePath | None = None,
) -> NodePath:
    r = float(radius)
    vertices = [
        (0, 0, r),
        (r, 0, 0),
        (0, r, 0),
        (-r, 0, 0),
        (0, -r, 0),
        (0, 0, -r),
    ]
    triangles = [
        (0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 1),
        (5, 2, 1), (5, 3, 2), (5, 4, 3), (5, 1, 4),
    ]
    node = _build_mesh(name, vertices, triangles, color)
    _apply_default_material(node, name, color)
    if parent is not None:
        node.reparentTo(parent)
    return node


def make_pyramid(
    name: str,
    width: float,
    depth: float,
    height: float,
    color: Color,
    parent: NodePath | None = None,
) -> NodePath:
    w = width * 0.5
    d = depth * 0.5
    vertices = [
        (-w, -d, 0),
        (w, -d, 0),
        (w, d, 0),
        (-w, d, 0),
        (0, 0, height),
    ]
    triangles = [
        (0, 2, 1), (0, 3, 2),
        (0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4),
    ]
    node = _build_mesh(name, vertices, triangles, color)
    _apply_default_material(node, name, color)
    if parent is not None:
        node.reparentTo(parent)
    return node


def make_ring(
    name: str,
    inner_radius: float,
    outer_radius: float,
    segments: int,
    color: Color,
    parent: NodePath | None = None,
) -> NodePath:
    segments = max(6, int(segments))
    vertices: List[Tuple[float, float, float]] = []
    triangles: List[Tuple[int, int, int]] = []
    for i in range(segments):
        angle = math.tau * i / segments
        ca = math.cos(angle)
        sa = math.sin(angle)
        vertices.append((ca * inner_radius, sa * inner_radius, 0.0))
        vertices.append((ca * outer_radius, sa * outer_radius, 0.0))
    for i in range(segments):
        ni = (i + 1) % segments
        a = i * 2
        b = a + 1
        c = ni * 2
        d = c + 1
        triangles.extend([(a, b, d), (a, d, c)])
    node = _build_mesh(name, vertices, triangles, color)
    _apply_default_material(node, name, color)
    if parent is not None:
        node.reparentTo(parent)
    if color[3] < 0.999:
        node.setTransparency(TransparencyAttrib.MAlpha)
    return node


def make_lines(
    name: str,
    segments: Iterable[Tuple[Vec3, Vec3]],
    color: Color,
    thickness: float = 1.0,
    parent: NodePath | None = None,
) -> NodePath:
    lines = LineSegs(name)
    lines.setThickness(thickness)
    lines.setColor(Vec4(*color))
    for start, end in segments:
        lines.moveTo(start)
        lines.drawTo(end)
    node = NodePath(lines.create())
    if parent is not None:
        node.reparentTo(parent)
    return node


def make_grid(
    name: str,
    half_size: int,
    spacing: float,
    color: Color,
    parent: NodePath | None = None,
    z: float = 0.01,
) -> NodePath:
    extent = half_size * spacing
    segments = []
    for index in range(-half_size, half_size + 1):
        p = index * spacing
        segments.append((Vec3(-extent, p, z), Vec3(extent, p, z)))
        segments.append((Vec3(p, -extent, z), Vec3(p, extent, z)))
    return make_lines(name, segments, color, 1.0, parent)


def make_crosshair_3d(
    name: str,
    size: float,
    gap: float,
    color: Color,
    parent: NodePath | None = None,
) -> NodePath:
    s = size
    g = gap
    segments = [
        (Vec3(-s, 0, 0), Vec3(-g, 0, 0)),
        (Vec3(g, 0, 0), Vec3(s, 0, 0)),
        (Vec3(0, 0, -s), Vec3(0, 0, -g)),
        (Vec3(0, 0, g), Vec3(0, 0, s)),
    ]
    return make_lines(name, segments, color, 2.0, parent)
