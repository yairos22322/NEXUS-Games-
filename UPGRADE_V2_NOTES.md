# NEXUS FIVE 3D - Deep Gameplay Upgrade V2

This branch focuses on runtime behaviour instead of line-count inflation.

## Combat AI
- Line-of-sight checks against existing world colliders.
- Neon Ops enemies use assault, suppress, flank, hunt, retreat and cover roles.
- Hidden enemies have firing discipline and no longer intentionally fire through solid cover.
- Low-health non-elite units attempt to reach useful cover.
- Elite units reposition more aggressively.
- Zombie hordes receive orbit slots around the player instead of stacking in one point.
- Runners flank, brutes pressure the centre, and simultaneous melee attacks are token-limited for fairness.

## Driving
- Traffic follows slower vehicles instead of ghosting through them.
- AI can overtake into a clear lane and can yield around the player.
- Every traffic vehicle gets persistent aggression and preferred-speed traits.
- Player handbrake now has an inertial drift layer with body yaw/roll response.
- Controlled drifts can extend scoring flow.

## Space Combat
- Fighters use broad V formations.
- Interceptors orbit and evade incoming projectiles.
- Bombers perform slower attack runs.
- Capital ships hold a readable command position.
- Enemy ships react to nearby player projectiles.
- Player shield has delayed combat recharge to create attack/retreat rhythm.

## Parkour
- Coyote time.
- Jump buffering.
- Context-sensitive vault assist over low cover.
- Wall-run support at rooftop edges.
- Wall jump.
- Slide momentum conversion.
- Landing feedback and flow-energy rewards.

## Dynamic Difficulty
- The selected difficulty remains authoritative.
- A small runtime intensity multiplier reacts to score rate, damage rate and health.
- Pressure rises slowly on strong runs and falls faster when the player is struggling.
- Only future encounters/timers are adjusted, avoiding unfair mid-fight health changes.

## Graphics and Camera Feel
- Pooled 3D camera-space speed streaks.
- Per-mode accent colours.
- Dynamic boost vignette.
- Nitro, dash and boost increase visual speed feedback.
- Dynamic FOV remains shared across all five modes.
- Subtle camera lean reacts to steering and lateral movement.

## Safety
- No save format migration is required.
- New systems use capability detection and are isolated from each mode's scoring/damage ownership.
- New hot-path visual effects are pooled and allocate no nodes per frame.
