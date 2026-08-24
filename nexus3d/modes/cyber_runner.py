from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List, Tuple

from direct.gui.DirectGui import DirectFrame, DirectLabel
from panda3d.core import TextNode, Vec3

from ..config import CYAN, GREEN, MAGENTA, MUTED, ORANGE, RED, WHITE, YELLOW
from ..data.content_catalog import runner_pattern_for_distance
from ..math3d import aabb_overlap, clamp, damp, damp_vec3
from ..primitives import make_box, make_plane
from ..world import BaseMode, CharacterRig

Color = Tuple[float, float, float, float]


@dataclass
class RunnerObstacle:
    node: object
    kind: str
    pos: Vec3
    half: Vec3
    passed: bool = False
    phase: float = 0.0


@dataclass
class DataShard:
    node: object
    pos: Vec3
    collected: bool = False
    phase: float = 0.0


@dataclass
class Drone:
    node: object
    pos: Vec3
    fire_timer: float
    phase: float


class CyberRunner(BaseMode):
    game_id = "cyber_runner"

    def __init__(self,app) -> None:
        super().__init__(app)
        self.elapsed=0.0
        self.player_pos=Vec3(0,0,1.05)
        self.player_velocity=Vec3(0)
        self.grounded=True
        self.sliding=False
        self.slide_timer=0.0
        self.dash_timer=0.0
        self.dash_cooldown=0.0
        self.health=100.0
        self.energy=100.0
        self.speed=15.0
        self.target_speed=15.0
        self.max_speed=32.0
        self.distance=0.0
        self.multiplier=1
        self.multiplier_timer=0.0
        self.obstacles:List[RunnerObstacle]=[]
        self.shards:List[DataShard]=[]
        self.drones:List[Drone]=[]
        self.segment_timer=0.0
        self.damage_alpha=0.0
        self._build_world()
        self._build_hud()

    def _build_world(self) -> None:
        self.base.setBackgroundColor(0.015,0.006,0.002,1)
        self.add_standard_lighting(
            ambient=(0.17,0.10,0.07,1),
            sun=(0.76,0.48,0.24,1),
            hpr=(-28,-51,0),
        )
        self.set_fog((0.04,0.012,0.004,1),0.008)
        self.player=CharacterRig(self.actor_root,"runner",self.player_pos,(0.08,0.10,0.13,1),ORANGE,0.95)
        self.player.weapon.hide()
        self.track_segments=[]
        for index in range(22):
            y=index*14.0-22.0
            root=self.world_root.attachNewNode(f"track-{index}")
            root.setY(y)
            make_box("roof",(13.5,14.2,0.45),(0.035,0.038,0.045,1),root,(0,0,-0.22))
            make_box("edge-l",(0.18,14.0,0.12),ORANGE,root,(-6.55,0,0.12))
            make_box("edge-r",(0.18,14.0,0.12),CYAN,root,(6.55,0,0.12))
            if index%2==0:
                for x in (-4.2,4.2):
                    make_box("vent",(1.3,2.0,0.85),(0.07,0.075,0.085,1),root,(x,3.5,0.43))
            self.track_segments.append(root)
        self._build_skyline()
        self.camera.setPos(0,-13.5,6.0)
        self.camera.setHpr(0,-13,0)
        self.add_point_light("runner-orange",Vec3(-8,18,7),(0.75,0.18,0.02,1),(1,0.03,0.004))
        self.add_point_light("runner-cyan",Vec3(8,45,8),(0.03,0.45,0.68,1),(1,0.03,0.004))

    def _build_skyline(self) -> None:
        rng=random.Random(9917)
        self.skyline=[]
        for index in range(38):
            side=-1 if index%2==0 else 1
            y=rng.uniform(-15,250)
            x=side*rng.uniform(10,28)
            width=rng.uniform(4,9)
            depth=rng.uniform(4,9)
            height=rng.uniform(12,42)
            color=(rng.uniform(0.02,0.045),rng.uniform(0.02,0.04),rng.uniform(0.025,0.06),1)
            node=make_box("skyscraper",(width,depth,height),color,self.world_root,(x,y,height*0.5-1))
            accent=ORANGE if side<0 else CYAN
            for floor in range(3,int(height),5):
                if rng.random()<0.78:
                    make_box("window",(width*0.65,0.05,0.08),accent,node,(0,-depth*0.505,floor-height*0.5))
            self.skyline.append(node)

    def _build_hud(self) -> None:
        self.score_label=DirectLabel(parent=self.hud_root,text="SCORE 0",text_fg=WHITE,text_scale=0.040,text_align=TextNode.ARight,frameColor=(0,0,0,0),pos=(1.58,0,0.88))
        self.distance_label=DirectLabel(parent=self.hud_root,text="0 M",text_fg=ORANGE,text_scale=0.036,text_align=TextNode.ARight,frameColor=(0,0,0,0),pos=(1.58,0,0.80))
        self.multiplier_label=DirectLabel(parent=self.hud_root,text="x1",text_fg=YELLOW,text_scale=0.065,text_align=TextNode.ARight,frameColor=(0,0,0,0),pos=(1.58,0,0.67))
        self.speed_label=DirectLabel(parent=self.hud_root,text="SPEED 15",text_fg=CYAN,text_scale=0.031,text_align=TextNode.ARight,frameColor=(0,0,0,0),pos=(1.58,0,-0.90))
        self.health_bg=DirectFrame(parent=self.hud_root,frameColor=(0.05,0.06,0.07,0.94),frameSize=(-1.62,-0.78,-0.92,-0.875))
        self.health_bar=DirectFrame(parent=self.hud_root,frameColor=ORANGE,frameSize=(-1.62,-0.78,-0.92,-0.875))
        self.energy_bg=DirectFrame(parent=self.hud_root,frameColor=(0.05,0.06,0.07,0.94),frameSize=(-1.62,-0.90,-0.83,-0.80))
        self.energy_bar=DirectFrame(parent=self.hud_root,frameColor=CYAN,frameSize=(-1.62,-0.90,-0.83,-0.80))
        self.state_label=DirectLabel(parent=self.hud_root,text="FLOW STABLE",text_fg=CYAN,text_scale=0.029,text_align=TextNode.ALeft,frameColor=(0,0,0,0),pos=(-1.60,0,-0.74))
        self.damage_overlay=DirectFrame(parent=self.hud_root,frameColor=(0.8,0.02,0.01,0),frameSize=(-1.8,1.8,-1.05,1.05),sortOrder=-1)

    def _spawn_pattern(self) -> None:
        base_y=random.uniform(68,82)
        catalog_pattern = runner_pattern_for_distance(self.distance)
        pattern = int(catalog_pattern.name[-3:]) % 7
        if pattern==0:
            for x in (-3.8,0,3.8):
                self._add_barrier(Vec3(x,base_y,0.7),Vec3(1.4,1.0,1.4),"barrier")
        elif pattern==1:
            self._add_barrier(Vec3(-3.4,base_y,1.25),Vec3(2.3,1.0,2.5),"wall")
            self._add_barrier(Vec3(3.4,base_y+5,1.25),Vec3(2.3,1.0,2.5),"wall")
        elif pattern==2:
            self._add_barrier(Vec3(0,base_y,0.45),Vec3(9.5,1.0,0.9),"laser_low",ORANGE)
        elif pattern==3:
            self._add_barrier(Vec3(0,base_y,2.0),Vec3(9.5,1.0,0.45),"laser_high",CYAN)
        elif pattern==4:
            for i in range(5):
                self._add_shard(Vec3(-4+i*2.0,base_y+i*2.6,1.2+math.sin(i)*0.5))
        elif pattern==5:
            self._add_barrier(Vec3(-4.0,base_y,0.8),Vec3(1.5,1.0,1.6),"barrier")
            self._add_barrier(Vec3(0,base_y+4,2.0),Vec3(7.0,1.0,0.42),"laser_high",CYAN)
            self._add_barrier(Vec3(4.0,base_y+8,0.8),Vec3(1.5,1.0,1.6),"barrier")
        else:
            self._spawn_drone(Vec3(random.choice([-4.2,4.2]),base_y,4.0))
            for i in range(4):
                self._add_shard(Vec3(random.uniform(-4.5,4.5),base_y+4+i*3,random.uniform(0.9,2.0)))

    def _add_barrier(self,pos:Vec3,size:Vec3,kind:str,color:Color=RED) -> None:
        if kind.startswith("laser"):
            node=make_box(kind,tuple(size),(color[0],color[1],color[2],0.86),self.actor_root,tuple(pos))
        else:
            node=make_box(kind,tuple(size),(0.10,0.09,0.08,1),self.actor_root,tuple(pos))
            make_box("warning",(size.x*0.75,size.y*1.02,0.10),ORANGE,node,(0,0,size.z*0.24))
        self.obstacles.append(RunnerObstacle(node=node,kind=kind,pos=Vec3(pos),half=size*0.5,phase=random.uniform(0,math.tau)))

    def _add_shard(self,pos:Vec3) -> None:
        node=make_box("data-shard",(0.32,0.32,0.80),CYAN,self.actor_root,tuple(pos),(45,20,0))
        self.shards.append(DataShard(node=node,pos=Vec3(pos),phase=random.uniform(0,math.tau)))

    def _spawn_drone(self,pos:Vec3) -> None:
        root=self.actor_root.attachNewNode("drone")
        root.setPos(pos)
        make_box("drone-body",(1.2,0.8,0.42),(0.08,0.08,0.11,1),root)
        make_box("drone-eye",(0.28,0.08,0.16),RED,root,(0,-0.44,0))
        make_box("wing-l",(1.1,0.25,0.12),ORANGE,root,(-0.9,0,0))
        make_box("wing-r",(1.1,0.25,0.12),CYAN,root,(0.9,0,0))
        self.drones.append(Drone(node=root,pos=Vec3(pos),fire_timer=random.uniform(0.8,1.6),phase=random.uniform(0,math.tau)))

    def _update_player(self,dt:float) -> None:
        lateral=(1 if self.key["d"] else 0)-(1 if self.key["a"] else 0)
        self.target_speed=min(self.max_speed,self.target_speed+0.42*dt)
        if self.key["w"]:
            self.target_speed=min(self.max_speed,self.target_speed+4.0*dt)
        self.speed=damp(self.speed,self.target_speed,2.0,dt)
        self.player_pos.x+=lateral*(7.8+self.speed*0.08)*dt
        self.player_pos.x=clamp(self.player_pos.x,-5.6,5.6)

        if self.key["space"] and self.grounded and not self.sliding:
            self.player_velocity.z=9.4
            self.grounded=False
            self.app.audio.play("dash",self.app.sfx_volume()*0.26,1.5)
        if self.key["control"] and self.grounded and self.slide_timer<=0:
            self.sliding=True
            self.slide_timer=0.75
        if self.sliding:
            self.slide_timer-=dt
            if self.slide_timer<=0:
                self.sliding=False

        self.dash_cooldown=max(0,self.dash_cooldown-dt)
        if self.key["shift"] and self.dash_cooldown<=0 and self.energy>=22:
            self.dash_timer=0.24
            self.dash_cooldown=1.4
            self.energy-=22
            self.app.audio.play("dash",self.app.sfx_volume()*0.45)
            self.camera_shake.add(0.22)
        if self.dash_timer>0:
            self.dash_timer-=dt
            self.speed=max(self.speed,38)
        else:
            self.energy=min(100,self.energy+12*dt)

        self.player_velocity.z-=22*dt
        self.player_pos.z+=self.player_velocity.z*dt
        ground_z=0.78 if self.sliding else 1.05
        if self.player_pos.z<=ground_z:
            self.player_pos.z=ground_z
            self.player_velocity.z=0
            self.grounded=True
        self.player.set_pos(self.player_pos)
        self.player.root.setR(damp(self.player.root.getR(),-lateral*10,7,dt))
        self.player.root.setScale(1,1,0.58 if self.sliding else 1)
        self.player.animate_walk(dt,1.0)
        camera_target=Vec3(self.player_pos.x*0.18,-13.5,5.8+self.speed*0.025)
        self.camera.setPos(damp_vec3(self.camera.getPos(),camera_target,6.0,dt))
        self.camera.lookAt(Vec3(self.player_pos.x*0.25,8,1.2))
        self.base.camLens.setFov(damp(self.base.camLens.getFov()[0],78+clamp((self.speed-15)*0.65,0,18),3.4,dt))

    def _scroll_world(self,dt:float) -> None:
        scroll=self.speed*dt
        self.distance+=scroll
        self.app.save.add_stat(self.game_id,"distance",scroll)
        for segment in self.track_segments:
            segment.setY(segment.getY()-scroll)
            if segment.getY()<-32:
                segment.setY(segment.getY()+len(self.track_segments)*14.0)
        for building in self.skyline:
            building.setY(building.getY()-scroll*0.72)
            if building.getY()<-40:
                building.setY(building.getY()+300)

    def _update_obstacles(self,dt:float) -> None:
        alive=[]
        player_half=Vec3(0.40,0.42,0.38 if self.sliding else 0.92)
        player_center=Vec3(self.player_pos.x,0,self.player_pos.z)
        for obstacle in self.obstacles:
            obstacle.phase+=dt*3
            obstacle.pos.y-=self.speed*dt
            obstacle.node.setY(obstacle.pos.y)
            if obstacle.kind.startswith("laser"):
                pulse=0.72+math.sin(obstacle.phase*4)*0.22
                obstacle.node.setColorScale(1,1,1,pulse)
            if -1.3<obstacle.pos.y<1.5:
                center=Vec3(obstacle.pos.x,0,obstacle.pos.z)
                if aabb_overlap(player_center,player_half,center,obstacle.half):
                    safe=False
                    if obstacle.kind=="laser_low" and self.player_pos.z>1.7:
                        safe=True
                    if obstacle.kind=="laser_high" and self.sliding:
                        safe=True
                    if not safe:
                        self._damage_player(24 if obstacle.kind.startswith("laser") else 32)
                        obstacle.node.removeNode()
                        continue
            if not obstacle.passed and obstacle.pos.y<-2:
                obstacle.passed=True
                self.multiplier=min(12,self.multiplier+1)
                self.multiplier_timer=3.0
                self.score+=75*self.multiplier
            if obstacle.pos.y<-25:
                obstacle.node.removeNode()
                continue
            alive.append(obstacle)
        self.obstacles=alive

    def _update_shards(self,dt:float) -> None:
        alive=[]
        for shard in self.shards:
            shard.phase+=dt*3.2
            shard.pos.y-=self.speed*dt
            shard.node.setPos(shard.pos.x,shard.pos.y,shard.pos.z+math.sin(shard.phase)*0.16)
            shard.node.setH(shard.node.getH()+130*dt)
            if abs(shard.pos.y)<1.3 and abs(shard.pos.x-self.player_pos.x)<0.85 and abs(shard.pos.z-self.player_pos.z)<1.25:
                self.score+=120*self.multiplier
                self.energy=min(100,self.energy+8)
                self.particles.pickup(Vec3(shard.pos.x,0,shard.pos.z),CYAN)
                self.app.audio.play("pickup",self.app.sfx_volume()*0.35,1.35)
                shard.node.removeNode()
                continue
            if shard.pos.y<-20:
                shard.node.removeNode()
                continue
            alive.append(shard)
        self.shards=alive

    def _update_drones(self,dt:float) -> None:
        alive=[]
        for drone in self.drones:
            drone.phase+=dt*1.7
            drone.pos.y-=self.speed*dt*0.72
            drone.pos.x+=math.sin(drone.phase)*0.8*dt
            drone.node.setPos(drone.pos.x,drone.pos.y,drone.pos.z+math.sin(drone.phase*2.1)*0.35)
            drone.fire_timer-=dt
            if drone.fire_timer<=0 and 4<drone.pos.y<30:
                drone.fire_timer=random.uniform(1.2,1.9)/self.difficulty_scale
                self._drone_shot(drone)
            if drone.pos.y<-18:
                drone.node.removeNode()
                continue
            alive.append(drone)
        self.drones=alive

    def _drone_shot(self,drone:Drone) -> None:
        origin=Vec3(drone.pos.x,drone.pos.y,drone.pos.z)
        target=Vec3(self.player_pos.x,0,self.player_pos.z)
        direction=target-origin
        self.spawn_projectile(origin,direction,24,14*self.difficulty_scale,RED,"enemy",0.22,3.0,0.11)

    def _projectile_collision(self,projectile) -> bool:
        pos=projectile.node.getPos(self.root)
        if projectile.team=="enemy" and abs(pos.y)<1.0 and abs(pos.x-self.player_pos.x)<0.7 and abs(pos.z-self.player_pos.z)<0.9:
            self._damage_player(projectile.damage)
            self.particles.sparks(pos,RED,7)
            return True
        return pos.y<-20 or abs(pos.x)>20 or pos.z<-8 or pos.z>20

    def _damage_player(self,amount:float) -> None:
        if self.dash_timer>0:
            self.score+=50
            return
        self.health-=amount*self.difficulty_scale
        self.damage_alpha=min(0.8,self.damage_alpha+0.42)
        self.camera_shake.add(0.55)
        self.multiplier=1
        self.multiplier_timer=0
        self.target_speed=max(13,self.target_speed-5)
        self.speed=max(11,self.speed-8)
        if self.health<=0:
            self.health=0
            self.finish_game("RUN TERMINATED")

    def _update_hud(self,dt:float) -> None:
        ht=clamp(self.health/100,0,1)
        et=clamp(self.energy/100,0,1)
        self.health_bar["frameSize"]=(-1.62,-1.62+0.84*ht,-0.92,-0.875)
        self.health_bar["frameColor"]=ORANGE if self.health>30 else RED
        self.energy_bar["frameSize"]=(-1.62,-1.62+0.72*et,-0.83,-0.80)
        self.score_label["text"]=f"SCORE {int(self.score):,}"
        self.distance_label["text"]=f"{int(self.distance):,} M"
        self.multiplier_label["text"]=f"x{self.multiplier}"
        self.speed_label["text"]=f"SPEED {self.speed:04.1f}"
        if self.dash_timer>0:
            self.state_label["text"]="PHASE DASH"
            self.state_label["text_fg"]=ORANGE
        elif self.sliding:
            self.state_label["text"]="SLIDE"
            self.state_label["text_fg"]=YELLOW
        else:
            self.state_label["text"]="FLOW STABLE"
            self.state_label["text_fg"]=CYAN
        self.damage_alpha=damp(self.damage_alpha,0,4.0,dt)
        self.damage_overlay["frameColor"]=(0.8,0.02,0.01,self.damage_alpha*0.36)

    def update(self,dt:float) -> None:
        if self.paused or self.game_over:
            self.tick_common(dt)
            return
        self.elapsed+=dt
        self.segment_timer-=dt
        self.multiplier_timer-=dt
        self.dash_cooldown=max(0,self.dash_cooldown-dt)
        if self.multiplier_timer<=0 and self.multiplier>1:
            self.multiplier-=1
            self.multiplier_timer=0.55 if self.multiplier>1 else 0
        if self.segment_timer<=0:
            self.segment_timer=max(0.55,1.25-self.speed*0.018)/self.difficulty_scale
            self._spawn_pattern()
        self._update_player(dt)
        self._scroll_world(dt)
        self._update_obstacles(dt)
        self._update_shards(dt)
        self._update_drones(dt)
        self.update_projectiles(dt,self._projectile_collision)
        self.score+=self.speed*dt*(0.62+self.multiplier*0.025)
        self._update_hud(dt)
        self.tick_common(dt)

    def destroy(self) -> None:
        try:
            self.player.destroy()
        except Exception:
            pass
        super().destroy()
