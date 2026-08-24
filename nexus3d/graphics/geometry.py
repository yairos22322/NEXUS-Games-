from __future__ import annotations

import math
from typing import List, Tuple

from panda3d.core import (
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    NodePath,
    Vec3,
)


def make_uv_sphere(name: str, radius: float, segments: int = 48, rings: int = 24) -> NodePath:
    segments = max(8, int(segments))
    rings = max(4, int(rings))
    fmt = GeomVertexFormat.getV3n3t2()
    data = GeomVertexData(name, fmt, Geom.UHStatic)
    vertex = GeomVertexWriter(data, "vertex")
    normal = GeomVertexWriter(data, "normal")
    uv = GeomVertexWriter(data, "texcoord")

    for ring in range(rings + 1):
        v = ring / rings
        phi = math.pi * v
        z = math.cos(phi)
        xy = math.sin(phi)
        for segment in range(segments + 1):
            u = segment / segments
            theta = math.tau * u
            x = math.cos(theta) * xy
            y = math.sin(theta) * xy
            vertex.addData3f(x * radius, y * radius, z * radius)
            normal.addData3f(-x, -y, -z)
            uv.addData2f(u, v)

    triangles = GeomTriangles(Geom.UHStatic)
    stride = segments + 1
    for ring in range(rings):
        for segment in range(segments):
            a = ring * stride + segment
            b = a + 1
            c = a + stride
            d = c + 1
            triangles.addVertices(a, c, b)
            triangles.addVertices(b, c, d)
    triangles.closePrimitive()

    geom = Geom(data)
    geom.addPrimitive(triangles)
    geom_node = GeomNode(name)
    geom_node.addGeom(geom)
    return NodePath(geom_node)


def make_subdivided_plane(
    name: str,
    width: float,
    depth: float,
    x_segments: int = 32,
    y_segments: int = 32,
) -> NodePath:
    x_segments = max(1, int(x_segments))
    y_segments = max(1, int(y_segments))
    fmt = GeomVertexFormat.getV3n3t2()
    data = GeomVertexData(name, fmt, Geom.UHDynamic)
    vertex = GeomVertexWriter(data, "vertex")
    normal = GeomVertexWriter(data, "normal")
    uv = GeomVertexWriter(data, "texcoord")

    for y in range(y_segments + 1):
        fy = y / y_segments
        py = (fy - 0.5) * depth
        for x in range(x_segments + 1):
            fx = x / x_segments
            px = (fx - 0.5) * width
            vertex.addData3f(px, py, 0.0)
            normal.addData3f(0, 0, 1)
            uv.addData2f(fx, fy)

    triangles = GeomTriangles(Geom.UHStatic)
    stride = x_segments + 1
    for y in range(y_segments):
        for x in range(x_segments):
            a = y * stride + x
            b = a + 1
            c = a + stride
            d = c + 1
            triangles.addVertices(a, b, d)
            triangles.addVertices(a, d, c)
    triangles.closePrimitive()

    geom = Geom(data)
    geom.addPrimitive(triangles)
    geom_node = GeomNode(name)
    geom_node.addGeom(geom)
    return NodePath(geom_node)
