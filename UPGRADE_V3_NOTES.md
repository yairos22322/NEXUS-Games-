# NEXUS FIVE 3D - Simulation V3

Simulation V3 focuses on systems that make the existing five modes behave like deeper games instead of adding line count or static preset data.

## Core simulation

- Adaptive frame substeps, up to 3 simulation slices on heavy frames.
- Spatial-hash broadphase for dense enemy separation.
- Swept projectile collision fallback for fast lasers/projectiles.
- Runtime LOD for optional procedural rig details.
- Dynamic player-only light budget.
- Slow dynamic key-light / sun movement during runs.

## Neon Ops

- A* navigation around box colliders when direct line of sight is blocked.
- Existing tactical roles remain active: assault, flank, suppress, hunt, retreat and cover.
- Three runtime weapon slots:
  - `1` VX-7 Assault
  - `2` KITE-9 SMG
  - `3` Sentinel DMR
- Separate ammo/reserve state per weapon.
- ADS and weapon-specific recoil behavior.
- Destructible crates and barriers remove their colliders when destroyed.
- Tracers and world impact feedback.
- Directional hit reactions on enemies.
- Weather can reduce long-range enemy firing confidence.

## Zombie Siege

- A* path assist through ruined district geometry.
- Existing surround-slot horde logic remains authoritative.
- Runners, walkers and brutes receive different knockback reactions.
- Destructible cover changes navigation during a wave.
- Shotgun tracer fan and landing/impact feedback.
- Heavy rain/storms slightly de-synchronize horde attack timing.

## Street Rush

- Existing traffic car-following / overtaking logic remains active.
- Wet weather now changes grip, brake authority and acceleration slightly.
- Handbrake drift leaves pooled skid marks and smoke.
- Dynamic headlights and nitro glow.
- Runtime LOD removes tiny vehicle detail outside useful visual range.

## Orbital Wars

- Existing formations, bomber runs, interceptor evasion and capital positioning remain active.
- Swept projectile collision catches fast crossings between simulation samples.
- Directional hit impulse and roll reaction on enemy ships.
- Dynamic engine / cockpit point lights.
- Mid-run perks can improve lasers, missiles, shield, hull, energy or pulse.

## Cyber Runner

- Existing coyote time, jump buffering, vaulting and wall-running remain active.
- Wind can gently affect airborne lateral position in heavy weather presets.
- Landing particles provide stronger contact feedback.
- Dynamic runner glow increases during dash.

## Contracts

Every mode receives optional short in-run contracts with a HUD progress bar. Contracts reward score, XP and credits and then roll into a follow-up objective.

Examples include kills, waves/sectors, survival time, score, distance and flow multiplier.

## Combat perks

Neon Ops, Zombie Siege and Orbital Wars offer a three-card upgrade choice every few waves. Controls while the perk screen is open:

- `Z` left perk
- `X` middle perk
- `C` right perk

The perk overlay is modal. Shared AI and simulation remain frozen while a choice is active.

## Destruction

Combat modes receive a small number of deliberately placed destructible props rather than making the whole procedural city destructible. Destroyed props:

- create debris / particles
- remove their solid collider
- increment navigation revision
- force the A* navigation grid to rebuild
- award a small score bonus

## Performance

Simulation V3 adds work, so it also adds explicit scaling systems:

- spatial hashing replaces the old global crowd pair scan
- A* repathing is budgeted across actors
- runtime LOD only hides optional detail geometry, never gameplay rigs
- surface feedback uses reusable tracer / impact / skid pools
- V2 particle pooling remains active
- adaptive graphics remains the graphics density governor

## CI / validation

The V3 branch upgrades GitHub Actions to:

1. install the real Panda3D project dependencies
2. compile all Python source
3. run `CHECK_PROJECT.py`
4. import Panda3D / Direct / simplepbr
5. run V3 unit tests on Python 3.11, 3.12 and 3.13

`CHECK_PROJECT.py` also contains a conservative accidental-secret scan for common API-token/private-key formats.

## Manual playtest checklist

### Neon Ops
- Switch 1/2/3 repeatedly and verify ammo is independent.
- ADS while firing and verify recoil differs by weapon.
- Shoot destructible cover and verify AI can route through the opening after destruction.
- Verify weapon switching does not create a fake tracer or damage cover.
- Open a perk choice, press Escape, and verify gameplay does not resume behind the overlay.

### Zombie Siege
- Kite a large horde around ruins and verify actors route instead of stacking on walls.
- Destroy cover while zombies are pathing.
- Verify runners receive stronger knockback than brutes.

### Street Rush
- Test handbrake drift in dry and rainy presets.
- Verify skid marks recycle instead of growing forever.
- Check headlights / nitro light at night.

### Orbital Wars
- Cross a fast laser through an enemy between frames and verify swept collision catches it.
- Confirm enemy formations are still active after hit reactions.

### Cyber Runner
- Check coyote jump, buffered jump, wall run and landing feedback.
- Verify strong wind is noticeable but not strong enough to steal control.

## Known visual ceiling

The largest remaining visual limitation is art content, not simulation code. The project still relies heavily on procedural primitives. The next major visual step should be a real asset pipeline for skeletal characters, detailed vehicles, animations and authored PBR models rather than another large increase in Python line count.
