from __future__ import annotations

import math
import os
import random
import struct
import wave
from typing import Dict

from direct.showbase.ShowBase import ShowBase

from .config import AUDIO_FOLDER


class ProceduralAudio:
    """Creates tiny sound effects locally, so the project ships without external assets."""

    SAMPLE_RATE = 22050

    def __init__(self, base: ShowBase) -> None:
        self.base = base
        self.sounds: Dict[str, object] = {}
        os.makedirs(AUDIO_FOLDER, exist_ok=True)
        self._ensure_assets()
        self._load_assets()

    def _ensure_assets(self) -> None:
        specs = {
            "click": (0.07, 720.0, 0.35, "tone"),
            "hover": (0.04, 1100.0, 0.18, "tone"),
            "shot": (0.12, 130.0, 0.55, "noise"),
            "laser": (0.14, 880.0, 0.45, "sweep"),
            "hit": (0.08, 180.0, 0.50, "noise"),
            "explosion": (0.42, 75.0, 0.65, "noise"),
            "reload": (0.18, 320.0, 0.28, "clicks"),
            "pickup": (0.20, 660.0, 0.35, "rise"),
            "dash": (0.18, 250.0, 0.32, "sweep"),
            "nitro": (0.28, 105.0, 0.38, "noise"),
            "menu_open": (0.30, 360.0, 0.28, "rise"),
            "game_over": (0.65, 220.0, 0.35, "fall"),
        }
        for name, (duration, freq, volume, shape) in specs.items():
            path = os.path.join(AUDIO_FOLDER, f"{name}.wav")
            if not os.path.exists(path):
                self._write_wave(path, duration, freq, volume, shape)

    def _write_wave(self, path: str, duration: float, freq: float, volume: float, shape: str) -> None:
        frames = int(self.SAMPLE_RATE * duration)
        samples = []
        phase = 0.0
        for i in range(frames):
            t = i / self.SAMPLE_RATE
            progress = i / max(1, frames - 1)
            envelope = max(0.0, 1.0 - progress)
            if shape == "noise":
                value = random.uniform(-1.0, 1.0) * envelope
            elif shape == "sweep":
                f = freq * (1.7 - 0.9 * progress)
                phase += math.tau * f / self.SAMPLE_RATE
                value = math.sin(phase) * envelope
            elif shape == "rise":
                f = freq * (0.65 + 1.2 * progress)
                phase += math.tau * f / self.SAMPLE_RATE
                value = (math.sin(phase) + 0.35 * math.sin(phase * 2.0)) * envelope
            elif shape == "fall":
                f = freq * (1.3 - 0.8 * progress)
                phase += math.tau * f / self.SAMPLE_RATE
                value = math.sin(phase) * (0.4 + 0.6 * envelope)
            elif shape == "clicks":
                carrier = math.sin(math.tau * freq * t)
                gate = 1.0 if (i // max(1, frames // 6)) % 2 == 0 else 0.25
                value = carrier * gate * envelope
            else:
                value = math.sin(math.tau * freq * t) * envelope
            value = max(-1.0, min(1.0, value * volume))
            samples.append(int(value * 32767))

        with wave.open(path, "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(self.SAMPLE_RATE)
            handle.writeframes(b"".join(struct.pack("<h", sample) for sample in samples))

    def _load_assets(self) -> None:
        for filename in os.listdir(AUDIO_FOLDER):
            if not filename.endswith(".wav"):
                continue
            name = os.path.splitext(filename)[0]
            path = os.path.join(AUDIO_FOLDER, filename)
            try:
                self.sounds[name] = self.base.loader.loadSfx(path)
            except Exception:
                pass

    def play(self, name: str, volume: float = 1.0, rate: float = 1.0) -> None:
        sound = self.sounds.get(name)
        if sound is None:
            return
        try:
            sound.setVolume(max(0.0, min(1.0, volume)))
            sound.setPlayRate(max(0.25, min(3.0, rate)))
            sound.play()
        except Exception:
            pass

    def stop_all(self) -> None:
        for sound in self.sounds.values():
            try:
                sound.stop()
            except Exception:
                pass
