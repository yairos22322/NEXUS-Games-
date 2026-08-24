from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List, Optional, Tuple

from direct.gui.DirectGui import DirectFrame, DirectLabel
from panda3d.core import TextNode, Vec3

from ..config import BLUE, CYAN, DARK, GREEN, MUTED, ORANGE, RED, WHITE
from ..data.content_catalog import arena_for_seed, neon_enemy_for_wave, weapon_for_level
from ..math3d import clamp, damp, distance_2d, heading_vector, right_vector, segment_point_distance, yaw_pitch_forward
from ..primitives import make_box, make_grid, make_plane, make_ring
from ..world import BaseMode, CharacterRig, Pickup, Projectile

Color = Tuple[float, float, float, float]


@dataclass
class Enemy:
    rig: CharacterRig
    health: float
    max_health: float
    speed: float
    damage: float
    fire_interval: float
    fire_timer: float
    radius: float
    elite: bool
    strafe_phase: float
    hurt_timer: float = 0.0
    alive: bool = True


class NeonOps(BaseMode):
    game_id = "neon_ops"

    def __init__(self, app) -> None:
        super().__init__(app)
        self.health = 100.0
        self.armor = 55.0
        self.magazine_size = 30
        self.ammo = self.magazine_size
        self.reserve_ammo = 150
        self.reload_time = 1.55
        self.reload_timer = 0.0
        self.reloading = False
        self.fire_interval = 0.095
        self.fire_timer = 0.0
        weapon = weapon_for_level(int(app.save.profile.get("level", 1)))
        self.magazine_size = weapon.magazine
        self.ammo = self.magazine_size
        self.reserve_ammo = weapon.reserve
        self.reload_time = weapon.reload_time
        self.fire_interval = weapon.fire_interval
        self.weapon_damage = weapon.damage
        self.weapon_spread = weapon.spread
        self.weapon_name = weapon.name
        self.player_pos = Vec3(0, -18, 1.05)
        self.player_half = Vec3(0.42, 0.42, 1.02)
        self.velocity = Vec3(0)
        self.yaw = 0.0
        self.pitch = 0.0
        self.walk_speed = 8.5
        self.sprint_speed = 12.8
        self.dash_timer = 0.0
        self.dash_cooldown = 0.0
        self.dash_duration = 0.16
        self.dash_direction = Vec3(0)
        self.wave = 0
        self.wave_delay = 0.8
        self.wave_spawn_timer = 0.0
        self.enemies_to_spawn = 0
        self.spawn_interval = 0.42
        self.enemies: List[Enemy] = []
        self.elapsed = 0.0
        self.hitmarker_timer = 0.0
        self.damage_vignette = 0.0
        self.muzzle_timer = 0.0
        self.crosshair_kick = 0.0
        self._build_world()
        self._build_hud()
        self.set_mouse_capture(True)
        self._start_wave()

    def _build_world(self) -> None:
        self.base.setBackgroundColor(0.005, 0.012, 0.020, 1)
        self.add_standard_lighting(
            ambient=(0.13, 0.18, 0.26, 1),
            sun=(0.45, 0.72, 1.0, 1),
            hpr=(-42, -57, 0),
        )
        self.set_fog((0.008, 0.025, 0.04, 1), 0.012)
        make_plane("arena-ground", 92, 92, (0.018, 0.025, 0.038, 1), self.world_root, 0)
        make_grid("arena-grid", 23, 2.0, (0.03, 0.22, 0.28, 0.50), self.world_root, 0.015)

        wall_color = (0.055, 0.075, 0.105, 1)
        trim = (0.03, 0.65, 0.78, 0.85)
        self.add_solid_box("north-wall", Vec3(0, 44, 3), Vec3(92, 1.5, 6), wall_color)
        self.add_solid_box("south-wall", Vec3(0, -44, 3), Vec3(92, 1.5, 6), wall_color)
        self.add_solid_box("east-wall", Vec3(44, 0, 3), Vec3(1.5, 92, 6), wall_color)
        self.add_solid_box("west-wall", Vec3(-44, 0, 3), Vec3(1.5, 92, 6), wall_color)

        for y in (-43.1, 43.1):
            make_box("wall-trim", (80, 0.15, 0.14), trim, self.world_root, (0, y, 2.1))
        for x in (-43.1, 43.1):
            make_box("wall-trim", (0.15, 80, 0.14), trim, self.world_root, (x, 0, 2.1))

        layout = arena_for_seed(int(self.app.save.profile.get("level", 1)) + self.app.save.score_for(self.game_id))
        obstacle_specs = list(layout.obstacles)
        for index, (x, y, sx, sy, sz) in enumerate(obstacle_specs):
            color = (0.045 + (index % 3) * 0.012, 0.06, 0.09, 1)
            node = self.add_solid_box(
                f"cover-{index}",
                Vec3(x, y, sz * 0.5),
                Vec3(sx, sy, sz),
                color,
            )
            make_box(
                "cover-glow",
                (sx * 0.86, sy * 1.02, 0.08),
                CYAN if index % 2 == 0 else BLUE,
                node,
                (0, 0, sz * 0.35),
            )

        for index in range(16):
            angle = math.tau * index / 16
            radius = 36.5
            x = math.cos(angle) * radius
            y = math.sin(angle) * radius
            pillar = make_box(
                f"pillar-{index}",
                (0.8, 0.8, 5.8),
                (0.035, 0.05, 0.075, 1),
                self.world_root,
                (x, y, 2.9),
            )
            make_box(
                "pillar-light",
                (0.92, 0.92, 0.09),
                CYAN if index % 2 == 0 else BLUE,
                pillar,
                (0, 0, 0.75),
            )

        self.spawn_points = [Vec3(*point) for point in layout.spawn_points]
        self.add_point_light("arena-blue", Vec3(0, 4, 9), (0.04, 0.35, 0.65, 1), (1, 0.03, 0.002))
        self.add_point_light("arena-cyan", Vec3(-22, -7, 7), (0.02, 0.65, 0.72, 1), (1, 0.04, 0.004))
        self.add_point_light("arena-orange", Vec3(24, 19, 7), (0.70, 0.21, 0.04, 1), (1, 0.04, 0.004))

        self.weapon_root = self.camera.attachNewNode("fps-weapon")
        self.weapon_body = make_box("rifle-body", (0.24, 1.15, 0.24), (0.055, 0.065, 0.085, 1), self.weapon_root, (0.40, 0.92, -0.36), (0, 0, -5))
        self.weapon_barrel = make_box("rifle-barrel", (0.10, 0.82, 0.10), (0.12, 0.14, 0.16, 1), self.weapon_root, (0.39, 1.72, -0.31))
        self.weapon_accent = make_box("rifle-accent", (0.06, 0.72, 0.08), CYAN, self.weapon_root, (0.29, 0.86, -0.22))
        self.muzzle = make_box("muzzle", (0.11, 0.11, 0.11), (0.9, 0.95, 1.0, 0.95), self.weapon_root, (0.39, 2.15, -0.31))
        self.muzzle.hide()

    def _build_hud(self) -> None:
        self.health_bar_bg = DirectFrame(
            parent=self.hud_root,
            frameColor=(0.06, 0.075, 0.095, 0.92),
            frameSize=(-1.62, -0.78, -0.88, -0.835),
        )
        self.health_bar = DirectFrame(
            parent=self.hud_root,
            frameColor=CYAN,
            frameSize=(-1.62, -0.78, -0.88, -0.835),
        )
        self.armor_bar_bg = DirectFrame(
            parent=self.hud_root,
            frameColor=(0.06, 0.075, 0.095, 0.92),
            frameSize=(-1.62, -0.96, -0.94, -0.912),
        )
        self.armor_bar = DirectFrame(
            parent=self.hud_root,
            frameColor=BLUE,
            frameSize=(-1.62, -0.96, -0.94, -0.912),
        )
        self.health_label = DirectLabel(
            parent=self.hud_root,
            text="100 HP",
            text_fg=WHITE,
            text_scale=0.033,
            text_align=TextNode.ALeft,
            frameColor=(0, 0, 0, 0),
            pos=(-1.60, 0, -0.79),
        )
        self.ammo_label = DirectLabel(
            parent=self.hud_root,
            text="30 / 150",
            text_fg=WHITE,
            text_scale=0.060,
            text_align=TextNode.ARight,
            frameColor=(0, 0, 0, 0),
            pos=(1.58, 0, -0.85),
        )
        self.weapon_label = DirectLabel(
            parent=self.hud_root,
            text=f"{self.weapon_name} // ASSAULT",
            text_fg=MUTED,
            text_scale=0.026,
            text_align=TextNode.ARight,
            frameColor=(0, 0, 0, 0),
            pos=(1.58, 0, -0.93),
        )
        self.score_label = DirectLabel(
            parent=self.hud_root,
            text="SCORE 0",
            text_fg=WHITE,
            text_scale=0.040,
            text_align=TextNode.ARight,
            frameColor=(0, 0, 0, 0),
            pos=(1.58, 0, 0.88),
        )
        self.wave_label = DirectLabel(
            parent=self.hud_root,
            text="WAVE 01",
            text_fg=CYAN,
            text_scale=0.034,
            text_align=TextNode.ARight,
            frameColor=(0, 0, 0, 0),
            pos=(1.58, 0, 0.80),
        )
        self.combo_label = DirectLabel(
            parent=self.hud_root,
            text="",
            text_fg=ORANGE,
            text_scale=0.035,
            text_align=TextNode.ARight,
            frameColor=(0, 0, 0, 0),
            pos=(1.58, 0, 0.71),
        )
        self.crosshair_parts = []
        for frame_size in [(-0.040, -0.013, -0.003, 0.003), (0.013, 0.040, -0.003, 0.003), (-0.003, 0.003, 0.013, 0.040), (-0.003, 0.003, -0.040, -0.013)]:
            self.crosshair_parts.append(DirectFrame(parent=self.hud_root, frameColor=WHITE, frameSize=frame_size))
        self.hitmarker_parts = []
        for x, z in [(-0.018, 0.018), (0.018, 0.018), (-0.018, -0.018), (0.018, -0.018)]:
            mark = DirectFrame(parent=self.hud_root, frameColor=(1, 1, 1, 0), frameSize=(-0.012, 0.012, -0.0018, 0.0018), pos=(x, 0, z))
            mark.setR(45 if x * z > 0 else -45)
            self.hitmarker_parts.append(mark)
        self.damage_overlay = DirectFrame(
            parent=self.hud_root,
            frameColor=(0.8, 0.02, 0.02, 0),
            frameSize=(-1.8, 1.8, -1.05, 1.05),
            sortOrder=-1,
        )
        self.reload_label = DirectLabel(
            parent=self.hud_root,
            text="",
            text_fg=CYAN,
            text_scale=0.034,
            frameColor=(0, 0, 0, 0),
            pos=(0, 0, -0.18),
        )

    def _start_wave(self) -> None:
        self.wave += 1
        self.enemies_to_spawn = 4 + self.wave * 2
        self.wave_spawn_timer = 0.4
        self.app.save.max_stat(self.game_id, "best_wave", self.wave)
        self.wave_label["text"] = f"WAVE {self.wave:02d}"
        self.spawn_floating_text(f"WAVE {self.wave:02d}", (0, 0.34), CYAN, 0.075, 1.4)

    def _spawn_enemy(self) -> None:
        possible = sorted(self.spawn_points, key=lambda p: -(p - self.player_pos).length())
        spawn = Vec3(random.choice(possible[: max(3, len(possible) // 2)]))
        elite_chance = min(0.35, 0.04 + self.wave * 0.025)
        elite = random.random() < elite_chance
        profile = neon_enemy_for_wave(self.wave, elite)
        health = profile.health * self.difficulty_scale * (1.35 if elite else 1.0)
        primary = ORANGE if elite else profile.primary
        secondary = RED if elite else profile.secondary
        rig = CharacterRig(self.actor_root, "enemy", spawn, primary, secondary, profile.scale * (1.08 if elite else 1.0))
        enemy = Enemy(
            rig=rig,
            health=health,
            max_health=health,
            speed=profile.speed * (1.08 if elite else 1.0),
            damage=profile.damage * self.difficulty_scale * (1.25 if elite else 1.0),
            fire_interval=max(0.42, profile.fire_interval) * (0.8 if elite else 1.0),
            fire_timer=random.uniform(0.2, 1.0),
            radius=0.58 if elite else 0.48,
            elite=elite,
            strafe_phase=random.uniform(0, math.tau),
        )
        self.enemies.append(enemy)

    def _handle_mouse_look(self) -> None:
        delta = self.mouse_delta()
        sensitivity = float(self.app.save.setting("mouse_sensitivity", 0.18))
        self.yaw -= delta.x * sensitivity
        self.pitch = clamp(self.pitch - delta.y * sensitivity, -78.0, 78.0)

    def _move_player(self, dt: float) -> None:
        forward = heading_vector(self.yaw)
        right = right_vector(self.yaw)
        move = Vec3(0)
        if self.key["w"]:
            move += forward
        if self.key["s"]:
            move -= forward
        if self.key["d"]:
            move += right
        if self.key["a"]:
            move -= right
        if move.lengthSquared() > 0.001:
            move.normalize()
        speed = self.sprint_speed if self.key["shift"] and self.key["w"] else self.walk_speed

        self.dash_cooldown = max(0.0, self.dash_cooldown - dt)
        if self.key["space"] and self.dash_cooldown <= 0 and self.dash_timer <= 0:
            self.dash_direction = Vec3(move if move.lengthSquared() > 0.1 else forward)
            self.dash_timer = self.dash_duration
            self.dash_cooldown = 1.35
            self.app.audio.play("dash", self.app.sfx_volume() * 0.55)
            self.camera_shake.add(0.20)

        if self.dash_timer > 0:
            self.dash_timer -= dt
            delta = self.dash_direction * 26.0 * dt
        else:
            delta = move * speed * dt
        self.player_pos = self.move_with_collisions(self.player_pos, delta, self.player_half)

        bob_amount = min(1.0, move.length())
        bob = math.sin(self.elapsed * (12 if speed > self.walk_speed else 9)) * 0.035 * bob_amount
        shake_pos, shake_hpr = self.camera_shake.update(dt)
        self.camera.setPos(self.player_pos + Vec3(0, 0, 0.68 + bob) + shake_pos)
        self.camera.setHpr(self.yaw + shake_hpr.x, self.pitch + shake_hpr.y, shake_hpr.z)
        strafe = (1 if self.key["d"] else 0) - (1 if self.key["a"] else 0)
        target_roll = -strafe * 2.0
        self.weapon_root.setR(damp(self.weapon_root.getR(), target_roll, 12.0, dt))
        self.weapon_root.setZ(math.sin(self.elapsed * 10.0) * 0.010 * bob_amount)

    def _try_fire(self) -> None:
        if self.reloading or self.fire_timer > 0 or not self.key["mouse1"]:
            return
        if self.ammo <= 0:
            self._start_reload()
            return
        self.fire_timer = self.fire_interval
        self.ammo -= 1
        self.muzzle_timer = 0.045
        self.crosshair_kick = min(0.045, self.crosshair_kick + 0.010)
        self.muzzle.show()
        self.app.audio.play("shot", self.app.sfx_volume() * 0.48, random.uniform(0.93, 1.08))
        self.camera_shake.add(0.08)

        spread_x = random.uniform(-self.weapon_spread, self.weapon_spread)
        spread_z = random.uniform(-self.weapon_spread, self.weapon_spread)
        direction = yaw_pitch_forward(self.yaw + spread_x * 50, self.pitch + spread_z * 50)
        origin = self.camera.getPos(self.root)
        best_enemy: Optional[Enemy] = None
        best_along = 9999.0
        headshot = False
        for enemy in self.enemies:
            if not enemy.alive:
                continue
            target = enemy.rig.get_pos() + Vec3(0, 0, 1.25)
            distance, along = segment_point_distance(origin, direction, target)
            if along < 0 or along > 90:
                continue
            threshold = 0.66 if enemy.elite else 0.58
            if distance <= threshold and along < best_along:
                best_enemy = enemy
                best_along = along
                head_distance, _ = segment_point_distance(origin, direction, enemy.rig.get_pos() + Vec3(0, 0, 1.95))
                headshot = head_distance <= 0.28
        if best_enemy is not None:
            damage = self.weapon_damage * (1.75 if headshot else 1.0)
            self._damage_enemy(best_enemy, damage, headshot)

    def _damage_enemy(self, enemy: Enemy, damage: float, headshot: bool) -> None:
        enemy.health -= damage
        enemy.hurt_timer = 0.08
        enemy.rig.flash(WHITE, 0.55)
        impact = enemy.rig.get_pos() + Vec3(0, 0, 1.6 if headshot else 1.1)
        self.particles.sparks(impact, CYAN if not enemy.elite else ORANGE, 9 if not headshot else 14)
        self.hitmarker_timer = 0.10
        self.combo += 1
        self.best_combo = max(self.best_combo, self.combo)
        self.score += 15 if headshot else 8
        if headshot:
            self.spawn_floating_text("HEADSHOT", (0.0, 0.12), ORANGE, 0.035, 0.55)
        if enemy.health <= 0:
            self._kill_enemy(enemy, headshot)

    def _kill_enemy(self, enemy: Enemy, headshot: bool) -> None:
        enemy.alive = False
        position = enemy.rig.get_pos()
        reward = 220 if enemy.elite else 100
        if headshot:
            reward += 65
        reward += min(250, self.combo * 5)
        self.score += reward
        self.app.save.add_stat(self.game_id, "kills", 1)
        self.particles.explosion(position + Vec3(0, 0, 1), CYAN if not enemy.elite else ORANGE, BLUE if not enemy.elite else RED)
        self.pulses.emit(position + Vec3(0, 0, 0.1), CYAN if not enemy.elite else ORANGE, 0.4, 2.5, 0.35)
        enemy.rig.destroy()
        if random.random() < 0.20:
            roll = random.random()
            if roll < 0.45:
                self.spawn_pickup(position + Vec3(0, 0, 0.6), "ammo", 35, CYAN)
            elif roll < 0.75:
                self.spawn_pickup(position + Vec3(0, 0, 0.6), "armor", 25, BLUE)
            else:
                self.spawn_pickup(position + Vec3(0, 0, 0.6), "health", 28, GREEN)

    def _start_reload(self) -> None:
        if self.reloading or self.ammo >= self.magazine_size or self.reserve_ammo <= 0:
            return
        self.reloading = True
        self.reload_timer = self.reload_time
        self.app.audio.play("reload", self.app.sfx_volume() * 0.45)

    def _finish_reload(self) -> None:
        needed = self.magazine_size - self.ammo
        loaded = min(needed, self.reserve_ammo)
        self.ammo += loaded
        self.reserve_ammo -= loaded
        self.reloading = False
        self.reload_timer = 0

    def _enemy_fire(self, enemy: Enemy) -> None:
        origin = enemy.rig.get_pos() + Vec3(0, 0, 1.4)
        target = self.player_pos + Vec3(0, 0, 0.8)
        direction = target - origin
        distance = direction.length()
        if distance <= 0.01:
            return
        direction.normalize()
        spread = min(0.18, 0.025 + distance * 0.0012)
        direction += Vec3(random.uniform(-spread, spread), random.uniform(-spread, spread), random.uniform(-spread * 0.6, spread * 0.6))
        direction.normalize()
        self.spawn_projectile(
            origin,
            direction,
            24.0,
            enemy.damage,
            ORANGE if enemy.elite else RED,
            "enemy",
            radius=0.18,
            lifetime=3.4,
            scale=0.11 if enemy.elite else 0.075,
        )

    def _update_enemies(self, dt: float) -> None:
        alive: List[Enemy] = []
        for enemy in self.enemies:
            if not enemy.alive or enemy.rig.root.isEmpty():
                continue
            if enemy.hurt_timer > 0:
                enemy.hurt_timer -= dt
                if enemy.hurt_timer <= 0:
                    enemy.rig.clear_flash()

            pos = enemy.rig.get_pos()
            to_player = self.player_pos - pos
            distance = max(0.001, to_player.length())
            flat = Vec3(to_player.x, to_player.y, 0)
            if flat.lengthSquared() > 0.001:
                flat.normalize()
            heading = math.degrees(math.atan2(flat.x, flat.y))
            enemy.rig.face_heading(heading)
            enemy.strafe_phase += dt * (1.2 + enemy.speed * 0.05)
            strafe = right_vector(heading) * math.sin(enemy.strafe_phase) * 0.45
            if distance > 9.5:
                move = (flat + strafe).normalized() * enemy.speed * dt
                candidate = self.move_with_collisions(pos, move, Vec3(0.40, 0.40, 1.0))
                enemy.rig.set_pos(candidate)
                enemy.rig.animate_walk(dt, 1.0)
            else:
                enemy.rig.animate_walk(dt, 0.15)

            enemy.fire_timer -= dt
            if distance < 35 and enemy.fire_timer <= 0:
                enemy.fire_timer = enemy.fire_interval * random.uniform(0.82, 1.25)
                self._enemy_fire(enemy)
            alive.append(enemy)
        self.enemies = alive

    def _projectile_collision(self, projectile: Projectile) -> bool:
        pos = projectile.node.getPos(self.root)
        if projectile.team == "enemy":
            if (pos - (self.player_pos + Vec3(0, 0, 0.8))).length() <= projectile.radius + 0.55:
                self._damage_player(projectile.damage)
                self.particles.sparks(pos, projectile.color, 8)
                return True
        if self.position_blocked(pos, Vec3(projectile.radius), ("solid",)):
            self.particles.sparks(pos, projectile.color, 5)
            return True
        return False

    def _damage_player(self, amount: float) -> None:
        if self.game_over:
            return
        remaining = amount
        if self.armor > 0:
            absorbed = min(self.armor, remaining * 0.78)
            self.armor -= absorbed
            remaining -= absorbed
        self.health -= max(0, remaining)
        self.damage_vignette = min(0.55, self.damage_vignette + 0.25)
        self.camera_shake.add(0.30)
        self.combo = max(0, self.combo - 2)
        if self.health <= 0:
            self.health = 0
            self.finish_game("OPERATIVE DOWN")

    def _collect_pickup(self, pickup: Pickup) -> None:
        if pickup.kind == "health":
            self.health = min(100.0, self.health + pickup.amount)
            text = f"+{int(pickup.amount)} HEALTH"
        elif pickup.kind == "armor":
            self.armor = min(100.0, self.armor + pickup.amount)
            text = f"+{int(pickup.amount)} ARMOR"
        else:
            self.reserve_ammo = min(360, self.reserve_ammo + int(pickup.amount))
            text = f"+{int(pickup.amount)} AMMO"
        self.spawn_floating_text(text, (0.0, -0.08), GREEN if pickup.kind == "health" else CYAN, 0.033, 0.65)
        self.app.audio.play("pickup", self.app.sfx_volume() * 0.48)

    def _update_hud(self, dt: float) -> None:
        health_t = clamp(self.health / 100.0, 0, 1)
        armor_t = clamp(self.armor / 100.0, 0, 1)
        self.health_bar["frameSize"] = (-1.62, -1.62 + 0.84 * health_t, -0.88, -0.835)
        self.armor_bar["frameSize"] = (-1.62, -1.62 + 0.66 * armor_t, -0.94, -0.912)
        self.health_bar["frameColor"] = CYAN if self.health > 30 else RED
        self.health_label["text"] = f"{int(self.health):03d} HP   //   {int(self.armor):03d} ARM"
        self.ammo_label["text"] = f"{self.ammo:02d} / {self.reserve_ammo:03d}"
        self.score_label["text"] = f"SCORE {int(self.score):,}"
        self.combo_label["text"] = f"COMBO x{self.combo}" if self.combo >= 2 else ""
        self.reload_label["text"] = f"RELOADING  {self.reload_timer:.1f}s" if self.reloading else ""

        self.crosshair_kick = damp(self.crosshair_kick, 0.0, 11.0, dt)
        gap = self.crosshair_kick
        base = 0.013 + gap
        outer = 0.040 + gap
        frames = [
            (-outer, -base, -0.003, 0.003),
            (base, outer, -0.003, 0.003),
            (-0.003, 0.003, base, outer),
            (-0.003, 0.003, -outer, -base),
        ]
        for node, frame in zip(self.crosshair_parts, frames):
            node["frameSize"] = frame

        self.hitmarker_timer = max(0.0, self.hitmarker_timer - dt)
        alpha = clamp(self.hitmarker_timer / 0.10, 0, 1)
        for mark in self.hitmarker_parts:
            mark["frameColor"] = (1, 1, 1, alpha)

        self.damage_vignette = damp(self.damage_vignette, 0.0, 4.0, dt)
        self.damage_overlay["frameColor"] = (0.72, 0.01, 0.02, self.damage_vignette * 0.45)

    def on_resume(self) -> None:
        self.set_mouse_capture(True)

    def update(self, dt: float) -> None:
        if self.paused or self.game_over:
            self.tick_common(dt)
            return
        self.elapsed += dt
        self.fire_timer = max(0.0, self.fire_timer - dt)
        self.muzzle_timer = max(0.0, self.muzzle_timer - dt)
        if self.muzzle_timer <= 0:
            self.muzzle.hide()

        self._handle_mouse_look()
        self._move_player(dt)

        if self.key["r"]:
            self._start_reload()

        if self.reloading:
            self.reload_timer -= dt
            if self.reload_timer <= 0:
                self._finish_reload()
        else:
            self._try_fire()

        if self.enemies_to_spawn > 0:
            self.wave_spawn_timer -= dt
            if self.wave_spawn_timer <= 0:
                self.wave_spawn_timer = self.spawn_interval
                self._spawn_enemy()
                self.enemies_to_spawn -= 1
        elif not self.enemies:
            self.wave_delay -= dt
            if self.wave_delay <= 0:
                self.wave_delay = 1.4
                self._start_wave()

        self._update_enemies(dt)
        self.update_projectiles(dt, self._projectile_collision)
        self.update_pickups(dt, self.player_pos, self._collect_pickup)
        self._update_hud(dt)
        self.tick_common(dt)

    def destroy(self) -> None:
        if hasattr(self, "weapon_root") and not self.weapon_root.isEmpty():
            self.weapon_root.removeNode()
        super().destroy()
