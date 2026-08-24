from __future__ import annotations

import math

from direct.showbase.ShowBase import ShowBase
from panda3d.core import ClockObject, WindowProperties, loadPrcFileData

from .audio import ProceduralAudio
from .config import APP_TITLE, DIFFICULTIES, TARGET_FPS, WINDOW_HEIGHT, WINDOW_WIDTH
from .gameplay import GameplayDirector
from .graphics.pipeline import GraphicsDirector
from .save_system import SaveSystem

loadPrcFileData("", f"window-title {APP_TITLE}")
loadPrcFileData("", f"win-size {WINDOW_WIDTH} {WINDOW_HEIGHT}")
loadPrcFileData("", "show-frame-rate-meter 0")
loadPrcFileData("", "gl-version 3 2")
loadPrcFileData("", "depth-bits 24")
loadPrcFileData("", "color-bits 24")
loadPrcFileData("", "sync-video 1")
loadPrcFileData("", "framebuffer-multisample 1")
loadPrcFileData("", "multisamples 4")
loadPrcFileData("", "texture-anisotropic-degree 16")
loadPrcFileData("", "audio-library-name p3openal_audio")


class NexusApp(ShowBase):
    def __init__(self) -> None:
        super().__init__()
        self.disableMouse()
        self.setBackgroundColor(0.005, 0.008, 0.016, 1)
        self.clock = ClockObject.getGlobalClock()
        self.clock.setMode(ClockObject.MLimited)
        self.clock.setFrameRate(TARGET_FPS)
        self.save = SaveSystem()
        self.audio = ProceduralAudio(self)
        self.graphics = GraphicsDirector(self)
        self.gameplay = GameplayDirector(self)
        self.menu = None
        self.mode = None
        self.simulation_step_target = 1.0 / 60.0
        self.max_simulation_substeps = 3
        self.accept("f11", self.toggle_fullscreen)
        self.accept("alt-enter", self.toggle_fullscreen)
        self.apply_window_settings()
        self.show_menu()
        self.taskMgr.add(self._update, "nexus-main-update", sort=0)

    def apply_window_settings(self) -> None:
        props = WindowProperties()
        fullscreen = bool(self.save.setting("fullscreen", False))
        props.setFullscreen(fullscreen)
        if not fullscreen:
            props.setSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.win.requestProperties(props)
        fov = float(self.save.setting("fov", 82))
        self.camLens.setFov(fov)

    def toggle_fullscreen(self) -> None:
        value = not bool(self.save.setting("fullscreen", False))
        self.save.set_setting("fullscreen", value)
        self.apply_window_settings()

    def master_volume(self) -> float:
        return float(self.save.setting("master_volume", 0.72))

    def sfx_volume(self) -> float:
        return self.master_volume() * float(self.save.setting("sfx_volume", 0.78))

    def music_volume(self) -> float:
        return self.master_volume() * float(self.save.setting("music_volume", 0.42))

    def difficulty_scale(self) -> float:
        name = str(self.save.setting("difficulty", "OPERATIVE"))
        return float(DIFFICULTIES.get(name, 1.0))

    def show_menu(self) -> None:
        if self.mode is not None:
            try:
                self.mode.destroy()
            finally:
                self.mode = None
        if self.menu is not None:
            try:
                self.menu.destroy()
            except Exception:
                pass
        from .ui import NexusMenu
        self.render.clearLight()
        self.render.clearFog()
        self.setBackgroundColor(0.005, 0.008, 0.016, 1)
        self.camera.setPos(0, -18, 7.8)
        self.camera.setHpr(0, -7, 0)
        self.camLens.setFov(float(self.save.setting("fov", 82)))
        self.gameplay.reset()
        self.graphics.set_profile("menu")
        self.menu = NexusMenu(self)

    def start_game(self, game_id: str) -> None:
        if self.menu is not None:
            self.menu.destroy()
            self.menu = None
        if self.mode is not None:
            self.mode.destroy()
            self.mode = None

        self.gameplay.reset()
        self.graphics.set_profile(game_id)
        mode_cls = self._mode_class(game_id)
        self.mode = mode_cls(self)
        self.save.add_play(game_id)

    @staticmethod
    def _mode_class(game_id: str):
        if game_id == "neon_ops":
            from .modes.neon_ops import NeonOps
            return NeonOps
        if game_id == "street_rush":
            from .modes.street_rush import StreetRush
            return StreetRush
        if game_id == "zombie_siege":
            from .modes.zombie_siege import ZombieSiege
            return ZombieSiege
        if game_id == "orbital_wars":
            from .modes.orbital_wars import OrbitalWars
            return OrbitalWars
        if game_id == "cyber_runner":
            from .modes.cyber_runner import CyberRunner
            return CyberRunner
        raise ValueError(f"Unknown game mode: {game_id}")

    def _update(self, task):
        dt = min(0.05, max(0.0, self.clock.getDt()))
        self.graphics.update(dt)
        if self.menu is not None:
            self.menu.update(dt)

        if self.mode is not None and self.mode.active:
            # When a frame hitches, split simulation into smaller deterministic
            # chunks. This reduces tunnelling and unstable steering without
            # forcing the renderer itself to run multiple times.
            steps = max(1, min(
                self.max_simulation_substeps,
                int(math.ceil(dt / self.simulation_step_target)),
            ))
            step_dt = dt / steps if steps > 0 else dt
            for _ in range(steps):
                if self.mode is None or not self.mode.active:
                    break
                self.mode.update(step_dt)
                self.gameplay.update(step_dt, self.mode)
        else:
            self.gameplay.update(dt, self.mode)
        return task.cont

    def userExit(self) -> None:
        if self.mode is not None:
            try:
                self.mode.destroy()
            except Exception:
                pass
            self.mode = None
        self.save.save()
        try:
            self.gameplay.destroy()
        except Exception:
            pass
        self.graphics.destroy()
        self.audio.stop_all()
        super().userExit()
