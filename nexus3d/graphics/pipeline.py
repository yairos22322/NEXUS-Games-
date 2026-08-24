from __future__ import annotations

import traceback
from typing import Optional

from panda3d.core import AntialiasAttrib

from .environment import CinematicEnvironment
from .materials import MaterialLibrary
from .quality import GraphicsQuality, resolve_quality


class GraphicsDirector:
    """Owns the renderer upgrade and one cinematic environment at a time."""

    def __init__(self, app) -> None:
        self.app = app
        self.materials = MaterialLibrary()
        self.quality: GraphicsQuality = resolve_quality(app.save.setting("graphics_quality", "ULTRA"))
        self.backend = "uninitialized"
        self.pbr_pipeline = None
        self.filters = None
        self.environment: Optional[CinematicEnvironment] = None
        self.profile_id = "menu"
        self.seed_counter = 0
        self.errors: list[str] = []
        self.initialize()

    def initialize(self) -> None:
        self.app.render.setAntialias(AntialiasAttrib.MMultisample)
        self.app.camLens.setNearFar(0.05, 1200.0)
        self._try_simplepbr()
        if self.pbr_pipeline is None:
            self._enable_builtin_shader_pipeline()
            self._try_common_filters()
        self.backend = "simplepbr" if self.pbr_pipeline is not None else "panda-auto"

    def _try_simplepbr(self) -> None:
        try:
            import simplepbr

            self.pbr_pipeline = simplepbr.init(
                render_node=self.app.render,
                window=self.app.win,
                camera_node=self.app.cam,
                msaa_samples=self.quality.msaa_samples,
                max_lights=self.quality.max_lights,
                enable_shadows=self.quality.enable_shadows,
                shadow_bias=0.006,
                exposure=0.35,
                enable_fog=True,
                use_normal_maps=False,
                use_emission_maps=True,
                use_occlusion_maps=False,
            )
        except Exception as exc:
            self.pbr_pipeline = None
            self.errors.append(f"simplepbr unavailable: {exc}")

    def _enable_builtin_shader_pipeline(self) -> None:
        try:
            self.app.render.setShaderAuto()
        except Exception as exc:
            self.errors.append(f"auto shader unavailable: {exc}")

    def _try_common_filters(self) -> None:
        if not bool(self.app.save.setting("cinematic_postfx", True)):
            return
        try:
            from direct.filter.CommonFilters import CommonFilters, ToneMap

            filters = CommonFilters(self.app.win, self.app.cam)
            if self.quality.enable_postfx:
                try:
                    filters.setHighDynamicRange(ToneMap.ACES)
                    filters.setExposureAdjust(0.25)
                except Exception:
                    pass
                try:
                    filters.setBloom(
                        blend=(0.30, 0.40, 0.30, 0.16),
                        mintrigger=0.72,
                        maxtrigger=1.25,
                        desat=0.28,
                        intensity=self.quality.bloom_intensity,
                        size="medium" if self.quality.environment_detail < 4 else "large",
                    )
                except Exception:
                    pass
                try:
                    filters.setAmbientOcclusion(
                        numsamples=self.quality.ssao_samples,
                        radius=0.06,
                        amount=1.8,
                        strength=self.quality.ssao_strength,
                        falloff=0.000002,
                    )
                except Exception:
                    pass
                try:
                    filters.setGammaAdjust(1.03)
                except Exception:
                    pass
            self.filters = filters
        except Exception as exc:
            self.filters = None
            self.errors.append(f"post-processing unavailable: {exc}")

    def set_profile(self, profile_id: str) -> None:
        self.profile_id = profile_id
        if self.environment is not None:
            self.environment.destroy()
            self.environment = None
        self.seed_counter += 1
        persistent_seed = int(self.app.save.profile.get("level", 1)) * 10007
        score_seed = int(self.app.save.score_for(profile_id)) if profile_id != "menu" else 0
        seed = persistent_seed + score_seed + self.seed_counter * 193
        self.environment = CinematicEnvironment(
            self.app,
            self.materials,
            profile_id,
            self.quality,
            seed,
        )

    def update(self, dt: float) -> None:
        if self.environment is not None:
            self.environment.update(dt)

    def configure_directional_light(self, light) -> None:
        if not self.quality.enable_shadows:
            return
        try:
            size = self.quality.shadow_map_size
            light.setShadowCaster(True, size, size)
            lens = light.getLens()
            lens.setNearFar(1.0, 260.0)
            lens.setFilmSize(150.0, 150.0)
        except Exception as exc:
            self.errors.append(f"shadow configuration failed: {exc}")

    def apply_surface(self, node, name: str, color=None) -> None:
        try:
            self.materials.apply_by_name(node, name, color)
        except Exception:
            pass

    def destroy(self) -> None:
        if self.environment is not None:
            self.environment.destroy()
            self.environment = None
        if self.filters is not None:
            try:
                self.filters.cleanup()
            except Exception:
                pass
            self.filters = None
