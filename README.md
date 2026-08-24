# NEXUS FIVE 3D // ULTRA

A five-mode Python 3D arcade project built on Panda3D with an optional `panda3d-simplepbr` physically based rendering pipeline.

This ULTRA build focuses on the render layer rather than simply adding more gameplay code. It adds a separate graphics subsystem for PBR-style materials, dynamic shadow maps, procedural sky shaders, animated water shaders, weather volumes, distant city detail, emissive accents, material variation, cinematic quality presets and a fallback post-processing path.


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

## GitHub-ready repository

This distribution includes repository hygiene and collaboration files out of the box:

- `.gitignore` and `.gitattributes`
- GitHub Actions syntax checks
- bug and feature issue templates
- pull request template
- `CONTRIBUTING.md`, `SECURITY.md`, and `CHANGELOG.md`
- `PUBLISH_TO_GITHUB.bat` and PowerShell publisher
- `GITHUB_UPLOAD_GUIDE.md`

No open-source license is selected automatically. Choose one later only if you want to grant reuse rights.

## Reality check

This project is **not GTA 6 and does not claim to beat GTA 6 visually**. A modern Rockstar-scale game depends on a huge proprietary engine, professional 3D art, scanned materials, character animation, motion capture, authored world assets, streaming systems and a very large team. More source lines alone cannot replace those assets.

The goal of this build is different: push a pure-Python/Panda3D prototype much further visually while keeping the whole project editable.

## Current project size

Run:

```bash
python CHECK_PROJECT.py
```

The ULTRA build contains more than 70,000 Python source lines. The large count is mainly caused by runtime-used visual, weather and material preset libraries. The renderer itself is much smaller and is where the important visual work happens.

## New ULTRA graphics layer

- Physically based metallic/roughness material parameters
- Optional `panda3d-simplepbr` render pipeline
- Filmic tone mapping through the PBR pipeline
- Directional shadow maps up to 4096 x 4096 on CINEMATIC
- Automatic fallback shader pipeline if simplepbr is unavailable
- Fallback HDR, bloom and SSAO through Panda3D CommonFilters
- Procedural GLSL 1.50 sky with gradient atmosphere, sun halo, clouds and stars
- Procedural animated water with vertex displacement and ripple highlights
- Camera-centred 3D rain, storms, ash, dust, snow and spark fields
- Lightning flash treatment without permanently changing the clear colour
- Distant procedural skyline for stronger depth and parallax
- Emissive signs and distant light artifacts
- Flat-corrected box normals for better per-pixel lighting
- Material library with metallic, roughness, glass, concrete, asphalt, skin, rubber, vehicle paint, weapon metal and emissive categories
- 2,100 visual environment presets
- 1,900 material presets
- 600 weather presets
- LOW / MEDIUM / HIGH / ULTRA / CINEMATIC quality modes

## Five 3D games

### 1. NEON OPS
First-person arena shooter with mouse aim, rifle, ammo, reload, armor, headshots, enemy squads, elites, projectiles, waves, pickups, procedural arenas and 3D impact effects.

### 2. STREET RUSH
Third-person 3D traffic racer with chase camera, traffic vehicles, moving city sections, nitro, collisions, near misses, health and dynamic field of view.

### 3. ZOMBIE SIEGE
3D survival shooter with shotgun simulation, walker/runner/brute infected, health, armor, stamina, medkits, waves, drops and ruined-city scenery.

### 4. ORBITAL WARS
3D space combat with fighters, bombers, capital enemies, lasers, missiles, shields, hull, energy, boost, pulse attacks, starfield and planet geometry.

### 5. CYBER RUNNER
Third-person rooftop parkour with jumping, sliding, phase dash, laser gates, barriers, data shards, drones, increasing speed and procedural obstacle sequences.

## Graphics quality

The Settings screen now contains:

```text
LOW
MEDIUM
HIGH
ULTRA
CINEMATIC
```

A restart is recommended after changing the quality because MSAA, the light budget and parts of the PBR pipeline are created at startup.

CINEMATIC uses the highest shadow resolution and environment density and is intentionally expensive.

## Install on Windows

1. Extract the ZIP.
2. Open the extracted folder.
3. Double-click `INSTALL_AND_RUN.bat`.
4. The installer installs the requirements and runs `main.py`.

Manual installation:

```bash
python -m pip install -r requirements.txt
python main.py
```

## Requirements

```text
panda3d==1.10.16
panda3d-simplepbr==0.13.1
```

The game still has a built-in shader/post-processing fallback if `simplepbr` cannot initialize.

## Important art limitation

The included world is intentionally procedural and code-generated. That makes the ZIP self-contained, but it is also the biggest reason it cannot look like a current AAA open-world game.

For the next major visual jump, replace procedural boxes/ships/characters with properly authored `.glb` assets that contain:

- high-poly/low-poly models
- UVs
- 2K or 4K base-colour textures
- roughness and metallic maps
- normal maps
- baked detail
- rigged characters
- authored animations

The render layer in this build is structured so those assets can be integrated later without rewriting all five game modes.

## Key folders

```text
NEXUS_FIVE_3D_ULTRA/
  main.py
  CHECK_PROJECT.py
  INSTALL_AND_RUN.bat
  RUN.bat
  requirements.txt
  nexus3d/
    app.py
    primitives.py
    world.py
    ui.py
    graphics/
      pipeline.py
      quality.py
      environment.py
      atmosphere.py
      weather.py
      materials.py
      geometry.py
      visual_presets.py
      material_presets.py
      weather_presets.py
    shaders/
      sky.vert
      sky.frag
      water.vert
      water.frag
    modes/
      neon_ops.py
      street_rush.py
      zombie_siege.py
      orbital_wars.py
      cyber_runner.py
```
