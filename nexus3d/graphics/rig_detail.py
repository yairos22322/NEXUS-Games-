from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Dict, Optional

from panda3d.core import NodePath, TransparencyAttrib, Vec3

from ..primitives import make_box, make_octahedron, make_ring


Color = tuple[float, float, float, float]


@dataclass
class DetailRecord:
    root: NodePath
    kind: str
    glow_nodes: list[NodePath]
    phase: float = 0.0


class RigDetailDirector:
    """Adds a second visual-detail pass to procedural gameplay rigs.

    The project intentionally ships without external character/car model packs.
    This system improves the close-range silhouettes of the existing rigs by
    attaching reusable procedural details exactly once per actor. It does not
    replace proper authored GLB assets, but it makes the current geometry read
    much less like raw boxes while remaining self-contained.
    """

    def __init__(self, app) -> None:
        self.app = app
        self.records: Dict[int, DetailRecord] = {}
        self._scan_timer = 0.0
        self._weapon_roots: set[int] = set()

    def reset(self) -> None:
        # Decorations live under mode-owned rigs and are destroyed with them.
        self.records.clear()
        self._weapon_roots.clear()
        self._scan_timer = 0.0

    def update(self, dt: float, mode) -> None:
        if dt <= 0.0 or mode is None or not getattr(mode, "active", False):
            return
        self._scan_timer -= dt
        if self._scan_timer <= 0.0:
            self._scan_timer = 0.22
            self._scan(mode)
        self._animate(dt, mode)

    def _scan(self, mode) -> None:
        game_id = str(getattr(mode, "game_id", ""))
        player = getattr(mode, "player", None)
        if player is not None:
            self._decorate_rig(player, game_id, None, player_owned=True)

        for group_name in ("enemies", "zombies", "traffic"):
            for actor in list(getattr(mode, group_name, []) or [])[:80]:
                rig = getattr(actor, "rig", None)
                if rig is not None:
                    self._decorate_rig(rig, game_id, actor, player_owned=False)

        if hasattr(mode, "weapon_root"):
            weapon_root = mode.weapon_root
            if weapon_root is not None and not weapon_root.isEmpty() and id(weapon_root) not in self._weapon_roots:
                self._decorate_fps_weapon(mode)
                self._weapon_roots.add(id(weapon_root))

    def _decorate_rig(self, rig, game_id: str, actor, player_owned: bool) -> None:
        root = getattr(rig, "root", None)
        if root is None or root.isEmpty():
            return
        key = id(root)
        if key in self.records:
            return

        if hasattr(rig, "chassis") and hasattr(rig, "wheels"):
            record = self._decorate_vehicle(rig, game_id, player_owned)
        elif hasattr(rig, "left_wing") and hasattr(rig, "engine_glow_left"):
            record = self._decorate_ship(rig, actor, player_owned)
        elif hasattr(rig, "body") and hasattr(rig, "head"):
            record = self._decorate_character(rig, game_id, actor, player_owned)
        else:
            return
        self.records[key] = record

    def _decorate_character(self, rig, game_id: str, actor, player_owned: bool) -> DetailRecord:
        root = rig.root.attachNewNode("runtime-character-detail")
        glows: list[NodePath] = []
        is_zombie = game_id == "zombie_siege"
        elite = bool(getattr(actor, "elite", False)) if actor is not None else False

        if is_zombie:
            make_box("torn-shoulder-l", (0.34, 0.34, 0.22), (0.18,0.08,0.05,1), root, (-0.49,0.01,1.48), (10,18,22))
            make_box("torn-shoulder-r", (0.28, 0.30, 0.18), (0.12,0.15,0.07,1), root, (0.50,-0.02,1.39), (-12,-9,-18))
            wound = make_box("infected-glow", (0.18,0.05,0.30), (0.20,0.90,0.20,0.60), root, (0,-0.245,1.40))
            wound.setTransparency(TransparencyAttrib.MAlpha)
            self._emissive(wound, (0.18, 0.8, 0.18, 0.7))
            glows.append(wound)
            make_box("jaw-shadow", (0.31,0.46,0.10), (0.20,0.17,0.14,1), root, (0,-0.02,1.82), (0,8,0))
        else:
            helmet_color = (0.035,0.045,0.065,1) if not elite else (0.10,0.055,0.025,1)
            make_box("helmet", (0.56,0.50,0.28), helmet_color, root, (0,0,2.19), (0,-4,0))
            visor_color = (0.03,0.72,0.95,0.72) if not elite else (1.0,0.30,0.04,0.78)
            visor = make_box("visor", (0.42,0.055,0.13), visor_color, root, (0,-0.245,2.15), (0,-4,0))
            visor.setTransparency(TransparencyAttrib.MAlpha)
            self._emissive(visor, visor_color)
            glows.append(visor)
            shoulder = (0.08,0.10,0.14,1) if not elite else (0.18,0.08,0.035,1)
            make_box("pauldron-l", (0.34,0.50,0.22), shoulder, root, (-0.52,0,1.58), (0,0,-7))
            make_box("pauldron-r", (0.34,0.50,0.22), shoulder, root, (0.52,0,1.58), (0,0,7))
            make_box("chest-plate", (0.60,0.055,0.39), shoulder, root, (0,-0.275,1.39), (0,4,0))
            chest_light = make_box("chest-light", (0.22,0.035,0.035), visor_color, root, (0,-0.315,1.45))
            self._emissive(chest_light, visor_color)
            glows.append(chest_light)
            make_box("belt", (0.70,0.52,0.12), (0.025,0.028,0.035,1), root, (0,0,0.89))
            make_box("boot-l", (0.34,0.42,0.24), (0.025,0.028,0.035,1), root, (-0.22,-0.01,0.10))
            make_box("boot-r", (0.34,0.42,0.24), (0.025,0.028,0.035,1), root, (0.22,-0.01,0.10))

        # Weapon attachments improve silhouette for armed NPCs while respecting
        # modes that hide the base weapon node (zombies/runner).
        try:
            if not rig.weapon.isHidden():
                make_box("weapon-stock", (0.20,0.35,0.22), (0.025,0.03,0.04,1), root, (0.46,-0.18,1.36), (0,0,-8))
                sight = make_box("weapon-sight", (0.12,0.18,0.12), (0.05,0.08,0.10,1), root, (0.46,0.52,1.50), (0,0,-8))
                dot = make_box("weapon-dot", (0.035,0.03,0.035), (0.08,0.85,1.0,0.9), sight, (0,-0.10,0.05))
                self._emissive(dot, (0.08,0.85,1.0,0.9))
                glows.append(dot)
        except Exception:
            pass

        return DetailRecord(root=root, kind="character", glow_nodes=glows, phase=float(len(self.records)) * 0.37)

    def _decorate_vehicle(self, rig, game_id: str, player_owned: bool) -> DetailRecord:
        root = rig.root.attachNewNode("runtime-vehicle-detail")
        glows: list[NodePath] = []
        accent: Color = (1.0,0.12,0.65,0.9) if player_owned else (0.18,0.65,1.0,0.82)

        make_box("front-splitter", (1.55,0.28,0.10), (0.018,0.02,0.025,1), root, (0,2.04,0.35))
        make_box("rear-diffuser", (1.42,0.30,0.14), (0.012,0.014,0.018,1), root, (0,-2.05,0.35), (0,8,0))
        make_box("side-skirt-l", (0.10,2.65,0.12), (0.025,0.028,0.034,1), root, (-0.90,0,0.34))
        make_box("side-skirt-r", (0.10,2.65,0.12), (0.025,0.028,0.034,1), root, (0.90,0,0.34))
        make_box("mirror-l", (0.22,0.25,0.16), (0.05,0.06,0.075,1), root, (-0.96,0.52,1.20))
        make_box("mirror-r", (0.22,0.25,0.16), (0.05,0.06,0.075,1), root, (0.96,0.52,1.20))
        make_box("hood-crease", (0.10,1.12,0.035), accent, root, (0,0.92,1.00), (0,-6,0))

        for x in (-0.54, 0.54):
            tail = make_box("tail-light", (0.34,0.055,0.14), (1.0,0.04,0.03,0.82), root, (x,-2.08,0.70))
            self._emissive(tail, (1.0,0.035,0.025,0.9))
            glows.append(tail)
            exhaust = make_box("exhaust", (0.16,0.28,0.16), (0.035,0.04,0.045,1), root, (x*0.72,-2.10,0.30))
            exhaust.setP(90)

        underglow = make_box("underglow", (1.52,2.75,0.025), accent, root, (0,-0.12,0.17))
        underglow.setTransparency(TransparencyAttrib.MAlpha)
        self._emissive(underglow, accent)
        glows.append(underglow)
        return DetailRecord(root=root, kind="vehicle", glow_nodes=glows, phase=float(len(self.records)) * 0.23)

    def _decorate_ship(self, rig, actor, player_owned: bool) -> DetailRecord:
        root = rig.root.attachNewNode("runtime-ship-detail")
        glows: list[NodePath] = []
        kind = str(getattr(actor, "kind", "player" if player_owned else "fighter")) if actor is not None else "player"
        accent: Color = (0.05,0.85,1.0,0.95) if player_owned else (1.0,0.20,0.50,0.85)
        if kind == "capital":
            accent = (1.0,0.12,0.06,0.9)

        make_box("dorsal-fin", (0.16,1.25,0.72), (0.055,0.065,0.09,1), root, (0,-0.38,0.55), (0,-12,0))
        for side in (-1, 1):
            make_box("wing-tip", (0.24,0.72,0.22), (0.05,0.06,0.08,1), root, (side*2.02,-0.25,0))
            pod = make_box("weapon-pod", (0.24,0.65,0.24), (0.035,0.042,0.06,1), root, (side*1.18,0.34,-0.12))
            light = make_box("pod-light", (0.08,0.08,0.08), accent, pod, (0,0.36,0))
            self._emissive(light, accent)
            glows.append(light)
            tip = make_box("nav-light", (0.08,0.12,0.08), accent, root, (side*2.18,-0.25,0.02))
            self._emissive(tip, accent)
            glows.append(tip)

        cockpit_frame = make_ring("cockpit-frame", 0.40, 0.48, 24, accent, root)
        cockpit_frame.setPos(0,0.58,0.45)
        cockpit_frame.setP(90)
        cockpit_frame.setScale(1.0,1.25,0.72)
        self._emissive(cockpit_frame, accent)
        glows.append(cockpit_frame)
        return DetailRecord(root=root, kind="ship", glow_nodes=glows, phase=float(len(self.records)) * 0.31)

    def _decorate_fps_weapon(self, mode) -> None:
        root = mode.weapon_root.attachNewNode("runtime-fps-weapon-detail")
        make_box("receiver-rail", (0.12,0.72,0.05), (0.025,0.03,0.04,1), root, (0.40,1.02,-0.20))
        make_box("foregrip", (0.10,0.20,0.32), (0.035,0.04,0.05,1), root, (0.39,1.26,-0.46), (0,0,6))
        sight = make_box("holo-frame", (0.20,0.16,0.18), (0.04,0.05,0.065,1), root, (0.40,0.78,-0.14))
        lens = make_box("holo-lens", (0.13,0.025,0.10), (0.04,0.72,0.92,0.48), sight, (0,-0.09,0.02))
        lens.setTransparency(TransparencyAttrib.MAlpha)
        self._emissive(lens, (0.04,0.72,0.92,0.65))
        make_box("magazine", (0.18,0.34,0.36), (0.03,0.035,0.045,1), root, (0.40,0.48,-0.47), (0,0,-8))
        make_box("stock", (0.20,0.42,0.23), (0.025,0.03,0.04,1), root, (0.40,0.16,-0.34), (0,0,-5))

    def _animate(self, dt: float, mode) -> None:
        stale = []
        game_id = str(getattr(mode, "game_id", ""))
        braking = bool(getattr(mode, "key", None) and mode.key["s"]) if game_id == "street_rush" else False
        nitro = bool(getattr(mode, "nitro_active", False))

        for key, record in self.records.items():
            if record.root.isEmpty():
                stale.append(key)
                continue
            record.phase += dt
            pulse = 0.82 + math.sin(record.phase * 3.1) * 0.10
            for index, glow in enumerate(record.glow_nodes):
                if glow.isEmpty():
                    continue
                alpha = pulse
                if record.kind == "vehicle":
                    if index < 2 and braking:
                        alpha = 1.25
                    elif nitro:
                        alpha = min(1.25, pulse + 0.25)
                try:
                    glow.setAlphaScale(max(0.25, alpha))
                except Exception:
                    pass
        for key in stale:
            self.records.pop(key, None)

    def _emissive(self, node: NodePath, color: Color) -> None:
        try:
            self.app.graphics.apply_surface(node, "emissive", color)
        except Exception:
            node.setLightOff(5)
