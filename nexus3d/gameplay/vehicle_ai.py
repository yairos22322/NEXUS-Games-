from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Dict, List

from panda3d.core import Vec3


@dataclass
class TrafficBrain:
    target_lane: int
    cooldown: float
    aggression: float
    preferred_speed: float
    indicator: float = 0.0


class VehicleDynamicsDirector:
    """Adds traffic decisions and a lightweight drift model to Street Rush."""

    def __init__(self) -> None:
        self._brains: Dict[int, TrafficBrain] = {}
        self._rng = random.Random(0x535452454554)
        self._lateral_velocity = 0.0
        self._drift = 0.0
        self._last_handbrake = False
        self._cleanup_timer = 0.0

    def reset(self) -> None:
        self._brains.clear()
        self._lateral_velocity = 0.0
        self._drift = 0.0
        self._last_handbrake = False
        self._cleanup_timer = 0.0

    def update(self, dt: float, mode) -> None:
        if dt <= 0.0 or str(getattr(mode, "game_id", "")) != "street_rush":
            return
        self._update_player_dynamics(dt, mode)
        self._update_traffic(dt, mode)
        self._cleanup_timer += dt
        if self._cleanup_timer > 2.5:
            self._cleanup_timer = 0.0
            live = {id(car) for car in getattr(mode, "traffic", [])}
            for key in list(self._brains):
                if key not in live:
                    self._brains.pop(key, None)

    def _update_player_dynamics(self, dt: float, mode) -> None:
        key = getattr(mode, "key", None)
        if key is None or not hasattr(mode, "player"):
            return

        steer = float(getattr(mode, "steer", 0.0))
        speed = float(getattr(mode, "speed", 0.0))
        player_x = float(getattr(mode, "player_x", 0.0))
        handbrake = bool(key["space"]) and speed > 33.0 and abs(steer) > 0.08

        # Tires build lateral force progressively. Handbrake drops rear grip,
        # allowing a controlled slide rather than instantly teleporting lanes.
        speed_factor = max(0.0, min(1.4, speed / 72.0))
        grip = 10.0 if not handbrake else 2.8
        desired_lat = steer * (3.5 + speed_factor * 4.0)
        response = 1.0 - math.exp(-grip * dt)
        self._lateral_velocity += (desired_lat - self._lateral_velocity) * response

        if handbrake:
            self._drift += (steer * 1.0 - self._drift) * (1.0 - math.exp(-5.2 * dt))
            self._lateral_velocity += steer * speed_factor * 5.8 * dt
            mode.target_speed = max(float(getattr(mode, "min_speed", 18.0)), float(mode.target_speed) - 7.5 * dt)
            if not self._last_handbrake:
                try:
                    mode.camera_shake.add(0.08)
                    mode.app.audio.play("dash", mode.app.sfx_volume() * 0.18, 0.78)
                except Exception:
                    pass
        else:
            self._drift += (0.0 - self._drift) * (1.0 - math.exp(-6.5 * dt))

        # The base mode already performs primary steering. This small inertial
        # contribution makes transitions and counter-steer feel physical.
        player_x += self._lateral_velocity * dt * 0.28
        player_x = max(-7.0, min(7.0, player_x))
        mode.player_x = player_x
        mode.player.root.setX(player_x)

        yaw = -steer * 4.0 - self._drift * (8.0 + speed_factor * 8.0)
        roll = -steer * 5.5 - self._drift * 5.0
        try:
            mode.player.root.setH(yaw)
            mode.player.root.setR(roll)
        except Exception:
            pass

        # Reward sustained controlled drifts, but only while the vehicle stays
        # away from the outer wall so holding space is not a free score exploit.
        if handbrake and abs(self._drift) > 0.28 and abs(player_x) < 6.25:
            bonus = speed * abs(self._drift) * dt * 0.24
            mode.score += bonus
            mode.combo_timer = max(float(getattr(mode, "combo_timer", 0.0)), 0.45)

        self._last_handbrake = handbrake

    def _update_traffic(self, dt: float, mode) -> None:
        traffic: List = list(getattr(mode, "traffic", []) or [])
        lanes = tuple(getattr(mode, "LANES", ()))
        if not traffic or not lanes:
            return

        player_x = float(getattr(mode, "player_x", 0.0))
        player_speed = float(getattr(mode, "speed", 0.0))

        # Snapshot positions before applying changes so decisions are stable and
        # independent of list iteration order.
        snapshot = []
        for car in traffic:
            if not hasattr(car, "rig") or car.rig.root.isEmpty():
                continue
            snapshot.append((car, car.rig.root.getX(), car.rig.root.getY(), float(car.speed)))

        for car, x, y, speed in snapshot:
            brain = self._brain_for(car, lanes)
            brain.cooldown = max(0.0, brain.cooldown - dt)
            brain.indicator = max(0.0, brain.indicator - dt)

            current_lane = self._nearest_lane(x, lanes)
            target_lane = max(0, min(len(lanes) - 1, brain.target_lane))
            obstacle = self._car_ahead(car, current_lane, snapshot, lanes)

            if obstacle is not None:
                gap, ahead_speed = obstacle
                closing = speed - ahead_speed
                if gap < 16.0 and closing > -1.5:
                    candidate = self._choose_overtake_lane(
                        current_lane,
                        y,
                        snapshot,
                        lanes,
                        player_x,
                    )
                    if candidate is not None and brain.cooldown <= 0.0:
                        target_lane = candidate
                        brain.target_lane = candidate
                        brain.cooldown = self._rng.uniform(1.7, 3.4)
                        brain.indicator = 0.8
                    else:
                        # Smooth car-following instead of driving through the
                        # traffic vehicle in front.
                        desired = max(18.0, ahead_speed - max(0.0, (10.0 - gap) * 0.8))
                        car.speed += (desired - car.speed) * min(1.0, dt * 2.4)
                elif gap > 24.0:
                    car.speed += (brain.preferred_speed - car.speed) * min(1.0, dt * 0.45)
            else:
                car.speed += (brain.preferred_speed - car.speed) * min(1.0, dt * 0.35)

            # Cars near the player occasionally choose a safer lane rather than
            # behaving like static obstacles. Aggressive drivers are less likely
            # to yield, preserving difficulty and close calls.
            if -8.0 < y < 24.0 and abs(lanes[current_lane] - player_x) < 1.9:
                if brain.cooldown <= 0.0 and self._rng.random() > brain.aggression:
                    away = current_lane + (-1 if player_x > lanes[current_lane] else 1)
                    if 0 <= away < len(lanes) and self._lane_clear(away, y, snapshot, lanes, 10.0):
                        target_lane = away
                        brain.target_lane = away
                        brain.cooldown = self._rng.uniform(1.8, 3.0)

            desired_x = float(lanes[target_lane])
            lane_delta = desired_x - x
            lane_speed = 2.8 + min(3.8, abs(lane_delta) * 1.1)
            step = max(-lane_speed * dt, min(lane_speed * dt, lane_delta))
            car.rig.root.setX(x + step)
            car.lane = self._nearest_lane(x + step, lanes)

            # Slight body lean communicates the lane change even with primitive
            # vehicle geometry.
            try:
                car.rig.root.setR(max(-5.0, min(5.0, -step * 16.0)))
                car.rig.root.setH(max(-3.0, min(3.0, step * 8.0)))
            except Exception:
                pass

            # Prevent absurd AI speeds relative to the player as the run ramps.
            upper = max(28.0, player_speed * 0.93 + 12.0)
            car.speed = max(16.0, min(upper, float(car.speed)))

    def _brain_for(self, car, lanes) -> TrafficBrain:
        key = id(car)
        brain = self._brains.get(key)
        if brain is None:
            lane = max(0, min(len(lanes) - 1, int(getattr(car, "lane", 0))))
            base_speed = float(getattr(car, "speed", 30.0))
            brain = TrafficBrain(
                target_lane=lane,
                cooldown=self._rng.uniform(0.3, 2.0),
                aggression=self._rng.uniform(0.25, 0.82),
                preferred_speed=base_speed * self._rng.uniform(0.96, 1.06),
            )
            self._brains[key] = brain
        return brain

    @staticmethod
    def _nearest_lane(x: float, lanes) -> int:
        return min(range(len(lanes)), key=lambda idx: abs(float(lanes[idx]) - x))

    def _car_ahead(self, car, lane: int, snapshot, lanes):
        y = car.rig.root.getY()
        best_gap = 1e9
        best_speed = 0.0
        for other, ox, oy, speed in snapshot:
            if other is car:
                continue
            if self._nearest_lane(ox, lanes) != lane:
                continue
            gap = oy - y
            if 0.0 < gap < best_gap:
                best_gap = gap
                best_speed = speed
        if best_gap >= 1e9:
            return None
        return best_gap, best_speed

    def _choose_overtake_lane(self, lane: int, y: float, snapshot, lanes, player_x: float):
        candidates = []
        for candidate in (lane - 1, lane + 1):
            if candidate < 0 or candidate >= len(lanes):
                continue
            if not self._lane_clear(candidate, y, snapshot, lanes, 12.0):
                continue
            player_penalty = abs(float(lanes[candidate]) - player_x) < 1.8
            candidates.append((1 if player_penalty else 0, self._rng.random(), candidate))
        if not candidates:
            return None
        candidates.sort()
        return candidates[0][2]

    def _lane_clear(self, lane: int, y: float, snapshot, lanes, radius: float) -> bool:
        for _, ox, oy, _ in snapshot:
            if self._nearest_lane(ox, lanes) == lane and abs(oy - y) < radius:
                return False
        return True
