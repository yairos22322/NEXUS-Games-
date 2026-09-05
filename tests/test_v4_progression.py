from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from nexus3d.config import DEFAULT_SETTINGS, SAVE_SCHEMA_VERSION
from nexus3d.data.content_catalog import (
    arena_for_seed,
    neon_enemy_for_wave,
    runner_pattern_for_distance,
    space_formation_for_wave,
    traffic_for_distance,
    weapon_for_level,
    zombie_for_wave,
)
from nexus3d.gameplay.missions import MissionDirector, OPERATION_BOOK
from nexus3d.save_system import SaveSystem


class SaveV4Tests(unittest.TestCase):
    def test_old_save_is_migrated_without_losing_score(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            path.write_text(
                json.dumps(
                    {
                        "profile": {"level": 3, "xp": 120, "credits": 90},
                        "scores": {"neon_ops": 12345},
                    }
                ),
                encoding="utf-8",
            )
            save = SaveSystem(str(path))
            self.assertEqual(save.data["schema_version"], SAVE_SCHEMA_VERSION)
            self.assertEqual(save.profile["level"], 3)
            self.assertEqual(save.score_for("neon_ops"), 12345)
            self.assertIn("upgrade_ranks", save.progression)
            self.assertIn("missions", DEFAULT_SETTINGS)

    def test_credit_spending_is_atomic_at_api_level(self) -> None:
        with TemporaryDirectory() as directory:
            save = SaveSystem(str(Path(directory) / "profile.json"))
            save.add_credits(500)
            self.assertTrue(save.spend_credits(320))
            self.assertEqual(save.profile["credits"], 180)
            self.assertFalse(save.spend_credits(181))
            self.assertEqual(save.profile["credits"], 180)
            self.assertEqual(save.progression["lifetime_credits_spent"], 320)

    def test_upgrade_rank_is_clamped(self) -> None:
        with TemporaryDirectory() as directory:
            save = SaveSystem(str(Path(directory) / "profile.json"))
            save.set_upgrade_rank("firepower", 999)
            self.assertEqual(save.upgrade_rank("firepower"), 10)


class CompactCatalogTests(unittest.TestCase):
    def test_arena_generation_is_deterministic(self) -> None:
        first = arena_for_seed(991)
        second = arena_for_seed(991)
        other = arena_for_seed(992)
        self.assertEqual(first, second)
        self.assertNotEqual(first.obstacles, other.obstacles)
        self.assertGreaterEqual(len(first.obstacles), 8)

    def test_profiles_scale_without_literal_catalogs(self) -> None:
        self.assertGreater(weapon_for_level(20).damage, weapon_for_level(1).damage)
        self.assertGreater(neon_enemy_for_wave(10, False).health, neon_enemy_for_wave(1, False).health)
        self.assertGreater(zombie_for_wave(10).health, zombie_for_wave(1).health)
        self.assertGreaterEqual(traffic_for_distance(5000).cruise_speed, traffic_for_distance(0).cruise_speed - 5)

    def test_runner_and_space_generators_are_valid(self) -> None:
        pattern = runner_pattern_for_distance(2500)
        self.assertRegex(pattern.name, r"\d{3}$")
        self.assertTrue(pattern.obstacle_types)
        formation = space_formation_for_wave(12)
        self.assertEqual(len(formation.offsets), len(formation.kinds))
        self.assertGreaterEqual(len(formation.kinds), 3)


class MissionDefinitionTests(unittest.TestCase):
    def test_every_mode_has_three_stage_operations(self) -> None:
        self.assertEqual(
            set(OPERATION_BOOK),
            {"neon_ops", "street_rush", "zombie_siege", "orbital_wars", "cyber_runner"},
        )
        for templates in OPERATION_BOOK.values():
            self.assertGreaterEqual(len(templates), 2)
            for operation in templates:
                self.assertEqual(len(operation.stages), 3)
                self.assertGreater(operation.reward_xp, 0)
                self.assertGreater(operation.reward_credits, 0)

    def test_scaled_operation_increases_rewards(self) -> None:
        original = OPERATION_BOOK["neon_ops"][0]
        scaled = MissionDirector._scaled_template(original, 4)
        self.assertGreater(scaled.reward_xp, original.reward_xp)
        self.assertGreater(scaled.reward_credits, original.reward_credits)


if __name__ == "__main__":
    unittest.main()
