from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List, Optional, Tuple

from direct.gui.DirectGui import DirectFrame, DirectLabel
from panda3d.core import TextNode, Vec3

from ..config import CYAN, GREEN, MUTED, ORANGE, RED, WHITE, YELLOW
from ..data.content_catalog import zombie_for_wave
from ..math3d import clamp, damp, damp_vec3, distance_2d, heading_vector, right_vector, segment_point_distance
from ..primitives import make_box, make_grid, make_plane
from ..world import BaseMode, CharacterRig, Pickup, Projectile

Color = Tuple[float, float, float, float]


@dataclass
class Zombie:
    rig: CharacterRig
    health: float
    max_health: float
    speed: float
    damage: float
    radius: float
    kind: str
    attack_timer: float
    stagger: float = 0.0
    hurt_timer: float = 0.0
    alive: bool = True


class ZombieSiege(BaseMode):
    game_id = "zombie_siege"

    def __init__(self, app) -> None:
        super().__init__(app)
        self.elapsed = 0.0
        self.player_pos = Vec3(0, 0, 0.9)
        self.player_half = Vec3(0.45, 0.45, 0.9)
        self.player_heading = 0.0
        self.health = 100.0
        self.armor = 35.0
        self.medkits = 2
        self.stamina = 100.0
        self.mag_size = 8
        self.ammo = 8
        self.reserve = 48
        self.reload_timer = 0.0
        self.reload_time = 1.65
        self.reloading = False
        self.shot_timer = 0.0
        self.shot_interval = 0.46
        self.damage = 46.0
        self.wave = 0
        self.spawn_remaining = 0
        self.spawn_timer = 0.0
        self.wave_break = 0.8
        self.zombies: List[Zombie] = []
        self.damage_alpha = 0.0
        self.hitmarker_timer = 0.0
        self.last_mouse_world = Vec3(0, 10, 0)
        self._build_world()
        self._build_hud()
        self._start_wave()

    def _build_world(self) -> None:
        self.base.setBackgroundColor(0.008, 0.012, 0.008, 1)
        self.add_standard_lighting(
            ambient=(0.11, 0.14, 0.11, 1),
            sun=(0.42, 0.54, 0.36, 1),
            hpr=(-32, -62, 0),
        )
        self.set_fog((0.012, 0.022, 0.014, 1), 0.016)
        make_plane("district-floor", 100, 100, (0.022, 0.029, 0.023, 1), self.world_root, 0)
        make_grid("district-grid", 25, 2.0, (0.05, 0.11, 0.05, 0.35), self.world_root, 0.012)

        self.player = CharacterRig(
            self.actor_root,
            "survivor",
            self.player_pos,
            (0.13, 0.16, 0.19, 1),
            (0.18, 0.30, 0.18, 1),
            1.0,
        )
        self.player.weapon.setScale(1.0, 1.25, 1.0)

        wall_color = (0.055, 0.060, 0.052, 1)
        for x, y, sx, sy, sz in [
            (-22, 13, 7, 4, 4), (20, 15, 5, 9, 5), (3, 24, 10, 3, 3),
            (-17, -17, 5, 10, 4), (18, -20, 8, 4, 3), (0, -28, 13, 3, 4),
            (-31, 0, 3, 11, 5), (31, 1, 3, 12, 5), (-4, 5, 6, 3, 2),
        ]:
            building = self.add_solid_box("ruin", Vec3(x, y, sz * 0.5), Vec3(sx, sy, sz), wall_color)
            make_box("rust", (sx * 0.75, sy * 1.01, 0.07), (0.23, 0.10, 0.035, 0.75), building, (0, 0, sz * 0.25))

        for index in range(18):
            rng = random.Random(8100 + index)
            x = rng.uniform(-39, 39)
            y = rng.uniform(-39, 39)
            if abs(x) < 8 and abs(y) < 8:
                x += 12 if x >= 0 else -12
            h = rng.uniform(1.0, 2.2)
            crate = self.add_solid_box("barricade", Vec3(x, y, h * 0.5), Vec3(rng.uniform(1.4, 3.4), rng.uniform(1.0, 2.0), h), (0.10, 0.075, 0.045, 1))
            if index % 3 == 0:
                make_box("warning", (1.0, 0.04, 0.10), YELLOW, crate, (0, -0.52, 0.15))

        self.spawn_points = [
            Vec3(-42, -42, 0), Vec3(0, -44, 0), Vec3(42, -42, 0),
            Vec3(-44, 0, 0), Vec3(44, 0, 0), Vec3(-42, 42, 0),
            Vec3(0, 44, 0), Vec3(42, 42, 0),
        ]
        self.add_point_light("sick-green", Vec3(-18, 4, 6), (0.16, 0.45, 0.10, 1), (1, 0.04, 0.006))
        self.add_point_light("burning-orange", Vec3(22, -15, 5), (0.65, 0.20, 0.03, 1), (1, 0.04, 0.006))
        self.camera.setPos(0, -15, 13)
        self.camera.setHpr(0, -42, 0)

    def _build_hud(self) -> None:
        self.health_bg = DirectFrame(parent=self.hud_root, frameColor=(0.05, 0.06, 0.05, 0.94), frameSize=(-1.62, -0.74, -0.91, -0.86))
        self.health_bar = DirectFrame(parent=self.hud_root, frameColor=GREEN, frameSize=(-1.62, -0.74, -0.91, -0.86))
        self.stamina_bg = DirectFrame(parent=self.hud_root, frameColor=(0.05, 0.06, 0.05, 0.94), frameSize=(-1.62, -0.86, -0.82, -0.79))
        self.stamina_bar = DirectFrame(parent=self.hud_root, frameColor=YELLOW, frameSize=(-1.62, -0.86, -0.82, -0.79))
        self.health_label = DirectLabel(parent=self.hud_root, text="100 HP", text_fg=WHITE, text_scale=0.034, text_align=TextNode.ALeft, frameColor=(0,0,0,0), pos=(-1.60,0,-0.75))
        self.ammo_label = DirectLabel(parent=self.hud_root, text="08 / 48", text_fg=WHITE, text_scale=0.060, text_align=TextNode.ARight, frameColor=(0,0,0,0), pos=(1.58,0,-0.86))
        self.medkit_label = DirectLabel(parent=self.hud_root, text="MEDKITS 2", text_fg=GREEN, text_scale=0.029, text_align=TextNode.ARight, frameColor=(0,0,0,0), pos=(1.58,0,-0.94))
        self.score_label = DirectLabel(parent=self.hud_root, text="SCORE 0", text_fg=WHITE, text_scale=0.039, text_align=TextNode.ARight, frameColor=(0,0,0,0), pos=(1.58,0,0.88))
        self.wave_label = DirectLabel(parent=self.hud_root, text="NIGHT 01", text_fg=GREEN, text_scale=0.034, text_align=TextNode.ARight, frameColor=(0,0,0,0), pos=(1.58,0,0.80))
        self.combo_label = DirectLabel(parent=self.hud_root, text="", text_fg=ORANGE, text_scale=0.035, text_align=TextNode.ARight, frameColor=(0,0,0,0), pos=(1.58,0,0.72))
        self.reload_label = DirectLabel(parent=self.hud_root, text="", text_fg=YELLOW, text_scale=0.034, frameColor=(0,0,0,0), pos=(0,0,-0.17))
        self.crosshair = []
        for fs in [(-0.034,-0.010,-0.003,0.003),(0.010,0.034,-0.003,0.003),(-0.003,0.003,0.010,0.034),(-0.003,0.003,-0.034,-0.010)]:
            self.crosshair.append(DirectFrame(parent=self.hud_root, frameColor=WHITE, frameSize=fs))
        self.damage_overlay = DirectFrame(parent=self.hud_root, frameColor=(0.65,0.02,0.02,0), frameSize=(-1.8,1.8,-1.05,1.05), sortOrder=-1)

    def _start_wave(self) -> None:
        self.wave += 1
        self.spawn_remaining = 5 + self.wave * 3
        self.spawn_timer = 0.3
        self.wave_break = 1.4
        self.wave_label["text"] = f"NIGHT {self.wave:02d}"
        self.spawn_floating_text(f"NIGHT {self.wave:02d}", (0,0.35), GREEN, 0.072, 1.35)
        self.app.save.max_stat(self.game_id, "best_wave", self.wave)

    def _spawn_zombie(self) -> None:
        spawn = max(self.spawn_points, key=lambda p: (p - self.player_pos).length() + random.uniform(-9,9))
        spawn = Vec3(spawn) + Vec3(random.uniform(-3,3), random.uniform(-3,3), 0)
        roll = random.random()
        if roll < min(0.18, 0.035 + self.wave * 0.012):
            kind = "brute"
            health_mul, speed_mul, damage_mul, scale = 2.9, 0.72, 1.8, 1.42
            primary, secondary = (0.22,0.12,0.08,1), ORANGE
        elif roll < min(0.38, 0.12 + self.wave * 0.018):
            kind = "runner"
            health_mul, speed_mul, damage_mul, scale = 0.70, 1.72, 0.78, 0.88
            primary, secondary = (0.08,0.18,0.08,1), GREEN
        else:
            kind = "walker"
            health_mul, speed_mul, damage_mul, scale = 1.0, 1.0, 1.0, 1.0
            primary, secondary = (0.10,0.14,0.09,1), (0.28,0.34,0.18,1)
        profile = zombie_for_wave(self.wave)
        health = profile.health * health_mul * self.difficulty_scale
        primary = tuple((primary[i] + profile.primary[i]) * 0.5 for i in range(3)) + (1.0,)
        secondary = tuple((secondary[i] + profile.secondary[i]) * 0.5 for i in range(3)) + (1.0,)
        rig = CharacterRig(self.actor_root, "infected", spawn, primary, secondary, scale * profile.scale)
        rig.weapon.hide()
        zombie = Zombie(
            rig=rig,
            health=health,
            max_health=health,
            speed=profile.speed * speed_mul,
            damage=profile.damage * damage_mul * self.difficulty_scale,
            radius=0.48 * scale,
            kind=kind,
            attack_timer=random.uniform(0.2,0.9),
        )
        self.zombies.append(zombie)

    def _screen_mouse_world(self) -> Vec3:
        if not self.base.mouseWatcherNode.hasMouse():
            return Vec3(self.last_mouse_world)
        mouse = self.base.mouseWatcherNode.getMouse()
        # This maps normalized screen coordinates into the ground plane relative to the player.
        forward = Vec3(0, 1, 0)
        right = Vec3(1, 0, 0)
        target = self.player_pos + forward * (12.0 + mouse.y * 8.0) + right * (mouse.x * 16.0)
        target.z = 0
        self.last_mouse_world = Vec3(target)
        return target

    def _update_player(self, dt: float) -> None:
        move = Vec3(
            (1 if self.key["d"] else 0) - (1 if self.key["a"] else 0),
            (1 if self.key["w"] else 0) - (1 if self.key["s"] else 0),
            0,
        )
        if move.lengthSquared() > 0.001:
            move.normalize()
        sprinting = bool(self.key["shift"] and self.stamina > 1 and move.lengthSquared() > 0.1)
        speed = 8.8 if sprinting else 5.9
        if sprinting:
            self.stamina = max(0.0, self.stamina - 27.0 * dt)
        else:
            self.stamina = min(100.0, self.stamina + 18.0 * dt)
        self.player_pos = self.move_with_collisions(self.player_pos, move * speed * dt, self.player_half)
        self.player.set_pos(self.player_pos)
        aim = self._screen_mouse_world() - self.player_pos
        if aim.lengthSquared() > 0.01:
            self.player_heading = math.degrees(math.atan2(aim.x, aim.y))
        self.player.face_heading(self.player_heading)
        self.player.animate_walk(dt, 1.0 if move.lengthSquared() > 0.1 else 0.08)

        camera_target = self.player_pos + Vec3(0, -15, 13)
        self.camera.setPos(damp_vec3(self.camera.getPos(), camera_target, 7.0, dt))
        self.camera.lookAt(self.player_pos + Vec3(0, 2.2, 0.4))
        shake_pos, shake_hpr = self.camera_shake.update(dt)
        self.camera.setPos(self.camera.getPos() + shake_pos)
        self.camera.setHpr(self.camera.getHpr() + shake_hpr)

    def _start_reload(self) -> None:
        if self.reloading or self.ammo >= self.mag_size or self.reserve <= 0:
            return
        self.reloading = True
        self.reload_timer = self.reload_time
        self.app.audio.play("reload", self.app.sfx_volume() * 0.45)

    def _finish_reload(self) -> None:
        need = self.mag_size - self.ammo
        loaded = min(need, self.reserve)
        self.ammo += loaded
        self.reserve -= loaded
        self.reloading = False
        self.reload_timer = 0

    def _shoot(self) -> None:
        if self.reloading or self.shot_timer > 0 or not self.key["mouse1"]:
            return
        if self.ammo <= 0:
            self._start_reload()
            return
        self.shot_timer = self.shot_interval
        self.ammo -= 1
        self.camera_shake.add(0.18)
        self.app.audio.play("shot", self.app.sfx_volume() * 0.55, random.uniform(0.82,0.93))
        origin = self.player_pos + Vec3(0,0,1.35) + heading_vector(self.player_heading) * 0.5
        direction = heading_vector(self.player_heading)
        pellets = 7
        hit_any = False
        for pellet in range(pellets):
            spread = random.uniform(-7.5, 7.5)
            dir_pellet = heading_vector(self.player_heading + spread)
            best: Optional[Zombie] = None
            best_along = 999
            for zombie in self.zombies:
                if not zombie.alive:
                    continue
                target = zombie.rig.get_pos() + Vec3(0,0,1.1)
                dist, along = segment_point_distance(origin, dir_pellet, target)
                if 0 < along < 28 and dist <= zombie.radius + 0.35 and along < best_along:
                    best = zombie
                    best_along = along
            if best:
                hit_any = True
                self._damage_zombie(best, self.damage / pellets * random.uniform(0.82,1.14))
        self.particles.burst(origin + direction * 0.7, ORANGE, count=5, speed=4, lifetime=0.22, size=0.035, gravity=1)
        if hit_any:
            self.hitmarker_timer = 0.10

    def _damage_zombie(self, zombie: Zombie, damage: float) -> None:
        zombie.health -= damage
        zombie.stagger = min(0.34, zombie.stagger + 0.08)
        zombie.hurt_timer = 0.08
        zombie.rig.flash(WHITE, 0.45)
        self.particles.sparks(zombie.rig.get_pos() + Vec3(0,0,1.0), GREEN if zombie.kind != "brute" else ORANGE, 5)
        if zombie.health <= 0:
            self._kill_zombie(zombie)

    def _kill_zombie(self, zombie: Zombie) -> None:
        zombie.alive = False
        pos = zombie.rig.get_pos()
        reward = {"walker": 95, "runner": 135, "brute": 320}.get(zombie.kind, 100)
        self.combo += 1
        self.best_combo = max(self.best_combo, self.combo)
        self.score += reward + min(300, self.combo * 7)
        self.app.save.add_stat(self.game_id, "kills", 1)
        self.particles.explosion(pos + Vec3(0,0,0.9), GREEN if zombie.kind != "brute" else ORANGE, (0.28,0.42,0.12,1))
        zombie.rig.destroy()
        if random.random() < 0.22:
            roll = random.random()
            if roll < 0.48:
                self.spawn_pickup(pos + Vec3(0,0,0.6), "ammo", 10, YELLOW)
            elif roll < 0.72:
                self.spawn_pickup(pos + Vec3(0,0,0.6), "health", 24, GREEN)
            elif roll < 0.90:
                self.spawn_pickup(pos + Vec3(0,0,0.6), "armor", 22, CYAN)
            else:
                self.spawn_pickup(pos + Vec3(0,0,0.6), "medkit", 1, ORANGE)

    def _update_zombies(self, dt: float) -> None:
        alive: List[Zombie] = []
        for zombie in self.zombies:
            if not zombie.alive or zombie.rig.root.isEmpty():
                continue
            if zombie.hurt_timer > 0:
                zombie.hurt_timer -= dt
                if zombie.hurt_timer <= 0:
                    zombie.rig.clear_flash()
            zombie.stagger = max(0.0, zombie.stagger - dt)
            pos = zombie.rig.get_pos()
            to_player = self.player_pos - pos
            distance = max(0.01, to_player.length())
            flat = Vec3(to_player.x,to_player.y,0)
            if flat.lengthSquared() > 0.001:
                flat.normalize()
            heading = math.degrees(math.atan2(flat.x, flat.y))
            zombie.rig.face_heading(heading)
            if distance > 1.2 + zombie.radius:
                multiplier = 0.25 if zombie.stagger > 0 else 1.0
                move = flat * zombie.speed * multiplier * dt
                new_pos = self.move_with_collisions(pos, move, Vec3(zombie.radius * 0.7, zombie.radius * 0.7, 0.8))
                zombie.rig.set_pos(new_pos)
                zombie.rig.animate_walk(dt, multiplier)
            else:
                zombie.rig.animate_walk(dt, 0.15)
                zombie.attack_timer -= dt
                if zombie.attack_timer <= 0:
                    zombie.attack_timer = random.uniform(0.75,1.25)
                    self._damage_player(zombie.damage)
            alive.append(zombie)
        self.zombies = alive

    def _damage_player(self, amount: float) -> None:
        remaining = amount
        if self.armor > 0:
            absorb = min(self.armor, remaining * 0.55)
            self.armor -= absorb
            remaining -= absorb
        self.health -= max(0, remaining)
        self.damage_alpha = min(0.8, self.damage_alpha + 0.42)
        self.camera_shake.add(0.48)
        self.combo = max(0, self.combo - 2)
        if self.health <= 0:
            self.health = 0
            self.finish_game("OVERRUN")

    def _use_medkit(self) -> None:
        if self.medkits <= 0 or self.health >= 95:
            return
        self.medkits -= 1
        self.health = min(100.0, self.health + 54.0)
        self.spawn_floating_text("MEDKIT +54", (0,-0.08), GREEN, 0.034, 0.7)
        self.app.audio.play("pickup", self.app.sfx_volume() * 0.6)

    def _collect_pickup(self, pickup: Pickup) -> None:
        if pickup.kind == "ammo":
            self.reserve = min(96, self.reserve + int(pickup.amount))
            text = f"+{int(pickup.amount)} SHELLS"
        elif pickup.kind == "health":
            self.health = min(100, self.health + pickup.amount)
            text = f"+{int(pickup.amount)} HEALTH"
        elif pickup.kind == "armor":
            self.armor = min(100, self.armor + pickup.amount)
            text = f"+{int(pickup.amount)} ARMOR"
        else:
            self.medkits = min(5, self.medkits + int(pickup.amount))
            text = "+1 MEDKIT"
        self.spawn_floating_text(text, (0,-0.08), GREEN, 0.032, 0.65)
        self.app.audio.play("pickup", self.app.sfx_volume() * 0.48)

    def _update_hud(self, dt: float) -> None:
        ht = clamp(self.health/100,0,1)
        st = clamp(self.stamina/100,0,1)
        self.health_bar["frameSize"] = (-1.62,-1.62+0.88*ht,-0.91,-0.86)
        self.health_bar["frameColor"] = GREEN if self.health > 30 else RED
        self.stamina_bar["frameSize"] = (-1.62,-1.62+0.76*st,-0.82,-0.79)
        self.health_label["text"] = f"{int(self.health):03d} HP   //   {int(self.armor):03d} ARM"
        self.ammo_label["text"] = f"{self.ammo:02d} / {self.reserve:02d}"
        self.medkit_label["text"] = f"MEDKITS {self.medkits}"
        self.score_label["text"] = f"SCORE {int(self.score):,}"
        self.combo_label["text"] = f"KILL CHAIN x{self.combo}" if self.combo >= 2 else ""
        self.reload_label["text"] = f"RELOADING {self.reload_timer:.1f}s" if self.reloading else ""
        self.damage_alpha = damp(self.damage_alpha,0,4.0,dt)
        self.damage_overlay["frameColor"] = (0.65,0.01,0.02,self.damage_alpha*0.42)

    def update(self, dt: float) -> None:
        if self.paused or self.game_over:
            self.tick_common(dt)
            return
        self.elapsed += dt
        self.shot_timer = max(0,self.shot_timer-dt)
        self._update_player(dt)
        if self.key["r"]:
            self._start_reload()
        if self.key["q"]:
            self._use_medkit()
        if self.reloading:
            self.reload_timer -= dt
            if self.reload_timer <= 0:
                self._finish_reload()
        else:
            self._shoot()

        if self.spawn_remaining > 0:
            self.spawn_timer -= dt
            if self.spawn_timer <= 0:
                self.spawn_timer = max(0.18, 0.72 - self.wave * 0.018) / self.difficulty_scale
                self._spawn_zombie()
                self.spawn_remaining -= 1
        elif not self.zombies:
            self.wave_break -= dt
            if self.wave_break <= 0:
                self._start_wave()

        self._update_zombies(dt)
        self.update_pickups(dt,self.player_pos,self._collect_pickup)
        self._update_hud(dt)
        self.tick_common(dt)

    def destroy(self) -> None:
        try:
            self.player.destroy()
        except Exception:
            pass
        super().destroy()
