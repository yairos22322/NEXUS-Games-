from __future__ import annotations

from types import SimpleNamespace
import unittest

from panda3d.core import Vec3

from nexus3d.gameplay.environment_gameplay import EnvironmentGameplayDirector
from nexus3d.gameplay.navigation import NavGrid
from nexus3d.gameplay.projectile_safety import SweptProjectileSafety
from nexus3d.gameplay.spatial import SpatialHash2D
from nexus3d.gameplay.weapons import WeaponLoadoutDirector


class SpatialHashTests(unittest.TestCase):
    def test_nearby_pair_is_returned_once(self) -> None:
        a, b, c = object(), object(), object()
        spatial = SpatialHash2D(cell_size=3.0)
        spatial.rebuild([
            (a, Vec3(0, 0, 0), 0.5),
            (b, Vec3(0.8, 0, 0), 0.5),
            (c, Vec3(20, 20, 0), 0.5),
        ])
        pairs = list(spatial.iter_unique_pairs(extra_radius=0.1))
        self.assertEqual(len(pairs), 1)
        self.assertEqual({pairs[0][0].obj, pairs[0][1].obj}, {a, b})

    def test_radius_query_excludes_distant_objects(self) -> None:
        near, far = object(), object()
        spatial = SpatialHash2D(cell_size=4.0)
        spatial.rebuild([
            (near, Vec3(1, 0, 0), 0.4),
            (far, Vec3(12, 0, 0), 0.4),
        ])
        result = {entry.obj for entry in spatial.query_radius(Vec3(0), 3.0)}
        self.assertIn(near, result)
        self.assertNotIn(far, result)


class NavigationTests(unittest.TestCase):
    def test_astar_routes_around_box_collider(self) -> None:
        collider = SimpleNamespace(
            center=Vec3(0, 0, 1),
            half=Vec3(2.4, 2.4, 2.0),
            tag="solid",
        )
        mode = SimpleNamespace(game_id="neon_ops", colliders=[collider])
        grid = NavGrid(mode, cell_size=1.5, agent_radius=0.45)
        path = grid.find_path(Vec3(-8, 0, 0), Vec3(8, 0, 0))
        self.assertTrue(path, "A* should find a route around a central obstacle")
        self.assertLess((path[-1] - Vec3(8, 0, 0)).length(), 2.5)
        for waypoint in path:
            cell = grid.world_to_cell(waypoint)
            self.assertTrue(grid.passable(cell))

    def test_closest_open_recovers_from_blocked_goal(self) -> None:
        collider = SimpleNamespace(
            center=Vec3(0, 0, 1),
            half=Vec3(1.5, 1.5, 2.0),
            tag="solid",
        )
        mode = SimpleNamespace(game_id="neon_ops", colliders=[collider])
        grid = NavGrid(mode, cell_size=1.0, agent_radius=0.35)
        blocked = grid.world_to_cell(Vec3(0, 0, 0))
        recovered = grid.closest_open(blocked, radius=5)
        self.assertIsNotNone(recovered)
        self.assertTrue(grid.passable(recovered))


class ProjectileSafetyTests(unittest.TestCase):
    def test_segment_sphere_detects_fast_crossing(self) -> None:
        hit = SweptProjectileSafety._segment_sphere(
            Vec3(-10, 0, 0),
            Vec3(10, 0, 0),
            Vec3(0, 0, 0),
            0.5,
        )
        self.assertIsNotNone(hit)
        self.assertLess(abs(hit.x), 0.6)

    def test_segment_sphere_rejects_miss(self) -> None:
        hit = SweptProjectileSafety._segment_sphere(
            Vec3(-10, 4, 0),
            Vec3(10, 4, 0),
            Vec3(0, 0, 0),
            0.5,
        )
        self.assertIsNone(hit)


class WeatherGameplayTests(unittest.TestCase):
    def test_storm_is_wetter_than_rain(self) -> None:
        rain = EnvironmentGameplayDirector._wetness_for("rain", 0.8)
        storm = EnvironmentGameplayDirector._wetness_for("storm", 0.8)
        self.assertGreater(storm, rain)

    def test_dust_reduces_visibility(self) -> None:
        clear = EnvironmentGameplayDirector._visibility_for("none", 0.0)
        dust = EnvironmentGameplayDirector._visibility_for("dust", 0.9)
        self.assertLess(dust, clear)
        self.assertGreaterEqual(dust, 0.5)


class WeaponDataTests(unittest.TestCase):
    def test_weapon_slots_are_distinct_and_valid(self) -> None:
        specs = WeaponLoadoutDirector.SPECS
        self.assertEqual(len(specs), 3)
        self.assertEqual(len({spec.weapon_id for spec in specs}), 3)
        for spec in specs:
            self.assertGreater(spec.damage, 0)
            self.assertGreater(spec.magazine, 0)
            self.assertGreater(spec.reserve, 0)
            self.assertGreater(spec.reload_time, 0)
            self.assertGreater(spec.fire_interval, 0)


if __name__ == "__main__":
    unittest.main()
