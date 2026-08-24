from __future__ import annotations

import unittest

from nexus3d.config import DEFAULT_SETTINGS


class V3SettingsContractTests(unittest.TestCase):
    def test_high_value_v3_systems_are_enabled_by_default(self) -> None:
        required = {
            "advanced_ai",
            "weather_gameplay",
            "dynamic_world_lighting",
            "contracts",
            "run_perks",
            "destructible_props",
            "surface_feedback",
            "weapon_loadout",
            "swept_projectiles",
            "hit_reactions",
            "runtime_lod",
            "player_dynamic_lights",
        }
        missing = sorted(key for key in required if not DEFAULT_SETTINGS.get(key, False))
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
