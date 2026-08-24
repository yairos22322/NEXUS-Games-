from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List, Optional, Tuple

from direct.gui.DirectGui import DirectFrame, DirectLabel
from panda3d.core import TextNode, Vec3

from ..config import BLUE, CYAN, GREEN, MAGENTA, MUTED, ORANGE, PURPLE, RED, WHITE, YELLOW
from ..data.content_catalog import space_formation_for_wave
from ..math3d import clamp, damp, damp_vec3, segment_point_distance
from ..primitives import make_box, make_octahedron, make_ring
from ..world import BaseMode, Projectile, ShipRig

Color = Tuple[float, float, float, float]


@dataclass
class SpaceEnemy:
    rig: ShipRig
    health: float
    max_health: float
    speed: float
    damage: float
    fire_timer: float
    fire_interval: float
    radius: float
    kind: str
    phase: float
    alive: bool = True
    hurt_timer: float = 0.0


@dataclass
class Star:
    node: object
    depth: float
    speed: float


class OrbitalWars(BaseMode):
    game_id = "orbital_wars"

    def __init__(self, app) -> None:
        super().__init__(app)
        self.elapsed = 0.0
        self.player_pos = Vec3(0, 0, 0)
        self.velocity = Vec3(0)
        self.health = 100.0
        self.shield = 100.0
        self.energy = 100.0
        self.missiles = 6
        self.laser_timer = 0.0
        self.laser_interval = 0.12
        self.missile_timer = 0.0
        self.pulse_cooldown = 0.0
        self.wave = 0
        self.spawn_remaining = 0
        self.spawn_timer = 0.0
        self.wave_break = 0.8
        self.enemies: List[SpaceEnemy] = []
        self.stars: List[Star] = []
        self.damage_alpha = 0.0
        self._build_world()
        self._build_hud()
        self._start_wave()

    def _build_world(self) -> None:
        self.base.setBackgroundColor(0.001, 0.002, 0.012, 1)
        self.add_standard_lighting(
            ambient=(0.11, 0.13, 0.22, 1),
            sun=(0.62, 0.72, 1.0, 1),
            hpr=(-25, -38, 0),
        )
        self.player = ShipRig(
            self.actor_root,
            "player-ship",
            self.player_pos,
            (0.08, 0.13, 0.22, 1),
            CYAN,
            1.0,
        )
        self.player.root.setP(0)
        self.camera.setPos(0, -14, 5.2)
        self.camera.setHpr(0, -8, 0)
        self._create_starfield()
        self._create_planets()
        self.add_point_light("space-blue", Vec3(-12, 30, 12), (0.12, 0.30, 0.72, 1), (1, 0.008, 0.0008))
        self.add_point_light("space-purple", Vec3(18, 60, -5), (0.48, 0.12, 0.70, 1), (1, 0.008, 0.0008))

    def _create_starfield(self) -> None:
        rng = random.Random(44123)
        for index in range(180):
            x = rng.uniform(-42, 42)
            y = rng.uniform(4, 170)
            z = rng.uniform(-26, 28)
            size = rng.uniform(0.018, 0.085)
            color = random.choice([WHITE, CYAN, (0.55,0.65,1.0,1), (1.0,0.72,0.44,1)])
            node = make_box(f"star-{index}", (size,size,size*2.3), color, self.world_root, (x,y,z))
            self.stars.append(Star(node=node, depth=y, speed=rng.uniform(0.75,1.45)))

    def _create_planets(self) -> None:
        planet = make_octahedron("distant-planet", 8.5, (0.10,0.16,0.28,1), self.world_root)
        planet.setPos(-29, 116, 20)
        planet.setScale(1.0, 1.0, 1.0)
        ring = make_ring("planet-ring", 10.5, 13.0, 72, (0.20,0.42,0.78,0.34), self.world_root)
        ring.setPos(-29,116,20)
        ring.setHpr(22,65,0)
        ring.setTransparency(True)
        moon = make_octahedron("moon", 2.4, (0.18,0.20,0.25,1), self.world_root)
        moon.setPos(25,142,-11)

    def _build_hud(self) -> None:
        self.health_bg = DirectFrame(parent=self.hud_root, frameColor=(0.05,0.06,0.10,0.94), frameSize=(-1.62,-0.76,-0.92,-0.875))
        self.health_bar = DirectFrame(parent=self.hud_root, frameColor=MAGENTA, frameSize=(-1.62,-0.76,-0.92,-0.875))
        self.shield_bg = DirectFrame(parent=self.hud_root, frameColor=(0.05,0.06,0.10,0.94), frameSize=(-1.62,-0.76,-0.84,-0.80))
        self.shield_bar = DirectFrame(parent=self.hud_root, frameColor=CYAN, frameSize=(-1.62,-0.76,-0.84,-0.80))
        self.energy_bg = DirectFrame(parent=self.hud_root, frameColor=(0.05,0.06,0.10,0.94), frameSize=(-1.62,-0.92,-0.76,-0.735))
        self.energy_bar = DirectFrame(parent=self.hud_root, frameColor=YELLOW, frameSize=(-1.62,-0.92,-0.76,-0.735))
        self.status_label = DirectLabel(parent=self.hud_root,text="SHIELD 100   HULL 100",text_fg=WHITE,text_scale=0.032,text_align=TextNode.ALeft,frameColor=(0,0,0,0),pos=(-1.60,0,-0.68))
        self.score_label = DirectLabel(parent=self.hud_root,text="SCORE 0",text_fg=WHITE,text_scale=0.040,text_align=TextNode.ARight,frameColor=(0,0,0,0),pos=(1.58,0,0.88))
        self.wave_label = DirectLabel(parent=self.hud_root,text="SECTOR 01",text_fg=CYAN,text_scale=0.034,text_align=TextNode.ARight,frameColor=(0,0,0,0),pos=(1.58,0,0.80))
        self.missile_label = DirectLabel(parent=self.hud_root,text="MISSILES 06",text_fg=ORANGE,text_scale=0.030,text_align=TextNode.ARight,frameColor=(0,0,0,0),pos=(1.58,0,-0.88))
        self.combo_label = DirectLabel(parent=self.hud_root,text="",text_fg=YELLOW,text_scale=0.036,text_align=TextNode.ARight,frameColor=(0,0,0,0),pos=(1.58,0,0.71))
        self.pulse_label = DirectLabel(parent=self.hud_root,text="Q PULSE READY",text_fg=CYAN,text_scale=0.026,text_align=TextNode.ARight,frameColor=(0,0,0,0),pos=(1.58,0,-0.95))
        self.crosshair = []
        for fs in [(-0.045,-0.015,-0.0025,0.0025),(0.015,0.045,-0.0025,0.0025),(-0.0025,0.0025,0.015,0.045),(-0.0025,0.0025,-0.045,-0.015)]:
            self.crosshair.append(DirectFrame(parent=self.hud_root,frameColor=CYAN,frameSize=fs))
        self.damage_overlay = DirectFrame(parent=self.hud_root,frameColor=(0.8,0.01,0.05,0),frameSize=(-1.8,1.8,-1.05,1.05),sortOrder=-1)

    def _start_wave(self) -> None:
        self.wave += 1
        self.spawn_remaining = 4 + self.wave * 2
        self.spawn_timer = 0.3
        self.wave_break = 1.8
        self.wave_label["text"] = f"SECTOR {self.wave:02d}"
        self.spawn_floating_text(f"SECTOR {self.wave:02d}",(0,0.35),CYAN,0.073,1.35)
        self.app.save.max_stat(self.game_id,"best_wave",self.wave)

    def _spawn_enemy(self) -> None:
        formation = space_formation_for_wave(self.wave)
        suggested_kind = random.choice(formation.kinds)
        roll = random.random()
        if self.wave % 5 == 0 and self.spawn_remaining == 1:
            kind = "capital"
            health_mul, speed, damage, scale, radius = 8.0, 3.5, 2.1, 3.2, 2.2
            primary, secondary = (0.20,0.05,0.08,1), RED
        elif suggested_kind == "interceptor" or roll < min(0.28,0.10+self.wave*0.012):
            kind = "interceptor"
            health_mul, speed, damage, scale, radius = 0.70, 10.8, 0.78, 0.78, 0.70
            primary, secondary = (0.08,0.08,0.18,1), PURPLE
        elif suggested_kind == "bomber" or roll < min(0.46,0.18+self.wave*0.014):
            kind = "bomber"
            health_mul, speed, damage, scale, radius = 2.2, 5.2, 1.5, 1.45, 1.05
            primary, secondary = (0.16,0.07,0.04,1), ORANGE
        else:
            kind = "fighter"
            health_mul, speed, damage, scale, radius = 1.0, 7.4, 1.0, 1.0, 0.78
            primary, secondary = (0.06,0.10,0.18,1), MAGENTA
        x = random.uniform(-18,18)
        y = random.uniform(62,92)
        z = random.uniform(-8,14)
        health = (62+self.wave*8)*health_mul*self.difficulty_scale
        rig = ShipRig(self.actor_root,"enemy-ship",Vec3(x,y,z),primary,secondary,scale)
        rig.root.setH(180)
        self.enemies.append(SpaceEnemy(
            rig=rig,
            health=health,
            max_health=health,
            speed=speed*(0.96+0.04*self.difficulty_scale),
            damage=(8.0+self.wave*0.52)*damage*self.difficulty_scale,
            fire_timer=random.uniform(0.4,1.4),
            fire_interval=max(0.48,1.45-self.wave*0.025)*(0.70 if kind=="interceptor" else 1.0),
            radius=radius,
            kind=kind,
            phase=random.uniform(0,math.tau),
        ))

    def _update_player(self,dt:float) -> None:
        move = Vec3(
            (1 if self.key["d"] else 0)-(1 if self.key["a"] else 0),
            (1 if self.key["w"] else 0)-(1 if self.key["s"] else 0),
            (1 if self.key["space"] else 0)-(1 if self.key["control"] else 0),
        )
        if move.lengthSquared()>0.001:
            move.normalize()
        boosting = bool(self.key["shift"] and self.energy>0.5)
        speed = 14.0 if boosting else 8.5
        if boosting:
            self.energy=max(0,self.energy-28*dt)
        else:
            self.energy=min(100,self.energy+18*dt)
        target_velocity = move*speed
        self.velocity = damp_vec3(self.velocity,target_velocity,4.8,dt)
        self.player_pos += self.velocity*dt
        self.player_pos.x=clamp(self.player_pos.x,-18,18)
        self.player_pos.y=clamp(self.player_pos.y,-4,20)
        self.player_pos.z=clamp(self.player_pos.z,-7,12)
        self.player.root.setPos(self.player_pos)
        self.player.root.setR(damp(self.player.root.getR(),-move.x*22,5.5,dt))
        self.player.root.setP(damp(self.player.root.getP(),move.z*10,5.5,dt))
        self.player.animate_engine(self.elapsed,1.0 if boosting else 0.0)
        camera_target=self.player_pos+Vec3(-self.player_pos.x*0.08,-14.5,5.4)
        self.camera.setPos(damp_vec3(self.camera.getPos(),camera_target,6.2,dt))
        self.camera.lookAt(self.player_pos+Vec3(0,8,0.5))
        shake_pos,shake_hpr=self.camera_shake.update(dt)
        self.camera.setPos(self.camera.getPos()+shake_pos)
        self.camera.setHpr(self.camera.getHpr()+shake_hpr)

    def _aim_direction(self) -> Vec3:
        direction=Vec3(0,1,0)
        if self.base.mouseWatcherNode.hasMouse():
            mouse=self.base.mouseWatcherNode.getMouse()
            direction=Vec3(mouse.x*0.42,1.0,mouse.y*0.28)
        if direction.lengthSquared()<0.001:
            direction=Vec3(0,1,0)
        direction.normalize()
        return direction

    def _fire_laser(self) -> None:
        if not self.key["mouse1"] or self.laser_timer>0 or self.energy<1.5:
            return
        self.laser_timer=self.laser_interval
        self.energy=max(0,self.energy-1.8)
        direction=self._aim_direction()
        for x in (-0.48,0.48):
            origin=self.player_pos+Vec3(x,1.3,0.05)
            self.spawn_projectile(origin,direction,44.0,26.0,CYAN,"player",0.14,2.5,0.075)
        self.app.audio.play("laser",self.app.sfx_volume()*0.36,random.uniform(1.15,1.35))

    def _fire_missile(self) -> None:
        if not self.key["mouse3"] or self.missile_timer>0 or self.missiles<=0:
            return
        target=self._nearest_enemy_ahead()
        if target is None:
            return
        self.missile_timer=1.1
        self.missiles-=1
        origin=self.player_pos+Vec3(0,1.0,-0.2)
        direction=target.rig.root.getPos()-origin
        self.spawn_projectile(origin,direction,23.0,95.0,ORANGE,"player",0.32,5.0,0.18,target.rig.root,2.1)
        self.app.audio.play("dash",self.app.sfx_volume()*0.42,0.72)

    def _nearest_enemy_ahead(self) -> Optional[SpaceEnemy]:
        alive=[e for e in self.enemies if e.alive and not e.rig.root.isEmpty() and e.rig.root.getY()>self.player_pos.y]
        if not alive:
            return None
        return min(alive,key=lambda e:(e.rig.root.getPos()-self.player_pos).length())

    def _pulse(self) -> None:
        if not self.key["q"] or self.pulse_cooldown>0 or self.energy<35:
            return
        self.energy-=35
        self.pulse_cooldown=8.0
        self.pulses.emit(self.player_pos,CYAN,0.7,13.0,0.75)
        self.camera_shake.add(0.35)
        self.app.audio.play("explosion",self.app.sfx_volume()*0.33,1.8)
        for enemy in self.enemies:
            if not enemy.alive:
                continue
            distance=(enemy.rig.root.getPos()-self.player_pos).length()
            if distance<13:
                damage=70*(1-distance/18)
                self._damage_enemy(enemy,max(18,damage))

    def _enemy_fire(self,enemy:SpaceEnemy) -> None:
        origin=enemy.rig.root.getPos()+Vec3(0,-1.3,0)
        target=self.player_pos+Vec3(random.uniform(-0.8,0.8),0,random.uniform(-0.5,0.5))
        direction=target-origin
        color=RED if enemy.kind in ("bomber","capital") else MAGENTA
        speed=20 if enemy.kind=="capital" else 26
        self.spawn_projectile(origin,direction,speed,enemy.damage,color,"enemy",0.20,4.5,0.11 if enemy.kind!="capital" else 0.18)

    def _update_enemies(self,dt:float) -> None:
        alive=[]
        for enemy in self.enemies:
            if not enemy.alive or enemy.rig.root.isEmpty():
                continue
            if enemy.hurt_timer>0:
                enemy.hurt_timer-=dt
                if enemy.hurt_timer<=0:
                    enemy.rig.root.clearColorScale()
            enemy.phase+=dt*(0.8+enemy.speed*0.03)
            pos=enemy.rig.root.getPos()
            target=Vec3(self.player_pos.x*0.45+math.sin(enemy.phase)*4.0,self.player_pos.y+18,self.player_pos.z*0.35+math.cos(enemy.phase*1.3)*3.0)
            direction=target-pos
            if direction.lengthSquared()>0.001:
                direction.normalize()
            pos+=direction*enemy.speed*dt
            if enemy.kind=="interceptor":
                pos.x+=math.sin(enemy.phase*2.8)*2.0*dt
            enemy.rig.root.setPos(pos)
            enemy.rig.animate_engine(self.elapsed,0.2)
            enemy.fire_timer-=dt
            if enemy.fire_timer<=0 and pos.y<50:
                enemy.fire_timer=enemy.fire_interval*random.uniform(0.8,1.25)
                self._enemy_fire(enemy)
            if pos.y<self.player_pos.y-18:
                self._damage_player(enemy.damage*0.45)
                enemy.rig.destroy()
                continue
            alive.append(enemy)
        self.enemies=alive

    def _projectile_collision(self,projectile:Projectile) -> bool:
        pos=projectile.node.getPos(self.root)
        if projectile.team=="player":
            for enemy in self.enemies:
                if not enemy.alive:
                    continue
                if (enemy.rig.root.getPos()-pos).length()<=enemy.radius+projectile.radius:
                    self._damage_enemy(enemy,projectile.damage)
                    self.particles.sparks(pos,projectile.color,8)
                    return True
        else:
            if (self.player_pos-pos).length()<=0.85+projectile.radius:
                self._damage_player(projectile.damage)
                self.particles.sparks(pos,RED,8)
                return True
        return abs(pos.x)>45 or pos.y>190 or pos.y<-35 or abs(pos.z)>45

    def _damage_enemy(self,enemy:SpaceEnemy,damage:float) -> None:
        enemy.health-=damage
        enemy.hurt_timer=0.08
        enemy.rig.root.setColorScale(1.7,1.7,1.7,1)
        if enemy.health<=0:
            self._kill_enemy(enemy)

    def _kill_enemy(self,enemy:SpaceEnemy) -> None:
        enemy.alive=False
        pos=enemy.rig.root.getPos()
        reward={"fighter":110,"interceptor":150,"bomber":260,"capital":1100}.get(enemy.kind,100)
        self.combo+=1
        self.best_combo=max(self.best_combo,self.combo)
        self.score+=reward+min(400,self.combo*11)
        self.app.save.add_stat(self.game_id,"kills",1)
        self.particles.explosion(pos,CYAN if enemy.kind!="capital" else ORANGE,MAGENTA if enemy.kind!="capital" else RED)
        self.pulses.emit(pos,CYAN if enemy.kind!="capital" else ORANGE,0.5,4.5 if enemy.kind!="capital" else 9.0,0.5)
        self.app.audio.play("explosion",self.app.sfx_volume()*0.32,0.9 if enemy.kind=="capital" else 1.2)
        enemy.rig.destroy()
        if random.random()<0.17:
            self.missiles=min(9,self.missiles+1)
            self.spawn_floating_text("+1 MISSILE",(0,-0.06),ORANGE,0.032,0.6)

    def _damage_player(self,damage:float) -> None:
        remaining=damage
        if self.shield>0:
            absorb=min(self.shield,remaining*0.82)
            self.shield-=absorb
            remaining-=absorb
        self.health-=max(0,remaining)
        self.damage_alpha=min(0.8,self.damage_alpha+0.36)
        self.camera_shake.add(0.44)
        self.combo=max(0,self.combo-2)
        if self.health<=0:
            self.health=0
            self.finish_game("SHIP LOST")

    def _update_starfield(self,dt:float) -> None:
        speed=18+max(0,self.velocity.y)*1.4
        for star in self.stars:
            node=star.node
            node.setY(node.getY()-speed*star.speed*dt)
            if node.getY()<self.player_pos.y-18:
                node.setY(node.getY()+180)
                node.setX(random.uniform(-42,42))
                node.setZ(random.uniform(-26,28))

    def _update_hud(self,dt:float) -> None:
        ht=clamp(self.health/100,0,1)
        st=clamp(self.shield/100,0,1)
        et=clamp(self.energy/100,0,1)
        self.health_bar["frameSize"]=(-1.62,-1.62+0.86*ht,-0.92,-0.875)
        self.shield_bar["frameSize"]=(-1.62,-1.62+0.86*st,-0.84,-0.80)
        self.energy_bar["frameSize"]=(-1.62,-1.62+0.70*et,-0.76,-0.735)
        self.status_label["text"]=f"SHIELD {int(self.shield):03d}   HULL {int(self.health):03d}"
        self.score_label["text"]=f"SCORE {int(self.score):,}"
        self.missile_label["text"]=f"MISSILES {self.missiles:02d}"
        self.combo_label["text"]=f"CHAIN x{self.combo}" if self.combo>=2 else ""
        self.pulse_label["text"]="Q PULSE READY" if self.pulse_cooldown<=0 else f"PULSE {self.pulse_cooldown:.1f}s"
        self.pulse_label["text_fg"]=CYAN if self.pulse_cooldown<=0 else MUTED
        self.damage_alpha=damp(self.damage_alpha,0,4.0,dt)
        self.damage_overlay["frameColor"]=(0.8,0.01,0.05,self.damage_alpha*0.38)

    def update(self,dt:float) -> None:
        if self.paused or self.game_over:
            self.tick_common(dt)
            return
        self.elapsed+=dt
        self.laser_timer=max(0,self.laser_timer-dt)
        self.missile_timer=max(0,self.missile_timer-dt)
        self.pulse_cooldown=max(0,self.pulse_cooldown-dt)
        self.shield=min(100,self.shield+4.5*dt)
        self._update_player(dt)
        self._fire_laser()
        self._fire_missile()
        self._pulse()
        if self.spawn_remaining>0:
            self.spawn_timer-=dt
            if self.spawn_timer<=0:
                self.spawn_timer=max(0.22,0.65-self.wave*0.015)/self.difficulty_scale
                self._spawn_enemy()
                self.spawn_remaining-=1
        elif not self.enemies:
            self.wave_break-=dt
            if self.wave_break<=0:
                self._start_wave()
        self._update_enemies(dt)
        self.update_projectiles(dt,self._projectile_collision)
        self._update_starfield(dt)
        self.score+=dt*(5+self.wave*0.4)
        self._update_hud(dt)
        self.tick_common(dt)

    def destroy(self) -> None:
        try:
            self.player.destroy()
        except Exception:
            pass
        super().destroy()
