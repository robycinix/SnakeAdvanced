"""
Modulo che gestisce il sistema di particelle per gli effetti visivi:
esplosioni luminose, scintille, scie e onde d'urto ad anello.
Le particelle "glow" sono disegnate in modalità additiva per un effetto luce.
"""

import math
import random
from typing import List, Tuple

import pygame

import visuals as vfx

Color = Tuple[int, int, int]

MAX_PARTICLES: int = 2500


class Particle:
    """
    Una singola particella che si muove, rallenta, cade e svanisce.
    kind: "glow" (punto luminoso additivo) oppure "spark" (scintilla a linea).
    """

    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "size",
                 "color", "gravity", "drag", "kind")

    def __init__(self, x: float, y: float, color: Color, velocity: Tuple[float, float],
                 life: float = 1.0, size: float = 3.0, gravity: float = 0.0,
                 drag: float = 2.0, kind: str = "glow"):
        self.x = x
        self.y = y
        self.vx, self.vy = velocity
        self.life = life
        self.max_life = life
        self.size = size
        self.color = color
        self.gravity = gravity
        self.drag = drag
        self.kind = kind

    @property
    def current_lifetime(self) -> float:
        """Compatibilità con la vecchia API: vita residua in secondi."""
        return self.life

    def update(self, dt: float) -> None:
        """Integra posizione e velocità con attrito e gravità (Delta Time)."""
        damp = max(0.0, 1.0 - self.drag * dt)
        self.vx *= damp
        self.vy = self.vy * damp + self.gravity * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.life -= dt

    def draw(self, surface: pygame.Surface) -> None:
        """Disegna la particella in base al tipo, sfumandola col tempo."""
        frac = max(0.0, self.life / self.max_life)
        if self.kind == "spark":
            c = vfx.scale_color(self.color, frac)
            tail = 0.035
            pygame.draw.line(surface, c, (self.x, self.y),
                             (self.x - self.vx * tail, self.y - self.vy * tail),
                             2 if self.size > 2 else 1)
        else:
            radius = self.size * (0.5 + 2.5 * frac)
            vfx.blit_glow(surface, (self.x, self.y), radius, self.color, frac)


class Ring:
    """Onda d'urto: anello che si espande e svanisce."""

    __slots__ = ("x", "y", "color", "max_radius", "duration", "t", "width")

    def __init__(self, x: float, y: float, color: Color, max_radius: float,
                 duration: float, width: int):
        self.x, self.y = x, y
        self.color = color
        self.max_radius = max_radius
        self.duration = duration
        self.t = 0.0
        self.width = width

    def draw(self, surface: pygame.Surface) -> None:
        """Disegna l'anello con easing "ease-out" per un'esplosione naturale."""
        p = min(1.0, self.t / self.duration)
        ease = 1.0 - (1.0 - p) ** 3
        radius = max(1.0, self.max_radius * ease)
        fade = 1.0 - p
        width = max(1, int(self.width * fade + 0.5))
        pygame.draw.circle(surface, vfx.scale_color(self.color, fade * 0.35),
                           (self.x, self.y), radius + width, width + 2)
        pygame.draw.circle(surface, vfx.scale_color(self.color, fade),
                           (self.x, self.y), radius, width)


class ParticleSystem:
    """
    Gestisce tutte le particelle e gli anelli attivi.
    Ha un tetto massimo di particelle per non far crollare il frame rate
    durante le esplosioni più grandi.
    """

    def __init__(self):
        self.particles: List[Particle] = []
        self.rings: List[Ring] = []

    def clear(self) -> None:
        """Rimuove tutti gli effetti (usato al reset della partita)."""
        self.particles.clear()
        self.rings.clear()

    def _add(self, p: Particle) -> None:
        if len(self.particles) < MAX_PARTICLES:
            self.particles.append(p)

    def emit_explosion(self, x: float, y: float, color: Color, count: int = 10) -> None:
        """Esplosione semplice (API storica): delega a emit_burst."""
        self.emit_burst(x, y, color, count)

    def emit_burst(self, x: float, y: float, color: Color, count: int,
                   speed: Tuple[float, float] = (60, 260), life: Tuple[float, float] = (0.4, 1.0),
                   size: Tuple[float, float] = (1.5, 3.5), gravity: float = 0.0,
                   drag: float = 2.5) -> None:
        """Esplosione radiale di punti luminosi."""
        for _ in range(count):
            a = random.uniform(0, math.tau)
            s = random.uniform(*speed)
            self._add(Particle(x, y, color, (math.cos(a) * s, math.sin(a) * s),
                               random.uniform(*life), random.uniform(*size), gravity, drag))

    def emit_sparks(self, x: float, y: float, color: Color, count: int,
                    speed: Tuple[float, float] = (150, 420), life: Tuple[float, float] = (0.25, 0.6),
                    gravity: float = 300.0) -> None:
        """Scintille a linea, veloci e soggette a gravità."""
        for _ in range(count):
            a = random.uniform(0, math.tau)
            s = random.uniform(*speed)
            self._add(Particle(x, y, color, (math.cos(a) * s, math.sin(a) * s),
                               random.uniform(*life), 3, gravity, 3.0, "spark"))

    def emit_trail(self, x: float, y: float, color: Color, size: float = 2.5,
                   life: float = 0.4, spread: float = 20.0) -> None:
        """Singola particella di scia, quasi ferma."""
        self._add(Particle(x, y, color,
                           (random.uniform(-spread, spread), random.uniform(-spread, spread)),
                           life * random.uniform(0.7, 1.2), size, 0.0, 3.0))

    def emit_ring(self, x: float, y: float, color: Color, max_radius: float = 60,
                  duration: float = 0.5, width: int = 4) -> None:
        """Onda d'urto ad anello."""
        self.rings.append(Ring(x, y, color, max_radius, duration, width))

    def update(self, dt: float) -> None:
        """Aggiorna e rimuove le particelle e gli anelli esauriti."""
        for p in self.particles:
            p.update(dt)
        self.particles = [p for p in self.particles if p.life > 0]
        for r in self.rings:
            r.t += dt
        self.rings = [r for r in self.rings if r.t < r.duration]

    def draw(self, surface: pygame.Surface) -> None:
        """Disegna prima gli anelli poi le particelle (luci sopra)."""
        for r in self.rings:
            r.draw(surface)
        for p in self.particles:
            p.draw(surface)
