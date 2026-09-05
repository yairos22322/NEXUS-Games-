from __future__ import annotations

import ast
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
python_files = sorted(path for path in ROOT.rglob("*.py") if "__pycache__" not in path.parts)
total_lines = 0
errors: list[str] = []

REQUIRED_V4 = [
    "nexus3d/progression.py",
    "nexus3d/gameplay/camera.py",
    "nexus3d/gameplay/missions.py",
    "nexus3d/gameplay/run_modifiers.py",
    "nexus3d/gameplay/spatial.py",
    "nexus3d/gameplay/navigation.py",
    "nexus3d/gameplay/contracts.py",
    "nexus3d/gameplay/destruction.py",
    "nexus3d/gameplay/environment_gameplay.py",
    "nexus3d/gameplay/projectile_safety.py",
    "nexus3d/gameplay/hit_reactions.py",
    "nexus3d/gameplay/weapons.py",
    "nexus3d/gameplay/perks.py",
    "nexus3d/graphics/surface_feedback.py",
    "nexus3d/graphics/world_lighting.py",
    "nexus3d/graphics/player_lighting.py",
    "nexus3d/graphics/runtime_lod.py",
]

REQUIRED_SETTING_TOKENS = [
    '"advanced_ai": True',
    '"weather_gameplay": True',
    '"contracts": True',
    '"missions": True',
    '"run_perks": True',
    '"run_modifiers": True',
    '"destructible_props": True',
    '"weapon_loadout": True',
    '"swept_projectiles": True',
    '"hit_reactions": True',
    '"runtime_lod": True',
    '"player_dynamic_lights": True',
    '"meta_progression": True',
    '"run_payouts": True',
]

SECRET_PATTERNS = {
    "OpenAI-style secret": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "GitHub classic token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    "GitHub fine-grained token": re.compile(r"\bgithub_pat_[A-Za-z0-9_]{30,}\b"),
    "AWS access key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "Google API key": re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
    "Slack token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    "Private key block": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |)PRIVATE KEY-----"),
}

TEXT_EXTENSIONS = {
    ".py", ".md", ".txt", ".json", ".yml", ".yaml", ".toml",
    ".ini", ".cfg", ".bat", ".ps1", ".env", ".pem", ".key",
}

for path in python_files:
    text = path.read_text(encoding="utf-8")
    total_lines += len(text.splitlines())
    try:
        ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        errors.append(f"{path.relative_to(ROOT)}:{exc.lineno}: {exc.msg}")

for relative in REQUIRED_V4:
    if not (ROOT / relative).is_file():
        errors.append(f"Missing required V4 module: {relative}")

config_path = ROOT / "nexus3d" / "config.py"
if config_path.is_file():
    config_text = config_path.read_text(encoding="utf-8")
    for token in REQUIRED_SETTING_TOKENS:
        if token not in config_text:
            errors.append(f"Missing V4 default setting: {token}")
    if "SAVE_SCHEMA_VERSION = 4" not in config_text:
        errors.append("V4 save schema marker is missing")

catalog_path = ROOT / "nexus3d" / "data" / "content_catalog.py"
if catalog_path.is_file() and catalog_path.stat().st_size > 80_000:
    errors.append(
        "content_catalog.py regressed above 80 KB. V4 intentionally uses compact deterministic generators."
    )

secret_hits: list[str] = []
for path in ROOT.rglob("*"):
    if not path.is_file() or ".git" in path.parts or "__pycache__" in path.parts:
        continue
    if path.suffix.lower() not in TEXT_EXTENSIONS and path.name not in {".env", ".env.local"}:
        continue
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        continue
    for label, pattern in SECRET_PATTERNS.items():
        match = pattern.search(text)
        if match:
            line = text.count("\n", 0, match.start()) + 1
            secret_hits.append(f"{path.relative_to(ROOT)}:{line}: possible {label}")

if secret_hits:
    errors.extend(secret_hits)

print(f"Python files: {len(python_files)}")
print(f"Total Python lines: {total_lines:,}")
print(f"Required V4 modules: {len(REQUIRED_V4)}")
print(f"Secret patterns checked: {len(SECRET_PATTERNS)}")

if errors:
    print("Validation errors:")
    for error in errors:
        print(" -", error)
    raise SystemExit(1)

print("Syntax check: PASS")
print("V4 integrity: PASS")
print("Secret scan: PASS")
