from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from panda3d.core import Vec3


@dataclass
class LODState:
    visible: bool = True
    last_distance: float = 0.0


class RuntimeLODDirector:
    """Distance-based LOD for the secondary procedural detail pass.

    Base gameplay rigs never disappear. Only optional high-frequency detail
    geometry created by RigDetailDirector is culled at distance. Hysteresis
    prevents rapid show/hide flicker around the threshold.
    """

    BASE_DISTANCE = {
        "character": 38.0,
        "vehicle": 62.0,
        "ship": 100.0,
    }

    def __init__(self, app, rig_detail) -> None:
        self.app = app
        self.rig_detail = rig_detail
        self.states: Dict[int, LODState] = {}
        self.accumulator = 0.0
        self.mode_identity: Optional[int] = None

    def reset(self) -> None:
        for key, record in list(getattr(self.rig_detail, "records", {}).items()):
            try:
                if not record.root.isEmpty():
                    record.root.show()
            except Exception:
                pass
        self.states.clear()
        self.accumulator = 0.0
        self.mode_identity = None

    def update(self, dt: float, mode) -> None:
        if mode is None or not getattr(mode, "active", False):
            return
        if id(mode) != self.mode_identity:
            self.states.clear()
            self.mode_identity = id(mode)
        self.accumulator += max(0.0, dt)
        if self.accumulator < 0.16:
            return
        self.accumulator = 0.0

        try:
            camera_pos = self.app.camera.getPos(self.app.render)
        except Exception:
            return

        detail_factor = self._quality_factor()
        live: set[int] = set()
        records = getattr(self.rig_detail, "records", {})
        for key, record in list(records.items()):
            root = getattr(record, "root", None)
            if root is None or root.isEmpty():
                continue
            live.add(key)
            state = self.states.setdefault(key, LODState())
            try:
                position = root.getPos(self.app.render)
            except Exception:
                continue
            distance = (Vec3(position) - camera_pos).length()
            state.last_distance = distance
            base = self.BASE_DISTANCE.get(str(getattr(record, "kind", "character")), 42.0)
            hide_distance = base * detail_factor
            show_distance = hide_distance * 0.84

            if state.visible and distance > hide_distance:
                root.hide()
                state.visible = False
            elif not state.visible and distance < show_distance:
                root.show()
                state.visible = True

            # Emissive details remain useful slightly farther than geometry in
            # night scenes, but Panda's hide on the detail root wins once the
            # entire detail pass becomes visually irrelevant.
            if state.visible:
                glow_cutoff = hide_distance * 0.92
                for glow in getattr(record, "glow_nodes", []) or []:
                    if glow is None or glow.isEmpty():
                        continue
                    if distance > glow_cutoff:
                        glow.hide()
                    else:
                        glow.show()

        for key in list(self.states):
            if key not in live:
                self.states.pop(key, None)

    def _quality_factor(self) -> float:
        try:
            detail = int(self.app.graphics.quality.environment_detail)
        except Exception:
            detail = 3
        return {
            1: 0.64,
            2: 0.78,
            3: 0.92,
            4: 1.08,
            5: 1.22,
        }.get(detail, 0.92)
