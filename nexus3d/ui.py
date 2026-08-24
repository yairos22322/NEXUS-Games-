from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence, Tuple

from direct.gui.DirectGui import (
    DGG,
    DirectButton,
    DirectFrame,
    DirectLabel,
    DirectSlider,
)
from panda3d.core import NodePath, TextNode, Vec3

from .config import (
    BLACK,
    BLUE,
    CYAN,
    DARK,
    GAME_BY_ID,
    GAMES,
    GREEN,
    MAGENTA,
    MUTED,
    ORANGE,
    PANEL,
    PANEL_ALT,
    PURPLE,
    RED,
    WHITE,
    YELLOW,
)
from .math3d import clamp, damp, format_time
from .primitives import make_box, make_grid, make_octahedron, make_plane, make_ring

Color = Tuple[float, float, float, float]


@dataclass
class MenuButtonState:
    button: DirectButton
    target_scale: float = 1.0
    pulse: float = 0.0


class MenuBackdrop:
    def __init__(self, app) -> None:
        self.app = app
        self.root = app.render.attachNewNode("menu-backdrop")
        self.city = self.root.attachNewNode("city")
        self.elapsed = 0.0
        self.buildings: List[NodePath] = []
        self.floaters: List[Tuple[NodePath, float, float, float]] = []
        self._build_scene()

    def _build_scene(self) -> None:
        make_plane("menu-floor", 180, 180, (0.01, 0.014, 0.026, 1), self.city, -0.05)
        make_grid("menu-grid", 45, 2.0, (0.04, 0.16, 0.22, 0.34), self.city, 0.0)
        random.seed(24701)
        accents = [CYAN, BLUE, PURPLE, MAGENTA, ORANGE]
        for row in range(9):
            y = 14 + row * 9
            for side in (-1, 1):
                count = 3 + (row % 2)
                for index in range(count):
                    x = side * (11 + index * 7 + random.uniform(-1.8, 1.8))
                    width = random.uniform(4.0, 7.0)
                    depth = random.uniform(4.0, 7.0)
                    height = random.uniform(8.0, 28.0) + row * 0.75
                    base_color = (
                        random.uniform(0.018, 0.038),
                        random.uniform(0.025, 0.050),
                        random.uniform(0.045, 0.085),
                        1,
                    )
                    building = make_box(
                        f"building-{row}-{side}-{index}",
                        (width, depth, height),
                        base_color,
                        self.city,
                        (x, y, height * 0.5),
                    )
                    self.buildings.append(building)
                    accent = random.choice(accents)
                    for floor in range(2, int(height), 3):
                        if random.random() < 0.72:
                            strip = make_box(
                                "window-strip",
                                (width * 0.78, 0.05, 0.07),
                                (accent[0], accent[1], accent[2], random.uniform(0.35, 0.75)),
                                building,
                                (0, -depth * 0.505, floor - height * 0.5),
                            )
                            strip.setTransparency(True)

        for index in range(14):
            color = accents[index % len(accents)]
            floater = make_octahedron(f"drone-{index}", 0.18, color, self.root)
            radius = 12 + (index % 5) * 4.2
            phase = index * 0.83
            height = 4 + (index % 4) * 2.2
            floater.setPos(math.cos(phase) * radius, 20 + math.sin(phase) * radius, height)
            self.floaters.append((floater, radius, phase, height))

        portal = make_ring("menu-portal", 4.7, 5.0, 64, (0.04, 0.78, 1.0, 0.55), self.root)
        portal.setPos(0, 34, 9)
        portal.setP(90)
        portal.setTransparency(True)
        self.floaters.append((portal, 0.0, 0.0, 9.0))

    def update(self, dt: float) -> None:
        self.elapsed += dt
        self.city.setH(math.sin(self.elapsed * 0.07) * 0.5)
        for index, (node, radius, phase, height) in enumerate(self.floaters):
            if node.isEmpty():
                continue
            if radius > 0:
                angle = self.elapsed * (0.12 + index * 0.003) + phase
                node.setPos(
                    math.cos(angle) * radius,
                    24 + math.sin(angle) * radius,
                    height + math.sin(angle * 2.4) * 0.7,
                )
                node.setH(node.getH() + 50 * dt)
            else:
                pulse = 1.0 + math.sin(self.elapsed * 2.0) * 0.04
                node.setScale(pulse)
                node.setR(self.elapsed * 12.0)

    def destroy(self) -> None:
        if not self.root.isEmpty():
            self.root.removeNode()


class NexusMenu:
    def __init__(self, app) -> None:
        self.app = app
        self.root = DirectFrame(
            parent=app.aspect2d,
            frameColor=(0, 0, 0, 0),
            frameSize=(-1.78, 1.78, -1, 1),
            sortOrder=10,
        )
        self.elapsed = 0.0
        self.selected_game = 0
        self.page = "games"
        self.buttons: List[MenuButtonState] = []
        self.dynamic_nodes: List[object] = []
        self.backdrop = MenuBackdrop(app)
        self.game_title: Optional[DirectLabel] = None
        self.game_subtitle: Optional[DirectLabel] = None
        self.game_description: Optional[DirectLabel] = None
        self.game_score: Optional[DirectLabel] = None
        self.game_index: Optional[DirectLabel] = None
        self.control_labels: List[DirectLabel] = []
        self.nav_indicator: Optional[DirectFrame] = None
        self._build_shell()
        self.show_games()
        self.app.camera.setPos(0, -18, 7.8)
        self.app.camera.setHpr(0, -7, 0)

    def _build_shell(self) -> None:
        left_gradient = DirectFrame(
            parent=self.root,
            frameColor=(0.012, 0.017, 0.031, 0.94),
            frameSize=(-1.78, -0.52, -1.0, 1.0),
        )
        DirectFrame(
            parent=self.root,
            frameColor=(0.02, 0.025, 0.04, 0.56),
            frameSize=(-0.52, 1.78, -1.0, 1.0),
        )
        DirectFrame(
            parent=self.root,
            frameColor=(0.03, 0.82, 1.0, 0.84),
            frameSize=(-1.78, 1.78, 0.936, 0.944),
        )
        DirectLabel(
            parent=self.root,
            text="NEXUS",
            text_fg=WHITE,
            text_scale=0.092,
            text_align=TextNode.ALeft,
            frameColor=(0, 0, 0, 0),
            pos=(-1.60, 0, 0.79),
        )
        DirectLabel(
            parent=self.root,
            text="FIVE // 3D",
            text_fg=CYAN,
            text_scale=0.040,
            text_align=TextNode.ALeft,
            frameColor=(0, 0, 0, 0),
            pos=(-1.60, 0, 0.685),
        )
        DirectLabel(
            parent=self.root,
            text="BUILD 02.00   ONLINE PROFILE",
            text_fg=MUTED,
            text_scale=0.025,
            text_align=TextNode.ALeft,
            frameColor=(0, 0, 0, 0),
            pos=(-1.60, 0, 0.615),
        )

        nav = [
            ("PLAY", self.show_games),
            ("PROFILE", self.show_profile),
            ("SETTINGS", self.show_settings),
            ("CREDITS", self.show_credits),
            ("QUIT", self.app.userExit),
        ]
        for index, (label, command) in enumerate(nav):
            y = 0.40 - index * 0.135
            button = DirectButton(
                parent=left_gradient,
                text=label,
                text_fg=WHITE,
                text_scale=0.045,
                text_align=TextNode.ALeft,
                text_pos=(-0.30, -0.015),
                frameColor=(0, 0, 0, 0),
                frameSize=(-0.34, 0.34, -0.055, 0.055),
                pos=(-0.01, 0, y),
                command=self._nav_click,
                extraArgs=[label, command, index],
                relief=DGG.FLAT,
            )
            button.bind(DGG.ENTER, self._hover_button, [button, True])
            button.bind(DGG.EXIT, self._hover_button, [button, False])
            self.buttons.append(MenuButtonState(button))

        self.nav_indicator = DirectFrame(
            parent=left_gradient,
            frameColor=CYAN,
            frameSize=(-0.008, 0.008, -0.047, 0.047),
            pos=(-0.337, 0, 0.40),
        )
        self._build_profile_strip()

    def _build_profile_strip(self) -> None:
        profile = self.app.save.profile
        level = int(profile.get("level", 1))
        xp = int(profile.get("xp", 0))
        next_xp = max(1, self.app.save.xp_for_next_level())
        progress = clamp(xp / next_xp, 0.0, 1.0)
        DirectFrame(
            parent=self.root,
            frameColor=(0.035, 0.05, 0.075, 0.94),
            frameSize=(-1.66, -0.62, -0.91, -0.70),
        )
        DirectLabel(
            parent=self.root,
            text=f"LVL {level:02d}",
            text_fg=WHITE,
            text_scale=0.045,
            text_align=TextNode.ALeft,
            frameColor=(0, 0, 0, 0),
            pos=(-1.57, 0, -0.785),
        )
        DirectLabel(
            parent=self.root,
            text=f"{xp:,} / {next_xp:,} XP",
            text_fg=MUTED,
            text_scale=0.026,
            text_align=TextNode.ARight,
            frameColor=(0, 0, 0, 0),
            pos=(-0.70, 0, -0.782),
        )
        DirectFrame(
            parent=self.root,
            frameColor=(0.12, 0.16, 0.22, 0.9),
            frameSize=(-1.56, -0.72, -0.875, -0.850),
        )
        DirectFrame(
            parent=self.root,
            frameColor=CYAN,
            frameSize=(-1.56, -1.56 + 0.84 * progress, -0.875, -0.850),
        )

    def _nav_click(self, label: str, command: Callable, index: int) -> None:
        self.app.audio.play("click", self.app.sfx_volume() * 0.55)
        if self.nav_indicator is not None:
            self.nav_indicator.setZ(0.40 - index * 0.135)
        command()

    def _hover_button(self, button: DirectButton, entered: bool, event=None) -> None:
        button["text_fg"] = CYAN if entered else WHITE
        if entered:
            self.app.audio.play("hover", self.app.sfx_volume() * 0.25, 1.0 + random.uniform(-0.04, 0.04))

    def clear_dynamic(self) -> None:
        for node in self.dynamic_nodes:
            try:
                node.destroy()
            except Exception:
                try:
                    node.removeNode()
                except Exception:
                    pass
        self.dynamic_nodes.clear()
        self.control_labels.clear()

    def add_dynamic(self, node):
        self.dynamic_nodes.append(node)
        return node

    def show_games(self) -> None:
        self.page = "games"
        self.clear_dynamic()
        panel = self.add_dynamic(
            DirectFrame(
                parent=self.root,
                frameColor=(0.02, 0.03, 0.05, 0.88),
                frameSize=(-0.42, 1.67, -0.90, 0.84),
            )
        )
        self.add_dynamic(
            DirectLabel(
                parent=panel,
                text="SELECT OPERATION",
                text_fg=MUTED,
                text_scale=0.030,
                text_align=TextNode.ALeft,
                frameColor=(0, 0, 0, 0),
                pos=(-0.31, 0, 0.70),
            )
        )

        for index, game in enumerate(GAMES):
            y = 0.50 - index * 0.22
            button = self.add_dynamic(
                DirectButton(
                    parent=panel,
                    text=f"{game.badge}    {game.title}",
                    text_fg=WHITE,
                    text_scale=0.039,
                    text_align=TextNode.ALeft,
                    text_pos=(-0.42, -0.012),
                    frameColor=(0.045, 0.065, 0.10, 0.78),
                    frameSize=(-0.47, 0.47, -0.078, 0.078),
                    pos=(0.17, 0, y),
                    command=self.select_game,
                    extraArgs=[index],
                    relief=DGG.FLAT,
                )
            )
            button.bind(DGG.ENTER, self._game_hover, [button, index, True])
            button.bind(DGG.EXIT, self._game_hover, [button, index, False])

        self.game_index = self.add_dynamic(
            DirectLabel(
                parent=panel,
                text="",
                text_fg=CYAN,
                text_scale=0.040,
                text_align=TextNode.ALeft,
                frameColor=(0, 0, 0, 0),
                pos=(0.70, 0, 0.62),
            )
        )
        self.game_title = self.add_dynamic(
            DirectLabel(
                parent=panel,
                text="",
                text_fg=WHITE,
                text_scale=0.095,
                text_align=TextNode.ALeft,
                frameColor=(0, 0, 0, 0),
                pos=(0.68, 0, 0.46),
            )
        )
        self.game_subtitle = self.add_dynamic(
            DirectLabel(
                parent=panel,
                text="",
                text_fg=CYAN,
                text_scale=0.034,
                text_align=TextNode.ALeft,
                frameColor=(0, 0, 0, 0),
                pos=(0.70, 0, 0.34),
            )
        )
        self.game_description = self.add_dynamic(
            DirectLabel(
                parent=panel,
                text="",
                text_fg=(0.74, 0.79, 0.87, 1),
                text_scale=0.033,
                text_align=TextNode.ALeft,
                text_wordwrap=31,
                frameColor=(0, 0, 0, 0),
                pos=(0.70, 0, 0.20),
            )
        )
        self.game_score = self.add_dynamic(
            DirectLabel(
                parent=panel,
                text="",
                text_fg=WHITE,
                text_scale=0.037,
                text_align=TextNode.ALeft,
                frameColor=(0, 0, 0, 0),
                pos=(0.70, 0, -0.06),
            )
        )
        self.add_dynamic(
            DirectButton(
                parent=panel,
                text="DEPLOY",
                text_fg=BLACK,
                text_scale=0.048,
                frameColor=CYAN,
                frameSize=(-0.27, 0.27, -0.075, 0.075),
                pos=(1.10, 0, -0.67),
                command=self.launch_selected,
                relief=DGG.FLAT,
            )
        )
        self._refresh_selected_game()

    def _game_hover(self, button: DirectButton, index: int, entered: bool, event=None) -> None:
        if entered:
            button["frameColor"] = (0.07, 0.12, 0.17, 0.96)
            button["text_fg"] = GAMES[index].accent
            self.select_game(index, quiet=True)
        else:
            button["frameColor"] = (0.045, 0.065, 0.10, 0.78)
            button["text_fg"] = WHITE

    def select_game(self, index: int, quiet: bool = False) -> None:
        self.selected_game = max(0, min(len(GAMES) - 1, index))
        if not quiet:
            self.app.audio.play("click", self.app.sfx_volume() * 0.42)
        self._refresh_selected_game()

    def _refresh_selected_game(self) -> None:
        if self.page != "games":
            return
        game = GAMES[self.selected_game]
        if self.game_index:
            self.game_index["text"] = f"OPERATION {game.badge}  //  {game.genre}"
            self.game_index["text_fg"] = game.accent
        if self.game_title:
            self.game_title["text"] = game.title
        if self.game_subtitle:
            self.game_subtitle["text"] = game.subtitle
            self.game_subtitle["text_fg"] = game.accent
        if self.game_description:
            self.game_description["text"] = game.description
        if self.game_score:
            score = self.app.save.score_for(game.game_id)
            plays = self.app.save.data["stats"][game.game_id]["plays"]
            self.game_score["text"] = f"PERSONAL BEST  {score:,}      RUNS  {plays}"

        for label in self.control_labels:
            try:
                label.destroy()
            except Exception:
                pass
        self.control_labels.clear()
        if self.game_description is None:
            return
        parent = self.game_description.getParent()
        for index, control in enumerate(game.controls):
            row = index // 3
            col = index % 3
            label = DirectLabel(
                parent=parent,
                text=control,
                text_fg=MUTED,
                text_scale=0.024,
                text_align=TextNode.ALeft,
                frameColor=(0.06, 0.075, 0.11, 0.8),
                frameSize=(-0.015, 0.34, -0.034, 0.034),
                pos=(0.70 + col * 0.35, 0, -0.24 - row * 0.09),
            )
            self.control_labels.append(label)
            self.dynamic_nodes.append(label)

    def launch_selected(self) -> None:
        game = GAMES[self.selected_game]
        self.app.audio.play("menu_open", self.app.sfx_volume() * 0.65)
        self.app.start_game(game.game_id)

    def show_profile(self) -> None:
        self.page = "profile"
        self.clear_dynamic()
        profile = self.app.save.profile
        panel = self.add_dynamic(
            DirectFrame(
                parent=self.root,
                frameColor=(0.02, 0.03, 0.05, 0.91),
                frameSize=(-0.42, 1.67, -0.90, 0.84),
            )
        )
        self.add_dynamic(DirectLabel(
            parent=panel,
            text="OPERATOR PROFILE",
            text_fg=WHITE,
            text_scale=0.073,
            text_align=TextNode.ALeft,
            frameColor=(0, 0, 0, 0),
            pos=(-0.28, 0, 0.63),
        ))
        cards = [
            ("LEVEL", str(profile.get("level", 1)), CYAN),
            ("GAMES PLAYED", f"{profile.get('games_played', 0):,}", MAGENTA),
            ("PLAY TIME", format_time(profile.get("total_seconds", 0)), ORANGE),
            ("CREDITS", f"{profile.get('credits', 0):,}", GREEN),
        ]
        for index, (label, value, accent) in enumerate(cards):
            x = -0.12 + (index % 2) * 0.93
            y = 0.33 - (index // 2) * 0.32
            card = self.add_dynamic(DirectFrame(
                parent=panel,
                frameColor=(0.045, 0.065, 0.095, 0.92),
                frameSize=(-0.41, 0.41, -0.115, 0.115),
                pos=(x, 0, y),
            ))
            self.add_dynamic(DirectFrame(
                parent=card,
                frameColor=accent,
                frameSize=(-0.41, -0.395, -0.115, 0.115),
            ))
            self.add_dynamic(DirectLabel(
                parent=card,
                text=label,
                text_fg=MUTED,
                text_scale=0.025,
                text_align=TextNode.ALeft,
                frameColor=(0, 0, 0, 0),
                pos=(-0.34, 0, 0.035),
            ))
            self.add_dynamic(DirectLabel(
                parent=card,
                text=value,
                text_fg=WHITE,
                text_scale=0.055,
                text_align=TextNode.ALeft,
                frameColor=(0, 0, 0, 0),
                pos=(-0.34, 0, -0.045),
            ))

        y = -0.35
        self.add_dynamic(DirectLabel(
            parent=panel,
            text="PERSONAL BESTS",
            text_fg=MUTED,
            text_scale=0.030,
            text_align=TextNode.ALeft,
            frameColor=(0, 0, 0, 0),
            pos=(-0.28, 0, y),
        ))
        for index, game in enumerate(GAMES):
            row_y = y - 0.11 - index * 0.09
            score = self.app.save.score_for(game.game_id)
            self.add_dynamic(DirectLabel(
                parent=panel,
                text=game.title,
                text_fg=game.accent,
                text_scale=0.027,
                text_align=TextNode.ALeft,
                frameColor=(0, 0, 0, 0),
                pos=(-0.27, 0, row_y),
            ))
            self.add_dynamic(DirectLabel(
                parent=panel,
                text=f"{score:,}",
                text_fg=WHITE,
                text_scale=0.028,
                text_align=TextNode.ARight,
                frameColor=(0, 0, 0, 0),
                pos=(1.42, 0, row_y),
            ))

    def _setting_row(self, panel, title: str, y: float, value_text: str, accent: Color = CYAN) -> DirectLabel:
        self.add_dynamic(DirectLabel(
            parent=panel,
            text=title,
            text_fg=WHITE,
            text_scale=0.034,
            text_align=TextNode.ALeft,
            frameColor=(0, 0, 0, 0),
            pos=(-0.27, 0, y),
        ))
        label = self.add_dynamic(DirectLabel(
            parent=panel,
            text=value_text,
            text_fg=accent,
            text_scale=0.030,
            text_align=TextNode.ARight,
            frameColor=(0, 0, 0, 0),
            pos=(1.42, 0, y),
        ))
        return label

    def show_settings(self) -> None:
        self.page = "settings"
        self.clear_dynamic()
        settings = self.app.save.settings
        panel = self.add_dynamic(DirectFrame(
            parent=self.root,
            frameColor=(0.02, 0.03, 0.05, 0.92),
            frameSize=(-0.42, 1.67, -0.90, 0.84),
        ))
        self.add_dynamic(DirectLabel(
            parent=panel,
            text="SETTINGS",
            text_fg=WHITE,
            text_scale=0.073,
            text_align=TextNode.ALeft,
            frameColor=(0, 0, 0, 0),
            pos=(-0.28, 0, 0.66),
        ))
        difficulty_label = self._setting_row(panel, "DIFFICULTY", 0.46, settings.get("difficulty", "OPERATIVE"), MAGENTA)
        for index, name in enumerate(("RECRUIT", "OPERATIVE", "VETERAN")):
            button = self.add_dynamic(DirectButton(
                parent=panel,
                text=name,
                text_fg=WHITE,
                text_scale=0.024,
                frameColor=(0.06, 0.08, 0.12, 0.9),
                frameSize=(-0.18, 0.18, -0.045, 0.045),
                pos=(0.31 + index * 0.39, 0, 0.46),
                command=self._set_difficulty,
                extraArgs=[name, difficulty_label],
                relief=DGG.FLAT,
            ))

        volume_label = self._setting_row(panel, "MASTER VOLUME", 0.27, f"{int(settings.get('master_volume', 0.72) * 100)}%", CYAN)
        slider = self.add_dynamic(DirectSlider(
            parent=panel,
            range=(0.0, 1.0),
            value=settings.get("master_volume", 0.72),
            pageSize=0.05,
            scale=0.48,
            pos=(0.83, 0, 0.27),
            frameColor=(0.08, 0.11, 0.16, 1),
            thumb_frameColor=CYAN,
        ))
        slider["command"] = self._set_master_volume
        slider["extraArgs"] = [slider, volume_label]
        sensitivity_label = self._setting_row(panel, "MOUSE SENSITIVITY", 0.08, f"{settings.get('mouse_sensitivity', 0.18):.2f}", ORANGE)
        sensitivity_slider = self.add_dynamic(DirectSlider(
            parent=panel,
            range=(0.06, 0.40),
            value=settings.get("mouse_sensitivity", 0.18),
            pageSize=0.02,
            scale=0.48,
            pos=(0.83, 0, 0.08),
            frameColor=(0.08, 0.11, 0.16, 1),
            thumb_frameColor=ORANGE,
        ))
        sensitivity_slider["command"] = self._set_sensitivity
        sensitivity_slider["extraArgs"] = [sensitivity_slider, sensitivity_label]
        fov_label = self._setting_row(panel, "FIELD OF VIEW", -0.11, f"{int(settings.get('fov', 82))}", GREEN)
        fov_slider = self.add_dynamic(DirectSlider(
            parent=panel,
            range=(68, 105),
            value=settings.get("fov", 82),
            pageSize=2,
            scale=0.48,
            pos=(0.83, 0, -0.11),
            frameColor=(0.08, 0.11, 0.16, 1),
            thumb_frameColor=GREEN,
        ))
        fov_slider["command"] = self._set_fov
        fov_slider["extraArgs"] = [fov_slider, fov_label]

        quality = str(settings.get("graphics_quality", "ULTRA")).upper()
        quality_label = self._setting_row(panel, "GRAPHICS QUALITY", -0.29, quality, CYAN)
        self.add_dynamic(DirectButton(
            parent=panel,
            text="CYCLE",
            text_fg=WHITE,
            text_scale=0.024,
            frameColor=(0.06, 0.08, 0.12, 0.9),
            frameSize=(-0.19, 0.19, -0.043, 0.043),
            pos=(0.80, 0, -0.29),
            command=self._cycle_graphics_quality,
            extraArgs=[quality_label],
            relief=DGG.FLAT,
        ))
        self.add_dynamic(DirectLabel(
            parent=panel,
            text="restart for full renderer changes",
            text_fg=(0.48, 0.55, 0.64, 1),
            text_scale=0.018,
            text_align=TextNode.ARight,
            frameColor=(0, 0, 0, 0),
            pos=(1.42, 0, -0.355),
        ))
        self._toggle_row(panel, "CAMERA SHAKE", -0.46, "camera_shake", MAGENTA)
        self._toggle_row(panel, "PARTICLES", -0.60, "particles", CYAN)
        self._toggle_row(panel, "FULLSCREEN", -0.74, "fullscreen", ORANGE)

    def _toggle_row(self, panel, title: str, y: float, key: str, accent: Color) -> None:
        value = bool(self.app.save.setting(key, False))
        value_label = self._setting_row(panel, title, y, "ON" if value else "OFF", accent)
        self.add_dynamic(DirectButton(
            parent=panel,
            text="TOGGLE",
            text_fg=WHITE,
            text_scale=0.024,
            frameColor=(0.06, 0.08, 0.12, 0.9),
            frameSize=(-0.19, 0.19, -0.043, 0.043),
            pos=(0.80, 0, y),
            command=self._toggle_setting,
            extraArgs=[key, value_label],
            relief=DGG.FLAT,
        ))

    def _set_difficulty(self, name: str, label: DirectLabel) -> None:
        self.app.save.set_setting("difficulty", name)
        label["text"] = name
        self.app.audio.play("click", self.app.sfx_volume() * 0.4)

    def _set_master_volume(self, slider: DirectSlider, label: DirectLabel) -> None:
        value = float(slider["value"])
        self.app.save.set_setting("master_volume", value)
        label["text"] = f"{int(value * 100)}%"

    def _set_sensitivity(self, slider: DirectSlider, label: DirectLabel) -> None:
        value = float(slider["value"])
        self.app.save.set_setting("mouse_sensitivity", value)
        label["text"] = f"{value:.2f}"

    def _set_fov(self, slider: DirectSlider, label: DirectLabel) -> None:
        value = int(float(slider["value"]))
        self.app.save.set_setting("fov", value)
        self.app.camLens.setFov(value)
        label["text"] = f"{value}"

    def _cycle_graphics_quality(self, label: DirectLabel) -> None:
        levels = ("LOW", "MEDIUM", "HIGH", "ULTRA", "CINEMATIC")
        current = str(self.app.save.setting("graphics_quality", "ULTRA")).upper()
        try:
            index = levels.index(current)
        except ValueError:
            index = 2
        value = levels[(index + 1) % len(levels)]
        self.app.save.set_setting("graphics_quality", value)
        label["text"] = value
        self.app.audio.play("click", self.app.sfx_volume() * 0.4)

    def _toggle_setting(self, key: str, label: DirectLabel) -> None:
        value = not bool(self.app.save.setting(key, False))
        self.app.save.set_setting(key, value)
        label["text"] = "ON" if value else "OFF"
        if key == "fullscreen":
            self.app.apply_window_settings()
        self.app.audio.play("click", self.app.sfx_volume() * 0.4)

    def show_credits(self) -> None:
        self.page = "credits"
        self.clear_dynamic()
        panel = self.add_dynamic(DirectFrame(
            parent=self.root,
            frameColor=(0.02, 0.03, 0.05, 0.92),
            frameSize=(-0.42, 1.67, -0.90, 0.84),
        ))
        self.add_dynamic(DirectLabel(
            parent=panel,
            text="NEXUS FIVE // 3D",
            text_fg=CYAN,
            text_scale=0.080,
            text_align=TextNode.ALeft,
            frameColor=(0, 0, 0, 0),
            pos=(-0.28, 0, 0.58),
        ))
        lines = [
            "A Python 3D arcade collection built on Panda3D.",
            "Five standalone game modes. One launcher. One profile.",
            "All geometry is generated from code. No paid assets required.",
            "Procedural sound effects are generated locally at first launch.",
            "This is a prototype framework, not a Call of Duty or GTA clone.",
            "Use it as a base for maps, models, textures, animations and networking.",
        ]
        for index, line in enumerate(lines):
            self.add_dynamic(DirectLabel(
                parent=panel,
                text=line,
                text_fg=WHITE if index < 2 else MUTED,
                text_scale=0.033,
                text_align=TextNode.ALeft,
                frameColor=(0, 0, 0, 0),
                pos=(-0.27, 0, 0.35 - index * 0.10),
            ))

    def update(self, dt: float) -> None:
        self.elapsed += dt
        self.backdrop.update(dt)
        self.app.camera.setX(math.sin(self.elapsed * 0.12) * 0.42)
        self.app.camera.setZ(7.8 + math.sin(self.elapsed * 0.18) * 0.18)
        self.app.camera.setH(math.sin(self.elapsed * 0.10) * 1.2)

    def destroy(self) -> None:
        self.clear_dynamic()
        for state in self.buttons:
            try:
                state.button.destroy()
            except Exception:
                pass
        self.buttons.clear()
        self.backdrop.destroy()
        self.root.destroy()
