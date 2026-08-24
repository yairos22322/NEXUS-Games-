from __future__ import annotations

import math
import random
from typing import Optional


class CombatFeelDirector:
    """First-person weapon presentation layered onto Neon Ops.

    The base mode owns hits, ammo and damage. This system reads that state and
    adds ADS, recoil, weapon kick, sprint lowering and reload presentation while
    feeding a temporary spread modifier back into the existing shot calculation.
    """

    def __init__(self) -> None:
        self._mode_id: Optional[int] = None
        self._base_spread = 0.0
        self._last_ammo: Optional[int] = None
        self._shot_index = 0
        self._recoil_pitch = 0.0
        self._recoil_yaw = 0.0
        self._kick = 0.0
        self._ads = 0.0
        self._pose_x = 0.0
        self._pose_y = 0.0
        self._pose_z = 0.0
        self._pose_p = 0.0
        self._rng = random.Random(0x5245434F494C)

    def reset(self) -> None:
        self._mode_id = None
        self._base_spread = 0.0
        self._last_ammo = None
        self._shot_index = 0
        self._recoil_pitch = 0.0
        self._recoil_yaw = 0.0
        self._kick = 0.0
        self._ads = 0.0
        self._pose_x = 0.0
        self._pose_y = 0.0
        self._pose_z = 0.0
        self._pose_p = 0.0

    def update(self, dt: float, mode) -> None:
        if dt <= 0.0 or str(getattr(mode, "game_id", "")) != "neon_ops":
            return
        if not hasattr(mode, "weapon_root") or mode.weapon_root.isEmpty():
            return

        if self._mode_id != id(mode):
            self._mode_id = id(mode)
            self._base_spread = max(0.0001, float(getattr(mode, "weapon_spread", 0.018)))
            self._last_ammo = int(getattr(mode, "ammo", 0))
            self._shot_index = 0

        paused = bool(getattr(mode, "paused", False) or getattr(mode, "game_over", False))
        key = getattr(mode, "key", None)
        sprinting = bool(key and key["shift"] and key["w"] and not getattr(mode, "reloading", False))
        ads_requested = bool(key and key["mouse3"] and not sprinting and not getattr(mode, "reloading", False) and not paused)
        ads_target = 1.0 if ads_requested else 0.0
        self._ads = self._smooth(self._ads, ads_target, 14.0 if ads_target > self._ads else 10.0, dt)
        mode.ads_active = self._ads > 0.55
        mode.ads_amount = self._ads

        ammo = int(getattr(mode, "ammo", 0))
        if self._last_ammo is not None and ammo < self._last_ammo and not getattr(mode, "reloading", False):
            shots = max(1, self._last_ammo - ammo)
            for _ in range(min(4, shots)):
                self._on_shot(mode)
        self._last_ammo = ammo

        # Recoil returns to centre in two stages: the sharp weapon kick decays
        # quickly, while camera recoil settles slightly slower.
        recovery = 13.5 if self._ads > 0.5 else 10.5
        self._recoil_pitch = self._smooth(self._recoil_pitch, 0.0, recovery, dt)
        self._recoil_yaw = self._smooth(self._recoil_yaw, 0.0, recovery * 1.2, dt)
        self._kick = self._smooth(self._kick, 0.0, 18.0, dt)

        # ADS meaningfully tightens the existing hitscan spread. Sustained fire
        # opens it back up, so holding the trigger is less accurate than bursts.
        recoil_bloom = min(1.0, abs(self._recoil_pitch) * 0.08 + self._kick * 0.55)
        ads_multiplier = 1.0 - self._ads * 0.58
        mode.weapon_spread = self._base_spread * ads_multiplier * (1.0 + recoil_bloom * 0.48)

        self._update_weapon_pose(dt, mode, sprinting)

    def _on_shot(self, mode) -> None:
        self._shot_index += 1
        pattern = self._shot_index
        ads_control = 1.0 - self._ads * 0.34
        vertical = (0.24 + min(0.34, pattern * 0.012)) * ads_control
        horizontal = math.sin(pattern * 1.73) * 0.075 + self._rng.uniform(-0.035, 0.035)
        horizontal *= ads_control
        self._recoil_pitch = min(3.4, self._recoil_pitch + vertical)
        self._recoil_yaw = max(-1.6, min(1.6, self._recoil_yaw + horizontal))
        self._kick = min(1.0, self._kick + 0.44)

        # Feed recoil into the aim state used by the next frame. The on-screen
        # weapon also kicks independently, which makes recoil readable without
        # huge camera shake.
        try:
            mode.pitch = min(78.0, float(mode.pitch) + vertical * 0.62)
            mode.yaw += horizontal * 0.34
        except Exception:
            pass

    def _update_weapon_pose(self, dt: float, mode, sprinting: bool) -> None:
        reloading = bool(getattr(mode, "reloading", False))
        if reloading:
            reload_total = max(0.01, float(getattr(mode, "reload_time", 1.5)))
            remain = max(0.0, float(getattr(mode, "reload_timer", 0.0)))
            progress = 1.0 - min(1.0, remain / reload_total)
            arc = math.sin(progress * math.pi)
            target_x = 0.08
            target_y = -0.06
            target_z = -0.16 - arc * 0.13
            target_p = 18.0 + arc * 24.0
        elif sprinting:
            target_x = 0.13
            target_y = -0.10
            target_z = -0.22
            target_p = -14.0
        else:
            target_x = -0.385 * self._ads
            target_y = 0.16 * self._ads - self._kick * 0.09
            target_z = 0.255 * self._ads - self._kick * 0.045
            target_p = self._recoil_pitch * 1.8

        self._pose_x = self._smooth(self._pose_x, target_x, 15.0, dt)
        self._pose_y = self._smooth(self._pose_y, target_y, 15.0, dt)
        self._pose_z = self._smooth(self._pose_z, target_z, 14.0, dt)
        self._pose_p = self._smooth(self._pose_p, target_p, 17.0, dt)

        # The base mode writes a small bob into root Z before this update.
        # Preserve a fraction of that bob in hip fire and suppress it in ADS.
        try:
            existing_bob = float(mode.weapon_root.getZ())
        except Exception:
            existing_bob = 0.0
        bob = existing_bob * (1.0 - self._ads * 0.82)

        try:
            mode.weapon_root.setX(self._pose_x)
            mode.weapon_root.setY(self._pose_y)
            mode.weapon_root.setZ(self._pose_z + bob)
            mode.weapon_root.setP(self._pose_p)
            # Base mode owns roll for strafing. Add a small recoil yaw only.
            mode.weapon_root.setH(self._recoil_yaw * 2.4)
        except Exception:
            pass

    @staticmethod
    def _smooth(current: float, target: float, sharpness: float, dt: float) -> float:
        return current + (target - current) * (1.0 - math.exp(-max(0.0, sharpness) * max(0.0, dt)))
