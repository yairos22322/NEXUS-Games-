# Changelog

## 4.0.0-ascension - 2026-09-05

V4 ASCENSION is a gameplay, progression and architecture overhaul.

### Progression
- Added versioned V4 save schema with backwards migration.
- Added atomic save writes and numeric sanitization.
- Added persistent credit earning and spending APIs.
- Added the F2 NEXUS Lab with six permanent upgrade tracks.
- Added persistent achievements with XP and credit rewards.
- Added game-over run payouts.

### Operations and replayability
- Added three-stage authored operations to all five modes.
- Operation completion now records real wins.
- Operations award score, XP and credits.
- Follow-up operations scale with player progress.
- Expanded contracts with more metric types.

### Roguelite combat builds
- Added mouse-selectable perk cards while retaining Z/X/C controls.
- Added heal-on-kill, armor/shield siphon, ammo/energy generation, low-health damage and dash-reload behaviours.
- Added shared RunModifierDirector so behavioural perks do not require duplicated mode logic.

### Simulation fixes
- Added CameraDirector as final shared FOV/roll authority.
- Fixed cumulative V3 camera-roll drift.
- Removed one-way adaptive-difficulty player power ratchets.
- Preserved A*, spatial hashing, swept collision, destruction, weather gameplay, LOD and V3 tactical systems.

### Content architecture
- Replaced the oversized literal content catalog with compact deterministic generators.
- Preserved the public content lookup interfaces used by all five modes.
- Added a validator size budget to prevent generated source bloat from returning.

### Validation
- Added V4 migration, economy, deterministic content and operation tests.
- V4 PR validation passed the complete Python 3.11 / 3.12 / 3.13 Panda3D CI matrix before merge.
- Added `UPGRADE_V4_NOTES.md` and `V4_PLAYTEST.md`.

## 1.0.0-ultra - 2026-08-24

Initial GitHub-ready ULTRA release.

### Included
- Five playable 3D game modes
- Panda3D rendering foundation
- Optional simplepbr pipeline
- Dynamic shadows and quality presets
- Procedural sky and animated water shaders
- Weather, skyline, materials, and environment systems
- Windows install/run scripts
- Project validation script
- GitHub Actions validation
- Issue and pull request templates
