from __future__ import annotations

import copy
import json
import os
import time
from typing import Any, Dict

from .config import DEFAULT_SETTINGS, GAMES, SAVE_FILE


class SaveSystem:
    def __init__(self, path: str = SAVE_FILE) -> None:
        self.path = path
        self.data = self._default_data()
        self.load()

    @staticmethod
    def _default_data() -> Dict[str, Any]:
        return {
            "profile": {
                "level": 1,
                "xp": 0,
                "credits": 0,
                "games_played": 0,
                "total_seconds": 0.0,
                "created_at": int(time.time()),
            },
            "settings": copy.deepcopy(DEFAULT_SETTINGS),
            "scores": {game.game_id: 0 for game in GAMES},
            "stats": {
                game.game_id: {
                    "plays": 0,
                    "wins": 0,
                    "kills": 0,
                    "distance": 0.0,
                    "best_combo": 0,
                    "best_wave": 0,
                }
                for game in GAMES
            },
            "unlocks": {
                "themes": ["default"],
                "badges": [],
            },
        }

    def load(self) -> None:
        if not os.path.exists(self.path):
            self.save()
            return
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            self._merge(self.data, loaded)
        except (OSError, json.JSONDecodeError, TypeError):
            backup = self.path + ".broken"
            try:
                os.replace(self.path, backup)
            except OSError:
                pass
            self.data = self._default_data()
            self.save()

    def save(self) -> None:
        temp_path = self.path + ".tmp"
        try:
            with open(temp_path, "w", encoding="utf-8") as handle:
                json.dump(self.data, handle, indent=2, ensure_ascii=False)
            os.replace(temp_path, self.path)
        except OSError:
            pass

    @staticmethod
    def _merge(base: Dict[str, Any], incoming: Dict[str, Any]) -> None:
        for key, value in incoming.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                SaveSystem._merge(base[key], value)
            else:
                base[key] = value

    @property
    def settings(self) -> Dict[str, Any]:
        return self.data["settings"]

    @property
    def profile(self) -> Dict[str, Any]:
        return self.data["profile"]

    def setting(self, key: str, fallback: Any = None) -> Any:
        return self.data.get("settings", {}).get(key, fallback)

    def set_setting(self, key: str, value: Any) -> None:
        self.data.setdefault("settings", {})[key] = value
        self.save()

    def score_for(self, game_id: str) -> int:
        return int(self.data.get("scores", {}).get(game_id, 0))

    def submit_score(self, game_id: str, score: int) -> bool:
        current = self.score_for(game_id)
        if score > current:
            self.data["scores"][game_id] = int(score)
            self.save()
            return True
        return False

    def add_play(self, game_id: str) -> None:
        self.profile["games_played"] += 1
        self.data["stats"][game_id]["plays"] += 1
        self.save()

    def add_session_time(self, seconds: float) -> None:
        self.profile["total_seconds"] += max(0.0, float(seconds))

    def add_xp(self, amount: int) -> int:
        amount = max(0, int(amount))
        self.profile["xp"] += amount
        levels_gained = 0
        while self.profile["xp"] >= self.xp_for_next_level():
            self.profile["xp"] -= self.xp_for_next_level()
            self.profile["level"] += 1
            self.profile["credits"] += 250
            levels_gained += 1
        self.save()
        return levels_gained

    def xp_for_next_level(self) -> int:
        level = int(self.profile.get("level", 1))
        return 800 + (level - 1) * 250

    def add_stat(self, game_id: str, key: str, value: float | int) -> None:
        stats = self.data["stats"].setdefault(game_id, {})
        stats[key] = stats.get(key, 0) + value

    def max_stat(self, game_id: str, key: str, value: float | int) -> None:
        stats = self.data["stats"].setdefault(game_id, {})
        stats[key] = max(stats.get(key, 0), value)

    def mark_win(self, game_id: str) -> None:
        self.data["stats"][game_id]["wins"] += 1
        self.save()

    def reset_profile(self) -> None:
        self.data = self._default_data()
        self.save()
