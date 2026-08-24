from __future__ import annotations

from typing import Optional

from panda3d.core import AntialiasAttrib

from .environment import CinematicEnvironment
from .materials import MaterialLibrary
from .quality import GraphicsQuality, resolve_quality
from .reactive_lighting import ReactiveLighting
from .runtime import AdaptiveGraphicsController


class GraphicsDirector:
    """Owns the renderer, post effects and one cinematic environment at a time."""

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
        self.runtime = AdaptiveGraphicsController(app)
        self.reactive_lighting: Optional[ReactiveLighting] = None
        self._exposure = 0.25
        self._exposure_target = 0.25
        self.initialize()
        try:
            self.reactive_lighting = ReactiveLighting(app)
        except Exception as exc:
            self.errors.append(f"reactive lighting unavailable: {exc}")

    def initialize(self) -> None:
        self.app.render.setAntialias(AntialiasAttrib.MMultisample)
        self.app.camLens.setNearFar(0.05, 1400.0)
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
                shadow_bias=0.0045,
                exposure=0.38,
                enable_fog=True,
                use_normal_maps=True,
                use_emission_maps=True,
                use_occlusion_maps=True,
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
                    filters.setExposureAdjust(self._exposure)
                except Exception:
                    pass
                try:
                    filters.setBloom(
                        blend=(0.28, 0.38, 0.32, 0.14),
                        mintrigger=0.78,
                        maxtrigger=1.35,
                        desat=0.22,
                        intensity=self.quality.bloom_intensity,
                        size="medium" if self.quality.environment_detail < 4 else "large",
                    )
                except Exception:
                    pass
                try:
                    filters.setAmbientOcclusion(
                        numsamples=self.quality.ssao_samples,
                        radius=0.055,
                        amount=1.65,
                        strength=self.quality.ssao_strength,
                        falloff=0.000002,
                    )
                except Exception:
                    pass
                try:
                    filters.setGammaAdjust(1.02)
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
        self.runtime.reset()
        self.runtime.update(1.0 / max(30.0, self.runtime.target_fps), self.environment)
        self._set_exposure_target(profile_id)

    def _set_exposure_target(self, profile_id: str) -> None:
        targets = {
            "menu": 0.30,
            "neon_ops": 0.34,
            "street_rush": 0.31,
            "zombie_siege": 0.20,
            "orbital_wars": 0.40,
            "cyber_runner": 0.36,
        }
        self._exposure_target = targets.get(profile_id, 0.28)

    def _update_exposure(self, dt: float) -> None:
        if not bool(self.app.save.setting("dynamic_exposure", True)):
            return
        flash = 0.0
        sky_luma = 0.5
        if self.environment is not None:
            flash = float(getattr(self.environment, "lightning_flash", 0.0))
            sky_luma = float(getattr(self.environment, "sky_luminance", 0.5))
        desired = self._exposure_target - flash * 0.16 - max(0.0, sky_luma - 0.55) * 0.10
        desired = max(0.04, min(0.55, desired))
        blend = min(1.0, dt * 2.0)
        self._exposure += (desired - self._exposure) * blend

        if self.filters is not None:
            try:
                self.filters.setExposureAdjust(self._exposure)
            except Exception:
                pass
        if self.pbr_pipeline is not None:
            try:
                self.pbr_pipeline.exposure = self._exposure + 0.12
            except Exception:
                pass

    def update(self, dt: float) -> None:
        self.runtime.update(dt, self.environment)
        if self.environment is not None:
            self.environment.update(dt)
        if self.reactive_lighting is not None:
            self.reactive_lighting.update(dt, getattr(self.app, "mode", None))
        self._update_exposure(dt)

    def runtime_snapshot(self):
        return self.runtime.snapshot()

    def configure_directional_light(self, light) -> None:
        if not self.quality.enable_shadows:
            return
        try:
            size = self.quality.shadow_map_size
            light.setShadowCaster(True, size, size)
            lens = light.getLens()
            lens.setNearFar(0.6, 320.0)
            lens.setFilmSize(175.0, 175.0)
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
        if self.reactive_lighting is not None:
            try:
                self.reactive_lighting.destroy()
            except Exception:
                pass
            self.reactive_lighting = None
        if self.filters is not None:
            try:
                self.filters.cleanup()
            except Exception:
                pass
            self.filters = None
