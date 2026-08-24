from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import math
from typing import DefaultDict, Dict, Iterable, Iterator, List, Sequence, Tuple

from panda3d.core import Vec3


Cell = Tuple[int, int]


@dataclass
class SpatialEntry:
    obj: object
    pos: Vec3
    radius: float


class SpatialHash2D:
    """Compact broadphase used by AI, crowd and nearby-object queries.

    The original crowd separation path compared every actor against every other
    actor. That is acceptable for a dozen enemies, but becomes expensive at
    horde scale. Spatial hashing limits pair checks to neighbouring cells and
    keeps the simulation cost close to linear for normally distributed actors.
    """

    def __init__(self, cell_size: float = 4.0) -> None:
        self.cell_size = max(0.5, float(cell_size))
        self._cells: DefaultDict[Cell, List[SpatialEntry]] = defaultdict(list)
        self._entries: Dict[int, SpatialEntry] = {}

    def clear(self) -> None:
        self._cells.clear()
        self._entries.clear()

    def rebuild(self, entries: Iterable[tuple[object, Vec3, float]]) -> None:
        self.clear()
        for obj, pos, radius in entries:
            self.insert(obj, pos, radius)

    def insert(self, obj: object, pos: Vec3, radius: float = 0.5) -> None:
        position = Vec3(pos)
        entry = SpatialEntry(obj=obj, pos=position, radius=max(0.01, float(radius)))
        self._entries[id(obj)] = entry
        min_cell = self._cell_for(position.x - entry.radius, position.y - entry.radius)
        max_cell = self._cell_for(position.x + entry.radius, position.y + entry.radius)
        for cx in range(min_cell[0], max_cell[0] + 1):
            for cy in range(min_cell[1], max_cell[1] + 1):
                self._cells[(cx, cy)].append(entry)

    def query_radius(self, pos: Vec3, radius: float) -> List[SpatialEntry]:
        center = Vec3(pos)
        radius = max(0.0, float(radius))
        min_cell = self._cell_for(center.x - radius, center.y - radius)
        max_cell = self._cell_for(center.x + radius, center.y + radius)
        radius_sq = radius * radius
        seen: set[int] = set()
        result: List[SpatialEntry] = []
        for cx in range(min_cell[0], max_cell[0] + 1):
            for cy in range(min_cell[1], max_cell[1] + 1):
                for entry in self._cells.get((cx, cy), ()):
                    key = id(entry.obj)
                    if key in seen:
                        continue
                    seen.add(key)
                    dx = entry.pos.x - center.x
                    dy = entry.pos.y - center.y
                    reach = radius + entry.radius
                    if dx * dx + dy * dy <= max(radius_sq, reach * reach):
                        result.append(entry)
        return result

    def iter_unique_pairs(self, extra_radius: float = 0.0) -> Iterator[tuple[SpatialEntry, SpatialEntry]]:
        """Yield nearby pairs once, without the global O(n^2) scan."""
        emitted: set[tuple[int, int]] = set()
        pad = max(0.0, float(extra_radius))
        for cell, entries in self._cells.items():
            cx, cy = cell
            neighbourhood: List[SpatialEntry] = []
            for ox in (-1, 0, 1):
                for oy in (-1, 0, 1):
                    neighbourhood.extend(self._cells.get((cx + ox, cy + oy), ()))
            for a in entries:
                for b in neighbourhood:
                    if a.obj is b.obj:
                        continue
                    ka, kb = id(a.obj), id(b.obj)
                    pair = (ka, kb) if ka < kb else (kb, ka)
                    if pair in emitted:
                        continue
                    emitted.add(pair)
                    dx = a.pos.x - b.pos.x
                    dy = a.pos.y - b.pos.y
                    reach = a.radius + b.radius + pad
                    if dx * dx + dy * dy <= reach * reach:
                        yield a, b

    def nearest(self, pos: Vec3, radius: float, predicate=None):
        best = None
        best_sq = float("inf")
        center = Vec3(pos)
        for entry in self.query_radius(center, radius):
            if predicate is not None and not predicate(entry.obj):
                continue
            dx = entry.pos.x - center.x
            dy = entry.pos.y - center.y
            dist_sq = dx * dx + dy * dy
            if dist_sq < best_sq:
                best_sq = dist_sq
                best = entry
        return best

    def density(self, pos: Vec3, radius: float) -> int:
        return len(self.query_radius(pos, radius))

    def _cell_for(self, x: float, y: float) -> Cell:
        inv = 1.0 / self.cell_size
        return math.floor(x * inv), math.floor(y * inv)
