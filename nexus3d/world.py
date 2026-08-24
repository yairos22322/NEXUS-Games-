from __future__ import annotations

import math
import random
import sys
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from direct.gui.DirectGui import DirectFrame, DirectLabel
from direct.showbase.DirectObject import DirectObject
from panda3d.core import (
    AmbientLight,
    DirectionalLight,
    Fog,
    NodePath,
    PointLight,
    TextNode,
    Vec2,
    Vec3,
    Vec4,
    WindowProperties,
)

from .config import BLACK, CYAN, DARK, GAME_BY_ID, GREEN, MUTED, ORANGE, RED, WHITE
from .fx import CameraShake, ParticleSystem, PulseSystem
from .math3d import aabb_overlap, clamp, damp, damp_vec3, heading_vector, right_vector
from .primitives import make_box, make_grid, make_octahedron, make_plane, make_pyramid

Color = Tuple[float, float, float, float]


@dataclass
class BoxCollider:
    center: Vec3
    half: Vec3
    tag: str = "solid"


@dataclass
class Projectile:
    node: NodePath
    velocity: Vec3
    damage: float
    lifetime: float
    radius: float
    team: str
    color: Color
    age: float = 0.0
    homing_target: Optional[NodePath] = None
    turn_rate: float = 0.0


@dataclass
class FloatingText:
    node: DirectLabel
    age: float
    lifetime: float
    start_pos: Vec2
    drift: Vec2


@dataclass
class Pickup:
    node: NodePath
    kind: str
    amount: float
    radius: float
    base_z: float
    phase: float = field(default_factory=lambda: random.uniform(0, math.tau))


class KeyState(DirectObject):
    def __init__(self) -> None:
        super().__init__()
        self.down: Dict[str, bool] = {}

    def bind(self, key: str, alias: Optional[str] = None) -> None:
        alias = alias or key
        self.down[alias] = False
        self.accept(key, self._set, [alias, True])
        self.accept(f"{key}-up", self._set, [alias, False])

    def bind_many(self, keys: Sequence[str]) -> None:
        for key in keys:
            self.bind(key)

    def _set(self, key: str, value: bool) -> None:
        self.down[key] = value

    def __getitem__(self, key: str) -> bool:
        return self.down.get(key, False)

    def clear(self) -> None:
        for key in list(self.down):
            self.down[key] = False
        self.ignoreAll()


class BaseMode(DirectObject):
    game_id = "base"

    def __init__(self, app) -> None:
        super().__init__()
        self.app = app
        self.base = app
        self.render = app.render
        self.camera = app.camera
        self.root = self.render.attachNewNode(f"mode-{self.game_id}")
        self.world_root = self.root.attachNewNode("world")
        self.actor_root = self.root.attachNewNode("actors")
        self.projectile_root = self.root.attachNewNode("projectiles")
        self.fx_root = self.root.attachNewNode("fx")
        self.key = KeyState()
        self.colliders: List[BoxCollider] = []
        self.projectiles: List[Projectile] = []
        self.pickups: List[Pickup] = []
        self.particles = ParticleSystem(self.fx_root)
        self.pulses = PulseSystem(self.fx_root)
        self.camera_shake = CameraShake(self.camera)
        self.camera_shake.enabled = bool(app.save.setting("camera_shake", True))
        self.particles.enabled = bool(app.save.setting("particles", True))
        self.score = 0
        self.combo = 0
        self.best_combo = 0
        self.session_start = time.time()
        self.active = True
        self.paused = False
        self.game_over = False
        self.hud_root = DirectFrame(
            parent=self.base.aspect2d,
            frameColor=(0, 0, 0, 0),
            frameSize=(-1.78, 1.78, -1, 1),
        )
        self.pause_root: Optional[DirectFrame] = None
        self.floating_text: List[FloatingText] = []
        self._mouse_captured = False
        self._last_mouse = Vec2(0, 0)
        self._ambient: Optional[NodePath] = None
        self._sun: Optional[NodePath] = None
        self._fog: Optional[Fog] = None
        self.difficulty_scale = app.difficulty_scale()
        self._configure_input()
        self.accept("escape", self.toggle_pause)
        self.accept("window-event", self._on_window_event)

    @property
    def meta(self):
        return GAME_BY_ID[self.game_id]

    def _configure_input(self) -> None:
        self.key.bind_many([
            "w", "a", "s", "d", "r", "shift", "control", "space", "q", "e",
            "mouse1", "mouse3", "arrow_left", "arrow_right", "arrow_up", "arrow_down",
        ])

    def add_standard_lighting(
        self,
        ambient: Color = (0.18, 0.21, 0.30, 1),
        sun: Color = (0.88, 0.92, 1.0, 1),
        hpr: Tuple[float, float, float] = (-35, -55, 0),
    ) -> None:
        ambient_light = AmbientLight(f"{self.game_id}-ambient")
        ambient_light.setColor(Vec4(*ambient))
        self._ambient = self.root.attachNewNode(ambient_light)
        self.root.setLight(self._ambient)

        sun_light = DirectionalLight(f"{self.game_id}-sun")
        sun_light.setColor(Vec4(*sun))
        if hasattr(self.app, "graphics"):
            self.app.graphics.configure_directional_light(sun_light)
        self._sun = self.root.attachNewNode(sun_light)
        self._sun.setHpr(*hpr)
        self.root.setLight(self._sun)

    def add_point_light(
        self,
        name: str,
        pos: Vec3,
        color: Color,
        attenuation: Tuple[float, float, float] = (1.0, 0.02, 0.004),
    ) -> NodePath:
        light = PointLight(name)
        light.setColor(Vec4(*color))
        light.setAttenuation(Vec3(*attenuation))
        node = self.root.attachNewNode(light)
        node.setPos(pos)
        self.root.setLight(node)
        return node

    def set_fog(self, color: Color, density: float) -> None:
        self._fog = Fog(f"{self.game_id}-fog")
        self._fog.setColor(*color[:3])
        self._fog.setExpDensity(max(0.0, density))
        self.root.setFog(self._fog)

    def clear_fog(self) -> None:
        self.root.clearFog()
        self._fog = None

    def create_ground(
        self,
        size: float = 120.0,
        color: Color = (0.025, 0.03, 0.045, 1),
        grid: bool = True,
        grid_color: Color = (0.06, 0.12, 0.16, 0.45),
    ) -> NodePath:
        ground = make_plane("ground", size, size, color, self.world_root, 0.0)
        if grid:
            make_grid("ground-grid", int(size // 4), 2.0, grid_color, self.world_root, 0.015)
        return ground

    def add_solid_box(
        self,
        name: str,
        pos: Vec3,
        size: Vec3,
        color: Color,
        tag: str = "solid",
        hpr: Tuple[float, float, float] = (0, 0, 0),
    ) -> NodePath:
        node = make_box(name, tuple(size), color, self.world_root, tuple(pos), hpr)
        self.colliders.append(BoxCollider(Vec3(pos), Vec3(size) * 0.5, tag))
        return node

    def position_blocked(self, position: Vec3, half: Vec3, tags: Sequence[str] = ("solid",)) -> bool:
        for collider in self.colliders:
            if collider.tag not in tags:
                continue
            if aabb_overlap(position, half, collider.center, collider.half):
                return True
        return False

    def move_with_collisions(
        self,
        position: Vec3,
        delta: Vec3,
        half: Vec3,
        tags: Sequence[str] = ("solid",),
    ) -> Vec3:
        result = Vec3(position)
        if abs(delta.x) > 0.00001:
            candidate = Vec3(result.x + delta.x, result.y, result.z)
            if not self.position_blocked(candidate, half, tags):
                result.x = candidate.x
        if abs(delta.y) > 0.00001:
            candidate = Vec3(result.x, result.y + delta.y, result.z)
            if not self.position_blocked(candidate, half, tags):
                result.y = candidate.y
        if abs(delta.z) > 0.00001:
            candidate = Vec3(result.x, result.y, result.z + delta.z)
            if not self.position_blocked(candidate, half, tags):
                result.z = candidate.z
        return result

    def spawn_projectile(
        self,
        position: Vec3,
        direction: Vec3,
        speed: float,
        damage: float,
        color: Color,
        team: str,
        radius: float = 0.10,
        lifetime: float = 4.0,
        scale: float = 0.08,
        homing_target: Optional[NodePath] = None,
        turn_rate: float = 0.0,
    ) -> Projectile:
        direction = Vec3(direction)
        if direction.lengthSquared() < 0.0001:
            direction = Vec3(0, 1, 0)
        direction.normalize()
        node = make_octahedron("projectile", scale, color, self.projectile_root)
        node.setPos(position)
        projectile = Projectile(
            node=node,
            velocity=direction * speed,
            damage=damage,
            lifetime=lifetime,
            radius=radius,
            team=team,
            color=color,
            homing_target=homing_target,
            turn_rate=turn_rate,
        )
        self.projectiles.append(projectile)
        return projectile

    def update_projectiles(self, dt: float, collision_callback: Callable[[Projectile], bool]) -> None:
        alive: List[Projectile] = []
        for projectile in self.projectiles:
            projectile.age += dt
            if projectile.age >= projectile.lifetime or projectile.node.isEmpty():
                if not projectile.node.isEmpty():
                    projectile.node.removeNode()
                continue

            if projectile.homing_target is not None and not projectile.homing_target.isEmpty():
                target_direction = projectile.homing_target.getPos(self.root) - projectile.node.getPos(self.root)
                if target_direction.lengthSquared() > 0.001:
                    target_direction.normalize()
                    speed = projectile.velocity.length()
                    current = Vec3(projectile.velocity)
                    current.normalize()
                    blend = clamp(projectile.turn_rate * dt, 0.0, 1.0)
                    direction = current * (1.0 - blend) + target_direction * blend
                    if direction.lengthSquared() > 0.001:
                        direction.normalize()
                    projectile.velocity = direction * speed

            projectile.node.setPos(projectile.node.getPos() + projectile.velocity * dt)
            projectile.node.setH(projectile.node.getH() + 480 * dt)
            if collision_callback(projectile):
                if not projectile.node.isEmpty():
                    projectile.node.removeNode()
                continue
            alive.append(projectile)
        self.projectiles = alive

    def spawn_pickup(
        self,
        position: Vec3,
        kind: str,
        amount: float,
        color: Color,
        radius: float = 0.7,
    ) -> Pickup:
        node = make_octahedron(f"pickup-{kind}", 0.38, color, self.actor_root)
        node.setPos(position)
        ring = make_box("pickup-core", (0.18, 0.18, 0.9), (1, 1, 1, 0.75), node)
        ring.setH(45)
        pickup = Pickup(node, kind, amount, radius, position.z)
        self.pickups.append(pickup)
        return pickup

    def update_pickups(self, dt: float, player_pos: Vec3, collect: Callable[[Pickup], None]) -> None:
        alive: List[Pickup] = []
        for pickup in self.pickups:
            pickup.phase += dt * 2.2
            pickup.node.setH(pickup.node.getH() + 80.0 * dt)
            pickup.node.setZ(pickup.base_z + math.sin(pickup.phase) * 0.18)
            if (pickup.node.getPos(self.root) - player_pos).length() <= pickup.radius:
                collect(pickup)
                self.particles.pickup(pickup.node.getPos(self.root), tuple(pickup.node.getColorScale()))
                pickup.node.removeNode()
                continue
            alive.append(pickup)
        self.pickups = alive

    def spawn_floating_text(
        self,
        text: str,
        screen_pos: Tuple[float, float] = (0.0, 0.1),
        color: Color = WHITE,
        scale: float = 0.05,
        lifetime: float = 0.8,
    ) -> None:
        label = DirectLabel(
            parent=self.hud_root,
            text=text,
            text_fg=color,
            text_scale=scale,
            text_align=TextNode.ACenter,
            frameColor=(0, 0, 0, 0),
            pos=(screen_pos[0], 0, screen_pos[1]),
        )
        self.floating_text.append(
            FloatingText(label, 0.0, lifetime, Vec2(*screen_pos), Vec2(0.0, 0.17))
        )

    def update_floating_text(self, dt: float) -> None:
        alive: List[FloatingText] = []
        for item in self.floating_text:
            item.age += dt
            if item.age >= item.lifetime:
                item.node.destroy()
                continue
            t = item.age / item.lifetime
            pos = item.start_pos + item.drift * t
            item.node.setPos(pos.x, 0, pos.y)
            item.node["text_fg"] = (1, 1, 1, max(0.0, 1.0 - t))
            alive.append(item)
        self.floating_text = alive

    def set_mouse_capture(self, captured: bool) -> None:
        self._mouse_captured = captured
        props = WindowProperties()
        props.setCursorHidden(captured)
        if captured:
            mode = WindowProperties.M_confined if sys.platform.startswith("win") else WindowProperties.M_relative
            props.setMouseMode(mode)
        else:
            props.setMouseMode(WindowProperties.M_absolute)
        self.base.win.requestProperties(props)

    def mouse_delta(self) -> Vec2:
        if not self._mouse_captured or not self.base.mouseWatcherNode.hasMouse():
            return Vec2(0, 0)
        pointer = self.base.win.getPointer(0)
        center_x = self.base.win.getXSize() // 2
        center_y = self.base.win.getYSize() // 2
        dx = pointer.getX() - center_x
        dy = pointer.getY() - center_y
        self.base.win.movePointer(0, center_x, center_y)
        return Vec2(dx, dy)

    def _on_window_event(self, window) -> None:
        if window is None:
            return
        if self._mouse_captured and self.active and not self.paused:
            center_x = self.base.win.getXSize() // 2
            center_y = self.base.win.getYSize() // 2
            self.base.win.movePointer(0, center_x, center_y)

    def toggle_pause(self) -> None:
        if self.game_over:
            self.exit_to_menu()
            return
        self.paused = not self.paused
        if self.paused:
            self.set_mouse_capture(False)
            self.show_pause_ui()
        else:
            if self.pause_root is not None:
                self.pause_root.destroy()
                self.pause_root = None
            self.on_resume()

    def show_pause_ui(self) -> None:
        if self.pause_root is not None:
            self.pause_root.destroy()
        self.pause_root = DirectFrame(
            parent=self.base.aspect2d,
            frameColor=(0.01, 0.015, 0.025, 0.92),
            frameSize=(-1.8, 1.8, -1.05, 1.05),
            sortOrder=80,
        )
        DirectLabel(
            parent=self.pause_root,
            text="PAUSED",
            text_fg=WHITE,
            text_scale=0.12,
            frameColor=(0, 0, 0, 0),
            pos=(0, 0, 0.28),
        )
        DirectLabel(
            parent=self.pause_root,
            text="ESC RESUME    |    M MAIN MENU",
            text_fg=MUTED,
            text_scale=0.045,
            frameColor=(0, 0, 0, 0),
            pos=(0, 0, 0.08),
        )
        self.acceptOnce("m", self.exit_to_menu)

    def on_resume(self) -> None:
        pass

    def finish_game(self, reason: str = "MISSION FAILED") -> None:
        if self.game_over:
            return
        self.game_over = True
        self.paused = True
        self.set_mouse_capture(False)
        self.app.audio.play("game_over", self.app.sfx_volume())
        new_best = self.app.save.submit_score(self.game_id, int(self.score))
        self.app.save.add_xp(max(20, int(self.score * 0.04)))
        self.app.save.max_stat(self.game_id, "best_combo", self.best_combo)
        self.app.save.save()
        if self.pause_root is not None:
            self.pause_root.destroy()
        self.pause_root = DirectFrame(
            parent=self.base.aspect2d,
            frameColor=(0.008, 0.012, 0.02, 0.95),
            frameSize=(-1.8, 1.8, -1.05, 1.05),
            sortOrder=100,
        )
        DirectLabel(
            parent=self.pause_root,
            text=reason,
            text_fg=self.meta.accent,
            text_scale=0.105,
            frameColor=(0, 0, 0, 0),
            pos=(0, 0, 0.33),
        )
        DirectLabel(
            parent=self.pause_root,
            text=f"SCORE  {int(self.score):,}",
            text_fg=WHITE,
            text_scale=0.075,
            frameColor=(0, 0, 0, 0),
            pos=(0, 0, 0.13),
        )
        if new_best:
            DirectLabel(
                parent=self.pause_root,
                text="NEW PERSONAL BEST",
                text_fg=self.meta.secondary,
                text_scale=0.045,
                frameColor=(0, 0, 0, 0),
                pos=(0, 0, 0.01),
            )
        DirectLabel(
            parent=self.pause_root,
            text="ENTER RETRY    |    ESC MAIN MENU",
            text_fg=MUTED,
            text_scale=0.042,
            frameColor=(0, 0, 0, 0),
            pos=(0, 0, -0.23),
        )
        self.acceptOnce("enter", self.retry)
        self.acceptOnce("escape", self.exit_to_menu)

    def retry(self) -> None:
        self.app.start_game(self.game_id)

    def exit_to_menu(self) -> None:
        self.app.show_menu()

    def tick_common(self, dt: float) -> None:
        self.particles.update(dt)
        self.pulses.update(dt)
        self.update_floating_text(dt)
        self.best_combo = max(self.best_combo, self.combo)

    def update(self, dt: float) -> None:
        raise NotImplementedError

    def destroy(self) -> None:
        if not self.active:
            return
        self.active = False
        self.set_mouse_capture(False)
        elapsed = max(0.0, time.time() - self.session_start)
        self.app.save.add_session_time(elapsed)
        self.app.save.max_stat(self.game_id, "best_combo", self.best_combo)
        self.app.save.save()
        self.key.clear()
        self.ignoreAll()
        for text in self.floating_text:
            text.node.destroy()
        self.floating_text.clear()
        if self.pause_root is not None:
            self.pause_root.destroy()
            self.pause_root = None
        if self.hud_root is not None:
            self.hud_root.destroy()
        self.particles.clear()
        self.pulses.clear()
        if not self.root.isEmpty():
            self.root.removeNode()
        self.base.camera.setPos(0, -20, 8)
        self.base.camera.setHpr(0, -12, 0)
        self.base.render.clearLight()
        self.base.render.clearFog()


class CharacterRig:
    def __init__(
        self,
        parent: NodePath,
        name: str,
        position: Vec3,
        primary: Color,
        secondary: Color,
        scale: float = 1.0,
    ) -> None:
        self.root = parent.attachNewNode(name)
        self.root.setPos(position)
        self.root.setScale(scale)
        self.body = make_box(f"{name}-body", (0.72, 0.46, 1.15), primary, self.root, (0, 0, 1.12))
        self.chest = make_box(f"{name}-chest", (0.82, 0.50, 0.48), secondary, self.root, (0, 0, 1.42))
        self.head = make_box(f"{name}-head", (0.48, 0.44, 0.48), (0.72, 0.68, 0.62, 1), self.root, (0, 0, 2.02))
        self.left_arm = make_box(f"{name}-arm-l", (0.22, 0.22, 0.90), primary, self.root, (-0.52, 0, 1.30))
        self.right_arm = make_box(f"{name}-arm-r", (0.22, 0.22, 0.90), primary, self.root, (0.52, 0, 1.30))
        self.left_leg = make_box(f"{name}-leg-l", (0.28, 0.30, 0.92), secondary, self.root, (-0.22, 0, 0.47))
        self.right_leg = make_box(f"{name}-leg-r", (0.28, 0.30, 0.92), secondary, self.root, (0.22, 0, 0.47))
        self.weapon = make_box(f"{name}-weapon", (0.16, 0.85, 0.18), (0.06, 0.07, 0.08, 1), self.root, (0.46, 0.35, 1.36), (0, 0, -8))
        self.walk_time = random.uniform(0, math.tau)

    def set_pos(self, pos: Vec3) -> None:
        self.root.setPos(pos)

    def get_pos(self) -> Vec3:
        return self.root.getPos()

    def face_heading(self, heading: float) -> None:
        self.root.setH(heading)

    def animate_walk(self, dt: float, amount: float) -> None:
        self.walk_time += dt * (5.0 + amount * 6.0)
        swing = math.sin(self.walk_time) * 28.0 * clamp(amount, 0, 1)
        self.left_arm.setP(swing)
        self.right_arm.setP(-swing)
        self.left_leg.setP(-swing)
        self.right_leg.setP(swing)
        bob = abs(math.sin(self.walk_time * 2.0)) * 0.025 * amount
        self.body.setZ(1.12 + bob)

    def flash(self, color: Color = (1, 1, 1, 1), strength: float = 1.0) -> None:
        self.root.setColorScale(
            1.0 + color[0] * strength,
            1.0 + color[1] * strength,
            1.0 + color[2] * strength,
            1.0,
        )

    def clear_flash(self) -> None:
        self.root.clearColorScale()

    def destroy(self) -> None:
        if not self.root.isEmpty():
            self.root.removeNode()


class VehicleRig:
    def __init__(
        self,
        parent: NodePath,
        name: str,
        position: Vec3,
        primary: Color,
        secondary: Color,
        scale: float = 1.0,
    ) -> None:
        self.root = parent.attachNewNode(name)
        self.root.setPos(position)
        self.root.setScale(scale)
        self.chassis = make_box(f"{name}-chassis", (1.75, 4.1, 0.60), primary, self.root, (0, 0, 0.62))
        self.cabin = make_box(f"{name}-cabin", (1.45, 1.95, 0.65), secondary, self.root, (0, -0.10, 1.15))
        self.windshield = make_box(f"{name}-glass", (1.30, 0.08, 0.44), (0.05, 0.12, 0.18, 0.85), self.root, (0, 0.92, 1.18), (0, 12, 0))
        self.spoiler = make_box(f"{name}-spoiler", (1.55, 0.20, 0.12), secondary, self.root, (0, -1.75, 1.05))
        self.wheels: List[NodePath] = []
        for x in (-0.92, 0.92):
            for y in (-1.25, 1.25):
                wheel = make_box(f"{name}-wheel", (0.25, 0.65, 0.58), (0.018, 0.018, 0.022, 1), self.root, (x, y, 0.42))
                self.wheels.append(wheel)
        self.left_light = make_box(f"{name}-light-l", (0.32, 0.08, 0.16), (1.0, 0.95, 0.65, 1), self.root, (-0.55, 2.08, 0.72))
        self.right_light = make_box(f"{name}-light-r", (0.32, 0.08, 0.16), (1.0, 0.95, 0.65, 1), self.root, (0.55, 2.08, 0.72))
        self.wheel_spin = 0.0

    def animate(self, dt: float, speed: float, steer: float = 0.0) -> None:
        self.wheel_spin += speed * dt * 8.0
        for wheel in self.wheels:
            wheel.setP(self.wheel_spin)
        self.root.setR(-steer * 5.5)

    def destroy(self) -> None:
        if not self.root.isEmpty():
            self.root.removeNode()


class ShipRig:
    def __init__(
        self,
        parent: NodePath,
        name: str,
        position: Vec3,
        primary: Color,
        secondary: Color,
        scale: float = 1.0,
    ) -> None:
        self.root = parent.attachNewNode(name)
        self.root.setPos(position)
        self.root.setScale(scale)
        self.body = make_pyramid(f"{name}-body", 1.35, 3.4, 0.72, primary, self.root)
        self.body.setP(-90)
        self.body.setZ(0.15)
        self.left_wing = make_box(f"{name}-wing-l", (2.2, 0.85, 0.12), secondary, self.root, (-1.0, -0.25, 0))
        self.right_wing = make_box(f"{name}-wing-r", (2.2, 0.85, 0.12), secondary, self.root, (1.0, -0.25, 0))
        self.cockpit = make_box(f"{name}-cockpit", (0.62, 1.05, 0.48), (0.06, 0.18, 0.28, 0.92), self.root, (0, 0.45, 0.42))
        self.engine_left = make_box(f"{name}-engine-l", (0.30, 0.75, 0.30), secondary, self.root, (-0.52, -1.30, -0.05))
        self.engine_right = make_box(f"{name}-engine-r", (0.30, 0.75, 0.30), secondary, self.root, (0.52, -1.30, -0.05))
        self.engine_glow_left = make_box(f"{name}-glow-l", (0.18, 0.45, 0.18), (0.2, 0.85, 1.0, 0.85), self.root, (-0.52, -1.78, -0.05))
        self.engine_glow_right = make_box(f"{name}-glow-r", (0.18, 0.45, 0.18), (0.2, 0.85, 1.0, 0.85), self.root, (0.52, -1.78, -0.05))

    def animate_engine(self, elapsed: float, boost: float) -> None:
        pulse = 0.72 + math.sin(elapsed * 14.0) * 0.14 + boost * 0.55
        self.engine_glow_left.setScale(1, pulse, 1)
        self.engine_glow_right.setScale(1, pulse, 1)

    def destroy(self) -> None:
        if not self.root.isEmpty():
            self.root.removeNode()
