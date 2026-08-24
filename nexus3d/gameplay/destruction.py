from __future__ import annotations

from dataclasses import dataclass
import math
import random
from types import SimpleNamespace
from typing import List, Optional

from panda3d.core import NodePath, Vec3

from ..math3d import yaw_pitch_forward
from ..primitives import make_box


@dataclass
class DestructibleProp:
    node: NodePath
    collider: object
    health: float
    max_health: float
    position: Vec3
    half: Vec3
    kind: str
    alive: bool = True


class DestructibleWorldDirector:
    """Self-contained destruction layer for the two ground combat arenas."""

    def __init__(self) -> None:
        self.mode_identity: Optional[int] = None
        self.props: List[DestructibleProp] = []
        self.last_ammo: Optional[int] = None
        self.last_weapon_name = ""
        self.rng = random.Random(0x44535452554354)

    def reset(self) -> None:
        self.mode_identity = None
        self.props.clear()
        self.last_ammo = None
        self.last_weapon_name = ""

    def update(self, dt: float, mode) -> None:
        game_id = str(getattr(mode, "game_id", ""))
        if game_id not in ("neon_ops", "zombie_siege"):
            return
        if id(mode) != self.mode_identity:
            self._attach(mode)
        ammo = self._ammo(mode)
        weapon_name = str(getattr(mode, "weapon_name", ""))
        if game_id == "neon_ops" and weapon_name != self.last_weapon_name:
            self.last_weapon_name = weapon_name
            self.last_ammo = ammo
            return
        if ammo is not None and self.last_ammo is not None and ammo < self.last_ammo:
            self._handle_shot(mode, game_id)
        self.last_ammo = ammo

    def _attach(self, mode) -> None:
        self.reset()
        self.mode_identity = id(mode)
        game_id = str(getattr(mode, "game_id", ""))
        for index, (pos, size, kind) in enumerate(self._specs(game_id)):
            position = Vec3(*pos)
            full = Vec3(*size)
            half = full * 0.5
            base = (0.12,0.09,0.055,1.0) if kind == "crate" else (0.08,0.09,0.105,1.0)
            node = make_box(f"destructible-{kind}-{index}",tuple(full),base,mode.world_root,tuple(position))
            make_box(
                "destructible-trim",
                (full.x*0.82,full.y*1.01,0.08),
                (0.95,0.38,0.06,0.76) if game_id == "neon_ops" else (0.38,0.62,0.12,0.66),
                node,
                (0,0,full.z*0.18),
            )
            collider = SimpleNamespace(center=Vec3(position),half=Vec3(half),tag="solid")
            mode.colliders.append(collider)
            hp = 92.0 if kind == "crate" else 145.0
            self.props.append(DestructibleProp(node,collider,hp,hp,position,half,kind))
        self.last_ammo = self._ammo(mode)
        self.last_weapon_name = str(getattr(mode,"weapon_name",""))
        mode.nav_revision = int(getattr(mode,"nav_revision",0)) + 1

    @staticmethod
    def _specs(game_id: str):
        if game_id == "neon_ops":
            return [
                ((-7.5,5.5,0.75),(1.8,1.8,1.5),"crate"),
                ((8.0,9.0,0.70),(2.2,1.4,1.4),"crate"),
                ((-14.0,-7.0,0.85),(2.8,1.3,1.7),"barrier"),
                ((14.5,-13.0,0.85),(2.6,1.4,1.7),"barrier"),
                ((1.0,18.0,0.75),(1.8,1.8,1.5),"crate"),
                ((-20.0,14.0,0.70),(2.0,1.5,1.4),"crate"),
                ((21.0,4.0,0.90),(2.8,1.2,1.8),"barrier"),
                ((5.0,-22.0,0.70),(1.7,1.7,1.4),"crate"),
            ]
        return [
            ((-8.0,8.0,0.72),(2.1,1.5,1.44),"crate"),
            ((9.0,7.0,0.72),(2.1,1.5,1.44),"crate"),
            ((-12.0,-5.0,0.86),(3.0,1.2,1.72),"barrier"),
            ((13.0,-9.0,0.86),(3.0,1.2,1.72),"barrier"),
            ((0.0,15.0,0.72),(2.0,1.6,1.44),"crate"),
            ((-20.0,-1.0,0.72),(1.8,1.8,1.44),"crate"),
            ((20.0,4.0,0.72),(1.8,1.8,1.44),"crate"),
        ]

    def _handle_shot(self, mode, game_id: str) -> None:
        if game_id == "neon_ops":
            origin = mode.camera.getPos(mode.root)
            direction = yaw_pitch_forward(float(getattr(mode,"yaw",0.0)),float(getattr(mode,"pitch",0.0)))
            damage = float(getattr(mode,"weapon_damage",28.0))*1.15
            max_distance = 90.0
        else:
            origin = Vec3(getattr(mode,"player_pos",Vec3(0))) + Vec3(0,0,1.25)
            heading = math.radians(float(getattr(mode,"player_heading",0.0)))
            direction = Vec3(math.sin(heading),math.cos(heading),0.02)
            direction.normalize()
            damage = float(getattr(mode,"damage",46.0))*0.92
            max_distance = 28.0
        prop, hit = self._nearest_hit(origin,direction,max_distance)
        if prop is None or hit is None:
            return
        prop.health -= damage
        ratio = max(0.0,prop.health/max(1.0,prop.max_health))
        try:
            mode.particles.sparks(hit,(1.0,0.52,0.10,1.0),7)
        except Exception:
            pass
        if ratio < 0.66:
            prop.node.setColorScale(1.0,0.78+ratio*0.22,0.62+ratio*0.38,1.0)
        if ratio < 0.34:
            prop.node.setR((1.0-ratio)*(3.0 if id(prop)%2 else -3.0))
        if prop.health <= 0.0:
            self._destroy_prop(mode,prop)

    def _destroy_prop(self, mode, prop: DestructibleProp) -> None:
        if not prop.alive:
            return
        prop.alive = False
        pos = Vec3(prop.position)
        try:
            mode.particles.explosion(pos+Vec3(0,0,prop.half.z),(1.0,0.46,0.08,1.0),(0.22,0.16,0.09,1.0))
            mode.pulses.emit(pos+Vec3(0,0,0.05),(1.0,0.38,0.06,0.82),0.25,2.0,0.28)
            mode.camera_shake.add(0.12)
        except Exception:
            pass
        for index in range(6):
            try:
                debris = make_box(
                    f"debris-{index}",(0.18,0.26,0.12),(0.12,0.09,0.055,1.0),mode.fx_root,
                    tuple(pos+Vec3(self.rng.uniform(-0.7,0.7),self.rng.uniform(-0.7,0.7),self.rng.uniform(0.2,1.2))),
                    (self.rng.uniform(-35,35),self.rng.uniform(-35,35),self.rng.uniform(-35,35)),
                )
                mode.base.taskMgr.doMethodLater(
                    1.8+self.rng.random()*0.8,
                    self._remove_debris,
                    f"remove-debris-{id(debris)}",
                    extraArgs=[debris],
                    appendTask=True,
                )
            except Exception:
                pass
        try:
            if prop.collider in mode.colliders:
                mode.colliders.remove(prop.collider)
        except Exception:
            pass
        if not prop.node.isEmpty():
            prop.node.removeNode()
        mode.score = float(getattr(mode,"score",0.0)) + 35.0
        mode.nav_revision = int(getattr(mode,"nav_revision",0)) + 1
        try:
            mode.spawn_floating_text("COVER DESTROYED +35",(0.0,0.05),(1.0,0.55,0.12,1.0),0.030,0.65)
        except Exception:
            pass

    @staticmethod
    def _remove_debris(node: NodePath, task):
        if node is not None and not node.isEmpty():
            node.removeNode()
        return task.done

    def _nearest_hit(self, origin: Vec3, direction: Vec3, max_distance: float):
        best_prop,best_t = None,max_distance+1.0
        for prop in self.props:
            if not prop.alive:
                continue
            t = self._ray_aabb(origin,direction,prop.position,prop.half,max_distance)
            if t is not None and t < best_t:
                best_t,best_prop = t,prop
        return (best_prop, origin+direction*best_t) if best_prop is not None else (None,None)

    @staticmethod
    def _ray_aabb(origin: Vec3, direction: Vec3, center: Vec3, half: Vec3, max_distance: float) -> Optional[float]:
        t_min,t_max = 0.0,max_distance
        for axis in range(3):
            s,d = origin[axis],direction[axis]
            lo,hi = center[axis]-half[axis],center[axis]+half[axis]
            if abs(d) < 1e-8:
                if s < lo or s > hi:
                    return None
                continue
            inv = 1.0/d
            t1,t2 = (lo-s)*inv,(hi-s)*inv
            if t1 > t2:
                t1,t2 = t2,t1
            t_min,t_max = max(t_min,t1),min(t_max,t2)
            if t_min > t_max:
                return None
        return t_min if 0.0 <= t_min <= max_distance else None

    @staticmethod
    def _ammo(mode) -> Optional[int]:
        try:
            return int(mode.ammo)
        except Exception:
            return None
