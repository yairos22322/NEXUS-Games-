# NEXUS FIVE 3D - V4 ASCENSION

V4 changes the project from a collection of impressive arcade systems into a stronger game loop with persistent goals, meaningful currency, authored operations and build-defining run upgrades.

## Core V4 changes

### Persistent NEXUS Lab
- Press `F2` from the main menu to open the NEXUS Lab.
- Credits now have a real purpose.
- Six account-wide upgrade tracks:
  - Ballistic Core
  - Reflex Link
  - Kinetic Frame
  - Field Cache
  - Aegis Plating
  - Salvage Protocol
- Upgrade costs scale by rank.
- Credits spent and earned are tracked in the save profile.
- Old V2/V3 saves migrate automatically to schema version 4.

### Operations and real wins
Every game mode now receives a three-stage operation on top of the existing endless score loop.

Examples:
- Neon Ops: kills -> waves -> score
- Street Rush: distance -> score -> close-call combo
- Zombie Siege: kills -> survival -> nights
- Orbital Wars: kills -> sectors -> score
- Cyber Runner: distance -> flow multiplier -> score

Completing an operation:
- records a win
- awards persistent credits
- awards XP
- awards score
- increases the in-run operation streak
- rolls a harder follow-up operation without ending the run

### Deeper roguelite builds
Combat perk drafts are expanded with behavioural upgrades, not only stat bumps.

Examples:
- Blood Circuit: heal on kill
- Dash Feed: dash reloads part of the magazine
- Adrenal Core: bonus damage at low health
- Execution Cache: kills generate reserve ammo
- Necro Siphon: infected kills restore health
- Scrap Plating: infected kills restore armor
- Void Siphon: space kills restore shield
- Reactor Feed: space kills restore energy

Perk cards can now be selected with the mouse or `Z / X / C`.

### Persistent rewards
- Game-over run payouts now grant credits.
- Achievement rewards grant credits and XP.
- Fortune upgrades increase operation, contract and payout credit rewards.
- Level-up credit rewards are tracked through the same economy API.

### Camera ownership
V4 introduces a dedicated CameraDirector.
- Shared FOV is applied after mode simulation.
- Camera roll no longer accumulates frame over frame.
- Roll returns smoothly to neutral.
- ADS, nitro, dash and velocity still influence FOV.

### Adaptive difficulty fix
V3 could permanently ratchet some player max-speed / fire-rate values upward in a run.
V4 removes those one-way mutations. Adaptive difficulty now adjusts reversible encounter pressure and future spawn scaling.

### Compact procedural content
`content_catalog.py` was previously hundreds of kilobytes of generated literal rows.

V4 replaces it with deterministic procedural generators for:
- weapons
- enemy profiles
- traffic profiles
- zombie profiles
- runner patterns
- space formations
- Neon Ops arenas

The result is:
- far smaller source
- faster imports
- easier balancing
- effectively unlimited deterministic variation
- less merge noise
- no line-count inflation pretending to be content depth

### Save reliability
- schema version 4
- merge-based backwards migration
- atomic temporary-file writes
- numeric sanitization
- invalid save recovery
- tracked save errors
- guarded credit spending

### Automated validation
V4 validation now requires:
- progression system
- mission system
- camera director
- run modifier system
- all V3 simulation modules
- V4 setting tokens
- compact content catalog size budget
- secret scan

New tests cover:
- V3 save migration to V4
- credit spending
- upgrade rank clamping
- deterministic content generation
- content scaling
- operation definitions and scaling

## What V4 intentionally does not fake

V4 does not claim that procedural box characters equal professional AAA art.

The next visual milestone should use authored `.glb` assets with:
- skeletal rigs
- animation clips
- high-quality weapon models
- vehicle meshes
- authored environment props
- PBR texture sets
- sound libraries

The code foundation is ready for that, but the actual art assets must exist before the project can truthfully be rated like a modern AAA presentation.
