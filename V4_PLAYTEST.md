# NEXUS V4 Playtest Checklist

## Global
- Launch an existing V3 save and confirm level, score and stats remain.
- From the main menu press `F2`.
- Buy a NEXUS Lab upgrade and verify credits decrease.
- Restart the game and verify the upgrade rank persists.
- Complete a run and verify a run payout is awarded once.
- Confirm the menu says `BUILD 04.00 LOCAL PROFILE`.
- Confirm no `ONLINE PROFILE` claim is visible.
- Complete an achievement and verify a toast appears once.

## Operations
For every game mode:
- Confirm a three-stage operation appears at the top of the HUD.
- Complete stage 1 and verify stage 2 starts from a fresh baseline.
- Complete all three stages.
- Confirm score, XP and credits are awarded.
- Confirm the mode's win counter increments.
- Confirm a follow-up operation appears after the completion delay.

## Neon Ops
- Switch between all three weapons.
- Verify NEXUS Lab Firepower affects weapon damage.
- Verify Handling affects reload time.
- Pick `BLOOD CIRCUIT` and verify kills restore health.
- Pick `DASH FEED`, empty part of a magazine, dash and verify rounds are restored.
- Pick `ADRENAL CORE`, drop below 35 HP and verify weapon damage increases.
- Select a perk by mouse.
- Select another perk with Z/X/C.
- Verify generated arenas remain navigable.

## Zombie Siege
- Pick `NECRO SIPHON` and verify infected kills restore health.
- Pick `SCRAP PLATING` and verify kills restore armor.
- Pick `SHELL FORGE` and verify kills generate reserve shells.
- Pick `LAST STAND` and verify low-health shotgun damage increases.

## Orbital Wars
- Pick `VOID SIPHON` and verify kills restore shields.
- Pick `REACTOR FEED` and verify kills restore energy.
- Verify persistent Firepower improves laser cadence without breaking energy use.

## Street Rush
- Confirm persistent Mobility makes handling slightly stronger.
- Verify adaptive difficulty can rise and later fall without permanently ratcheting max speed.

## Cyber Runner
- Confirm operation distance/flow/score stages progress.
- Confirm persistent Mobility is applied once per run, not repeatedly.

## Reliability
- Force-close during a session, relaunch and verify the JSON save remains valid.
- Corrupt a copy of the save and verify recovery creates a `.broken` backup.
- Run `python CHECK_PROJECT.py`.
- Run `python -m unittest discover -s tests -p "test_*.py" -v`.
