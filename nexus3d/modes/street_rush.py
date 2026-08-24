from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List, Tuple

from direct.gui.DirectGui import DirectFrame, DirectLabel
from panda3d.core import TextNode, Vec3

from ..config import CYAN, GREEN, MAGENTA, MUTED, ORANGE, PURPLE, RED, WHITE, YELLOW
from ..data.content_catalog import traffic_for_distance
from ..math3d import clamp, damp, damp_vec3
from ..primitives import make_box, make_plane
from ..world import BaseMode, VehicleRig

Color = Tuple[float, float, float, float]


@dataclass
class TrafficCar:
    rig: VehicleRig
    speed: float
    lane: int
    passed: bool = False
    near_miss: bool = False
    color: Color = WHITE


@dataclass
class RoadProp:
    node: object
    z: float
    side: int
    speed_scale: float


class StreetRush(BaseMode):
    game_id = "street_rush"

    LANES = (-5.2, -1.75, 1.75, 5.2)

    def __init__(self, app) -> None:
        super().__init__(app)
        self.elapsed = 0.0
        self.distance = 0.0
        self.speed = 34.0
        self.target_speed = 34.0
        self.max_speed = 76.0
        self.min_speed = 18.0
        self.accel = 17.0
        self.brake = 27.0
        self.lateral_speed = 10.8
        self.steer = 0.0
        self.player_x = 0.0
        self.health = 100.0
        self.nitro = 100.0
        self.nitro_active = False
        self.collision_cooldown = 0.0
        self.traffic: List[TrafficCar] = []
        self.road_props: List[RoadProp] = []
        self.spawn_timer = 0.0
        self.combo_timer = 0.0
        self.road_segments: List[object] = []
        self.city_segments: List[object] = []
        self._build_world()
        self._build_hud()

    def _build_world(self) -> None:
        self.base.setBackgroundColor(0.015, 0.006, 0.025, 1)
        self.add_standard_lighting(
            ambient=(0.16, 0.10, 0.22, 1),
            sun=(0.56, 0.38, 0.72, 1),
            hpr=(-18, -46, 0),
        )
        self.set_fog((0.03, 0.008, 0.05, 1), 0.008)
        self.player = VehicleRig(
            self.actor_root,
            "player-car",
            Vec3(0, 0, 0),
            (0.08, 0.12, 0.18, 1),
            MAGENTA,
            1.0,
        )
        make_box("player-neon", (1.55, 2.1, 0.06), (0.92, 0.05, 0.60, 0.72), self.player.root, (0, -0.2, 0.14))
        self.camera.setPos(0, -12.5, 5.6)
        self.camera.setHpr(0, -13, 0)

        for index in range(18):
            y = index * 18.0 - 20.0
            segment = self._make_road_segment(index, y)
            self.road_segments.append(segment)
            self._make_city_pair(index, y)
        self.add_point_light("road-magenta", Vec3(-8, 12, 7), (0.60, 0.02, 0.40, 1), (1, 0.025, 0.003))
        self.add_point_light("road-cyan", Vec3(8, 32, 7), (0.02, 0.42, 0.70, 1), (1, 0.025, 0.003))

    def _make_road_segment(self, index: int, y: float):
        root = self.world_root.attachNewNode(f"road-segment-{index}")
        root.setY(y)
        make_box("asphalt", (17.2, 18.2, 0.20), (0.025, 0.026, 0.034, 1), root, (0, 0, -0.11))
        make_box("left-curb", (0.65, 18.2, 0.35), (0.09, 0.06, 0.11, 1), root, (-8.85, 0, 0.04))
        make_box("right-curb", (0.65, 18.2, 0.35), (0.09, 0.06, 0.11, 1), root, (8.85, 0, 0.04))
        for x in (-3.48, 0, 3.48):
            for dash in (-6.2, 0, 6.2):
                make_box("lane-dash", (0.11, 3.0, 0.025), (0.62, 0.62, 0.68, 0.75), root, (x, dash, 0.02))
        for side in (-1, 1):
            make_box("edge-light", (0.08, 17.0, 0.05), MAGENTA if side < 0 else CYAN, root, (side * 8.25, 0, 0.08))
        return root

    def _make_city_pair(self, index: int, y: float) -> None:
        rng = random.Random(7000 + index)
        for side in (-1, 1):
            root = self.world_root.attachNewNode(f"city-{index}-{side}")
            root.setY(y)
            for tower in range(3):
                width = rng.uniform(3.0, 5.7)
                depth = rng.uniform(5.0, 8.5)
                height = rng.uniform(8.0, 25.0)
                x = side * (12.0 + tower * 5.0 + rng.uniform(-0.8, 0.8))
                z = height * 0.5 - 0.1
                color = (rng.uniform(0.025, 0.055), rng.uniform(0.02, 0.045), rng.uniform(0.05, 0.10), 1)
                building = make_box("tower", (width, depth, height), color, root, (x, 0, z))
                accent = MAGENTA if (index + tower + side) % 2 == 0 else CYAN
                for floor in range(2, int(height), 4):
                    if rng.random() < 0.8:
                        make_box("window", (width * 0.70, 0.08, 0.08), accent, building, (0, -depth * 0.51, floor - z))
            if index % 2 == 0:
                sign = make_box("billboard", (3.8, 0.16, 1.4), (0.03, 0.05, 0.08, 1), root, (side * 10.2, 1.5, 4.0))
                make_box("billboard-glow", (3.4, 0.04, 0.12), MAGENTA if side < 0 else CYAN, sign, (0, -0.10, 0))
        self.city_segments.extend([child for child in self.world_root.getChildren() if child.getName().startswith(f"city-{index}")])

    def _build_hud(self) -> None:
        self.speed_label = DirectLabel(
            parent=self.hud_root,
            text="000",
            text_fg=WHITE,
            text_scale=0.095,
            text_align=TextNode.ARight,
            frameColor=(0, 0, 0, 0),
            pos=(1.58, 0, -0.79),
        )
        self.kmh_label = DirectLabel(
            parent=self.hud_root,
            text="KM/H",
            text_fg=MUTED,
            text_scale=0.027,
            text_align=TextNode.ARight,
            frameColor=(0, 0, 0, 0),
            pos=(1.58, 0, -0.91),
        )
        self.distance_label = DirectLabel(
            parent=self.hud_root,
            text="0.00 KM",
            text_fg=CYAN,
            text_scale=0.037,
            text_align=TextNode.ARight,
            frameColor=(0, 0, 0, 0),
            pos=(1.58, 0, 0.87),
        )
        self.score_label = DirectLabel(
            parent=self.hud_root,
            text="SCORE 0",
            text_fg=WHITE,
            text_scale=0.038,
            text_align=TextNode.ARight,
            frameColor=(0, 0, 0, 0),
            pos=(1.58, 0, 0.79),
        )
        self.combo_label = DirectLabel(
            parent=self.hud_root,
            text="",
            text_fg=ORANGE,
            text_scale=0.040,
            text_align=TextNode.ACenter,
            frameColor=(0, 0, 0, 0),
            pos=(0, 0, 0.68),
        )
        self.health_bar_bg = DirectFrame(parent=self.hud_root, frameColor=(0.05, 0.06, 0.08, 0.9), frameSize=(-1.60, -0.72, -0.91, -0.865))
        self.health_bar = DirectFrame(parent=self.hud_root, frameColor=MAGENTA, frameSize=(-1.60, -0.72, -0.91, -0.865))
        self.nitro_bar_bg = DirectFrame(parent=self.hud_root, frameColor=(0.05, 0.06, 0.08, 0.9), frameSize=(-1.60, -0.72, -0.83, -0.785))
        self.nitro_bar = DirectFrame(parent=self.hud_root, frameColor=CYAN, frameSize=(-1.60, -0.72, -0.83, -0.785))
        self.status_label = DirectLabel(
            parent=self.hud_root,
            text="NITRO READY",
            text_fg=CYAN,
            text_scale=0.026,
            text_align=TextNode.ALeft,
            frameColor=(0, 0, 0, 0),
            pos=(-1.58, 0, -0.72),
        )
        self.damage_overlay = DirectFrame(parent=self.hud_root, frameColor=(1, 0.02, 0.03, 0), frameSize=(-1.8, 1.8, -1.05, 1.05), sortOrder=-1)
        self.damage_alpha = 0.0

    def _spawn_traffic(self) -> None:
        lane = random.randrange(len(self.LANES))
        x = self.LANES[lane]
        y = random.uniform(70.0, 105.0)
        profile = traffic_for_distance(self.distance)
        primary, secondary = profile.primary, profile.secondary
        rig = VehicleRig(self.actor_root, "traffic", Vec3(x, y, 0), primary, secondary, random.uniform(0.88, 1.08))
        speed = profile.cruise_speed * (0.92 + 0.08 * self.difficulty_scale)
        self.traffic.append(TrafficCar(rig=rig, speed=speed, lane=lane, color=secondary))

    def _update_road(self, dt: float) -> None:
        scroll = self.speed * dt
        for segment in self.road_segments:
            segment.setY(segment.getY() - scroll)
            if segment.getY() < -40:
                segment.setY(segment.getY() + len(self.road_segments) * 18.0)
        for node in self.city_segments:
            if node.isEmpty():
                continue
            node.setY(node.getY() - scroll)
            if node.getY() < -40:
                node.setY(node.getY() + 18 * 18.0)

    def _update_player(self, dt: float) -> None:
        steer_input = (1 if self.key["d"] or self.key["arrow_right"] else 0) - (1 if self.key["a"] or self.key["arrow_left"] else 0)
        accel_input = self.key["w"] or self.key["arrow_up"]
        brake_input = self.key["s"] or self.key["arrow_down"]

        if accel_input:
            self.target_speed = min(self.max_speed, self.target_speed + self.accel * dt)
        else:
            self.target_speed = max(30.0, self.target_speed - self.accel * 0.35 * dt)
        if brake_input:
            self.target_speed = max(self.min_speed, self.target_speed - self.brake * dt)

        self.nitro_active = bool(self.key["shift"] and self.nitro > 0.5 and self.speed > 24)
        if self.nitro_active:
            self.target_speed = min(96.0, self.target_speed + 32.0 * dt)
            self.nitro = max(0.0, self.nitro - 25.0 * dt)
            if random.random() < dt * 13:
                self.particles.burst(Vec3(self.player_x, -1.8, 0.45), CYAN, count=2, speed=3, lifetime=0.35, size=0.045, gravity=0)
        else:
            self.nitro = min(100.0, self.nitro + 7.0 * dt)

        self.speed = damp(self.speed, self.target_speed, 3.2, dt)
        self.steer = damp(self.steer, float(steer_input), 7.0, dt)
        self.player_x += self.steer * self.lateral_speed * dt * (0.7 + self.speed / 100.0)
        self.player_x = clamp(self.player_x, -7.0, 7.0)
        self.player.root.setX(self.player_x)
        self.player.animate(dt, self.speed, self.steer)
        self.player.root.setH(-self.steer * 4.0)
        if abs(self.player_x) > 6.65:
            self.speed = max(self.min_speed, self.speed - 22.0 * dt)
            self.target_speed = min(self.target_speed, 45.0)

        camera_target = Vec3(self.player_x * 0.28, -12.5, 5.5 + self.speed * 0.012)
        self.camera.setPos(damp_vec3(self.camera.getPos(), camera_target, 6.0, dt))
        self.camera.setHpr(-self.steer * 1.5, -13.0 - clamp((self.speed - 45) * 0.05, 0, 2.0), self.steer * 1.2)
        self.base.camLens.setFov(damp(self.base.camLens.getFov()[0], 76.0 + clamp((self.speed - 30) * 0.30, 0, 18), 3.0, dt))

    def _update_traffic(self, dt: float) -> None:
        alive: List[TrafficCar] = []
        self.spawn_timer -= dt
        density = 0.62 / self.difficulty_scale
        density *= clamp(1.2 - self.distance / 9000.0, 0.65, 1.2)
        if self.spawn_timer <= 0:
            self.spawn_timer = random.uniform(density * 0.65, density * 1.35)
            self._spawn_traffic()

        for car in self.traffic:
            relative_speed = self.speed - car.speed
            car.rig.root.setY(car.rig.root.getY() - relative_speed * dt)
            car.rig.animate(dt, car.speed, 0)
            y = car.rig.root.getY()
            x = car.rig.root.getX()
            dx = abs(x - self.player_x)

            if not car.near_miss and -1.8 < y < 2.6 and 1.08 < dx < 2.35:
                car.near_miss = True
                self.combo += 1
                self.best_combo = max(self.best_combo, self.combo)
                self.combo_timer = 2.8
                bonus = 180 + self.combo * 35
                self.score += bonus
                self.spawn_floating_text(f"NEAR MISS +{bonus}", (0.0, 0.18), ORANGE, 0.038, 0.7)
                self.app.audio.play("dash", self.app.sfx_volume() * 0.26, 1.25)

            if self.collision_cooldown <= 0 and -1.75 < y < 2.15 and dx < 1.28:
                self._collision(car)

            if y < -25:
                if not car.passed:
                    car.passed = True
                    self.score += 35
                car.rig.destroy()
                continue
            if y > 125:
                car.rig.destroy()
                continue
            alive.append(car)
        self.traffic = alive

    def _collision(self, car: TrafficCar) -> None:
        self.collision_cooldown = 1.0
        impact_speed = max(8.0, self.speed - car.speed)
        damage = clamp(impact_speed * 0.55, 8.0, 32.0) * self.difficulty_scale
        self.health -= damage
        self.speed *= 0.56
        self.target_speed = min(self.target_speed, self.speed + 8)
        self.combo = 0
        self.combo_timer = 0
        self.damage_alpha = min(0.7, self.damage_alpha + 0.45)
        self.camera_shake.add(0.78)
        pos = Vec3((self.player_x + car.rig.root.getX()) * 0.5, 1.0, 0.8)
        self.particles.explosion(pos, ORANGE, RED)
        self.pulses.emit(pos, ORANGE, 0.4, 3.2, 0.35)
        self.app.audio.play("explosion", self.app.sfx_volume() * 0.42)
        car.rig.root.setX(car.rig.root.getX() + (2.2 if car.rig.root.getX() > self.player_x else -2.2))
        if self.health <= 0:
            self.health = 0
            self.finish_game("VEHICLE DESTROYED")

    def _update_score(self, dt: float) -> None:
        self.distance += self.speed * dt
        self.score += self.speed * dt * (0.50 + self.combo * 0.025)
        self.app.save.add_stat(self.game_id, "distance", self.speed * dt)
        self.combo_timer -= dt
        if self.combo_timer <= 0 and self.combo > 0:
            self.combo = max(0, self.combo - 1)
            self.combo_timer = 0.65 if self.combo else 0

    def _update_hud(self, dt: float) -> None:
        self.speed_label["text"] = f"{int(self.speed * 3.6):03d}"
        self.distance_label["text"] = f"{self.distance / 1000.0:05.2f} KM"
        self.score_label["text"] = f"SCORE {int(self.score):,}"
        self.combo_label["text"] = f"x{self.combo} CLOSE CALL" if self.combo >= 2 else ""
        health_t = clamp(self.health / 100.0, 0, 1)
        nitro_t = clamp(self.nitro / 100.0, 0, 1)
        self.health_bar["frameSize"] = (-1.60, -1.60 + 0.88 * health_t, -0.91, -0.865)
        self.health_bar["frameColor"] = MAGENTA if self.health > 30 else RED
        self.nitro_bar["frameSize"] = (-1.60, -1.60 + 0.88 * nitro_t, -0.83, -0.785)
        self.status_label["text"] = "NITRO ENGAGED" if self.nitro_active else "NITRO READY" if self.nitro > 35 else "NITRO RECHARGING"
        self.status_label["text_fg"] = ORANGE if self.nitro_active else CYAN
        self.damage_alpha = damp(self.damage_alpha, 0.0, 3.8, dt)
        self.damage_overlay["frameColor"] = (0.9, 0.01, 0.03, self.damage_alpha * 0.35)

    def update(self, dt: float) -> None:
        if self.paused or self.game_over:
            self.tick_common(dt)
            return
        self.elapsed += dt
        self.collision_cooldown = max(0.0, self.collision_cooldown - dt)
        self._update_player(dt)
        self._update_road(dt)
        self._update_traffic(dt)
        self._update_score(dt)
        self._update_hud(dt)
        self.tick_common(dt)

    def destroy(self) -> None:
        try:
            self.player.destroy()
        except Exception:
            pass
        super().destroy()
