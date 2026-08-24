from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import List, Optional

from panda3d.core import NodePath, TransparencyAttrib, Vec3

from ..math3d import yaw_pitch_forward
from ..primitives import make_box, make_octahedron


@dataclass
class TimedNode:
    node: NodePath
    age: float = 999.0
    lifetime: float = 0.1


@dataclass
class SkidMark:
    node: NodePath
    age: float = 999.0
    lifetime: float = 2.8


class SurfaceFeedbackDirector:
    """Pooled transient geometry for actions that should leave visual evidence."""

    def __init__(self, app) -> None:
        self.app = app
        self.mode_identity: Optional[int] = None
        self.root: Optional[NodePath] = None
        self.tracers: List[TimedNode] = []
        self.impacts: List[TimedNode] = []
        self.skids: List[SkidMark] = []
        self.tracer_cursor = 0
        self.impact_cursor = 0
        self.skid_cursor = 0
        self.last_ammo: Optional[int] = None
        self.last_weapon_name = ""
        self.last_grounded = True
        self.skid_timer = 0.0
        self.rng = random.Random(0x53555246414345)

    def reset(self) -> None:
        if self.root is not None and not self.root.isEmpty():
            self.root.removeNode()
        self.root = None
        self.mode_identity = None
        self.tracers.clear()
        self.impacts.clear()
        self.skids.clear()
        self.tracer_cursor = 0
        self.impact_cursor = 0
        self.skid_cursor = 0
        self.last_ammo = None
        self.last_weapon_name = ""
        self.last_grounded = True
        self.skid_timer = 0.0

    def destroy(self) -> None:
        self.reset()

    def update(self, dt: float, mode) -> None:
        if mode is None or not getattr(mode, "active", False):
            return
        if id(mode) != self.mode_identity:
            self._attach(mode)
        self._update_nodes(dt, mode)
        game_id = str(getattr(mode, "game_id", ""))
        if game_id == "neon_ops":
            self._update_neon(mode)
        elif game_id == "zombie_siege":
            self._update_zombie(mode)
        elif game_id == "street_rush":
            self._update_street(dt, mode)
        elif game_id == "cyber_runner":
            self._update_runner(mode)
        elif game_id == "orbital_wars":
            self._update_space(dt, mode)

    def _attach(self, mode) -> None:
        self.reset()
        self.mode_identity = id(mode)
        parent = getattr(mode, "fx_root", mode.root)
        self.root = parent.attachNewNode("surface-feedback")
        for index in range(36):
            node = make_box(f"tracer-{index}",(0.018,1.0,0.018),(0.75,0.95,1.0,0.84),self.root)
            node.setTransparency(TransparencyAttrib.MAlpha)
            node.setLightOff(10)
            node.hide()
            self.tracers.append(TimedNode(node=node, lifetime=0.07))
        for index in range(48):
            node = make_octahedron(f"impact-{index}",0.055,(0.82,0.90,1.0,0.88),self.root)
            node.setTransparency(TransparencyAttrib.MAlpha)
            node.setLightOff(8)
            node.hide()
            self.impacts.append(TimedNode(node=node, lifetime=1.25))
        for index in range(72):
            node = make_box(f"skid-{index}",(0.24,1.15,0.018),(0.008,0.008,0.010,0.72),self.root)
            node.setTransparency(TransparencyAttrib.MAlpha)
            node.setLightOff(5)
            node.hide()
            self.skids.append(SkidMark(node=node, lifetime=3.2))
        self.last_ammo = self._ammo_value(mode)
        self.last_weapon_name = str(getattr(mode, "weapon_name", ""))
        self.last_grounded = bool(getattr(mode, "grounded", True))

    def _update_nodes(self, dt: float, mode) -> None:
        for item in self.tracers:
            if item.age >= item.lifetime:
                continue
            item.age += dt
            if item.age >= item.lifetime:
                item.node.hide()
            else:
                item.node.setColorScale(1.0,1.0,1.0,max(0.0,1.0-item.age/item.lifetime))
        for item in self.impacts:
            if item.age >= item.lifetime:
                continue
            item.age += dt
            if item.age >= item.lifetime:
                item.node.hide()
            else:
                t = item.age / item.lifetime
                item.node.setScale(1.0 + t * 1.8)
                item.node.setColorScale(1.0,0.90,0.70,max(0.0,1.0-t))
        scroll = float(getattr(mode,"speed",0.0))*dt if str(getattr(mode,"game_id","")) == "street_rush" else 0.0
        for item in self.skids:
            if item.age >= item.lifetime:
                continue
            item.age += dt
            if scroll:
                item.node.setY(item.node.getY()-scroll)
            if item.age >= item.lifetime or item.node.getY() < -45.0:
                item.node.hide()
                item.age = item.lifetime
            else:
                item.node.setColorScale(1.0,1.0,1.0,max(0.0,0.72*(1.0-item.age/item.lifetime)))

    def _update_neon(self, mode) -> None:
        ammo = self._ammo_value(mode)
        if ammo is None:
            return
        weapon_name = str(getattr(mode, "weapon_name", ""))
        if weapon_name != self.last_weapon_name:
            self.last_weapon_name = weapon_name
            self.last_ammo = ammo
            return
        if self.last_ammo is not None and ammo < self.last_ammo:
            origin = mode.camera.getPos(mode.root)
            direction = yaw_pitch_forward(float(getattr(mode,"yaw",0.0)),float(getattr(mode,"pitch",0.0)))
            hit = self._ray_world(mode, origin, direction, 92.0)
            end = hit if hit is not None else origin + direction * 78.0
            self._spawn_tracer(origin, end, (0.55,0.95,1.0,0.86))
            if hit is not None:
                self._spawn_impact(hit, (0.75,0.92,1.0,0.90))
                try:
                    mode.particles.sparks(hit,(0.55,0.90,1.0,1.0),4)
                except Exception:
                    pass
        self.last_ammo = ammo

    def _update_zombie(self, mode) -> None:
        ammo = self._ammo_value(mode)
        if ammo is None:
            return
        if self.last_ammo is not None and ammo < self.last_ammo:
            origin = Vec3(getattr(mode,"player_pos",Vec3(0))) + Vec3(0,0,1.25)
            heading = math.radians(float(getattr(mode,"player_heading",0.0)))
            base = Vec3(math.sin(heading),math.cos(heading),0.02)
            for pellet in range(5):
                spread = (pellet-2)*0.026 + self.rng.uniform(-0.008,0.008)
                direction = Vec3(base.x+spread,base.y,base.z+self.rng.uniform(-0.015,0.03))
                direction.normalize()
                hit = self._ray_world(mode,origin,direction,32.0)
                end = hit if hit is not None else origin + direction * 24.0
                self._spawn_tracer(origin,end,(1.0,0.72,0.28,0.62),lifetime=0.055)
                if hit is not None and pellet % 2 == 0:
                    self._spawn_impact(hit,(1.0,0.62,0.22,0.82))
        self.last_ammo = ammo

    def _update_street(self, dt: float, mode) -> None:
        key = getattr(mode,"key",None)
        if key is None:
            return
        speed = float(getattr(mode,"speed",0.0))
        steer = float(getattr(mode,"steer",0.0))
        handbrake = bool(key["space"] and speed > 30.0 and abs(steer) > 0.12)
        self.skid_timer = max(0.0,self.skid_timer-dt)
        if handbrake and self.skid_timer <= 0.0:
            self.skid_timer = 0.075
            x = float(getattr(mode,"player_x",0.0))
            for wheel_x in (-0.78,0.78):
                self._spawn_skid(Vec3(x+wheel_x,-1.15,0.03),steer)
            try:
                mode.particles.burst(Vec3(x,-1.6,0.28),(0.55,0.58,0.62,0.52),count=3,speed=1.7,lifetime=0.55,size=0.07,gravity=-0.15)
            except Exception:
                pass

    def _update_runner(self, mode) -> None:
        grounded = bool(getattr(mode,"grounded",True))
        if grounded and not self.last_grounded:
            pos = Vec3(getattr(mode,"player_pos",Vec3(0)))
            try:
                mode.particles.burst(pos+Vec3(0,0,-0.65),(0.85,0.42,0.12,0.55),count=8,speed=2.6,lifetime=0.45,size=0.045,gravity=1.6)
            except Exception:
                pass
        self.last_grounded = grounded

    def _update_space(self, dt: float, mode) -> None:
        key = getattr(mode,"key",None)
        if key is None or not key["shift"]:
            return
        if self.rng.random() > min(1.0,dt*24.0):
            return
        pos = Vec3(getattr(mode,"player_pos",Vec3(0))) + Vec3(0,-1.5,0)
        try:
            mode.particles.burst(pos,(0.15,0.75,1.0,0.62),count=2,speed=2.0,lifetime=0.35,size=0.035,gravity=0.0)
        except Exception:
            pass

    def _spawn_tracer(self, origin: Vec3, end: Vec3, color, lifetime: float = 0.07) -> None:
        if not self.tracers:
            return
        item = self.tracers[self.tracer_cursor % len(self.tracers)]
        self.tracer_cursor += 1
        vector = Vec3(end-origin)
        length = max(0.05,vector.length())
        midpoint = origin + vector * 0.5
        item.node.show()
        item.node.clearColorScale()
        item.node.setColor(*color)
        item.node.setPos(midpoint)
        try:
            item.node.lookAt(end)
        except Exception:
            pass
        item.node.setScale(1.0,length,1.0)
        item.age = 0.0
        item.lifetime = lifetime

    def _spawn_impact(self, pos: Vec3, color) -> None:
        if not self.impacts:
            return
        item = self.impacts[self.impact_cursor % len(self.impacts)]
        self.impact_cursor += 1
        item.node.show()
        item.node.setPos(pos)
        item.node.setScale(1.0)
        item.node.setColor(*color)
        item.node.clearColorScale()
        item.age = 0.0
        item.lifetime = self.rng.uniform(0.9,1.6)

    def _spawn_skid(self, pos: Vec3, steer: float) -> None:
        if not self.skids:
            return
        item = self.skids[self.skid_cursor % len(self.skids)]
        self.skid_cursor += 1
        item.node.show()
        item.node.setPos(pos)
        item.node.setH(-float(steer)*7.0)
        item.node.clearColorScale()
        item.age = 0.0
        item.lifetime = self.rng.uniform(2.4,3.5)

    @staticmethod
    def _ammo_value(mode) -> Optional[int]:
        try:
            return int(mode.ammo)
        except Exception:
            return None

    @staticmethod
    def _ray_world(mode, origin: Vec3, direction: Vec3, max_distance: float) -> Optional[Vec3]:
        direction = Vec3(direction)
        if direction.lengthSquared() < 0.00001:
            return None
        direction.normalize()
        best_t = max_distance + 1.0
        for collider in list(getattr(mode,"colliders",[]) or [])[:180]:
            if str(getattr(collider,"tag","solid")) != "solid":
                continue
            center = Vec3(collider.center)
            half = Vec3(collider.half)
            t_min,t_max,valid = 0.0,max_distance,True
            for axis in range(3):
                s,d = origin[axis],direction[axis]
                lo,hi = center[axis]-half[axis],center[axis]+half[axis]
                if abs(d) < 1e-8:
                    if s < lo or s > hi:
                        valid = False
                        break
                    continue
                inv = 1.0/d
                t1,t2 = (lo-s)*inv,(hi-s)*inv
                if t1 > t2:
                    t1,t2 = t2,t1
                t_min,t_max = max(t_min,t1),min(t_max,t2)
                if t_min > t_max:
                    valid = False
                    break
            if valid and 0.0 <= t_min < best_t and t_min <= max_distance:
                best_t = t_min
        return origin + direction * best_t if best_t <= max_distance else None
