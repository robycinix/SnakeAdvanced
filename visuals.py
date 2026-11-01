"""
Modulo View: tutte le primitive grafiche del gioco.
Contiene cache di sprite pre-renderizzati (luci additive, sfere ombreggiate),
lo sfondo, il renderer realistico del serpente e il disegno di cibo,
power-up, mine, fulmini e scudi.
Le sprite vengono generate una sola volta e riutilizzate: disegnare
gradienti pixel per pixel a ogni frame sarebbe troppo lento in Pygame.
"""

import math
import random
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import pygame

from config import SCREEN_WIDTH, SCREEN_HEIGHT, CELL_SIZE, COLOR_GOLD, COLOR_CYAN
from themes import THEMES, SkinPalette, Theme

Color = Tuple[int, int, int]
Point = Tuple[float, float]


# ---------------------------------------------------------------------------
# Utilità sui colori
# ---------------------------------------------------------------------------

def clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """Limita v all'intervallo [lo, hi]."""
    return lo if v < lo else hi if v > hi else v


def lerp_color(a: Color, b: Color, t: float) -> Color:
    """Interpolazione lineare tra due colori."""
    t = clamp(t)
    return (int(a[0] + (b[0] - a[0]) * t),
            int(a[1] + (b[1] - a[1]) * t),
            int(a[2] + (b[2] - a[2]) * t))


def scale_color(c: Color, k: float) -> Color:
    """Moltiplica la luminosità di un colore (k in [0, 1+])."""
    return (min(255, max(0, int(c[0] * k))),
            min(255, max(0, int(c[1] * k))),
            min(255, max(0, int(c[2] * k))))


def cell_center(pos: Tuple[int, int]) -> Point:
    """Centro in pixel di una cella della griglia."""
    return (pos[0] * CELL_SIZE + CELL_SIZE / 2, pos[1] * CELL_SIZE + CELL_SIZE / 2)


# ---------------------------------------------------------------------------
# Luci additive
# ---------------------------------------------------------------------------

_GLOW_CACHE: Dict[Tuple[int, Color], pygame.Surface] = {}
_INTENSITY_LEVELS = 12


def glow_sprite(radius: int, color: Color) -> pygame.Surface:
    """
    Sprite RGB su nero con un gradiente radiale: blittata in BLEND_ADD
    simula una sorgente di luce (il nero non aggiunge nulla).
    """
    key = (radius, color)
    spr = _GLOW_CACHE.get(key)
    if spr is None:
        if len(_GLOW_CACHE) > 900:
            _GLOW_CACHE.clear()
        spr = pygame.Surface((radius * 2, radius * 2))
        spr.fill((0, 0, 0))
        for r in range(radius, 0, -1):
            k = (1.0 - r / radius) ** 1.7
            pygame.draw.circle(spr, scale_color(color, k), (radius, radius), r)
        _GLOW_CACHE[key] = spr
    return spr


def blit_glow(target: pygame.Surface, pos: Point, radius: float, color: Color,
              intensity: float = 1.0) -> None:
    """Aggiunge una luce morbida centrata in pos."""
    if intensity <= 0.02 or radius < 1:
        return
    level = max(1, min(_INTENSITY_LEVELS, int(intensity * _INTENSITY_LEVELS + 0.5)))
    col = scale_color(color, level / _INTENSITY_LEVELS)
    r = int(radius)
    if r > 24:
        r -= r % 3  # Quantizza i raggi grandi per limitare la cache
    r = max(2, r)
    target.blit(glow_sprite(r, col), (pos[0] - r, pos[1] - r), special_flags=pygame.BLEND_ADD)


# ---------------------------------------------------------------------------
# Sfere ombreggiate (illuminazione dall'alto a sinistra)
# ---------------------------------------------------------------------------

_BALL_CACHE: Dict[Tuple[int, Color, float], pygame.Surface] = {}


def shaded_ball(radius: int, color: Color, highlight: float = 0.55) -> pygame.Surface:
    """
    Sfera con bordo scuro, corpo del colore base e riflesso speculare.
    Disegnata in super-campionamento 3x e poi ridotta: bordi anti-aliasati.
    Sovrapponendo molte sfere lungo un percorso si ottiene un "tubo" 3D.
    """
    key = (radius, color, highlight)
    spr = _BALL_CACHE.get(key)
    if spr is not None:
        return spr
    ss = 3
    big_r = radius * ss
    size = big_r * 2 + 2 * ss
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    c = size / 2
    dark = scale_color(color, 0.35)
    light = lerp_color(color, (255, 255, 255), highlight)
    steps = max(4, big_r)
    for i in range(steps):
        f = i / steps
        r = big_r * (1.0 - f)
        if f < 0.35:
            col = lerp_color(dark, color, f / 0.35)
        else:
            col = lerp_color(color, light, ((f - 0.35) / 0.65) ** 1.8)
        off = f * big_r * 0.38
        pygame.draw.circle(surf, col, (c - off, c - off), max(1.0, r))
    spr = pygame.transform.smoothscale(surf, (size // ss, size // ss))
    _BALL_CACHE[key] = spr
    return spr


_SHADOW_CACHE: Dict[Tuple[int, int, int], pygame.Surface] = {}


def shadow_ellipse(w: int, h: int, alpha: int = 90) -> pygame.Surface:
    """Ombra ellittica morbida da proiettare sotto gli oggetti."""
    key = (w, h, alpha)
    spr = _SHADOW_CACHE.get(key)
    if spr is None:
        spr = pygame.Surface((w, h), pygame.SRCALPHA)
        for i in range(4):
            k = i / 4
            rect = pygame.Rect(0, 0, w * (1 - k * 0.5), h * (1 - k * 0.5))
            rect.center = (w / 2, h / 2)
            pygame.draw.ellipse(spr, (0, 0, 0, int(alpha * (0.3 + 0.2 * i))), rect)
        _SHADOW_CACHE[key] = spr
    return spr


def blur(surface: pygame.Surface, radius: int) -> pygame.Surface:
    """Sfocatura gaussiana (pygame-ce) con ripiego a ridimensionamento."""
    if hasattr(pygame.transform, "gaussian_blur"):
        try:
            return pygame.transform.gaussian_blur(surface, radius)
        except (ValueError, pygame.error):
            pass
    w, h = surface.get_size()
    small = pygame.transform.smoothscale(surface, (max(1, w // 4), max(1, h // 4)))
    return pygame.transform.smoothscale(small, (w, h))


_TEXT_CACHE: Dict[tuple, pygame.Surface] = {}


def glow_text(font: pygame.font.Font, text: str, color: Color, glow_color: Color,
              glow_radius: int = 8) -> pygame.Surface:
    """
    Testo con alone luminoso: il testo viene renderizzato nel colore dell'alone,
    sfocato e poi ricoperto dal testo nitido.
    """
    key = (id(font), text, color, glow_color, glow_radius)
    surf = _TEXT_CACHE.get(key)
    if surf is not None:
        return surf
    if len(_TEXT_CACHE) > 300:
        _TEXT_CACHE.clear()
    sharp = font.render(text, True, color)
    pad = glow_radius * 2
    w, h = sharp.get_width() + pad * 2, sharp.get_height() + pad * 2
    halo = pygame.Surface((w, h), pygame.SRCALPHA)
    halo.blit(font.render(text, True, glow_color), (pad, pad))
    halo = blur(halo, glow_radius)
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    surf.blit(halo, (0, 0))
    surf.blit(halo, (0, 0))  # Doppio passaggio: alone più intenso
    surf.blit(sharp, (pad, pad))
    _TEXT_CACHE[key] = surf
    return surf


# ---------------------------------------------------------------------------
# Sfondo e ambiente
# ---------------------------------------------------------------------------

def build_background(theme: Theme = THEMES[0]) -> pygame.Surface:
    """
    Crea lo sfondo statico del tema: gradiente, scacchiera tenue, macchie di luce,
    granulosità, griglia sottile e vignettatura. Generato una volta per tema.
    """
    rng = random.Random(7)
    surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    for y in range(SCREEN_HEIGHT):
        pygame.draw.line(surf, lerp_color(theme.bg_top, theme.bg_bottom, y / SCREEN_HEIGHT),
                         (0, y), (SCREEN_WIDTH, y))

    # Scacchiera appena percettibile: aiuta a leggere la griglia senza linee forti
    for gx in range(0, SCREEN_WIDTH // CELL_SIZE):
        for gy in range(0, SCREEN_HEIGHT // CELL_SIZE):
            if (gx + gy) % 2 == 0:
                surf.fill(theme.checker, (gx * CELL_SIZE, gy * CELL_SIZE, CELL_SIZE, CELL_SIZE),
                          special_flags=pygame.BLEND_ADD)

    # Macchie organiche di muschio/luce lunare
    for _ in range(16):
        blit_glow(surf, (rng.uniform(0, SCREEN_WIDTH), rng.uniform(0, SCREEN_HEIGHT)),
                  rng.randint(70, 170), rng.choice(theme.blobs), 1.0)

    # Granulosità del terreno
    for _ in range(3500):
        v = rng.randint(2, 6)
        g = theme.grain
        surf.fill((g[0] * v, g[1] * v, g[2] * v), (rng.randrange(SCREEN_WIDTH), rng.randrange(SCREEN_HEIGHT), 1, 1),
                  special_flags=pygame.BLEND_ADD)

    # Griglia sottile
    for x in range(0, SCREEN_WIDTH, CELL_SIZE):
        surf.fill((5, 8, 9), (x, 0, 1, SCREEN_HEIGHT), special_flags=pygame.BLEND_ADD)
    for y in range(0, SCREEN_HEIGHT, CELL_SIZE):
        surf.fill((5, 8, 9), (0, y, SCREEN_WIDTH, 1), special_flags=pygame.BLEND_ADD)

    # Vignettatura: superficie piccola calcolata a mano e ingrandita (morbida)
    small = pygame.Surface((80, 60))
    for px in range(80):
        for py in range(60):
            dx = (px / 79 - 0.5) * 2
            dy = (py / 59 - 0.5) * 2
            d = min(1.0, (dx * dx + dy * dy) / 2)
            v = int(255 * (1 - 0.62 * d ** 1.3))
            small.set_at((px, py), (v, v, v))
    surf.blit(pygame.transform.smoothscale(small, (SCREEN_WIDTH, SCREEN_HEIGHT)), (0, 0),
              special_flags=pygame.BLEND_MULT)
    return surf


class Ambience:
    """Lucciole che fluttuano lentamente: danno vita allo sfondo."""

    def __init__(self, count: int = 34, color: Color = (120, 200, 140)):
        self.color = color
        self.motes = [[random.uniform(0, SCREEN_WIDTH), random.uniform(0, SCREEN_HEIGHT),
                       random.uniform(-8, 8), random.uniform(-12, -3),
                       random.uniform(0, math.tau), random.uniform(5, 11)]
                      for _ in range(count)]

    def update(self, dt: float) -> None:
        """Sposta le lucciole e le fa rientrare dal lato opposto."""
        for m in self.motes:
            m[0] = (m[0] + m[2] * dt) % SCREEN_WIDTH
            m[1] = (m[1] + m[3] * dt) % SCREEN_HEIGHT
            m[4] += dt * 1.3

    def draw(self, surface: pygame.Surface) -> None:
        """Disegna le lucciole pulsanti."""
        for x, y, _, _, phase, size in self.motes:
            k = 0.18 + 0.22 * (0.5 + 0.5 * math.sin(phase))
            blit_glow(surface, (x, y), size, self.color, k)


def draw_arena(surface: pygame.Surface, t: float, warnings: Dict[str, float],
               color: Color = (0, 70, 80)) -> None:
    """
    Bordo dell'arena luminoso. I lati vicini alla testa si accendono di rosso
    (warnings: lato -> intensità 0..1) per avvisare del pericolo.
    """
    pulse = 0.75 + 0.25 * math.sin(t * 2.0)
    base = scale_color(color, pulse)
    w, h = SCREEN_WIDTH, SCREEN_HEIGHT
    bands = {
        "top": lambda i: (0, i, w, 1),
        "bottom": lambda i: (0, h - 1 - i, w, 1),
        "left": lambda i: (i, 0, 1, h),
        "right": lambda i: (w - 1 - i, 0, 1, h),
    }
    for side, rect_of in bands.items():
        warn = warnings.get(side, 0.0)
        col = lerp_color(base, (255, 40, 50), warn)
        for i in range(8):
            k = (1 - i / 8) ** 2
            surface.fill(scale_color(col, k * (0.9 + 0.6 * warn)), rect_of(i),
                         special_flags=pygame.BLEND_ADD)


# ---------------------------------------------------------------------------
# Serpente realistico
# ---------------------------------------------------------------------------

HEAD_LENGTH: float = CELL_SIZE * 1.6
HEAD_WIDTH: float = CELL_SIZE * 1.08
_SUB_SAMPLES: int = 4          # Campioni per segmento (densità del "tubo")
_TONES: int = 20
_LIGHT: Point = (-0.6, -0.8)   # Direzione della luce (dall'alto a sinistra)

_DISC_CACHE: Dict[Tuple[int, Color], pygame.Surface] = {}


def flat_disc(radius: float, color: Color) -> pygame.Surface:
    """
    Disco a tinta unita anti-aliasato (raggio quantizzato a mezzo pixel).
    Dischi uguali sovrapposti si fondono senza giunture: è la base del
    corpo "a cilindro" del serpente, senza l'effetto a perline.
    """
    key = (max(2, int(radius * 2 + 0.5)), color)
    spr = _DISC_CACHE.get(key)
    if spr is None:
        if len(_DISC_CACHE) > 2500:
            _DISC_CACHE.clear()
        r = key[0] / 2
        ss = 4
        size = int(r * 2 + 2) * ss
        big = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(big, color, (size / 2, size / 2), r * ss)
        spr = pygame.transform.smoothscale(big, (size // ss, size // ss))
        _DISC_CACHE[key] = spr
    return spr


def _build_head(skin: SkinPalette) -> pygame.Surface:
    """
    Testa del serpente orientata verso destra, disegnata in super-campionamento:
    cranio a spatola che si restringe nel muso, cresta dorsale illuminata,
    strisce temporali scure, occhi laterali sporgenti con pupilla a fessura e narici.
    """
    ss = 4
    L, W = HEAD_LENGTH * ss, HEAD_WIDTH * ss
    w, h = int(L) + 8, int(W * 1.15) + 8
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    cy = h / 2
    x0 = 4
    dark, bright = skin.dark, skin.bright

    def shape(col: Color, shrink: float, width_k: float = 1.0, dy: float = 0.0) -> None:
        cranium = pygame.Rect(0, 0, L * 0.74 - shrink * 2, (W - shrink * 2) * width_k)
        cranium.midleft = (x0 + shrink, cy + dy)
        snout = pygame.Rect(0, 0, L * 0.70 - shrink * 2, (W * 0.66 - shrink * 2) * width_k)
        snout.midright = (x0 + L - shrink, cy + dy)
        for rect in (cranium, snout):
            if rect.width > 0 and rect.height > 0:
                pygame.draw.ellipse(surf, col, rect)

    outline = scale_color(dark, 0.45)
    shape(outline, 0)
    shape(bright, ss * 1.2)
    # Volume: fasce più chiare spostate verso la luce (in alto)
    shape(lerp_color(bright, (255, 255, 255), 0.16), ss * 2.4, 0.62, -W * 0.06)
    shape(lerp_color(bright, (255, 255, 255), 0.38), ss * 3.5, 0.26, -W * 0.12)

    # Squame scure: striscia centrale e strisce temporali dietro agli occhi
    mark = skin.mark
    pygame.draw.polygon(surf, mark, [(x0 + 2 * ss, cy - W * 0.07), (x0 + L * 0.42, cy - W * 0.02),
                                     (x0 + L * 0.42, cy + W * 0.02), (x0 + 2 * ss, cy + W * 0.07)])
    for side in (-1, 1):
        pygame.draw.polygon(surf, mark, [
            (x0 + L * 0.56, cy + side * W * 0.36), (x0 + L * 0.06, cy + side * W * 0.30),
            (x0 + L * 0.04, cy + side * W * 0.40), (x0 + L * 0.52, cy + side * W * 0.44)])

    # Occhi laterali: orbita scura, iride ambra sfumata, fessura, riflesso
    eye_r = W * 0.12
    for side in (-1, 1):
        ex, ey = x0 + L * 0.62, cy + side * W * 0.40
        pygame.draw.circle(surf, (8, 18, 8), (ex, ey), eye_r * 1.35)
        for i in range(8):
            f = i / 7
            pygame.draw.circle(surf, lerp_color((150, 70, 0), (255, 215, 70), f),
                               (ex, ey - f * eye_r * 0.2), eye_r * (1 - f * 0.55))
        pupil = pygame.Rect(0, 0, eye_r * 1.6, eye_r * 0.38)
        pupil.center = (ex, ey)
        pygame.draw.ellipse(surf, (5, 5, 5), pupil)
        pygame.draw.circle(surf, (255, 255, 240), (ex - eye_r * 0.3, ey - eye_r * 0.45), eye_r * 0.26)

    # Narici
    for side in (-1, 1):
        pygame.draw.circle(surf, (6, 22, 10), (x0 + L * 0.92, cy + side * W * 0.10), W * 0.035)

    return pygame.transform.smoothscale(surf, (w // ss, h // ss))


class SnakeRenderer:
    """
    Disegna il serpente come un corpo continuo e ombreggiato:
    - interpola tra il passo precedente e quello corrente (movimento fluido);
    - campiona densamente il percorso e lo riempie di sfere ombreggiate;
    - assottiglia la coda, aggiunge ondulazione laterale ancorata al terreno,
      macchie a diamante, riflessi umidi, rigonfiamenti delle prede ingoiate;
    - disegna testa ruotata, ombra proiettata, lingua biforcuta e occhi luminosi.
    """

    def __init__(self, skin: SkinPalette = THEMES[0].skin, scale: float = 1.0):
        """
        :param skin: Colori della pelle.
        :param scale: Moltiplicatore di spessore (il boss è più grosso).
        """
        self.layer = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        self.shadow = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        self.skin = skin
        self.scale = scale
        self.palette: List[Color] = [lerp_color(skin.dark, skin.bright, i / (_TONES - 1)) for i in range(_TONES)]
        self.head_base = _build_head(skin)
        self._rot_cache: Dict[Tuple[int, int], pygame.Surface] = {}
        # Regione disegnata al frame precedente: si pulisce solo quella
        self._dirty = pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT)
        self.head_pos: Point = (0.0, 0.0)
        self.heading: Point = (1.0, 0.0)

    # --- geometria -----------------------------------------------------

    @staticmethod
    def compute_points(snake, alpha: float) -> List[Point]:
        """
        Centri in pixel dei segmenti, interpolati tra prev_body e body.
        Se un segmento ha "saltato" (portale dello scudo) non viene interpolato.
        """
        prev, body = snake.prev_body, snake.body
        pts: List[Point] = []
        for i, (bx, by) in enumerate(body):
            px, py = prev[i] if i < len(prev) else (prev[-1] if prev else (bx, by))
            if abs(bx - px) > 1 or abs(by - py) > 1:
                px, py = bx, by
            x = px + (bx - px) * alpha
            y = py + (by - py) * alpha
            pts.append(((x + 0.5) * CELL_SIZE, (y + 0.5) * CELL_SIZE))
        return pts

    def _radius(self, seg: float, s: float, bulges: Sequence[float]) -> float:
        """Raggio del corpo: collo sottile, ventre pieno, coda affusolata, prede ingoiate."""
        k = 1.0
        if seg < 1.0:
            k = 0.80 + 0.20 * seg
        if s > 0.55:
            k *= 1.0 - 0.74 * ((s - 0.55) / 0.45) ** 1.25
        for b in bulges:
            d = seg - b
            if -2.5 < d < 2.5:
                k *= 1.0 + 0.42 * math.exp(-(d * d) / 0.55)
        return CELL_SIZE * 0.47 * k * self.scale

    def _tone(self, seg: float, s: float) -> Color:
        """Bande trasversali chiaro/scuro e scurimento progressivo verso la coda."""
        band = 0.5 + 0.5 * math.cos(seg * math.tau / 2.0)
        v = (0.98 - 0.34 * band) * (1.0 - 0.28 * s)
        return self.palette[int(clamp(v) * (_TONES - 1) + 0.5)]

    def _head_sprite(self, angle: float, scale: float) -> pygame.Surface:
        """Testa ruotata, con cache per angoli (2 gradi) e scale (5%) quantizzati."""
        ang = int(round(angle / 2.0)) * 2 % 360
        sc = int(round(scale * 20))
        key = (ang, sc)
        spr = self._rot_cache.get(key)
        if spr is None:
            if len(self._rot_cache) > 900:
                self._rot_cache.clear()
            spr = pygame.transform.rotozoom(self.head_base, ang, sc / 20)
            self._rot_cache[key] = spr
        return spr

    # --- disegno -------------------------------------------------------

    def draw(self, target: pygame.Surface, snake, alpha: float, t: float, travel: float, *,
             ghost: bool = False, skip: int = 0, bulges: Sequence[float] = (),
             points: Optional[List[Point]] = None, head_scale: float = 1.0,
             tongue_boost: bool = False, eye_color: Optional[Color] = None) -> None:
        """
        Disegna il serpente su target.

        :param alpha: Frazione di avanzamento tra il passo precedente e il corrente.
        :param t: Tempo visivo (lingua, battito).
        :param travel: Distanza percorsa in celle (ancora l'ondulazione al terreno).
        :param ghost: Rendi il corpo traslucido (power-up Fantasma).
        :param skip: Numero di segmenti iniziali già esplosi (animazione di morte).
        :param bulges: Posizioni (in segmenti) delle prede che scendono nel corpo.
        """
        pts = points if points is not None else self.compute_points(snake, alpha)
        n = len(pts)
        if n == 0:
            return
        eye = eye_color or self.skin.eye
        head_scale *= self.scale
        total = max(1, n - 1)

        # 1) Campionamento denso del percorso
        raw: List[Tuple[float, float, float]] = []
        jump = CELL_SIZE * 1.6
        for i in range(n - 1):
            ax, ay = pts[i]
            bx, by = pts[i + 1]
            if abs(bx - ax) > jump or abs(by - ay) > jump:
                raw.append((ax, ay, float(i)))
                continue
            for k in range(_SUB_SAMPLES):
                f = k / _SUB_SAMPLES
                raw.append((ax + (bx - ax) * f, ay + (by - ay) * f, i + f))
        raw.append((pts[-1][0], pts[-1][1], float(n - 1)))

        # 2) Tangenti e ondulazione laterale ancorata al terreno
        m = len(raw)
        samples: List[Tuple[float, float, float, float, float]] = []
        for j, (x, y, seg) in enumerate(raw):
            a = raw[max(0, j - 1)]
            b = raw[min(m - 1, j + 1)]
            tx, ty = a[0] - b[0], a[1] - b[1]
            ln = math.hypot(tx, ty)
            if ln < 1e-6 or ln > jump * 2:
                tx, ty = self.heading
            else:
                tx, ty = tx / ln, ty / ln
            s = seg / total
            amp = 2.6 * min(1.0, seg / 2.5) * (0.6 + 0.4 * s)
            off = amp * math.sin((travel - seg) * 1.25)
            samples.append((x - ty * off, y + tx * off, seg, tx, ty))

        # Regione interessata (+ margine per testa, ombra e rigonfiamenti):
        # pulire e comporre solo quella rende economici più serpenti a schermo
        margin = int(CELL_SIZE * 2 * self.scale) + 8
        xs = [smp[0] for smp in samples]
        ys = [smp[1] for smp in samples]
        area = pygame.Rect(int(min(xs)) - margin, int(min(ys)) - margin,
                           int(max(xs) - min(xs)) + margin * 2, int(max(ys) - min(ys)) + margin * 2)
        area = area.clip(pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT))
        clear = area.union(self._dirty)
        self._dirty = area
        layer, shadow = self.layer, self.shadow
        layer.fill((0, 0, 0, 0), clear)
        shadow.fill((0, 0, 0, 0), clear)

        # 3) Corpo a strati continui: contorno, base, fascia media, riflesso.
        #    Ogni strato è fatto di dischi uguali che si fondono senza giunture;
        #    gli strati chiari sono spostati verso la luce lungo la normale,
        #    così il corpo si legge come un cilindro e non come perline.
        visible = []
        marks = []
        for j in range(m - 1, -1, -1):
            x, y, seg, tx, ty = samples[j]
            if seg < skip:
                continue
            s = seg / total
            r = self._radius(seg, s, bulges)
            nx, ny = -ty, tx
            d = nx * _LIGHT[0] + ny * _LIGHT[1]
            visible.append((x, y, r, nx * d, ny * d, self._tone(seg, s)))
            pygame.draw.circle(shadow, (0, 0, 0, 255), (x + 4, y + 5), r)
            frac = seg - int(seg)
            if 0.45 < frac < 0.55 and seg >= 1:
                marks.append((x, y, int(seg), tx, ty, r))

        for x, y, r, lx, ly, tone in visible:
            spr = flat_disc(r + 1.0, scale_color(tone, 0.42))
            layer.blit(spr, spr.get_rect(center=(x, y)))
        for x, y, r, lx, ly, tone in visible:
            spr = flat_disc(r, tone)
            layer.blit(spr, spr.get_rect(center=(x, y)))

        # Fascia media più chiara verso la luce (volume del cilindro)
        for x, y, r, lx, ly, tone in visible:
            spr = flat_disc(r * 0.6, lerp_color(tone, (255, 255, 255), 0.13))
            layer.blit(spr, spr.get_rect(center=(x + lx * r * 0.3, y + ly * r * 0.3)))

        # 4) Disegni della pelle: selle dorsali scure e macchie laterali chiare
        for x, y, idx, tx, ty, r in marks:
            nx, ny = -ty, tx
            if idx % 2 == 0:
                poly = []
                for k in range(10):
                    a_ = k * math.tau / 10
                    u, v = math.cos(a_) * r * 0.42, math.sin(a_) * r * 0.80
                    poly.append((x + tx * u + nx * v, y + ty * u + ny * v))
                pygame.draw.polygon(layer, self.skin.mark, poly)
            else:
                for side in (-1, 1):
                    pygame.draw.circle(layer, self.skin.spot,
                                       (x + nx * r * 0.66 * side, y + ny * r * 0.66 * side),
                                       max(1.0, r * 0.13))

        # 5) Riflesso umido delle squame, additivo, verso la luce
        for i, (x, y, r, lx, ly, tone) in enumerate(visible):
            if i % 2 == 0:
                blit_glow(layer, (x + lx * r * 0.5, y + ly * r * 0.5), r * 0.42, (34, 44, 34), 1.0)

        # 6) Testa
        hx, hy, _, ux, uy = samples[0]
        self.heading = (ux, uy)
        draw_head = skip == 0
        if draw_head:
            angle = -math.degrees(math.atan2(uy, ux))
            cx, cy = hx + ux * CELL_SIZE * 0.22 * self.scale, hy + uy * CELL_SIZE * 0.22 * self.scale
            self.head_pos = (cx, cy)
            pygame.draw.circle(shadow, (0, 0, 0, 255), (cx + 4, cy + 5), CELL_SIZE * 0.6 * head_scale)
            spr = self._head_sprite(angle, head_scale)
            layer.blit(spr, spr.get_rect(center=(cx, cy)))

        # 7) Composizione: ombra, poi corpo (traslucido se Fantasma)
        shadow.set_alpha(35 if ghost else 85)
        target.blit(shadow, area.topleft, area)
        if ghost:
            layer.fill((170, 225, 255, 110), area, special_flags=pygame.BLEND_RGBA_MULT)
        target.blit(layer, area.topleft, area)

        if not draw_head:
            return
        cx, cy = self.head_pos
        nx, ny = -uy, ux

        # Occhi luminosi
        for side in (-1, 1):
            lx = (HEAD_LENGTH * 0.62 - HEAD_LENGTH / 2) * head_scale
            ly = HEAD_WIDTH * 0.40 * side * head_scale
            ex, ey = cx + ux * lx + nx * ly, cy + uy * lx + ny * ly
            blit_glow(target, (ex, ey), 7 * head_scale, eye, 0.45)

        # Lingua biforcuta che guizza
        period = 0.9 if tongue_boost else 2.4
        phase = (t % period) / period
        if phase < 0.22:
            ext = math.sin(phase / 0.22 * math.pi)
            length = CELL_SIZE * 0.75 * ext
            wig = math.sin(t * 60) * 0.25
            tip0 = (cx + ux * HEAD_LENGTH * 0.5 * head_scale, cy + uy * HEAD_LENGTH * 0.5 * head_scale)
            fork = (tip0[0] + ux * length, tip0[1] + uy * length)
            pygame.draw.line(target, (200, 30, 60), tip0, fork, 2)
            for side in (-1, 1):
                ang = math.atan2(uy, ux) + side * (0.45 + wig)
                pygame.draw.line(target, (230, 50, 80), fork,
                                 (fork[0] + math.cos(ang) * length * 0.35,
                                  fork[1] + math.sin(ang) * length * 0.35), 2)


# ---------------------------------------------------------------------------
# Cibo, power-up, mine ed effetti
# ---------------------------------------------------------------------------

def draw_food(surface: pygame.Surface, food, t: float, golden: bool = False) -> None:
    """Frutto lucido che fluttua con alone; quello d'oro ha raggi e timer."""
    if food.position is None:
        return
    cx, cy = cell_center(food.position)
    bob = math.sin(t * 3.0 + food.phase) * 2.0
    pulse = 0.5 + 0.5 * math.sin(t * 4.0 + food.phase)
    spawn = clamp(food.age / 0.25)
    if spawn <= 0:
        return

    left = food.time_left
    if golden and left is not None and left < 2.0 and int(t * 10) % 2 == 0:
        return  # Lampeggia quando sta per scadere

    shadow = shadow_ellipse(int(CELL_SIZE * 0.9), int(CELL_SIZE * 0.4))
    surface.blit(shadow, shadow.get_rect(center=(cx + 2, cy + CELL_SIZE * 0.42)))

    color = COLOR_GOLD if golden else (225, 40, 50)
    glow = (120, 90, 10) if golden else (110, 18, 22)
    blit_glow(surface, (cx, cy + bob), CELL_SIZE * (1.5 if golden else 1.2) * (0.9 + 0.15 * pulse), glow, 1.0)

    if golden:
        for i in range(6):
            a = t * 1.5 + i * math.tau / 6
            ln = CELL_SIZE * (0.9 + 0.25 * math.sin(t * 5 + i))
            pygame.draw.line(surface, (140, 105, 25), (cx, cy + bob),
                             (cx + math.cos(a) * ln, cy + bob + math.sin(a) * ln), 2)

    r = max(2, int(CELL_SIZE * 0.38 * (0.4 + 0.6 * spawn)))
    ball = shaded_ball(r, color, 0.6)
    surface.blit(ball, ball.get_rect(center=(cx, cy + bob)))

    # Picciolo e foglia
    top = (cx, cy + bob - r + 1)
    pygame.draw.line(surface, (90, 55, 20), top, (cx + 2, top[1] - 5), 2)
    leaf_c = (cx + 5, top[1] - 4)
    leaf = [(leaf_c[0] - 4, leaf_c[1] + 1), (leaf_c[0], leaf_c[1] - 3),
            (leaf_c[0] + 5, leaf_c[1] - 1), (leaf_c[0] + 1, leaf_c[1] + 2)]
    pygame.draw.polygon(surface, (60, 170, 60) if not golden else (240, 230, 140), leaf)

    if golden and left is not None:
        frac = left / food.lifetime
        rect = pygame.Rect(0, 0, CELL_SIZE * 1.7, CELL_SIZE * 1.7)
        rect.center = (cx, cy + bob)
        pygame.draw.arc(surface, COLOR_GOLD, rect, math.pi / 2, math.pi / 2 + math.tau * frac, 2)


def _poly(center: Point, pts: Iterable[Tuple[float, float]], s: float) -> List[Point]:
    return [(center[0] + x * s, center[1] + y * s) for x, y in pts]


def draw_power_symbol(surface: pygame.Surface, c: Point, kind: str, s: float, color: Color) -> None:
    """Icona del power-up (fulmine, scudo, clessidra, fantasma, magnete)."""
    if kind == "SPEED_BOOST":
        pygame.draw.polygon(surface, color, _poly(c, [(0.2, -1), (-0.6, 0.15), (-0.05, 0.15), (-0.25, 1),
                                                      (0.6, -0.2), (0.05, -0.2)], s))
    elif kind == "SHIELD":
        pts = _poly(c, [(0, -1), (0.8, -0.65), (0.7, 0.2), (0, 1), (-0.7, 0.2), (-0.8, -0.65)], s)
        pygame.draw.polygon(surface, color, pts)
        pygame.draw.polygon(surface, scale_color(color, 0.5), _poly(c, [(0, -0.6), (0.4, -0.4), (0.35, 0.1),
                                                                          (0, 0.55)], s))
    elif kind == "SLOW_MOTION":
        pygame.draw.polygon(surface, color, _poly(c, [(-0.7, -1), (0.7, -1), (0, 0)], s))
        pygame.draw.polygon(surface, color, _poly(c, [(-0.7, 1), (0.7, 1), (0, 0)], s))
    elif kind == "GHOST":
        pygame.draw.circle(surface, color, (c[0], c[1] - 0.2 * s), 0.65 * s)
        pygame.draw.polygon(surface, color, _poly(c, [(-0.65, -0.2), (0.65, -0.2), (0.65, 0.95), (0.33, 0.6),
                                                      (0, 0.95), (-0.33, 0.6), (-0.65, 0.95)], s))
        for side in (-1, 1):
            pygame.draw.circle(surface, (20, 20, 40), (c[0] + side * 0.25 * s, c[1] - 0.25 * s), 0.14 * s)
    elif kind == "MAGNET":
        w = max(2, int(0.38 * s))
        rect = pygame.Rect(0, 0, 1.4 * s, 1.4 * s)
        rect.center = (c[0], c[1] - 0.05 * s)
        pygame.draw.arc(surface, color, rect, math.pi, math.tau, w)
        for side in (-1, 1):
            x = c[0] + side * (0.7 * s - w / 2)
            pygame.draw.line(surface, color, (x, c[1] - 0.05 * s), (x, c[1] - 0.95 * s), w)
            pygame.draw.line(surface, (235, 235, 245), (x, c[1] - 0.7 * s), (x, c[1] - 1.0 * s), w)


def draw_power_up(surface: pygame.Surface, p, t: float, color: Color) -> None:
    """Sfera di vetro con anello rotante, alone colorato e simbolo."""
    cx, cy = cell_center(p.position)
    cy += math.sin(t * 2.5 + p.position[0]) * 2.0
    appear = clamp(p.age / 0.3)
    shadow = shadow_ellipse(int(CELL_SIZE * 0.9), int(CELL_SIZE * 0.4))
    surface.blit(shadow, shadow.get_rect(center=(cx + 2, cy + CELL_SIZE * 0.55)))
    blit_glow(surface, (cx, cy), CELL_SIZE * 1.6, scale_color(color, 0.45), 0.8 + 0.2 * math.sin(t * 5))
    ball = shaded_ball(max(2, int(CELL_SIZE * 0.5 * appear)), scale_color(color, 0.35), 0.45)
    surface.blit(ball, ball.get_rect(center=(cx, cy)))
    rect = pygame.Rect(0, 0, CELL_SIZE * 1.45, CELL_SIZE * 1.45)
    rect.center = (cx, cy)
    for i in range(3):
        a = t * 3.0 + i * math.tau / 3
        pygame.draw.arc(surface, color, rect, a, a + 1.2, 2)
    blink = p.lifetime < 3.0 and int(t * 8) % 2 == 0
    if not blink:
        draw_power_symbol(surface, (cx, cy), p.type.value, CELL_SIZE * 0.3, lerp_color(color, (255, 255, 255), 0.5))


def draw_mine(surface: pygame.Surface, mine, t: float) -> None:
    """Mina chiodata rotante con nucleo rosso pulsante e avviso di armamento."""
    cx, cy = cell_center(mine.position)
    fade = clamp((mine.lifetime - mine.age) / 1.0)
    if not mine.armed:
        p = mine.age / 1.5
        rr = CELL_SIZE * (2.2 - 1.6 * p)
        if int(t * 12) % 2 == 0:
            pygame.draw.circle(surface, (255, 60, 60), (cx, cy), rr, 2)
        scale = 0.5 + 0.5 * p
    else:
        scale = 1.0
    scale *= 0.3 + 0.7 * fade
    shadow = shadow_ellipse(int(CELL_SIZE * 1.0), int(CELL_SIZE * 0.45))
    surface.blit(shadow, shadow.get_rect(center=(cx + 3, cy + CELL_SIZE * 0.45)))
    r = CELL_SIZE * 0.36 * scale
    for i in range(8):
        a = t * 0.8 + i * math.tau / 8
        p1 = (cx + math.cos(a) * r * 0.8, cy + math.sin(a) * r * 0.8)
        p2 = (cx + math.cos(a) * r * 1.55, cy + math.sin(a) * r * 1.55)
        pygame.draw.line(surface, (70, 72, 82), p1, p2, 3)
        pygame.draw.circle(surface, (170, 170, 185), p2, 1.5)
    ball = shaded_ball(max(2, int(r)), (95, 100, 112), 0.5)
    surface.blit(ball, ball.get_rect(center=(cx, cy)))
    speed = 9.0 if mine.armed else 4.0
    beat = 0.5 + 0.5 * math.sin(t * speed + mine.position[1])
    blit_glow(surface, (cx, cy), CELL_SIZE * (0.7 + 0.5 * beat) * scale, (255, 30, 30), (0.35 + 0.65 * beat) * fade)
    pygame.draw.circle(surface, lerp_color((120, 0, 0), (255, 90, 80), beat), (cx, cy), max(1.0, r * 0.35))


def draw_lightning(surface: pygame.Surface, a: Point, b: Point, color: Color,
                   jitter: float = 7.0, rng: Optional[random.Random] = None) -> None:
    """Fulmine frastagliato tra due punti (magnete, Nova)."""
    uniform = rng.uniform if rng is not None else random.uniform
    dx, dy = b[0] - a[0], b[1] - a[1]
    dist = math.hypot(dx, dy)
    if dist < 2:
        return
    nx, ny = -dy / dist, dx / dist
    segs = max(3, int(dist / 12))
    pts = [a]
    for i in range(1, segs):
        f = i / segs
        o = uniform(-jitter, jitter) * math.sin(math.pi * f)
        pts.append((a[0] + dx * f + nx * o, a[1] + dy * f + ny * o))
    pts.append(b)
    pygame.draw.lines(surface, scale_color(color, 0.35), False, pts, 5)
    pygame.draw.lines(surface, color, False, pts, 2)
    pygame.draw.lines(surface, (255, 255, 255), False, pts, 1)


def draw_shield(surface: pygame.Surface, center: Point, t: float, strength: float = 1.0) -> None:
    """Bolla esagonale rotante attorno alla testa."""
    r = CELL_SIZE * (1.05 + 0.06 * math.sin(t * 6))
    blit_glow(surface, center, r * 1.4, (0, 70, 90), strength)
    pts = []
    for i in range(6):
        a = t * 1.2 + i * math.tau / 6
        pts.append((center[0] + math.cos(a) * r, center[1] + math.sin(a) * r))
    pygame.draw.polygon(surface, scale_color(COLOR_CYAN, 0.45 * strength), pts, 4)
    pygame.draw.polygon(surface, scale_color(COLOR_CYAN, strength), pts, 1)
    pygame.draw.circle(surface, scale_color(COLOR_CYAN, 0.6 * strength), center, r * 0.86, 1)


def draw_icon_badge(surface: pygame.Surface, center: Point, kind: str, color: Color,
                    frac: float, t: float) -> None:
    """Icona dell'HUD per un effetto attivo, con anello del tempo residuo."""
    blit_glow(surface, center, 22, scale_color(color, 0.5), 0.7)
    pygame.draw.circle(surface, (12, 16, 22), center, 15)
    pygame.draw.circle(surface, scale_color(color, 0.3), center, 15, 2)
    rect = pygame.Rect(0, 0, 30, 30)
    rect.center = (int(center[0]), int(center[1]))
    if frac > 0:
        pygame.draw.arc(surface, color, rect, math.pi / 2, math.pi / 2 + math.tau * clamp(frac), 3)
    draw_power_symbol(surface, center, kind, 8, lerp_color(color, (255, 255, 255), 0.4))


def draw_pellet(surface: pygame.Surface, pellet, t: float, color: Color) -> None:
    """Frammento luminoso lasciato da un rivale eliminato (lampeggia prima di sparire)."""
    if pellet.position is None:
        return
    left = pellet.time_left
    if left is not None and left < 2.0 and int(t * 10) % 2 == 0:
        return
    cx, cy = cell_center(pellet.position)
    pulse = 0.5 + 0.5 * math.sin(t * 6 + pellet.phase)
    blit_glow(surface, (cx, cy), CELL_SIZE * 0.8, scale_color(color, 0.6), 0.6 + 0.4 * pulse)
    ball = shaded_ball(max(2, int(CELL_SIZE * 0.2 * clamp(pellet.age / 0.2, 0.3, 1.0))), color, 0.7)
    surface.blit(ball, ball.get_rect(center=(cx, cy)))


def draw_portal(surface: pygame.Surface, center: Point, t: float, color: Color, k: float) -> None:
    """Portale vorticoso da cui emerge un nemico (k: intensità 0..1)."""
    if k <= 0:
        return
    blit_glow(surface, center, CELL_SIZE * 3 * k, scale_color(color, 0.6), k)
    for i in range(5):
        r = CELL_SIZE * (0.4 + i * 0.35) * k
        a = t * (4 - i * 0.5) + i
        rect = pygame.Rect(0, 0, r * 2, r * 2)
        rect.center = (int(center[0]), int(center[1]))
        pygame.draw.arc(surface, scale_color(color, k), rect, a, a + 2.2, 2)
