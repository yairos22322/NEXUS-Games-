from __future__ import annotations

import copy
import json
import os
import time
from typing import Any, Dict

from .config import DEFAULT_SETTINGS, GAMES, SAVE_FILE, SAVE_SCHEMA_VERSION


UPGRADE_KEYS = (
    "firepower",
    "handling",
    "mobility",
    "reserves",
    "plating",
    "fortune",
)


class SaveSystem:
    """Versioned, atomic local profile storage.

    V4 keeps backwards compatibility with V2/V3 saves. New keys are merged in,
    numeric fields are sanitized, and writes use a temporary file + replace so
    a crash cannot normally leave a half-written JSON profile.
    """

    def __init__(self, path: str = SAVE_FILE) -> None:
        self.path = path
        self.last_error: str | None = None
        self.data = self._default_data()
        self.load()

    @staticmethod
    def _default_data() -> Dict[str, Any]:
        return {
            "schema_version": SAVE_SCHEMA_VERSION,
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
            "progression": {
                "upgrade_ranks": {key: 0 for key in UPGRADE_KEYS},
                "achievements": {},
                "lifetime_credits_earned": 0,
                "lifetime_credits_spent": 0,
                "missions_completed": 0,
                "contracts_completed": 0,
                "best_mission_streak": 0,
            },
        }

    def load(self) -> None:
        if not os.path.exists(self.path):
            self.save()
            return
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            if not isinstance(loaded, dict):
                raise TypeError("save root must be an object")
            self._merge(self.data, loaded)
            self._migrate()
            self._sanitize()
            self.save()
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            self.last_error = str(exc)
            backup = self.path + ".broken"
            try:
                os.replace(self.path, backup)
            except OSError:
                pass
            self.data = self._default_data()
            self.save()

    def save(self) -> bool:
        temp_path = self.path + ".tmp"
        try:
            parent = os.path.dirname(os.path.abspath(self.path))
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(temp_path, "w", encoding="utf-8") as handle:
                json.dump(self.data, handle, indent=2, ensure_ascii=False, sort_keys=True)
                handle.flush()
                try:
                    os.fsync(handle.fileno())
                except OSError:
                    pass
            os.replace(temp_path, self.path)
            self.last_error = None
            return True
        except OSError as exc:
            self.last_error = str(exc)
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except OSError:
                pass
            return False

    @staticmethod
    def _merge(base: Dict[str, Any], incoming: Dict[str, Any]) -> None:
        for key, value in incoming.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                SaveSystem._merge(base[key], value)
            else:
                base[key] = value

    def _migrate(self) -> None:
        version = self._safe_int(self.data.get("schema_version", 1), 1)
        # V4 is intentionally merge-based. Old saves did not contain progression,
        # so the defaults already supply every new field without discarding stats.
        if version < SAVE_SCHEMA_VERSION:
            self.data["schema_version"] = SAVE_SCHEMA_VERSION

    def _sanitize(self) -> None:
        self.data["schema_version"] = SAVE_SCHEMA_VERSION
        profile = self.data.setdefault("profile", {})
        profile["level"] = max(1, self._safe_int(profile.get("level", 1), 1))
        profile["xp"] = max(0, self._safe_int(profile.get("xp", 0), 0))
        profile["credits"] = max(0, self._safe_int(profile.get("credits", 0), 0))
        profile["games_played"] = max(0, self._safe_int(profile.get("games_played", 0), 0))
        profile["total_seconds"] = max(0.0, self._safe_float(profile.get("total_seconds", 0.0), 0.0))
        profile["created_at"] = max(0, self._safe_int(profile.get("created_at", int(time.time())), int(time.time())))

        settings = self.data.setdefault("settings", {})
        for key, value in DEFAULT_SETTINGS.items():
            settings.setdefault(key, copy.deepcopy(value))

        scores = self.data.setdefault("scores", {})
        stats = self.data.setdefault("stats", {})
        for game in GAMES:
            scores[game.game_id] = max(0, self._safe_int(scores.get(game.game_id, 0), 0))
            row = stats.setdefault(game.game_id, {})
            row["plays"] = max(0, self._safe_int(row.get("plays", 0), 0))
            row["wins"] = max(0, self._safe_int(row.get("wins", 0), 0))
            row["kills"] = max(0, self._safe_int(row.get("kills", 0), 0))
            row["distance"] = max(0.0, self._safe_float(row.get("distance", 0.0), 0.0))
            row["best_combo"] = max(0, self._safe_int(row.get("best_combo", 0), 0))
            row["best_wave"] = max(0, self._safe_int(row.get("best_wave", 0), 0))

        progression = self.data.setdefault("progression", {})
        ranks = progression.setdefault("upgrade_ranks", {})
        for key in UPGRADE_KEYS:
            ranks[key] = max(0, min(10, self._safe_int(ranks.get(key, 0), 0)))
        achievements = progression.setdefault("achievements", {})
        if not isinstance(achievements, dict):
            progression["achievements"] = {}
        for key in (
            "lifetime_credits_earned",
            "lifetime_credits_spent",
            "missions_completed",
            "contracts_completed",
            "best_mission_streak",
        ):
            progression[key] = max(0, self._safe_int(progression.get(key, 0), 0))

    @staticmethod
    def _safe_int(value: Any, fallback: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError, OverflowError):
            return fallback

    @staticmethod
    def _safe_float(value: Any, fallback: float) -> float:
        try:
            result = float(value)
            if result != result or result in (float("inf"), float("-inf")):
                return fallback
            return result
        except (TypeError, ValueError, OverflowError):
            return fallback

    @property
    def settings(self) -> Dict[str, Any]:
        return self.data["settings"]

    @property
    def profile(self) -> Dict[str, Any]:
        return self.data["profile"]

    @property
    def progression(self) -> Dict[str, Any]:
        return self.data["progression"]

    def setting(self, key: str, fallback: Any = None) -> Any:
        return self.data.get("settings", {}).get(key, fallback)

    def set_setting(self, key: str, value: Any) -> None:
        self.data.setdefault("settings", {})[key] = value
        self.save()

    def score_for(self, game_id: str) -> int:
        return max(0, self._safe_int(self.data.get("scores", {}).get(game_id, 0), 0))

    def submit_score(self, game_id: str, score: int) -> bool:
        score = max(0, int(score))
        current = self.score_for(game_id)
        if score > current:
            self.data.setdefault("scores", {})[game_id] = score
            self.save()
            return True
        return False

    def add_play(self, game_id: str) -> None:
        self.profile["games_played"] = int(self.profile.get("games_played", 0)) + 1
        self.data["stats"].setdefault(game_id, {}).setdefault("plays", 0)
        self.data["stats"][game_id]["plays"] += 1
        self.save()

    def add_session_time(self, seconds: float) -> None:
        self.profile["total_seconds"] = float(self.profile.get("total_seconds", 0.0)) + max(0.0, float(seconds))

    def add_xp(self, amount: int) -> int:
        amount = max(0, int(amount))
        self.profile["xp"] = int(self.profile.get("xp", 0)) + amount
        levels_gained = 0
        while self.profile["xp"] >= self.xp_for_next_level():
            threshold = self.xp_for_next_level()
            self.profile["xp"] -= threshold
            self.profile["level"] = int(self.profile.get("level", 1)) + 1
            self.add_credits(250, save=False)
            levels_gained += 1
        self.save()
        return levels_gained

    def xp_for_next_level(self) -> int:
        level = max(1, int(self.profile.get("level", 1)))
        return 800 + (level - 1) * 250

    def add_credits(self, amount: int, save: bool = True) -> int:
        amount = max(0, int(amount))
        if amount <= 0:
            return int(self.profile.get("credits", 0))
        self.profile["credits"] = int(self.profile.get("credits", 0)) + amount
        self.progression["lifetime_credits_earned"] = int(
            self.progression.get("lifetime_credits_earned", 0)
        ) + amount
        if save:
            self.save()
        return int(self.profile["credits"])

    def spend_credits(self, amount: int) -> bool:
        amount = max(0, int(amount))
        balance = int(self.profile.get("credits", 0))
        if amount <= 0:
            return True
        if balance < amount:
            return False
        self.profile["credits"] = balance - amount
        self.progression["lifetime_credits_spent"] = int(
            self.progression.get("lifetime_credits_spent", 0)
        ) + amount
        self.save()
        return True

    def upgrade_rank(self, key: str) -> int:
        return max(0, int(self.progression.setdefault("upgrade_ranks", {}).get(key, 0)))

    def set_upgrade_rank(self, key: str, rank: int) -> None:
        if key not in UPGRADE_KEYS:
            raise KeyError(key)
        self.progression.setdefault("upgrade_ranks", {})[key] = max(0, min(10, int(rank)))
        self.save()

    def add_stat(self, game_id: str, key: str, value: float | int) -> None:
        stats = self.data["stats"].setdefault(game_id, {})
        stats[key] = stats.get(key, 0) + value

    def max_stat(self, game_id: str, key: str, value: float | int) -> None:
        stats = self.data["stats"].setdefault(game_id, {})
        stats[key] = max(stats.get(key, 0), value)

    def mark_win(self, game_id: str) -> None:
        row = self.data["stats"].setdefault(game_id, {})
        row["wins"] = int(row.get("wins", 0)) + 1
        self.save()

    def record_mission_complete(self, game_id: str, streak: int = 1) -> None:
        row = self.data["stats"].setdefault(game_id, {})
        row["wins"] = int(row.get("wins", 0)) + 1
        self.progression["missions_completed"] = int(self.progression.get("missions_completed", 0)) + 1
        self.progression["best_mission_streak"] = max(
            int(self.progression.get("best_mission_streak", 0)),
            max(1, int(streak)),
        )
        self.save()

    def record_contract_complete(self) -> None:
        self.progression["contracts_completed"] = int(self.progression.get("contracts_completed", 0)) + 1
        self.save()

    def reset_profile(self) -> None:
        self.data = self._default_data()
        self.save()
