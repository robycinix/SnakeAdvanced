"""
Musica di sottofondo generata proceduralmente (nessun file audio esterno).
Tre tracce in loop sintetizzate con numpy:
- "menu":   atmosferica e lenta;
- "action": synthwave incalzante durante la partita;
- "boss":   minore, veloce e aggressiva durante lo scontro col boss.
La sintesi avviene in un thread separato all'avvio, così la finestra si apre
subito; le tracce entrano in gioco appena pronte. Senza numpy o senza mixer
il gioco resta semplicemente senza musica.
"""

import threading
from typing import Dict, List, Optional, Tuple

import pygame

try:
    import numpy as np
except ImportError:  # pragma: no cover - dipende dall'ambiente
    np = None  # type: ignore[assignment]

MUSIC_VOLUME: float = 0.32

# Tracce già sintetizzate, condivise tra istanze (chiave: nome, formato mixer)
_SOUND_CACHE: Dict[Tuple[str, int, int], "pygame.mixer.Sound"] = {}
_CACHE_LOCK = threading.Lock()

# (bpm, accordi [(radice MIDI, minore?)], intensità 0..1)
_TRACKS: Dict[str, Tuple[int, List[Tuple[int, bool]], float]] = {
    "menu": (92, [(45, True), (41, False), (48, False), (43, False)], 0.2),
    "action": (124, [(45, True), (41, False), (43, False), (40, False)], 0.75),
    "boss": (146, [(38, True), (46, False), (45, False), (45, False)], 1.0),
}


def _hz(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def _render(rate: int, bpm: int, chords: List[Tuple[int, bool]], intensity: float):
    """Sintetizza 2 giri di accordi (8 battute) in un array float stereo."""
    beat = 60.0 / bpm
    bar = beat * 4
    bars = len(chords) * 2
    n = int(rate * bar * bars)
    left = np.zeros(n, dtype=np.float32)
    right = np.zeros(n, dtype=np.float32)
    rng = np.random.default_rng(5)

    def add(start: float, dur: float, freq: float, vol: float, wave: str, decay: float, pan: float = 0.0):
        s0 = int(start * rate)
        cnt = min(int(dur * rate), n - s0)
        if cnt <= 0:
            return
        t = np.arange(cnt, dtype=np.float32) / rate
        ph = 2 * np.pi * freq * t
        if wave == "saw":
            sig = 2 * ((freq * t) % 1.0) - 1
            sig = 0.6 * sig + 0.4 * np.sin(ph)  # "filtrata": meno aspra
        elif wave == "square":
            sig = np.sign(np.sin(ph)) * 0.5 + 0.3 * np.sin(ph)
        elif wave == "noise":
            sig = rng.uniform(-1, 1, cnt).astype(np.float32)
        elif wave == "kick":
            f = 150 * np.exp(-t * 28) + 42
            sig = np.sin(2 * np.pi * np.cumsum(f) / rate)
        else:
            sig = np.sin(ph) + 0.15 * np.sin(2 * ph)
        env = np.exp(-t * decay) * np.minimum(1.0, t * 400)
        out = sig * env * vol
        left[s0:s0 + cnt] += out * (1 - max(0.0, pan))
        right[s0:s0 + cnt] += out * (1 + min(0.0, pan))

    for b in range(bars):
        root, minor = chords[b % len(chords)]
        third = 3 if minor else 4
        tones = [0, third, 7, 12]
        t0 = b * bar
        # Pad: accordo tenuto
        for iv in (0, third, 7):
            add(t0, bar, _hz(root + 24 + iv), 0.05, "sine", 0.6, pan=-0.3 + iv * 0.05)
        # Basso a crome con salto d'ottava
        pattern = [0, 0, 12, 0, 0, 12, 0, 7]
        for i, iv in enumerate(pattern):
            add(t0 + i * beat / 2, beat / 2, _hz(root + iv), 0.16 + 0.08 * intensity, "saw", 7.0)
        # Arpeggio a semicrome (più denso con l'intensità)
        step = beat / 4 if intensity > 0.5 else beat / 2
        count = int(bar / step)
        for i in range(count):
            iv = tones[(i * 3 + b) % 4] + (12 if (i // 4) % 2 else 0)
            add(t0 + i * step, step * 1.5, _hz(root + 36 + iv), 0.05 + 0.04 * intensity, "square", 9.0,
                pan=0.5 if i % 2 else -0.5)
        # Batteria
        for i in range(4):
            if intensity > 0.5 or i % 2 == 0:
                add(t0 + i * beat, 0.35, 0, 0.55 * (0.5 + intensity / 2), "kick", 9.0)
            if intensity > 0.3:
                add(t0 + i * beat + beat / 2, 0.06, 0, 0.06 * intensity, "noise", 60.0, pan=0.2)
            if intensity > 0.9:
                add(t0 + i * beat + beat / 4, 0.04, 0, 0.04, "noise", 80.0, pan=-0.2)
                add(t0 + i * beat + 3 * beat / 4, 0.04, 0, 0.04, "noise", 80.0, pan=-0.2)
        if intensity > 0.5:
            for i in (1, 3):  # rullante
                add(t0 + i * beat, 0.18, 0, 0.13 * intensity, "noise", 22.0)
                add(t0 + i * beat, 0.12, 190, 0.12 * intensity, "sine", 30.0)

    stereo = np.stack([left, right], axis=1)
    stereo = np.tanh(stereo * 1.4) * 0.85  # Saturazione morbida, niente clipping
    return stereo


class MusicPlayer:
    """Gestisce le tracce in loop con dissolvenza tra una e l'altra."""

    def __init__(self, enabled: bool = True):
        self.tracks: Dict[str, pygame.mixer.Sound] = {}
        self.current: Optional[str] = None
        self.wanted: Optional[str] = None
        self.muted: bool = False
        self.channels: List[pygame.mixer.Channel] = []
        self.active: int = 0
        self._lock = _CACHE_LOCK
        if not enabled or np is None:
            return
        init = pygame.mixer.get_init()
        if init is None:
            return
        try:
            # Due canali riservati: uno sfuma in uscita mentre l'altro entra
            pygame.mixer.set_reserved(2)
            self.channels = [pygame.mixer.Channel(0), pygame.mixer.Channel(1)]
        except pygame.error:
            return
        self._format = (init[0], init[2])
        threading.Thread(target=self._build, args=init, daemon=True).start()

    def _build(self, rate: int, size: int, channels: int) -> None:
        """Sintetizza le tracce in background (priorità alla traccia del menu)."""
        for name in ("menu", "action", "boss"):
            key = (name, rate, channels)
            with self._lock:
                cached = _SOUND_CACHE.get(key)
            if cached is not None:
                with self._lock:
                    self.tracks[name] = cached
                continue
            bpm, chords, intensity = _TRACKS[name]
            data = _render(rate, bpm, chords, intensity)
            if channels == 1:
                data = data.mean(axis=1, keepdims=True)
            elif channels > 2:
                data = np.concatenate([data] + [data[:, :1]] * (channels - 2), axis=1)
            pcm = np.ascontiguousarray((data * 32000).astype(np.int16))
            try:
                snd = pygame.mixer.Sound(buffer=pcm.tobytes())
            except pygame.error:
                return
            with self._lock:
                _SOUND_CACHE[key] = snd
                self.tracks[name] = snd

    def play(self, name: str) -> None:
        """Richiede una traccia: parte appena è pronta, con dissolvenza."""
        self.wanted = name

    def update(self) -> None:
        """Da chiamare ogni frame: applica il cambio di traccia richiesto."""
        if not self.channels or self.wanted == self.current:
            return
        with self._lock:
            snd = self.tracks.get(self.wanted) if self.wanted else None
        if self.wanted is not None and snd is None:
            return  # Non ancora sintetizzata
        self.channels[self.active].fadeout(700)
        self.active ^= 1
        self.current = self.wanted
        if snd is not None:
            snd.set_volume(0.0 if self.muted else MUSIC_VOLUME)
            self.channels[self.active].play(snd, loops=-1, fade_ms=900)

    def set_muted(self, muted: bool) -> None:
        """Silenzia o riattiva la musica."""
        self.muted = muted
        with self._lock:
            for snd in self.tracks.values():
                snd.set_volume(0.0 if muted else MUSIC_VOLUME)
