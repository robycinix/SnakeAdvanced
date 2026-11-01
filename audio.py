"""
Modulo audio: effetti sonori sintetizzati al volo (nessun file esterno).
Le onde vengono generate una volta sola e messe in cache a livello di modulo,
così creare più istanze di Game (es. nei test) non rallenta.
Se il mixer non è disponibile il gioco resta muto senza errori.
"""

import array
import math
import random
from typing import Dict, List, Optional, Tuple

import pygame

_CACHE: Dict[str, "pygame.mixer.Sound"] = {}


def _render(parts: List[Tuple[float, float, float, float, str, float, float]], rate: int,
            channels: int, duration: float) -> bytes:
    """
    Miscela più "voci" in un unico buffer PCM a 16 bit.
    Ogni voce: (inizio, durata, freq_iniziale, freq_finale, forma, volume, rumore).
    """
    n = int(rate * duration)
    mix = [0.0] * n
    rng = random.Random(3)
    for start, dur, f0, f1, wave, vol, noise in parts:
        s0 = int(start * rate)
        cnt = int(dur * rate)
        phase = 0.0
        for i in range(cnt):
            idx = s0 + i
            if idx >= n:
                break
            f = i / cnt
            phase += math.tau * (f0 + (f1 - f0) * f) / rate
            if wave == "square":
                v = 0.6 if math.sin(phase) > 0 else -0.6
            elif wave == "saw":
                v = ((phase / math.tau) % 1.0) * 2 - 1
            else:
                v = math.sin(phase)
            if noise:
                v = v * (1 - noise) + rng.uniform(-1, 1) * noise
            env = min(1.0, i / (rate * 0.004)) * (1 - f) ** 2
            mix[idx] += v * env * vol
    buf = array.array("h")
    for v in mix:
        s = int(max(-1.0, min(1.0, v)) * 32000)
        for _ in range(channels):
            buf.append(s)
    return buf.tobytes()


# Ricette: (durata totale, voci)
_RECIPES = {
    "eat": (0.12, [(0, 0.12, 520, 1040, "sine", 0.45, 0.0)]),
    "eat2": (0.12, [(0, 0.12, 620, 1240, "sine", 0.45, 0.0)]),
    "eat3": (0.12, [(0, 0.12, 740, 1480, "sine", 0.45, 0.0)]),
    "eat4": (0.12, [(0, 0.12, 880, 1760, "sine", 0.45, 0.0)]),
    "eat5": (0.14, [(0, 0.14, 1040, 2080, "sine", 0.45, 0.0)]),
    "golden": (0.45, [(0, 0.15, 660, 660, "square", 0.25, 0), (0.1, 0.15, 880, 880, "square", 0.25, 0),
                      (0.2, 0.25, 1320, 1320, "square", 0.25, 0)]),
    "power": (0.4, [(0, 0.4, 300, 1500, "square", 0.25, 0.0), (0, 0.4, 600, 3000, "sine", 0.2, 0)]),
    "shield": (0.35, [(0, 0.35, 1400, 700, "sine", 0.4, 0.15), (0, 0.2, 2200, 1800, "sine", 0.2, 0)]),
    "dash": (0.35, [(0, 0.35, 200, 900, "saw", 0.18, 0.6)]),
    "nova": (1.1, [(0, 1.1, 140, 35, "sine", 0.7, 0.0), (0, 0.7, 80, 40, "saw", 0.3, 0.7),
                   (0, 0.3, 1200, 200, "square", 0.15, 0.2)]),
    "explode": (0.5, [(0, 0.5, 110, 40, "sine", 0.6, 0.0), (0, 0.4, 200, 80, "saw", 0.4, 0.8)]),
    "death": (0.9, [(0, 0.9, 420, 50, "saw", 0.35, 0.2), (0, 0.6, 100, 30, "sine", 0.5, 0.6)]),
    "level": (0.5, [(0, 0.12, 523, 523, "square", 0.2, 0), (0.1, 0.12, 659, 659, "square", 0.2, 0),
                    (0.2, 0.12, 784, 784, "square", 0.2, 0), (0.3, 0.2, 1047, 1047, "square", 0.22, 0)]),
    "start": (0.35, [(0, 0.35, 220, 880, "sine", 0.35, 0.0), (0, 0.35, 330, 1320, "sine", 0.2, 0)]),
    "deny": (0.18, [(0, 0.18, 180, 140, "square", 0.25, 0.0)]),
    "spawn": (0.25, [(0, 0.25, 1500, 2500, "sine", 0.15, 0.0)]),
    "shoot": (0.12, [(0, 0.12, 900, 260, "square", 0.22, 0.1), (0, 0.08, 2400, 1200, "sine", 0.12, 0.0)]),
    "laser": (0.3, [(0, 0.3, 2600, 500, "saw", 0.22, 0.0), (0, 0.3, 1300, 250, "sine", 0.25, 0.0)]),
    "jump": (0.22, [(0, 0.22, 260, 900, "sine", 0.35, 0.0), (0, 0.12, 120, 300, "saw", 0.1, 0.4)]),
    "land": (0.2, [(0, 0.2, 140, 40, "sine", 0.55, 0.0), (0, 0.12, 300, 80, "saw", 0.15, 0.7)]),
    "teleport": (0.45, [(0, 0.45, 1800, 160, "sine", 0.35, 0.0), (0, 0.3, 300, 1400, "saw", 0.12, 0.5),
                     (0.15, 0.3, 200, 2400, "sine", 0.2, 0.0)]),
}


class SoundBank:
    """Raccolta di effetti sonori pronti all'uso, con interruttore muto."""

    def __init__(self):
        self.enabled: bool = False
        self.muted: bool = False
        try:
            init = pygame.mixer.get_init()
            if init is None:
                pygame.mixer.init()
                init = pygame.mixer.get_init()
            if init is None:
                return
            rate, _, channels = init
            for name, (duration, parts) in _RECIPES.items():
                if name not in _CACHE:
                    snd = pygame.mixer.Sound(buffer=_render(parts, rate, channels, duration))
                    snd.set_volume(0.5)
                    _CACHE[name] = snd
            self.enabled = True
        except (pygame.error, ValueError, TypeError):
            self.enabled = False

    def play(self, name: str, volume: Optional[float] = None) -> None:
        """Riproduce un effetto (silenzioso se muto o mixer assente)."""
        if not self.enabled or self.muted:
            return
        snd = _CACHE.get(name)
        if snd is None:
            return
        if volume is not None:
            snd.set_volume(volume)
        snd.play()

    def toggle_mute(self) -> bool:
        """Attiva/disattiva l'audio. :return: True se ora è muto."""
        self.muted = not self.muted
        return self.muted
