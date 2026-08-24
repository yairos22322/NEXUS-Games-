from __future__ import annotations

from dataclasses import dataclass, field
import heapq
import math
import random
from typing import Dict, Iterable, List, Optional, Tuple

from panda3d.core import Vec3


Cell = Tuple[int, int]


@dataclass
class PathState:
    waypoints: List[Vec3] = field(default_factory=list)
    index: int = 0
    repath_timer: float = 0.0
    last_goal: Optional[Cell] = None
    stuck_timer: float = 0.0
    last_pos: Optional[Vec3] = None


class NavGrid:
    """Static 2D navigation grid derived from the mode's box colliders."""

    NEIGHBOURS = (
        (-1, 0, 1.0),
        (1, 0, 1.0),
        (0, -1, 1.0),
        (0, 1, 1.0),
        (-1, -1, 1.4142),
        (-1, 1, 1.4142),
        (1, -1, 1.4142),
        (1, 1, 1.4142),
    )

    def __init__(self, mode, cell_size: float = 2.0, agent_radius: float = 0.52) -> None:
        self.mode = mode
        self.cell_size = max(1.0, float(cell_size))
        self.agent_radius = max(0.25, float(agent_radius))
        self.min_x, self.max_x, self.min_y, self.max_y = self._resolve_bounds(mode)
        self.min_cell = self.world_to_cell(Vec3(self.min_x, self.min_y, 0))
        self.max_cell = self.world_to_cell(Vec3(self.max_x, self.max_y, 0))
        self.blocked: set[Cell] = set()
        self._build_blocked()

    @staticmethod
    def _resolve_bounds(mode) -> tuple[float, float, float, float]:
        game_id = str(getattr(mode, "game_id", ""))
        if game_id == "neon_ops":
            return -42.5, 42.5, -42.5, 42.5
        if game_id == "zombie_siege":
            return -46.0, 46.0, -46.0, 46.0
        colliders = list(getattr(mode, "colliders", []) or [])
        if not colliders:
            return -48.0, 48.0, -48.0, 48.0
        min_x = min(float(c.center.x - c.half.x) for c in colliders) - 3.0
        max_x = max(float(c.center.x + c.half.x) for c in colliders) + 3.0
        min_y = min(float(c.center.y - c.half.y) for c in colliders) - 3.0
        max_y = max(float(c.center.y + c.half.y) for c in colliders) + 3.0
        return min_x, max_x, min_y, max_y

    def _build_blocked(self) -> None:
        colliders = list(getattr(self.mode, "colliders", []) or [])
        if not colliders:
            return
        margin = self.agent_radius
        for collider in colliders:
            if str(getattr(collider, "tag", "solid")) != "solid":
                continue
            cx, cy = float(collider.center.x), float(collider.center.y)
            hx = float(collider.half.x) + margin
            hy = float(collider.half.y) + margin
            lo = self.world_to_cell(Vec3(cx - hx, cy - hy, 0))
            hi = self.world_to_cell(Vec3(cx + hx, cy + hy, 0))
            for x in range(lo[0], hi[0] + 1):
                for y in range(lo[1], hi[1] + 1):
                    if self.in_bounds((x, y)):
                        self.blocked.add((x, y))

    def in_bounds(self, cell: Cell) -> bool:
        return (
            self.min_cell[0] <= cell[0] <= self.max_cell[0]
            and self.min_cell[1] <= cell[1] <= self.max_cell[1]
        )

    def passable(self, cell: Cell) -> bool:
        return self.in_bounds(cell) and cell not in self.blocked

    def world_to_cell(self, pos: Vec3) -> Cell:
        return (
            int(math.floor(float(pos.x) / self.cell_size)),
            int(math.floor(float(pos.y) / self.cell_size)),
        )

    def cell_to_world(self, cell: Cell, z: float = 0.0) -> Vec3:
        return Vec3(
            (cell[0] + 0.5) * self.cell_size,
            (cell[1] + 0.5) * self.cell_size,
            z,
        )

    def closest_open(self, cell: Cell, radius: int = 4) -> Optional[Cell]:
        if self.passable(cell):
            return cell
        for r in range(1, max(1, radius) + 1):
            candidates: List[Cell] = []
            for x in range(cell[0] - r, cell[0] + r + 1):
                candidates.append((x, cell[1] - r))
                candidates.append((x, cell[1] + r))
            for y in range(cell[1] - r + 1, cell[1] + r):
                candidates.append((cell[0] - r, y))
                candidates.append((cell[0] + r, y))
            for candidate in candidates:
                if self.passable(candidate):
                    return candidate
        return None

    def find_path(self, start_world: Vec3, goal_world: Vec3, max_expansions: int = 900) -> List[Vec3]:
        start = self.closest_open(self.world_to_cell(start_world))
        goal = self.closest_open(self.world_to_cell(goal_world))
        if start is None or goal is None:
            return []
        if start == goal:
            return [self.cell_to_world(goal, start_world.z)]

        frontier: list[tuple[float, int, Cell]] = []
        push_counter = 0
        heapq.heappush(frontier, (0.0, push_counter, start))
        came_from: Dict[Cell, Optional[Cell]] = {start: None}
        g_score: Dict[Cell, float] = {start: 0.0}
        expansions = 0

        while frontier and expansions < max_expansions:
            _, _, current = heapq.heappop(frontier)
            if current == goal:
                break
            expansions += 1
            for dx, dy, cost in self.NEIGHBOURS:
                nxt = (current[0] + dx, current[1] + dy)
                if not self.passable(nxt):
                    continue
                if dx != 0 and dy != 0:
                    # No diagonal corner cutting through two blocked orthogonal cells.
                    if not self.passable((current[0] + dx, current[1])):
                        continue
                    if not self.passable((current[0], current[1] + dy)):
                        continue
                new_cost = g_score[current] + cost
                if new_cost >= g_score.get(nxt, float("inf")):
                    continue
                g_score[nxt] = new_cost
                came_from[nxt] = current
                heuristic = math.hypot(goal[0] - nxt[0], goal[1] - nxt[1])
                push_counter += 1
                heapq.heappush(frontier, (new_cost + heuristic, push_counter, nxt))

        if goal not in came_from:
            return []

        cells: List[Cell] = []
        cursor: Optional[Cell] = goal
        while cursor is not None:
            cells.append(cursor)
            cursor = came_from.get(cursor)
        cells.reverse()

        # String-pull simple runs to avoid visibly following every grid square.
        simplified: List[Cell] = []
        last_direction: Optional[Cell] = None
        for index, cell in enumerate(cells):
            if index == 0:
                simplified.append(cell)
                continue
            prev = cells[index - 1]
            direction = (cell[0] - prev[0], cell[1] - prev[1])
            if last_direction is None:
                last_direction = direction
            elif direction != last_direction:
                simplified.append(prev)
                last_direction = direction
        simplified.append(cells[-1])
        z = float(start_world.z)
        return [self.cell_to_world(cell, z) for cell in simplified[1:]]


class NavigationDirector:
    """Budgeted A* assist for enemies that cannot see the player directly."""

    def __init__(self) -> None:
        self.grid: Optional[NavGrid] = None
        self.mode_identity: Optional[int] = None
        self.states: Dict[int, PathState] = {}
        self.cursor = 0
        self.rng = random.Random(0x4E415650415448)
        self.accumulator = 0.0

    def reset(self) -> None:
        self.grid = None
        self.mode_identity = None
        self.states.clear()
        self.cursor = 0
        self.accumulator = 0.0

    def update(self, dt: float, mode) -> None:
        game_id = str(getattr(mode, "game_id", ""))
        if game_id not in ("neon_ops", "zombie_siege"):
            return
        if not hasattr(mode, "player_pos"):
            return
        self._ensure_grid(mode)
        if self.grid is None:
            return

        self.accumulator += dt
        if self.accumulator < 1.0 / 20.0:
            return
        step_dt = min(0.10, self.accumulator)
        self.accumulator = 0.0

        actors = list(getattr(mode, "enemies", []) or []) if game_id == "neon_ops" else list(getattr(mode, "zombies", []) or [])
        actors = [a for a in actors if getattr(a, "alive", True) and hasattr(a, "rig") and not a.rig.root.isEmpty()]
        if not actors:
            self.states.clear()
            return

        player = Vec3(mode.player_pos)
        live_ids = {id(a) for a in actors}
        for key in list(self.states):
            if key not in live_ids:
                self.states.pop(key, None)

        # Repath only a few actors per tick. Existing paths continue between
        # updates, so dense waves do not create A* spikes.
        budget = 3 if game_id == "neon_ops" else 5
        for offset in range(min(len(actors), budget)):
            actor = actors[(self.cursor + offset) % len(actors)]
            self._maybe_repath(actor, mode, player, step_dt)
        self.cursor = (self.cursor + budget) % max(1, len(actors))

        for actor in actors:
            self._follow(actor, mode, player, step_dt)

    def _ensure_grid(self, mode) -> None:
        identity = id(mode)
        if self.grid is not None and self.mode_identity == identity:
            return
        self.mode_identity = identity
        radius = 0.56 if str(getattr(mode, "game_id", "")) == "neon_ops" else 0.62
        self.grid = NavGrid(mode, cell_size=2.0, agent_radius=radius)
        self.states.clear()
        self.cursor = 0

    def _maybe_repath(self, actor, mode, player: Vec3, dt: float) -> None:
        state = self.states.setdefault(id(actor), PathState(repath_timer=self.rng.uniform(0.0, 0.35)))
        state.repath_timer -= dt
        pos = actor.rig.get_pos()
        blocked = not self._line_of_sight(mode, pos + Vec3(0, 0, 1.0), player + Vec3(0, 0, 0.8))
        goal_cell = self.grid.world_to_cell(player) if self.grid is not None else None

        if state.last_pos is not None and (pos - state.last_pos).length() < 0.03:
            state.stuck_timer += dt
        else:
            state.stuck_timer = max(0.0, state.stuck_timer - dt * 2.0)
        state.last_pos = Vec3(pos)

        needs_path = blocked and (
            state.repath_timer <= 0.0
            or not state.waypoints
            or goal_cell != state.last_goal
            or state.stuck_timer > 0.65
        )
        if not needs_path:
            if not blocked:
                state.waypoints.clear()
                state.index = 0
            return

        state.waypoints = self.grid.find_path(pos, player) if self.grid is not None else []
        state.index = 0
        state.last_goal = goal_cell
        state.repath_timer = self.rng.uniform(0.65, 1.25)
        state.stuck_timer = 0.0

    def _follow(self, actor, mode, player: Vec3, dt: float) -> None:
        state = self.states.get(id(actor))
        if state is None or not state.waypoints or state.index >= len(state.waypoints):
            return
        pos = actor.rig.get_pos()
        waypoint = Vec3(state.waypoints[state.index])
        waypoint.z = pos.z
        delta = waypoint - pos
        delta.z = 0
        if delta.length() < 0.85:
            state.index += 1
            if state.index >= len(state.waypoints):
                return
            waypoint = Vec3(state.waypoints[state.index])
            waypoint.z = pos.z
            delta = waypoint - pos
            delta.z = 0
        if delta.lengthSquared() < 0.0001:
            return
        delta.normalize()
        speed = float(getattr(actor, "speed", 4.0))
        scale = 0.52 if str(getattr(mode, "game_id", "")) == "neon_ops" else 0.34
        move = delta * speed * scale * dt
        half = Vec3(float(getattr(actor, "radius", 0.48)) * 0.75, float(getattr(actor, "radius", 0.48)) * 0.75, 1.0)
        try:
            new_pos = mode.move_with_collisions(pos, move, half)
        except Exception:
            new_pos = pos + move
        actor.rig.set_pos(new_pos)

    @staticmethod
    def _line_of_sight(mode, start: Vec3, end: Vec3) -> bool:
        colliders = list(getattr(mode, "colliders", []) or [])
        direction = end - start
        for collider in colliders[:180]:
            if str(getattr(collider, "tag", "solid")) != "solid":
                continue
            center = Vec3(collider.center)
            half = Vec3(collider.half)
            t_min = 0.0
            t_max = 1.0
            blocked = True
            for axis in range(3):
                s = start[axis]
                d = direction[axis]
                lo = center[axis] - half[axis]
                hi = center[axis] + half[axis]
                if abs(d) < 1e-8:
                    if s < lo or s > hi:
                        blocked = False
                        break
                    continue
                inv = 1.0 / d
                t1 = (lo - s) * inv
                t2 = (hi - s) * inv
                if t1 > t2:
                    t1, t2 = t2, t1
                t_min = max(t_min, t1)
                t_max = min(t_max, t2)
                if t_min > t_max:
                    blocked = False
                    break
            if blocked and t_max >= 0.0 and t_min <= 1.0:
                return False
        return True
