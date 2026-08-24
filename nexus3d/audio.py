from __future__ import annotations

from dataclasses import dataclass
import math
import os
import random
import struct
import wave
from typing import Dict, List, Tuple

from direct.showbase.ShowBase import ShowBase

from .config import AUDIO_FOLDER


@dataclass(frozen=True)
class SoundSpec:
    duration: float
    frequency: float
    volume: float
    shape: str
    voices: int = 3


class ProceduralAudio:
    """Deterministic layered sound engine generated entirely on the player's PC.

    The first version used one AudioSound instance per effect, which caused fast
    weapon fire to restart the same voice. Version 2 keeps a small round-robin
    voice pool, regenerates higher-detail source waves once, and layers selected
    transient effects for more weight without shipping copyrighted audio assets.
    """

    SAMPLE_RATE = 32000
    AUDIO_VERSION = 2

    SPECS: Dict[str, SoundSpec] = {
        "click": SoundSpec(0.075, 760.0, 0.30, "ui_click", 2),
        "hover": SoundSpec(0.045, 1180.0, 0.16, "tone", 2),
        "shot": SoundSpec(0.115, 118.0, 0.68, "gunshot", 6),
        "shot_tail": SoundSpec(0.20, 82.0, 0.34, "gun_tail", 6),
        "laser": SoundSpec(0.16, 920.0, 0.46, "laser", 6),
        "hit": SoundSpec(0.09, 185.0, 0.50, "impact", 5),
        "explosion": SoundSpec(0.48, 68.0, 0.74, "explosion", 5),
        "explosion_tail": SoundSpec(0.72, 42.0, 0.34, "rumble", 4),
        "reload": SoundSpec(0.34, 350.0, 0.34, "reload", 3),
        "pickup": SoundSpec(0.22, 680.0, 0.34, "rise", 3),
        "dash": SoundSpec(0.22, 270.0, 0.36, "whoosh", 4),
        "nitro": SoundSpec(0.32, 102.0, 0.42, "engine_burst", 4),
        "menu_open": SoundSpec(0.34, 390.0, 0.28, "rise", 2),
        "game_over": SoundSpec(0.72, 210.0, 0.38, "fall", 2),
        "shield": SoundSpec(0.17, 510.0, 0.30, "shield", 4),
        "warning": SoundSpec(0.16, 760.0, 0.24, "warning", 3),
        "land": SoundSpec(0.10, 90.0, 0.28, "impact", 3),
    }

    def __init__(self, base: ShowBase) -> None:
        self.base = base
        self.sounds: Dict[str, List[object]] = {}
        self.voice_index: Dict[str, int] = {}
        os.makedirs(AUDIO_FOLDER, exist_ok=True)
        self._ensure_assets()
        self._load_assets()

    def _ensure_assets(self) -> None:
        marker = os.path.join(AUDIO_FOLDER, ".nexus_audio_version")
        current = ""
        try:
            with open(marker, "r", encoding="utf-8") as handle:
                current = handle.read().strip()
        except OSError:
            pass
        regenerate = current != str(self.AUDIO_VERSION)

        for name, spec in self.SPECS.items():
            path = os.path.join(AUDIO_FOLDER, f"{name}.wav")
            if regenerate or not os.path.exists(path):
                self._write_wave(path, name, spec)

        if regenerate:
            try:
                with open(marker, "w", encoding="utf-8") as handle:
                    handle.write(str(self.AUDIO_VERSION))
            except OSError:
                pass

    def _write_wave(self, path: str, name: str, spec: SoundSpec) -> None:
        frames = max(1, int(self.SAMPLE_RATE * spec.duration))
        rng = random.Random(self._stable_seed(name))
        samples: List[int] = []
        phase = 0.0
        phase_b = 0.0
        previous_noise = 0.0

        for i in range(frames):
            t = i / self.SAMPLE_RATE
            progress = i / max(1, frames - 1)
            envelope = self._envelope(progress, spec.shape)
            noise = rng.uniform(-1.0, 1.0)
            smooth_noise = previous_noise * 0.72 + noise * 0.28
            previous_noise = smooth_noise

            if spec.shape == "gunshot":
                punch = math.sin(math.tau * (spec.frequency * (1.0 - progress * 0.35)) * t)
                crack = noise * (1.0 - progress) ** 2.7
                body = smooth_noise * math.exp(-progress * 4.8)
                value = punch * 0.46 + crack * 0.66 + body * 0.32
            elif spec.shape == "gun_tail":
                value = smooth_noise * math.exp(-progress * 3.2)
                value += math.sin(math.tau * spec.frequency * 0.72 * t) * math.exp(-progress * 5.0) * 0.28
            elif spec.shape == "explosion":
                low = math.sin(math.tau * spec.frequency * (1.0 - progress * 0.22) * t)
                sub = math.sin(math.tau * spec.frequency * 0.47 * t)
                value = smooth_noise * 0.62 + low * 0.48 + sub * 0.28
                value *= math.exp(-progress * 2.4)
            elif spec.shape == "rumble":
                sub = math.sin(math.tau * spec.frequency * t)
                value = sub * 0.42 + smooth_noise * 0.58
                value *= math.exp(-progress * 2.8)
            elif spec.shape == "laser":
                frequency = spec.frequency * (1.55 - progress * 0.82)
                phase += math.tau * frequency / self.SAMPLE_RATE
                phase_b += math.tau * frequency * 1.51 / self.SAMPLE_RATE
                value = math.sin(phase) * 0.72 + math.sin(phase_b) * 0.23 + noise * 0.08
            elif spec.shape == "whoosh":
                sweep = 140.0 + 880.0 * progress
                phase += math.tau * sweep / self.SAMPLE_RATE
                value = smooth_noise * 0.58 + math.sin(phase) * 0.22
            elif spec.shape == "engine_burst":
                frequency = spec.frequency * (0.82 + progress * 1.25)
                phase += math.tau * frequency / self.SAMPLE_RATE
                value = math.sin(phase) * 0.45 + math.sin(phase * 2.03) * 0.18 + smooth_noise * 0.38
            elif spec.shape == "reload":
                segment = int(progress * 8.0)
                gate = 1.0 if segment in (0, 1, 4, 6) else 0.22
                metallic = math.sin(math.tau * spec.frequency * (1.0 + segment * 0.08) * t)
                value = (metallic * 0.65 + noise * 0.18) * gate
            elif spec.shape == "impact":
                value = smooth_noise * 0.48 + math.sin(math.tau * spec.frequency * t) * 0.55
                value *= math.exp(-progress * 6.0)
            elif spec.shape == "shield":
                frequency = spec.frequency * (1.0 + progress * 0.55)
                phase += math.tau * frequency / self.SAMPLE_RATE
                value = math.sin(phase) * 0.58 + math.sin(phase * 2.4) * 0.20
            elif spec.shape == "warning":
                gate = 1.0 if int(progress * 6.0) % 2 == 0 else 0.16
                value = math.sin(math.tau * spec.frequency * t) * gate
            elif spec.shape == "ui_click":
                value = math.sin(math.tau * spec.frequency * t) * 0.62 + noise * 0.10
            elif spec.shape == "rise":
                frequency = spec.frequency * (0.62 + 1.30 * progress)
                phase += math.tau * frequency / self.SAMPLE_RATE
                value = math.sin(phase) + 0.30 * math.sin(phase * 2.0)
            elif spec.shape == "fall":
                frequency = spec.frequency * (1.35 - 0.82 * progress)
                phase += math.tau * frequency / self.SAMPLE_RATE
                value = math.sin(phase) * 0.78 + math.sin(phase * 0.5) * 0.18
            else:
                value = math.sin(math.tau * spec.frequency * t)

            # Tiny deterministic saturation gives transients more perceived
            # weight while keeping them inside the 16-bit range.
            value = math.tanh(value * 1.35) * envelope * spec.volume
            value = max(-1.0, min(1.0, value))
            samples.append(int(value * 32767))

        with wave.open(path, "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(self.SAMPLE_RATE)
            handle.writeframes(b"".join(struct.pack("<h", sample) for sample in samples))

    @staticmethod
    def _envelope(progress: float, shape: str) -> float:
        progress = max(0.0, min(1.0, progress))
        attack = min(1.0, progress / 0.025) if progress < 0.025 else 1.0
        if shape in ("rumble", "fall"):
            decay = (1.0 - progress) ** 1.2
        elif shape in ("laser", "whoosh", "rise", "shield"):
            decay = (1.0 - progress) ** 1.5
        else:
            decay = (1.0 - progress) ** 2.1
        return attack * decay

    @staticmethod
    def _stable_seed(name: str) -> int:
        seed = 2166136261
        for char in name:
            seed ^= ord(char)
            seed = (seed * 16777619) & 0xFFFFFFFF
        return seed

    def _load_assets(self) -> None:
        self.sounds.clear()
        self.voice_index.clear()
        for name, spec in self.SPECS.items():
            path = os.path.join(AUDIO_FOLDER, f"{name}.wav")
            voices: List[object] = []
            for _ in range(max(1, spec.voices)):
                try:
                    voices.append(self.base.loader.loadSfx(path))
                except Exception:
                    break
            if voices:
                self.sounds[name] = voices
                self.voice_index[name] = 0

    def _voice(self, name: str):
        voices = self.sounds.get(name)
        if not voices:
            return None
        index = self.voice_index.get(name, 0) % len(voices)
        self.voice_index[name] = (index + 1) % len(voices)
        return voices[index]

    def play(self, name: str, volume: float = 1.0, rate: float = 1.0) -> None:
        self._play_voice(name, volume, rate)

        # A few effects automatically get a quieter secondary layer. Call sites
        # remain unchanged, but the result has more body and spatial complexity.
        if name == "shot":
            self._play_voice("shot_tail", volume * 0.38, rate * 0.84)
        elif name == "explosion":
            self._play_voice("explosion_tail", volume * 0.52, rate * 0.76)
        elif name == "nitro":
            self._play_voice("dash", volume * 0.20, rate * 0.62)

    def _play_voice(self, name: str, volume: float, rate: float) -> None:
        sound = self._voice(name)
        if sound is None:
            return
        try:
            sound.setVolume(max(0.0, min(1.0, volume)))
            sound.setPlayRate(max(0.25, min(3.0, rate)))
            sound.play()
        except Exception:
            pass

    def stop_all(self) -> None:
        for voices in self.sounds.values():
            for sound in voices:
                try:
                    sound.stop()
                except Exception:
                    pass
