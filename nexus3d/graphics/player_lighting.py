from __future__ import annotations

import math
from typing import List, Optional

from panda3d.core import NodePath, PointLight, Vec3, Vec4


class PlayerLightingDirector:
    """A small budget of dynamic lights reserved for the local player."""

    def __init__(self, app) -> None:
        self.app = app
        self.mode_identity: Optional[int] = None
        self.root: Optional[NodePath] = None
        self.lights: List[NodePath] = []
        self.mode_root: Optional[NodePath] = None
        self.time = 0.0

    def reset(self) -> None:
        if self.mode_root is not None:
            for light in self.lights:
                try:
                    self.mode_root.clearLight(light)
                except Exception:
                    pass
        if self.root is not None and not self.root.isEmpty():
            self.root.removeNode()
        self.root = None
        self.lights.clear()
        self.mode_root = None
        self.mode_identity = None
        self.time = 0.0

    def destroy(self) -> None:
        self.reset()

    def update(self, dt: float, mode) -> None:
        if mode is None or not getattr(mode, "active", False):
            return
        if id(mode) != self.mode_identity:
            self._attach(mode)
        self.time += max(0.0, dt)
        game_id = str(getattr(mode, "game_id", ""))
        if game_id == "street_rush":
            self._street(mode)
        elif game_id == "neon_ops":
            self._neon(mode)
        elif game_id == "zombie_siege":
            self._zombie(mode)
        elif game_id == "orbital_wars":
            self._space(mode)
        elif game_id == "cyber_runner":
            self._runner(mode)

    def _attach(self, mode) -> None:
        self.reset()
        self.mode_identity = id(mode)
        self.mode_root = mode.root
        self.root = mode.root.attachNewNode("player-runtime-lighting")
        game_id = str(getattr(mode, "game_id", ""))
        if game_id == "street_rush":
            self._create_light("headlight-l", (1.00,0.88,0.62,1), (1.0,0.035,0.008))
            self._create_light("headlight-r", (1.00,0.88,0.62,1), (1.0,0.035,0.008))
            self._create_light("nitro-glow", (0.05,0.62,1.00,1), (1.0,0.06,0.018))
        elif game_id == "orbital_wars":
            self._create_light("engine-key", (0.08,0.70,1.00,1), (1.0,0.025,0.003))
            self._create_light("cockpit-key", (0.22,0.38,1.00,1), (1.0,0.045,0.009))
        elif game_id == "zombie_siege":
            self._create_light("survivor-lamp", (0.74,0.86,0.62,1), (1.0,0.055,0.016))
        elif game_id == "cyber_runner":
            self._create_light("runner-glow", (1.00,0.28,0.04,1), (1.0,0.08,0.025))
        else:
            self._create_light("weapon-fill", (0.55,0.82,1.00,1), (1.0,0.09,0.035))

    def _create_light(self, name: str, color, attenuation) -> NodePath:
        light = PointLight(name)
        light.setColor(Vec4(*color))
        light.setAttenuation(Vec3(*attenuation))
        node = self.root.attachNewNode(light)
        self.mode_root.setLight(node)
        self.lights.append(node)
        return node

    def _street(self, mode) -> None:
        if len(self.lights) < 3:
            return
        x = float(getattr(mode, "player_x", 0.0))
        self.lights[0].setPos(x - 0.58, 2.0, 0.78)
        self.lights[1].setPos(x + 0.58, 2.0, 0.78)
        self.lights[2].setPos(x, -1.75, 0.42)
        nitro = bool(getattr(mode, "nitro_active", False))
        intensity = 1.9 if nitro else 0.30
        self.lights[2].node().setColor(Vec4(0.04*intensity,0.38*intensity,0.70*intensity,1))
        braking = bool(getattr(mode, "key", None) and mode.key["s"])
        if braking:
            # Warm key lights soften during braking, allowing red tail geometry
            # to dominate without adding two more point lights.
            self.lights[0].node().setColor(Vec4(0.72,0.56,0.38,1))
            self.lights[1].node().setColor(Vec4(0.72,0.56,0.38,1))
        else:
            self.lights[0].node().setColor(Vec4(1.00,0.88,0.62,1))
            self.lights[1].node().setColor(Vec4(1.00,0.88,0.62,1))

    def _neon(self, mode) -> None:
        if not self.lights:
            return
        camera_pos = self.app.camera.getPos(mode.root)
        self.lights[0].setPos(camera_pos + Vec3(0, 1.3, -0.10))
        ads = float(getattr(mode, "ads_amount", 0.0) or 0.0)
        pulse = 0.78 + math.sin(self.time * 1.4) * 0.04
        self.lights[0].node().setColor(Vec4(0.36*pulse,0.60*pulse,0.78*pulse*(1.0+ads*0.12),1))

    def _zombie(self, mode) -> None:
        if not self.lights:
            return
        pos = Vec3(getattr(mode, "player_pos", Vec3(0)))
        self.lights[0].setPos(pos + Vec3(0,0,1.7))
        health = float(getattr(mode, "health", 100.0)) / 100.0
        flicker = 1.0
        if health < 0.30:
            flicker = 0.72 + (0.28 if math.sin(self.time*19.0)>-0.2 else 0.0)
        self.lights[0].node().setColor(Vec4(0.58*flicker,0.70*flicker,0.48*flicker,1))

    def _space(self, mode) -> None:
        if len(self.lights) < 2:
            return
        pos = Vec3(getattr(mode, "player_pos", Vec3(0)))
        self.lights[0].setPos(pos + Vec3(0,-1.4,0))
        self.lights[1].setPos(pos + Vec3(0,0.8,0.55))
        boosting = bool(getattr(mode, "key", None) and mode.key["shift"])
        boost = 2.0 if boosting else 1.0
        self.lights[0].node().setColor(Vec4(0.06*boost,0.48*boost,0.82*boost,1))

    def _runner(self, mode) -> None:
        if not self.lights:
            return
        pos = Vec3(getattr(mode, "player_pos", Vec3(0)))
        self.lights[0].setPos(pos + Vec3(0,0,0.6))
        dash = float(getattr(mode, "dash_timer", 0.0) or 0.0) > 0.0
        boost = 1.7 if dash else 0.82
        self.lights[0].node().setColor(Vec4(0.72*boost,0.18*boost,0.025*boost,1))
