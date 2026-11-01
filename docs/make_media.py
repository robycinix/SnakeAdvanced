"""
Genera le immagini e le GIF della pagina GitHub (docs/media) usando il vero
motore del gioco in modalità senza finestra.

    python docs/make_media.py

Il giocatore è guidato da una semplice IA (la stessa del menu dimostrativo),
così le scene mostrano partite "vere": rivali, tunnel, armi, salti e boss.
"""

import os
import random
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "media")
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import score_manager  # noqa: E402

score_manager.HIGH_SCORE_FILE = os.path.join(OUT, "_media_scores.json")

import pygame  # noqa: E402
from PIL import Image  # noqa: E402

from game import Game, GameState  # noqa: E402
from power_up import Mine, PowerUpType  # noqa: E402
from rival import Rival  # noqa: E402
from tunnel import Tunnel  # noqa: E402

DT = 1 / 60


def new_game(theme_steps: int = 0, seed: int = 1) -> Game:
    """Partita nuova con il tema scelto (0 = Giungla, 1 = Deserto, 2 = Neon, 3 = Abisso)."""
    random.seed(seed)
    if os.path.exists(score_manager.HIGH_SCORE_FILE):
        os.remove(score_manager.HIGH_SCORE_FILE)
    for name, score in [("LUCA", 2450), ("SARA", 1980), ("ROBY", 1720), ("MARCO", 960), ("GIO", 410)]:
        score_manager.ScoreManager.add_entry(name, score)
    g = Game()
    g.leaderboard = score_manager.ScoreManager.load_leaderboard()
    g.high_score = g.leaderboard[0]["score"]
    g.sounds.muted = True
    for _ in range(theme_steps):
        g.handle_key(pygame.K_t)
    return g


def steer(g: Game) -> None:
    """Fa guidare il serpente del giocatore dall'IA dimostrativa."""
    real = g.demo_snake, g.demo_food
    g.demo_snake, g.demo_food = g.snake, g.food
    g.snake.change_direction(g._demo_direction())
    g.demo_snake, g.demo_food = real


def tick(g: Game, frames: int = 1, ai: bool = True) -> None:
    for _ in range(frames):
        if ai and g.state == GameState.PLAYING:
            steer(g)
        g.update(DT)
        g.update_visuals(DT)


def grab(g: Game) -> pygame.Surface:
    g._draw()
    return g.screen.copy()


def save_png(surf: pygame.Surface, name: str) -> None:
    pygame.image.save(surf, os.path.join(OUT, name))
    print("  ", name)


def to_pil(surf: pygame.Surface, scale: float) -> Image.Image:
    w, h = surf.get_size()
    small = pygame.transform.smoothscale(surf, (int(w * scale), int(h * scale)))
    return Image.frombytes("RGB", small.get_size(), pygame.image.tobytes(small, "RGB"))


def save_gif(frames, name: str, fps: int = 25) -> None:
    """GIF con palette adattiva condivisa (meno sfarfallio, file più piccolo)."""
    base = frames[0].quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    pal = [f.quantize(palette=base, dither=Image.Dither.NONE) for f in frames]
    path = os.path.join(OUT, name)
    pal[0].save(path, save_all=True, append_images=pal[1:], duration=int(1000 / fps), loop=0, optimize=True)
    print("  ", name, f"{os.path.getsize(path) / 1024 / 1024:.1f} MB")


def place_rival(g: Game, cells, slot: int = 0) -> Rival:
    r = Rival(cells[0], slot=slot)
    r.snake.body = list(cells)
    r.snake.prev_body = list(cells)
    g.rivals.append(r)
    return r


def open_tunnel(g: Game, a, b, color: int) -> None:
    t = Tunnel(a, b, color)
    t.age = 1.0
    g.tunnels.append(t)


# ---------------------------------------------------------------------------

def hero_gif() -> None:
    """GIF principale: partita nella giungla con rivali, tunnel e veleno."""
    g = new_game(0, seed=7)
    g.handle_key(pygame.K_SPACE)
    g.snake.grow(14)
    tick(g, 120)
    g.level = 3
    open_tunnel(g, (8, 6), (31, 22), 0)
    open_tunnel(g, (30, 7), (9, 23), 1)
    place_rival(g, [(26, 14 + i) for i in range(6)], 0)
    place_rival(g, [(14 + i, 25) for i in range(5)], 1)
    g.effects[PowerUpType.TRIPLE_SHOT] = 30
    g.energy = 100
    frames = []
    for i in range(150):
        tick(g, 2)
        if i % 12 == 0:
            g.fire_cooldown = 0
            g._fire()
        if i == 60:
            g._jump()
        if g.state != GameState.PLAYING:
            break
        frames.append(to_pil(grab(g), 0.6))
    save_gif(frames, "hero.gif")


def boss_gif() -> None:
    """GIF del boss nel deserto."""
    g = new_game(1, seed=11)
    g.handle_key(pygame.K_SPACE)
    g.snake.grow(16)
    g.effects[PowerUpType.SHIELD] = 60
    tick(g, 60)
    g.level = 5
    tick(g, 140)
    g.energy = 100
    frames = []
    for i in range(110):
        tick(g, 2)
        if i == 70:
            g._nova()
        if g.state != GameState.PLAYING:
            break
        frames.append(to_pil(grab(g), 0.55))
    save_gif(frames, "boss.gif")


def jump_gif() -> None:
    """GIF ravvicinata del salto sopra una mina."""
    g = new_game(3, seed=5)
    g.handle_key(pygame.K_SPACE)
    g.snake.grow(12)
    tick(g, 60, ai=False)
    hx, hy = g.snake.head
    g.food.position = (1, 1)
    mine = Mine((hx + 4, hy))
    mine.age = 5
    g.mines = [mine]
    frames = []
    for i in range(70):
        if i == 12:
            g._jump()
        tick(g, 1, ai=False)
        shot = grab(g)
        x = max(0, min(800 - 400, (hx - 8) * 20))
        y = max(0, min(600 - 200, (hy - 5) * 20))
        frames.append(to_pil(shot.subsurface(pygame.Rect(x, y, 400, 200)), 1.0))
    save_gif(frames, "jump.gif", fps=30)


def screenshots() -> None:
    """Screenshot statici: menu, laser al neon, classifica."""
    g = new_game(0, seed=3)
    tick(g, 200, ai=False)
    g.menu_panel = 0
    save_png(grab(g), "menu.png")

    g = new_game(2, seed=9)
    g.handle_key(pygame.K_SPACE)
    g.snake.grow(12)
    tick(g, 90)
    hx, hy = g.snake.head
    dx = 1 if hx < 20 else -1
    g.snake.direction = g.snake.next_direction = "RIGHT" if dx > 0 else "LEFT"
    for k, cells in enumerate([[(hx + dx * 6, hy - 1 + i) for i in range(4)],
                               [(hx + dx * 12, hy + 2 - i) for i in range(5)]]):
        place_rival(g, cells, k)
    g.mines = [Mine((hx + dx * 9, hy))]
    g.effects[PowerUpType.LASER] = 6
    g.fire_cooldown = 0
    g._fire()
    tick(g, 4, ai=False)
    save_png(grab(g), "laser.png")

    g = new_game(0, seed=2)
    g.handle_key(pygame.K_SPACE)
    g.snake.grow(9)
    tick(g, 100)
    g.score = 2100
    g._game_over("RIVAL")
    g.player_name = "ROBY"
    tick(g, 120, ai=False)
    g._name_key(pygame.K_RETURN)
    tick(g, 20, ai=False)
    save_png(grab(g), "leaderboard.png")

    # I quattro temi affiancati in una sola immagine
    sheet = pygame.Surface((800, 600))
    for i in range(4):
        g = new_game(i, seed=20 + i)
        g.handle_key(pygame.K_SPACE)
        g.snake.grow(10)
        tick(g, 150)
        small = pygame.transform.smoothscale(grab(g), (400, 300))
        sheet.blit(small, ((i % 2) * 400, (i // 2) * 300))
    save_png(sheet, "themes.png")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    print("Generazione media in", OUT)
    screenshots()
    hero_gif()
    boss_gif()
    jump_gif()
    if os.path.exists(score_manager.HIGH_SCORE_FILE):
        os.remove(score_manager.HIGH_SCORE_FILE)
