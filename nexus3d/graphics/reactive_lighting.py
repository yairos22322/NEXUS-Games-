from __future__ import annotations

import math
from typing import Optional

from panda3d.core import PointLight, Vec3, Vec4


class ReactiveLighting:
    """Short-lived dynamic lights driven by gameplay state.

    The effect intentionally uses only two reusable lights.  No lights are
    created inside the frame loop, which avoids hitching and prevents runaway
    light counts on long sessions.
    """

    def __init__(self, app) -> None:
        self.app = app
        self.weapon_flash = 0.0
        self.movement_glow = 0.0
        self._last_mode_id = ""
        self._last_ammo: Optional[int] = None
        self._shot_light_node = self._make_light(
            "reactive-shot-light",
            (1.0, 0.72, 0.42, 1.0),
            (1.0, 0.10, 0.025),
        )
        self._move_light_node = self._make_light(
            "reactive-movement-light",
            (0.08, 0.58, 1.0, 1.0),
            (1.0, 0.08, 0.018),
        )
        self._shot_light_node.reparentTo(app.camera)
        self._shot_light_node.setPos(0.4, 1.7, -0.2)
        self._move_light_node.reparentTo(app.camera)
        self._move_light_node.setPos(0.0, -1.2, -0.2)
        app.render.setLight(self._shot_light_node)
        app.render.setLight(self._move_light_node)
        self._set_light(self._shot_light_node, (0, 0, 0, 1))
        self._set_light(self._move_light_node, (0, 0, 0, 1))

    def _make_light(self, name: str, color, attenuation):
        light = PointLight(name)
        light.setColor(Vec4(*color))
        light.setAttenuation(Vec3(*attenuation))
        return self.app.render.attachNewNode(light)

    @staticmethod
    def _set_light(node, color) -> None:
        try:
            node.node().setColor(Vec4(*color))
        except Exception:
            pass

    def update(self, dt: float, mode) -> None:
        dt = max(0.0, min(0.1, dt))
        if mode is None or not getattr(mode, "active", False):
            self._last_mode_id = ""
            self._last_ammo = None
            self.weapon_flash = max(0.0, self.weapon_flash - dt * 18.0)
            self.movement_glow = max(0.0, self.movement_glow - dt * 8.0)
            self._apply("", 0.0)
            return

        game_id = str(getattr(mode, "game_id", ""))
        if game_id != self._last_mode_id:
            self._last_mode_id = game_id
            self._last_ammo = self._read_ammo(mode)
            self.weapon_flash = 0.0
            self.movement_glow = 0.0

        ammo = self._read_ammo(mode)
        if ammo is not None and self._last_ammo is not None and ammo < self._last_ammo:
            # Any ammunition decrease is a reliable shot signal across FPS and
            # survival modes without coupling this system to their weapon code.
            self.weapon_flash = 1.0
        self._last_ammo = ammo

        muzzle_timer = float(getattr(mode, "muzzle_timer", 0.0) or 0.0)
        if muzzle_timer > 0.0:
            self.weapon_flash = max(self.weapon_flash, min(1.0, muzzle_timer * 18.0))

        movement_target = 0.0
        if bool(getattr(mode, "nitro_active", False)):
            movement_target = 1.0
        elif float(getattr(mode, "dash_timer", 0.0) or 0.0) > 0.0:
            movement_target = 0.75
        elif bool(getattr(mode, "boosting", False)):
            movement_target = 0.9

        self.weapon_flash = max(0.0, self.weapon_flash - dt * 13.0)
        smoothing = 1.0 - math.exp(-dt * 12.0)
        self.movement_glow += (movement_target - self.movement_glow) * smoothing
        self._apply(game_id, self.weapon_flash)

    @staticmethod
    def _read_ammo(mode) -> Optional[int]:
        for name in ("ammo", "magazine", "current_ammo"):
            value = getattr(mode, name, None)
            if isinstance(value, int):
                return value
        return None

    def _apply(self, game_id: str, flash: float) -> None:
        if flash > 0.001:
            if game_id == "neon_ops":
                base = (0.62, 0.86, 1.0)
            elif game_id == "zombie_siege":
                base = (1.0, 0.62, 0.28)
            elif game_id == "orbital_wars":
                base = (0.25, 0.72, 1.0)
            else:
                base = (1.0, 0.76, 0.42)
            intensity = flash * flash * 2.4
            self._set_light(
                self._shot_light_node,
                (base[0] * intensity, base[1] * intensity, base[2] * intensity, 1.0),
            )
        else:
            self._set_light(self._shot_light_node, (0, 0, 0, 1))

        glow = self.movement_glow
        if glow > 0.001:
            if game_id == "street_rush":
                base = (0.72, 0.08, 1.0)
            elif game_id == "cyber_runner":
                base = (1.0, 0.34, 0.04)
            else:
                base = (0.05, 0.52, 1.0)
            intensity = glow * 1.65
            self._set_light(
                self._move_light_node,
                (base[0] * intensity, base[1] * intensity, base[2] * intensity, 1.0),
            )
        else:
            self._set_light(self._move_light_node, (0, 0, 0, 1))

    def destroy(self) -> None:
        for node in (self._shot_light_node, self._move_light_node):
            if node is not None and not node.isEmpty():
                try:
                    self.app.render.clearLight(node)
                except Exception:
                    pass
                node.removeNode()
