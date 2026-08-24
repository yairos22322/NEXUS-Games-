from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

Color = Tuple[float, float, float, float]

APP_TITLE = "NEXUS FIVE 3D // ULTRA"
WINDOW_WIDTH = 1600
WINDOW_HEIGHT = 900
TARGET_FPS = 144
SAVE_FILE = "nexus3d_profile.json"
AUDIO_FOLDER = "generated_audio"

BLACK: Color = (0.01, 0.015, 0.025, 1.0)
DARK: Color = (0.025, 0.035, 0.06, 1.0)
PANEL: Color = (0.045, 0.065, 0.10, 0.96)
PANEL_ALT: Color = (0.07, 0.095, 0.14, 0.96)
WHITE: Color = (0.95, 0.97, 1.0, 1.0)
MUTED: Color = (0.55, 0.62, 0.72, 1.0)
CYAN: Color = (0.05, 0.9, 1.0, 1.0)
BLUE: Color = (0.12, 0.38, 1.0, 1.0)
PURPLE: Color = (0.62, 0.22, 1.0, 1.0)
MAGENTA: Color = (1.0, 0.12, 0.65, 1.0)
RED: Color = (1.0, 0.12, 0.18, 1.0)
ORANGE: Color = (1.0, 0.42, 0.08, 1.0)
YELLOW: Color = (1.0, 0.82, 0.10, 1.0)
GREEN: Color = (0.12, 1.0, 0.48, 1.0)


@dataclass(frozen=True)
class GameMeta:
    game_id: str
    title: str
    subtitle: str
    genre: str
    description: str
    controls: List[str]
    accent: Color
    secondary: Color
    badge: str


GAMES: List[GameMeta] = [
    GameMeta(
        game_id="neon_ops",
        title="NEON OPS",
        subtitle="TACTICAL ARENA",
        genre="3D FPS",
        description=(
            "First-person arena combat with hitscan weapons, reloads, enemy squads, "
            "wave escalation, armor, pickups, sprint and dash."
        ),
        controls=["WASD MOVE", "MOUSE AIM", "LMB FIRE", "R RELOAD", "SHIFT SPRINT", "SPACE DASH"],
        accent=CYAN,
        secondary=BLUE,
        badge="01",
    ),
    GameMeta(
        game_id="street_rush",
        title="STREET RUSH",
        subtitle="MIDNIGHT CIRCUIT",
        genre="3D DRIVING",
        description=(
            "High-speed third-person traffic run with nitro, close-call combos, "
            "lane dodging, destructible road props and escalating traffic density."
        ),
        controls=["A/D STEER", "W ACCELERATE", "S BRAKE", "SHIFT NITRO", "SPACE HANDBRAKE"],
        accent=MAGENTA,
        secondary=PURPLE,
        badge="02",
    ),
    GameMeta(
        game_id="zombie_siege",
        title="ZOMBIE SIEGE",
        subtitle="LAST DISTRICT",
        genre="3D SURVIVAL",
        description=(
            "Over-the-shoulder survival shooter with swarms, elite infected, "
            "medkits, armor drops, shotgun bursts and increasingly brutal nights."
        ),
        controls=["WASD MOVE", "MOUSE AIM", "LMB FIRE", "R RELOAD", "Q MEDKIT", "SHIFT SPRINT"],
        accent=GREEN,
        secondary=YELLOW,
        badge="03",
    ),
    GameMeta(
        game_id="orbital_wars",
        title="ORBITAL WARS",
        subtitle="VOID FRONT",
        genre="3D SPACE COMBAT",
        description=(
            "Arcade space combat with lasers, missiles, shields, boost, enemy formations, "
            "capital ships and boss encounters in a procedural star field."
        ),
        controls=["WASD FLY", "MOUSE AIM", "LMB LASER", "RMB MISSILE", "SHIFT BOOST", "Q PULSE"],
        accent=BLUE,
        secondary=CYAN,
        badge="04",
    ),
    GameMeta(
        game_id="cyber_runner",
        title="CYBER RUNNER",
        subtitle="SKYLINE BREACH",
        genre="3D PARKOUR",
        description=(
            "Third-person endless rooftop run with jumps, slides, air dashes, "
            "laser gates, drones, moving platforms and score multipliers."
        ),
        controls=["A/D STRAFE", "SPACE JUMP", "SHIFT DASH", "CTRL SLIDE", "W SPEED PUSH"],
        accent=ORANGE,
        secondary=YELLOW,
        badge="05",
    ),
]

GAME_BY_ID: Dict[str, GameMeta] = {game.game_id: game for game in GAMES}

DIFFICULTIES = {
    "RECRUIT": 0.80,
    "OPERATIVE": 1.00,
    "VETERAN": 1.22,
}

DEFAULT_SETTINGS = {
    "difficulty": "OPERATIVE",
    "master_volume": 0.72,
    "music_volume": 0.42,
    "sfx_volume": 0.78,
    "mouse_sensitivity": 0.18,
    "camera_shake": True,
    "particles": True,
    "fullscreen": False,
    "vsync": True,
    "fov": 82,
    "graphics_quality": "ULTRA",
    "cinematic_postfx": True,
    "dynamic_weather": True,
}
