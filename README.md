# NEXUS FIVE 3D // V4 ASCENSION

NEXUS FIVE is a five-mode 3D arcade project built in Python with Panda3D. V4 ASCENSION shifts the project from a systems-heavy prototype toward a stronger game loop with persistent progression, authored operations, meaningful rewards, deeper run builds and cleaner simulation architecture.

The project remains fully editable and self-contained. It uses procedural geometry as a fallback, while the render architecture is ready for authored `.glb` models and animation assets.

## V4 highlights

### Persistent NEXUS Lab
Press `F2` from the main menu to open the NEXUS Lab and spend credits on permanent account-wide upgrades:

- Ballistic Core: combat output
- Reflex Link: reload and weapon handling
- Kinetic Frame: movement and handling
- Field Cache: starting reserves and utility
- Aegis Plating: survivability
- Salvage Protocol: larger credit rewards

Credits are now earned from operations, contracts, run payouts, achievements and level-ups.

### Authored operations
Every mode has multi-stage operations layered over the endless arcade loop. Completing an operation records a real win and awards score, XP and credits before a harder follow-up operation is issued.

### Deeper roguelite builds
Combat perk drafts now include behavioural build effects in addition to stat upgrades. Examples include:

- heal on kill
- armor or shield siphon
- kill-generated ammunition or energy
- low-health damage bonuses
- dash-triggered magazine refill
- fire-rate overclocking

Perk cards can be selected with the mouse or `Z / X / C`.

### V4 simulation cleanup

- Dedicated CameraDirector owns final shared FOV and camera roll
- cumulative V3 camera-roll drift removed
- adaptive difficulty no longer permanently ratchets player power upward
- persistent upgrades are applied once per run
- run modifiers execute shared perk behaviours without duplicating logic in every mode
- versioned V4 save migration preserves older profiles
- save writes use a temporary file and atomic replace

### Compact deterministic content
V3 contained a very large generated literal content catalog. V4 replaces that catalog with compact deterministic generators for weapons, enemies, traffic, zombies, runner patterns, space formations and Neon Ops arenas.

The same public gameplay interfaces remain available, but balancing is easier and repository size is substantially lower.

## Five playable modes

### 1. NEON OPS
First-person cyber arena combat with:

- mouse aim and ADS
- AR / SMG / DMR weapon switching
- recoil and independent ammunition
- tactical enemy roles
- A* navigation
- destructible cover
- headshots and hit reactions
- run perks, contracts and multi-stage operations

### 2. STREET RUSH
Third-person traffic racing with:

- acceleration and braking
- nitro
- handbrake drifting
- close-call chains
- intelligent traffic behaviour
- weather-dependent road grip
- skid feedback
- contracts and operations

### 3. ZOMBIE SIEGE
Over-the-shoulder survival with:

- walker, runner and brute infected
- shotgun combat
- stamina, armor and medkits
- A* horde routing
- destructible cover
- knockback
- build-defining perks
- contracts and operations

### 4. ORBITAL WARS
3D space combat with:

- lasers and homing missiles
- shields, hull and energy
- boost and pulse abilities
- formations and evasive enemies
- swept projectile collision
- capital enemies
- shield/energy build perks
- contracts and operations

### 5. CYBER RUNNER
Third-person rooftop parkour with:

- buffered jumping and coyote time
- vaulting and wall-running support
- sliding
- air dash
- data shards and drones
- increasing speed and score flow
- contracts and operations

## Graphics

NEXUS supports:

- optional `panda3d-simplepbr` PBR rendering
- Panda3D fallback shader path
- dynamic shadow maps
- HDR / bloom / SSAO fallback post-processing
- procedural sky shaders
- animated water shaders
- weather volumes
- dynamic world and player lighting
- runtime LOD
- adaptive graphics density
- LOW / MEDIUM / HIGH / ULTRA / CINEMATIC presets

## Quick start

### Windows

1. Install Python.
2. Double-click `INSTALL_AND_RUN.bat`.
3. On later launches, use `RUN.bat`.

### Terminal

```bash
python -m pip install -r requirements.txt
python CHECK_PROJECT.py
python main.py
```

Requirements:

```text
panda3d==1.10.16
panda3d-simplepbr==0.13.1
```

## Validation

The GitHub Actions matrix runs on Python 3.11, 3.12 and 3.13 and performs:

1. dependency installation
2. full Python compilation
3. `CHECK_PROJECT.py`
4. Panda3D / Direct / simplepbr import verification
5. unit-test discovery

V4 adds tests for save migration, credit spending, upgrade clamping, deterministic procedural content and operation definitions/scaling in addition to the existing V3 simulation tests.

## V4 files

Key additions include:

```text
nexus3d/
  progression.py
  gameplay/
    camera.py
    missions.py
    run_modifiers.py
    perks.py
    contracts.py
    director.py
  data/
    content_catalog.py

tests/
  test_v4_progression.py

UPGRADE_V4_NOTES.md
V4_PLAYTEST.md
```

## Important presentation limitation

V4 improves systems, progression, simulation architecture and content structure. It does not pretend procedural box-built characters and vehicles equal modern AAA authored assets.

The largest remaining visual upgrade requires real asset production:

- rigged character models
- skeletal animation clips and blending
- high-quality weapon and vehicle meshes
- authored environment props
- PBR texture sets and normal maps
- professional sound libraries and music
- extensive hands-on playtesting and balance passes

The codebase is structured so those assets can be integrated without replacing the five-mode architecture.

## Project philosophy

NEXUS V4 prioritizes player-facing depth over source-line count. New systems should improve decisions, feel, progression, replayability or presentation. Generated literal data should not be used merely to make the repository look larger.

See `UPGRADE_V4_NOTES.md` for the full V4 technical summary and `V4_PLAYTEST.md` for the manual playtest checklist.
