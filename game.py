"""
Modulo che implementa la classe Game (Game Engine / Controller + View).
Gestisce il ciclo di vita del gioco, la macchina a stati, l'input, la logica
a passi (Delta Time) e il rendering: mondo con screen shake, HUD e overlay.

Separazione dei tempi:
- update(dt)         -> logica di gioco (solo in PLAYING), deterministica e testabile;
- update_visuals(dt) -> particelle, animazioni, menu dimostrativo (sempre).
"""

import math
import random
import sys
from typing import Dict, List, Optional, Set, Tuple

import pygame

from config import (
    SCREEN_WIDTH, SCREEN_HEIGHT, CELL_SIZE, GRID_WIDTH, GRID_HEIGHT, FPS, MAX_FRAME_DT,
    MOVE_INTERVAL, MIN_MOVE_INTERVAL, SPEEDUP_PER_FOOD, FOODS_PER_LEVEL,
    COMBO_WINDOW, MAX_COMBO, SCORE_MINE,
    ENERGY_MAX, ENERGY_START, ENERGY_REGEN, DASH_DRAIN, DASH_MIN_ENERGY, DASH_FACTOR, NOVA_RADIUS,
    SPEED_BOOST_FACTOR, SLOW_MOTION_FACTOR, MAX_POWERUPS, POWERUP_SPAWN_CHANCE,
    SHIELD_GRACE, MAGNET_RANGE,
    MINE_FIRST_SPAWN, MINE_SPAWN_INTERVAL, MINE_MAX_BASE, BONUS_SPAWN_INTERVAL,
    Direction, DIRECTION_VECTORS, OPPOSITE,
    COLOR_WHITE, COLOR_GRAY, COLOR_NEON_GREEN, COLOR_RED, COLOR_GOLD, COLOR_CYAN,
    COLOR_MAGENTA, COLOR_ORANGE,
    RIVAL_START_LEVEL, RIVAL_SPAWN_INTERVAL, BOSS_EVERY, BOSS_LENGTH, BOSS_MIN_LENGTH,
    SCORE_RIVAL, SCORE_BOSS, MAX_PELLETS,
)
from snake import Snake, COLLISION_WALL, COLLISION_SELF
from food import Food, FoodKind
from score_manager import ScoreManager, MAX_NAME_LENGTH
from power_up import PowerUp, PowerUpType, POWERUP_INFO, Mine
from particles import ParticleSystem
from audio import SoundBank
from music import MusicPlayer
from rival import Rival
from themes import THEMES, Theme, RIVAL_SKIN, BOSS_SKIN, theme_by_name
import visuals as vfx

GridPosition = Tuple[int, int]

# Posizione iniziale della testa: a sinistra, a metà altezza
START_POSITION: GridPosition = (GRID_WIDTH // 4, GRID_HEIGHT // 2)

# Mappatura tasti -> direzioni (frecce e WASD)
KEY_TO_DIRECTION: Dict[int, str] = {
    pygame.K_UP: Direction.UP, pygame.K_w: Direction.UP,
    pygame.K_DOWN: Direction.DOWN, pygame.K_s: Direction.DOWN,
    pygame.K_LEFT: Direction.LEFT, pygame.K_a: Direction.LEFT,
    pygame.K_RIGHT: Direction.RIGHT, pygame.K_d: Direction.RIGHT,
}
DASH_KEYS = (pygame.K_LSHIFT, pygame.K_RSHIFT)
NOVA_KEYS = (pygame.K_e, pygame.K_q)

BULGE_SPEED: float = 5.0  # Segmenti al secondo con cui la preda scende nel corpo


class GameState:
    """Stati della macchina a stati del gioco."""
    MENU = "MENU"
    PLAYING = "PLAYING"
    PAUSED = "PAUSED"
    GAMEOVER = "GAMEOVER"


class FloatingText:
    """Testo che sale e svanisce (punti, combo, nomi dei power-up)."""

    def __init__(self, x: float, y: float, text: str, color: Tuple[int, int, int],
                 size: str = "mid", life: float = 1.0, vy: float = -45.0):
        self.x, self.y = x, y
        self.text = text
        self.color = color
        self.size = size
        self.life = life
        self.max_life = life
        self.vy = vy


class Game:
    """
    Orchestra tutte le componenti del gioco Snake Advanced.
    """

    def __init__(self):
        """
        Inizializza Pygame, la finestra, le risorse grafiche/sonore e le entità.
        """
        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.init()
        self.screen: pygame.Surface = self._create_window()
        pygame.display.set_caption("Snake Advanced")
        self.clock: pygame.time.Clock = pygame.time.Clock()

        # Font: Bahnschrift/Segoe su Windows, ripiego sul font di default
        self.fonts: Dict[str, pygame.font.Font] = {}
        for key, size in (("title", 92), ("big", 54), ("mid", 30), ("small", 21), ("tiny", 16)):
            try:
                self.fonts[key] = pygame.font.SysFont("bahnschrift,segoeui,arial", size, bold=True)
            except (pygame.error, OSError):
                self.fonts[key] = pygame.font.Font(None, int(size * 1.3))
        self.font: pygame.font.Font = self.fonts["big"]
        self.small_font: pygame.font.Font = self.fonts["mid"]

        # Risorse della View
        self.world: pygame.Surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        # Tema grafico salvato nelle preferenze
        saved_theme = theme_by_name(str(ScoreManager.get_setting("theme", THEMES[0].name)))
        self.theme_index: int = THEMES.index(saved_theme)
        self.background: pygame.Surface = vfx.build_background(saved_theme)
        self.renderer = vfx.SnakeRenderer(saved_theme.skin)
        self.rival_renderers = [vfx.SnakeRenderer(RIVAL_SKIN) for _ in range(3)]
        self.boss_renderer = vfx.SnakeRenderer(BOSS_SKIN, 1.45)
        self.particles = ParticleSystem()
        self.ambience = vfx.Ambience(color=saved_theme.mote)
        self.sounds = SoundBank()
        self.music = MusicPlayer()
        self.leaderboard = ScoreManager.load_leaderboard()
        self.menu_panel: int = 0
        self.menu_panel_timer: float = 0.0
        self.banner_text: str = ""
        self.banner_color: Tuple[int, int, int] = COLOR_WHITE
        self.banner_glow: Tuple[int, int, int] = COLOR_WHITE
        self.banner_time: float = 0.0
        self._dim = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        self._panel_cache: Dict[Tuple[int, int, int], pygame.Surface] = {}

        # Entità
        self.snake: Snake = Snake(START_POSITION)
        self.food: Food = Food((0, 0))
        self.food.generate_new(self.snake.body)
        self.bonus_food: Optional[Food] = None
        self.power_ups: List[PowerUp] = []
        self.mines: List[Mine] = []
        self.effects: Dict[PowerUpType, float] = {}

        self.state: str = GameState.MENU
        self.score: int = 0
        self.won: bool = False

        # Delta Time accumulato: il serpente avanza di un passo ogni volta
        # che l'accumulatore supera move_interval (indipendente dagli FPS)
        self.move_accumulator: float = 0.0
        self.base_move_interval: float = MOVE_INTERVAL
        self.move_interval: float = MOVE_INTERVAL

        self.high_score: int = ScoreManager.get_current_high_score()
        if self.leaderboard:
            self.high_score = max(self.high_score, self.leaderboard[0]["score"])
        self._reset_session()

        # Stato puramente visivo
        self.time: float = 0.0
        self.shake_time: float = 0.0
        self.shake_intensity: float = 0.0
        self.flash: float = 0.0
        self.flash_color: Tuple[int, int, int] = (255, 255, 255)
        self.texts: List[FloatingText] = []
        self.death_timer: float = 0.0
        self.death_exploded: int = 0
        self.death_points: List[Tuple[float, float]] = []
        self.slowmo_blend: float = 0.0
        self.level_banner: float = 0.0

        # Serpente dimostrativo del menu (non tocca lo stato di gioco reale)
        self.demo_snake: Snake = Snake((GRID_WIDTH // 2, GRID_HEIGHT // 2 + 7))
        self.demo_food: Food = Food((0, 0))
        self.demo_food.generate_new(self.demo_snake.body)
        self.demo_acc: float = 0.0
        self.demo_bulges: List[float] = []

    @staticmethod
    def _create_window() -> pygame.Surface:
        """
        Crea la finestra scalabile con vsync (F11 = schermo intero);
        se il driver non lo supporta (es. test senza video) usa una finestra semplice.
        """
        if pygame.display.get_driver() in ("dummy", "offscreen"):
            return pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        try:
            return pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SCALED, vsync=1)
        except pygame.error:
            return pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))

    def _reset_session(self) -> None:
        """Azzera i valori della singola partita (combo, energia, timer)."""
        self.combo: int = 0
        self.combo_timer: float = 0.0
        self.best_combo: int = 0
        self.foods_eaten: int = 0
        self.mines_destroyed: int = 0
        self.level: int = 1
        self.energy: float = ENERGY_START
        self.dashing: bool = False
        self.play_time: float = 0.0
        self.mine_timer: float = MINE_FIRST_SPAWN
        self.bonus_timer: float = BONUS_SPAWN_INTERVAL
        self.grace: float = 0.0
        self.bulges: List[float] = []
        self.new_record: bool = False
        self.eat_pulse: float = 0.0
        self.rivals: List[Rival] = []
        self.pellets: List[Food] = []
        self.rival_timer: float = RIVAL_SPAWN_INTERVAL
        self.bosses_done: Set[int] = set()
        self.rivals_killed: int = 0
        self.entering_name: bool = False
        self.player_name: str = ""
        self.last_rank: int = 0

    # ------------------------------------------------------------------
    # Proprietà degli effetti
    # ------------------------------------------------------------------

    @property
    def shield_active(self) -> bool:
        """True se lo scudo è attivo."""
        return PowerUpType.SHIELD in self.effects

    @property
    def ghost_active(self) -> bool:
        """True se il Fantasma è attivo."""
        return PowerUpType.GHOST in self.effects

    def _current_interval(self) -> float:
        """
        Intervallo tra due passi: base (che cala col cibo) moltiplicato
        per gli effetti attivi. Ricalcolato a ogni passo, mai "sporcato",
        così la fine di un effetto ripristina sempre la velocità corretta.
        """
        interval = self.base_move_interval
        if PowerUpType.SPEED_BOOST in self.effects:
            interval *= SPEED_BOOST_FACTOR
        if PowerUpType.SLOW_MOTION in self.effects:
            interval *= SLOW_MOTION_FACTOR
        if self.dashing:
            interval *= DASH_FACTOR
        return interval

    # ------------------------------------------------------------------
    # Ciclo di vita della partita
    # ------------------------------------------------------------------

    def reset_game(self) -> None:
        """
        Resetta il gioco a uno stato giocabile (dal Menu o da Game Over).
        """
        self.snake.reset(START_POSITION)
        self.food = Food((0, 0))
        self.food.generate_new(self.snake.body)
        self.bonus_food = None
        self.power_ups = []
        self.mines = []
        self.effects = {}
        self.score = 0
        self.won = False
        self.move_accumulator = 0.0
        self.base_move_interval = MOVE_INTERVAL
        self.move_interval = MOVE_INTERVAL
        self._reset_session()
        self.particles.clear()
        self.texts = []
        self.death_timer = 0.0
        self.death_exploded = 0
        self.state = GameState.PLAYING
        hx, hy = vfx.cell_center(self.snake.head)
        self.particles.emit_ring(hx, hy, COLOR_NEON_GREEN, 120, 0.7, 5)
        self.sounds.play("start")

    def _handle_input(self) -> bool:
        """
        Gestisce gli eventi di input (tasti) e aggiorna stato e direzione.

        :return: False se l'utente ha chiesto di chiudere il gioco, True altrimenti.
        """
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                self.handle_key(event.key)
            elif event.type == pygame.KEYUP:
                self.handle_key_up(event.key)
            elif event.type == pygame.TEXTINPUT:
                self.handle_text(event.text)
        return True

    def handle_key(self, key: int) -> None:
        """
        Applica l'effetto di un singolo tasto in base allo stato corrente.
        Separato da _handle_input per poterlo testare senza la coda eventi.
        """
        if self.state == GameState.GAMEOVER and self.entering_name:
            self._name_key(key)
            return
        if key == pygame.K_m:
            muted = self.sounds.toggle_mute()
            self.music.set_muted(muted)
            self._text_center("AUDIO OFF" if muted else "AUDIO ON", COLOR_GRAY)
            return
        if key == pygame.K_F11:
            try:
                pygame.display.toggle_fullscreen()
            except pygame.error:
                pass
            return

        if self.state == GameState.MENU:
            if key in (pygame.K_SPACE, pygame.K_RETURN):
                self.reset_game()
            elif key == pygame.K_t:
                self._cycle_theme()
            elif key == pygame.K_TAB:
                self.menu_panel ^= 1
                self.menu_panel_timer = 0.0

        elif self.state == GameState.PLAYING:
            if key == pygame.K_SPACE or key == pygame.K_p:
                self.state = GameState.PAUSED
                self.dashing = False
            elif key == pygame.K_ESCAPE:
                self.state = GameState.MENU
                self.dashing = False
            elif key in KEY_TO_DIRECTION:
                self.snake.change_direction(KEY_TO_DIRECTION[key])
            elif key in DASH_KEYS:
                self._start_dash()
            elif key in NOVA_KEYS:
                self._nova()

        elif self.state == GameState.PAUSED:
            if key == pygame.K_SPACE or key == pygame.K_p:
                self.state = GameState.PLAYING
            elif key == pygame.K_ESCAPE:
                self.state = GameState.MENU

        elif self.state == GameState.GAMEOVER:
            if key in (pygame.K_r, pygame.K_RETURN, pygame.K_SPACE):
                self.reset_game()
            elif key == pygame.K_ESCAPE:
                self.state = GameState.MENU

    def handle_key_up(self, key: int) -> None:
        """Rilascio tasti: lo scatto dura finché SHIFT è premuto."""
        if key in DASH_KEYS:
            self.dashing = False

    # ------------------------------------------------------------------
    # Logica (Model update)
    # ------------------------------------------------------------------

    def update(self, dt: float) -> None:
        """
        Aggiorna la logica di gioco accumulando il Delta Time.
        Può eseguire zero o più passi per frame: se un frame dura molto,
        il serpente recupera i passi persi invece di rallentare.

        :param dt: Secondi trascorsi dal frame precedente.
        """
        if self.state != GameState.PLAYING:
            return
        self.play_time += dt

        # Timer degli effetti: ognuno scade in modo indipendente
        for kind in list(self.effects):
            self.effects[kind] -= dt
            if self.effects[kind] <= 0:
                del self.effects[kind]
        self.grace = max(0.0, self.grace - dt)

        if self.combo_timer > 0:
            self.combo_timer -= dt
            if self.combo_timer <= 0:
                self.combo = 0

        # Energia: lo scatto la consuma, altrimenti si rigenera lentamente
        if self.dashing:
            self.energy -= DASH_DRAIN * dt
            if self.energy <= 0:
                self.energy = 0.0
                self.dashing = False
        else:
            self.energy = min(ENERGY_MAX, self.energy + ENERGY_REGEN * dt)

        # Oggetti a tempo
        self.power_ups = [p for p in self.power_ups if p.update(dt)]
        self.mines = [m for m in self.mines if m.update(dt)]
        if self.bonus_food is not None:
            if not self.bonus_food.update(dt):
                self.bonus_food = None
        else:
            self.bonus_timer -= dt
            if self.bonus_timer <= 0:
                self.bonus_timer = BONUS_SPAWN_INTERVAL
                self._spawn_bonus()
        self.mine_timer -= dt
        if self.mine_timer <= 0:
            self.mine_timer = max(4.0, MINE_SPAWN_INTERVAL - min(self.level, 6) * 0.8)
            self._spawn_mine()
        if self.food.position is not None:
            self.food.update(dt)
        self.pellets = [pel for pel in self.pellets if pel.update(dt)]

        # Movimento a passi discreti scanditi dal tempo accumulato
        self.move_interval = self._current_interval()
        self.move_accumulator += dt
        while self.move_accumulator >= self.move_interval and self.state == GameState.PLAYING:
            self.move_accumulator -= self.move_interval
            self._step()
            self.move_interval = self._current_interval()

        if self.state == GameState.PLAYING:
            self._update_rivals(dt)

    def _step(self) -> None:
        """
        Esegue un singolo passo: movimento, collisioni, mine, magnete, cibo e power-up.
        """
        self.snake.step()

        kind = self.snake.collision_kind()
        if kind == COLLISION_SELF and (self.ghost_active or self.grace > 0):
            kind = None
        if kind is not None:
            if self.shield_active:
                self._consume_shield(kind)
            else:
                self._game_over(kind)
                return

        head = self.snake.head
        for mine in list(self.mines):
            if mine.armed and mine.position == head:
                if self.dashing:
                    self._destroy_mine(mine, "SFONDAMENTO!")
                elif self.shield_active:
                    self._consume_shield("MINE")
                    self._destroy_mine(mine, None)
                else:
                    self._game_over("MINE")
                    return

        if self._player_hits_rivals():
            return

        if PowerUpType.MAGNET in self.effects:
            self._magnet_pull()

        if self.food.position is not None and head == self.food.position:
            self._eat(self.food)
            if self.state != GameState.PLAYING:
                return
        if self.bonus_food is not None and head == self.bonus_food.position:
            self._eat(self.bonus_food)
            self.bonus_food = None
        for pel in self.pellets[:]:
            if head == pel.position:
                self._eat(pel)
                self.pellets.remove(pel)

        for p in self.power_ups[:]:
            if head == p.position:
                self._apply_power_up(p)
                self.power_ups.remove(p)

    def _blocked_cells(self) -> List[GridPosition]:
        """Celle occupate da oggetti diversi dal serpente."""
        cells = [m.position for m in self.mines] + [p.position for p in self.power_ups]
        cells += [pel.position for pel in self.pellets if pel.position is not None]
        for r in self.rivals:
            cells += r.body
        for f in (self.food, self.bonus_food):
            if f is not None and f.position is not None:
                cells.append(f.position)
        return cells

    def _free_cells(self, min_head_dist: int) -> List[GridPosition]:
        """
        Celle libere ad almeno min_head_dist (distanza di Manhattan) dalla testa:
        gli oggetti non devono comparire proprio davanti al serpente.
        """
        occupied = set(self.snake.body)
        occupied.update(self._blocked_cells())
        hx, hy = self.snake.head
        return [(x, y) for x in range(GRID_WIDTH) for y in range(GRID_HEIGHT)
                if (x, y) not in occupied and abs(x - hx) + abs(y - hy) >= min_head_dist]

    def _eat(self, food: Food) -> None:
        """Consuma un cibo: combo, punti, crescita, energia, livello ed effetti."""
        self.combo = min(MAX_COMBO, self.combo + 1) if self.combo_timer > 0 else 1
        self.combo_timer = COMBO_WINDOW
        self.best_combo = max(self.best_combo, self.combo)
        points = food.value * self.combo
        self.score += points
        self.snake.grow(food.growth)
        self.energy = min(ENERGY_MAX, self.energy + food.energy)
        if food.kind != FoodKind.PELLET:
            # I frammenti non contano per livello e velocità: solo per i punti
            self.foods_eaten += 1
            self.base_move_interval = max(MIN_MOVE_INTERVAL,
                                          MOVE_INTERVAL - self.foods_eaten * SPEEDUP_PER_FOOD)
        self.bulges.append(0.0)
        self.eat_pulse = 1.0

        golden = food.kind == FoodKind.GOLDEN
        assert food.position is not None  # Si mangia solo un cibo presente in griglia
        cx, cy = vfx.cell_center(food.position)
        color = COLOR_GOLD if golden else (255, 70, 60)
        self.particles.emit_burst(cx, cy, color, 40 if golden else 22)
        self.particles.emit_sparks(cx, cy, (255, 230, 160), 14 if golden else 6)
        self.particles.emit_ring(cx, cy, color, 70 if golden else 38, 0.45, 3)
        self._add_text(cx, cy - 10, f"+{points}", COLOR_GOLD if golden else COLOR_WHITE,
                       "mid" if golden else "small")
        if self.combo > 1:
            self._add_text(cx, cy - 32, f"COMBO x{self.combo}", COLOR_ORANGE, "small", 0.9)
        self._shake(0.12, 2.5 if not golden else 5)
        self.sounds.play("golden" if golden else ("eat" if self.combo <= 1 else f"eat{self.combo}"))

        new_level = 1 + self.foods_eaten // FOODS_PER_LEVEL
        if new_level > self.level:
            self.level = new_level
            self.level_banner = 1.6
            self.sounds.play("level")

        if food.kind == FoodKind.NORMAL:
            if not food.generate_new(self.snake.body, self._blocked_cells()):
                self.won = True
                self._game_over(None)
                return
            if random.random() < POWERUP_SPAWN_CHANCE + min(self.level, 5) * 0.02:
                self._generate_power_up()

    def _generate_power_up(self) -> None:
        """
        Genera un Power-up casuale in una cella libera lontana dalla testa.
        Estrae dalle celle libere: nessun ciclo infinito a griglia piena.
        """
        if len(self.power_ups) >= MAX_POWERUPS:
            return
        cells = self._free_cells(3)
        if not cells:
            return
        p = PowerUp(random.choice(cells), random.choice(list(PowerUpType)))
        self.power_ups.append(p)
        cx, cy = vfx.cell_center(p.position)
        self.particles.emit_ring(cx, cy, POWERUP_INFO[p.type][1], 40, 0.5, 2)
        self.sounds.play("spawn")

    def _spawn_bonus(self) -> None:
        """Fa comparire il frutto d'oro a tempo."""
        cells = self._free_cells(4)
        if not cells:
            return
        pos = random.choice(cells)
        self.bonus_food = Food(pos, FoodKind.GOLDEN)
        cx, cy = vfx.cell_center(pos)
        self.particles.emit_ring(cx, cy, COLOR_GOLD, 80, 0.7, 3)
        self.particles.emit_burst(cx, cy, COLOR_GOLD, 18, speed=(30, 120))
        self.sounds.play("spawn")

    def _spawn_mine(self) -> None:
        """Piazza una mina lontano dalla testa (il numero massimo cresce col livello)."""
        if len(self.mines) >= MINE_MAX_BASE + self.level:
            return
        cells = self._free_cells(6)
        if not cells:
            return
        self.mines.append(Mine(random.choice(cells)))

    def _apply_power_up(self, p: PowerUp) -> None:
        """
        Applica gli effetti del Power-up consumato. Ogni effetto ha il suo timer:
        riprenderne uno già attivo ne rinnova la durata.
        """
        name, color, duration = POWERUP_INFO[p.type]
        self.effects[p.type] = duration
        cx, cy = vfx.cell_center(p.position)
        self.particles.emit_burst(cx, cy, color, 45, speed=(80, 320))
        self.particles.emit_ring(cx, cy, color, 110, 0.6, 5)
        self.particles.emit_ring(cx, cy, COLOR_WHITE, 60, 0.35, 2)
        self._add_text(cx, cy - 18, name, color, "mid", 1.3)
        self._flash(color, 0.25)
        self._shake(0.15, 4)
        self.sounds.play("power")

    def _consume_shield(self, kind: Optional[str]) -> None:
        """
        Lo scudo assorbe un impatto: contro il muro la testa attraversa un portale
        e riappare dal lato opposto; dopo l'uso c'è un breve periodo di grazia.
        """
        self.effects.pop(PowerUpType.SHIELD, None)
        self.grace = SHIELD_GRACE
        hx, hy = self.snake.head
        old = ((hx + 0.5) * CELL_SIZE, (hy + 0.5) * CELL_SIZE)
        if kind == COLLISION_WALL:
            self.snake.wrap_head()
            nx, ny = vfx.cell_center(self.snake.head)
            self.particles.emit_ring(nx, ny, COLOR_CYAN, 70, 0.5, 4)
            self.particles.emit_burst(nx, ny, COLOR_CYAN, 25)
        self.particles.emit_ring(old[0], old[1], COLOR_CYAN, 90, 0.5, 5)
        self.particles.emit_sparks(old[0], old[1], COLOR_CYAN, 30)
        self._add_text(old[0], old[1] - 20, "SCUDO!", COLOR_CYAN, "mid")
        self._flash(COLOR_CYAN, 0.3)
        self._shake(0.25, 7)
        self.sounds.play("shield")

    def _destroy_mine(self, mine: Mine, label: Optional[str], award: bool = True) -> None:
        """Fa esplodere una mina (assegnando i punti se l'ha distrutta il giocatore)."""
        if mine in self.mines:
            self.mines.remove(mine)
        if award:
            self.mines_destroyed += 1
            self.score += SCORE_MINE
        cx, cy = vfx.cell_center(mine.position)
        self.particles.emit_burst(cx, cy, COLOR_ORANGE, 35, speed=(80, 340))
        self.particles.emit_burst(cx, cy, (255, 60, 30), 20, speed=(40, 160), life=(0.5, 1.2))
        self.particles.emit_sparks(cx, cy, (255, 220, 140), 22)
        self.particles.emit_ring(cx, cy, COLOR_ORANGE, 75, 0.5, 5)
        self._add_text(cx, cy - 14, label or f"+{SCORE_MINE}", COLOR_ORANGE, "small")
        self._shake(0.2, 6)
        self.sounds.play("explode")

    def _start_dash(self) -> None:
        """Avvia lo scatto (SHIFT): velocità doppia e mine sfondate al contatto."""
        if self.energy >= DASH_MIN_ENERGY and not self.dashing:
            self.dashing = True
            hx, hy = vfx.cell_center(self.snake.head)
            self.particles.emit_ring(hx, hy, COLOR_CYAN, 50, 0.3, 3)
            self.sounds.play("dash")
        elif not self.dashing:
            self.sounds.play("deny")

    def _nova(self) -> None:
        """
        Nova (E/Q): con energia piena rilascia un'onda d'urto che polverizza
        le mine nel raggio NOVA_RADIUS. Azzera l'energia.
        """
        if self.energy < ENERGY_MAX:
            self.sounds.play("deny")
            hx, hy = vfx.cell_center(self.snake.head)
            self._add_text(hx, hy - 24, "ENERGIA INSUFFICIENTE", COLOR_GRAY, "tiny", 0.8)
            return
        self.energy = 0.0
        self.dashing = False
        hx, hy = self.snake.head
        cx, cy = vfx.cell_center(self.snake.head)
        for i, (col, rad, dur, w) in enumerate(((COLOR_WHITE, 140, 0.4, 6), (COLOR_MAGENTA, 260, 0.8, 8),
                                                (COLOR_CYAN, 330, 1.0, 4))):
            self.particles.emit_ring(cx, cy, col, rad, dur, w)
        self.particles.emit_burst(cx, cy, COLOR_MAGENTA, 90, speed=(150, 520), life=(0.5, 1.2))
        self.particles.emit_burst(cx, cy, COLOR_CYAN, 60, speed=(100, 400))
        for mine in list(self.mines):
            mx, my = mine.position
            if math.hypot(mx - hx, my - hy) <= NOVA_RADIUS:
                self._destroy_mine(mine, None)
        for r in list(self.rivals):
            rx, ry = r.head
            if r.alive and math.hypot(rx - hx, ry - hy) <= NOVA_RADIUS:
                if r.boss:
                    self._damage_boss(r, max(3, int(len(r.body) * 0.4)))
                else:
                    self._kill_rival(r, "DISINTEGRATO!")
        self.grace = max(self.grace, 0.3)
        self._add_text(cx, cy - 30, "NOVA!", COLOR_MAGENTA, "big", 1.2)
        self._flash((255, 180, 255), 0.6)
        self._shake(0.5, 12)
        self.sounds.play("nova")

    def _magnet_pull(self) -> None:
        """Il magnete avvicina di una cella al passo il cibo entro MAGNET_RANGE."""
        hx, hy = self.snake.head
        obstacles = set(self.snake.body[1:])
        obstacles.update(m.position for m in self.mines)
        for f in (self.food, self.bonus_food):
            if f is None or f.position is None:
                continue
            fx, fy = f.position
            dx, dy = hx - fx, hy - fy
            if max(abs(dx), abs(dy)) > MAGNET_RANGE or (dx == 0 and dy == 0):
                continue
            if abs(dx) >= abs(dy):
                target = (fx + (1 if dx > 0 else -1), fy)
            else:
                target = (fx, fy + (1 if dy > 0 else -1))
            if target not in obstacles:
                f.position = target

    def _game_over(self, kind: Optional[str]) -> None:
        """
        Passa allo stato GAMEOVER, salva il record se battuto e avvia
        l'animazione di morte (il corpo esplode dalla testa verso la coda).
        """
        self.state = GameState.GAMEOVER
        self.dashing = False
        self.snake.is_alive = False
        if kind == COLLISION_WALL:
            self.snake.revert_step()
        if self.score > self.high_score:
            ScoreManager.save_high_score(self.score)
            self.high_score = self.score
            self.new_record = True
        self.last_rank = 0
        self.entering_name = ScoreManager.qualifies(self.score)
        if self.entering_name:
            self.player_name = str(ScoreManager.get_setting("last_name", "") or "")[:MAX_NAME_LENGTH]
            self._text_input(True)
        self.leaderboard = ScoreManager.load_leaderboard()
        self.death_points = self.renderer.compute_points(self.snake, 1.0)
        self.death_timer = 0.0
        self.death_exploded = 0
        if self.death_points:
            hx, hy = self.death_points[0]
            self.particles.emit_ring(hx, hy, COLOR_RED, 160, 0.8, 7)
            self.particles.emit_sparks(hx, hy, (255, 200, 120), 40)
        self._flash(COLOR_RED if not self.won else COLOR_GOLD, 0.5)
        self._shake(0.6, 14)
        self.sounds.play("death" if not self.won else "level")

    # ------------------------------------------------------------------
    # Rivali e boss
    # ------------------------------------------------------------------

    def _rival_interval(self, r: Rival) -> float:
        """Intervallo di passo del rivale: anche i nemici subiscono il Bullet Time."""
        return r.interval * (SLOW_MOTION_FACTOR if PowerUpType.SLOW_MOTION in self.effects else 1.0)

    def _all_food(self) -> List[Food]:
        """Tutto il cibo presente: frutto, frutto d'oro e frammenti."""
        foods = [self.food]
        if self.bonus_food is not None:
            foods.append(self.bonus_food)
        return foods + self.pellets

    def _update_rivals(self, dt: float) -> None:
        """Comparsa di rivali e boss, poi movimento a passi (Delta Time) di ciascuno."""
        if self.level >= RIVAL_START_LEVEL:
            self.rival_timer -= dt
            limit = 1 if self.level < 6 else 2 if self.level < 10 else 3
            if self.rival_timer <= 0:
                self.rival_timer = RIVAL_SPAWN_INTERVAL
                if sum(1 for r in self.rivals if not r.boss) < limit:
                    self._spawn_rival(False)
        if self.level % BOSS_EVERY == 0 and self.level not in self.bosses_done:
            self.bosses_done.add(self.level)
            self._spawn_rival(True)

        for r in list(self.rivals):
            r.age += dt
            r.acc += dt
            interval = self._rival_interval(r)
            while r.alive and r.acc >= interval and self.state == GameState.PLAYING:
                r.acc -= interval
                self._rival_step(r)
        self.rivals = [r for r in self.rivals if r.alive]

    def _spawn_rival(self, boss: bool) -> None:
        """Fa emergere un rivale (o il boss) da un portale lontano dal giocatore."""
        used = {r.slot for r in self.rivals if not r.boss}
        slots = [i for i in range(len(self.rival_renderers)) if i not in used]
        if not boss and not slots:
            return
        occupied = set(self.snake.body) | set(self._blocked_cells())
        hx, hy = self.snake.head
        cands = [(x, y) for x in range(3, GRID_WIDTH - 3) for y in range(2, GRID_HEIGHT - 2)
                 if abs(x - hx) + abs(y - hy) >= 14
                 and all((x - i, y) not in occupied for i in range(-1, 3))]
        if not cands:
            return
        pos = random.choice(cands)
        rival = Rival(pos, boss, 0 if boss else slots[0])
        self.rivals.append(rival)
        cx, cy = vfx.cell_center(pos)
        color = BOSS_SKIN.bright if boss else RIVAL_SKIN.bright
        self.particles.emit_ring(cx, cy, color, 90 if boss else 50, 0.8, 4)
        self.particles.emit_burst(cx, cy, color, 40 if boss else 18, speed=(40, 200))
        if boss:
            self._banner("BOSS IN ARRIVO!", (255, 200, 255), (170, 0, 190), 2.6)
            self._flash((180, 40, 220), 0.4)
            self._shake(0.7, 9)
            self.sounds.play("nova")
        else:
            self._add_text(cx, cy - 22, "RIVALE!", (255, 120, 120), "small", 1.2)
            self.sounds.play("spawn")

    def _rival_obstacles(self, me: Rival) -> Set[GridPosition]:
        """Celle che l'IA del rivale considera mortali."""
        blocked: Set[GridPosition] = {m.position for m in self.mines}
        for r in self.rivals:
            if r is not me and r.alive:
                blocked.update(r.body)
        if me.boss:
            return blocked  # Il boss ignora il proprio corpo e morde quello del giocatore
        blocked.update(me.body[:-1])
        blocked.update(self.snake.body)
        return blocked

    def _rival_step(self, r: Rival) -> None:
        """Un passo del rivale: IA, movimento e tutte le sue collisioni."""
        snake = r.snake
        if r.boss:
            hx, hy = self.snake.head
            dx, dy = DIRECTION_VECTORS[self.snake.direction]
            targets = [((hx + dx * 2) % GRID_WIDTH, (hy + dy * 2) % GRID_HEIGHT), (hx, hy)]
        else:
            targets = [f.position for f in self._all_food() if f.position is not None]
        snake.change_direction(r.choose_direction(targets, self._rival_obstacles(r)))
        snake.step()

        x, y = snake.head
        if not (0 <= x < GRID_WIDTH and 0 <= y < GRID_HEIGHT):
            if r.boss:
                snake.wrap_head()
            else:
                snake.revert_step()
                self._kill_rival(r, "SCHIANTATO!")
                return
        head = snake.head
        if not r.boss and head in snake.body[1:]:
            self._kill_rival(r, "SCHIANTATO!")
            return
        for other in self.rivals:
            if other is not r and other.alive and head in other.body:
                if r.boss:
                    self._kill_rival(other, "DIVORATO!", award=False)
                else:
                    self._kill_rival(r, "SCONTRO!")
                    return
        for mine in list(self.mines):
            if mine.armed and mine.position == head:
                self._destroy_mine(mine, None, award=False)
                if r.boss:
                    self._damage_boss(r, 3)
                else:
                    self._kill_rival(r, "BOOM!")
                return

        if head == self.snake.head:
            if r.boss and not self.dashing:
                if self.shield_active:
                    self._consume_shield(None)
                    self._damage_boss(r, 4)
                else:
                    self._game_over("BOSS")
                return
            if r.boss:
                self._damage_boss(r, 8)
            else:
                self._kill_rival(r, "TESTA A TESTA!")
            return
        if head in self.snake.body[1:]:
            if not r.boss:
                self._kill_rival(r, "INTRAPPOLATO!")
                return
            if self.shield_active:
                self._consume_shield(None)
                self._damage_boss(r, 2)
            elif not self.ghost_active:
                self._bite_player(head)

        for f in self._all_food():
            if f.position == head:
                snake.grow(f.growth)
                r.bulges.append(0.0)
                cx, cy = vfx.cell_center(head)
                self.particles.emit_burst(cx, cy, (255, 90, 70), 10, speed=(30, 140))
                if f is self.food:
                    self._add_text(cx, cy - 16, "RUBATO!", (255, 120, 120), "tiny", 0.8)
                    if not self.food.generate_new(self.snake.body, self._blocked_cells()):
                        self.food.position = None
                elif f is self.bonus_food:
                    self.bonus_food = None
                else:
                    self.pellets.remove(f)
                break

    def _player_hits_rivals(self) -> bool:
        """
        Collisione della testa del giocatore con i rivali.
        Scatto = taglia/sfonda, Scudo = assorbe e taglia, Fantasma = attraversa i corpi.

        :return: True se il giocatore è morto.
        """
        head = self.snake.head
        for r in list(self.rivals):
            if not r.alive:
                continue
            if head == r.head:
                if self.dashing or self.shield_active:
                    if not self.dashing:
                        self._consume_shield(None)
                    if r.boss:
                        self._damage_boss(r, 8)
                    else:
                        self._kill_rival(r, "SFONDAMENTO!")
                    continue
                self._game_over("RIVAL")
                return True
            if head in r.body[1:]:
                idx = r.body.index(head)
                if self.dashing:
                    self._cut_rival(r, idx)
                elif self.ghost_active:
                    continue
                elif self.shield_active:
                    self._consume_shield(None)
                    self._cut_rival(r, idx)
                else:
                    self._game_over("RIVAL")
                    return True
        return False

    def _cut_rival(self, r: Rival, idx: int) -> None:
        """Taglia il rivale nel punto colpito: la parte staccata diventa frammenti."""
        removed = r.cut_at(idx)
        for c in removed:
            cx, cy = vfx.cell_center(c)
            self.particles.emit_burst(cx, cy, BOSS_SKIN.bright if r.boss else RIVAL_SKIN.bright, 5)
        self._drop_pellets(removed[::2])
        self.score += 5 * len(removed)
        self._shake(0.2, 6)
        self.sounds.play("explode")
        if r.boss and len(r.body) < BOSS_MIN_LENGTH:
            self._kill_rival(r, None)
        elif not r.boss and len(r.body) < 3:
            self._kill_rival(r, "TAGLIATO!")
        elif removed:
            cx, cy = vfx.cell_center(removed[0])
            self._add_text(cx, cy - 16, f"TAGLIO -{len(removed)}", COLOR_ORANGE, "small", 0.9)

    def _damage_boss(self, r: Rival, amount: int) -> None:
        """Il boss perde `amount` segmenti dalla coda."""
        self._cut_rival(r, max(1, len(r.body) - amount))

    def _bite_player(self, cell: GridPosition) -> None:
        """Il boss morde il corpo del giocatore: la coda staccata va perduta."""
        idx = self.snake.body.index(cell)
        keep = max(3, idx)
        removed = self.snake.body[keep:]
        self.snake.body = self.snake.body[:keep]
        self.snake.prev_body = self.snake.prev_body[:keep]
        self.snake._pending_growth = 0
        for c in removed:
            cx, cy = vfx.cell_center(c)
            self.particles.emit_burst(cx, cy, self.theme.skin.bright, 6)
        self._drop_pellets(removed[::3])
        cx, cy = vfx.cell_center(cell)
        self._add_text(cx, cy - 18, "MORSO!", (255, 90, 90), "mid", 1.0)
        self._flash((255, 30, 30), 0.35)
        self._shake(0.4, 10)
        self.sounds.play("death")

    def _drop_pellets(self, cells: List[GridPosition]) -> None:
        """Lascia frammenti di cibo nelle celle libere indicate."""
        occupied = set(self.snake.body)
        occupied.update(m.position for m in self.mines)
        occupied.update(pel.position for pel in self.pellets if pel.position is not None)
        for c in cells:
            if len(self.pellets) >= MAX_PELLETS:
                break
            if 0 <= c[0] < GRID_WIDTH and 0 <= c[1] < GRID_HEIGHT and c not in occupied:
                self.pellets.append(Food(c, FoodKind.PELLET))
                occupied.add(c)

    def _kill_rival(self, r: Rival, label: Optional[str], award: bool = True) -> None:
        """Elimina un rivale con esplosione a catena e frammenti; il boss dà un premio enorme."""
        if not r.alive:
            return
        r.alive = False
        skin = BOSS_SKIN if r.boss else RIVAL_SKIN
        pts = vfx.SnakeRenderer.compute_points(r.snake, 1.0)
        for i, (x, y) in enumerate(pts):
            self.particles.emit_burst(x, y, skin.bright, 7, speed=(40, 220))
            if i % 3 == 0:
                self.particles.emit_sparks(x, y, (255, 220, 160), 4)
        self._drop_pellets(r.body if r.boss else r.body[::2])
        hx, hy = pts[0] if pts else vfx.cell_center(r.head)
        self.particles.emit_ring(hx, hy, skin.bright, 140 if r.boss else 70, 0.6, 5)
        self._shake(0.5 if r.boss else 0.25, 12 if r.boss else 6)
        self.sounds.play("explode")
        if not award:
            return
        self.rivals_killed += 1
        points = SCORE_BOSS if r.boss else SCORE_RIVAL
        self.score += points
        if r.boss:
            self._banner("BOSS SCONFITTO!", COLOR_GOLD, (180, 110, 0), 3.0)
            self._flash(COLOR_GOLD, 0.6)
            self.energy = ENERGY_MAX
            for _ in range(6):
                fx = random.uniform(100, SCREEN_WIDTH - 100)
                fy = random.uniform(100, SCREEN_HEIGHT - 150)
                col = random.choice([COLOR_GOLD, COLOR_MAGENTA, COLOR_CYAN, COLOR_ORANGE])
                self.particles.emit_burst(fx, fy, col, 60, speed=(80, 300), gravity=120)
                self.particles.emit_ring(fx, fy, col, 80, 0.7, 3)
            self.sounds.play("level")
        self._add_text(hx, hy - 20, label or f"+{points}", COLOR_ORANGE, "mid", 1.2)
        if label:
            self._add_text(hx, hy + 4, f"+{points}", COLOR_WHITE, "small", 1.2)

    # ------------------------------------------------------------------
    # Temi e classifica
    # ------------------------------------------------------------------

    @property
    def theme(self) -> Theme:
        """Tema grafico attivo."""
        return THEMES[self.theme_index]

    def _cycle_theme(self) -> None:
        """Passa al tema successivo, ricostruisce le risorse e lo salva nelle preferenze."""
        self.theme_index = (self.theme_index + 1) % len(THEMES)
        theme = self.theme
        self.background = vfx.build_background(theme)
        self.renderer = vfx.SnakeRenderer(theme.skin)
        self.ambience = vfx.Ambience(color=theme.mote)
        ScoreManager.set_setting("theme", theme.name)
        self.sounds.play("spawn")

    @staticmethod
    def _text_input(enabled: bool) -> None:
        """Attiva/disattiva gli eventi TEXTINPUT (servono solo per il nome)."""
        try:
            if enabled:
                pygame.key.start_text_input()
            else:
                pygame.key.stop_text_input()
        except pygame.error:
            pass

    def handle_text(self, text: str) -> None:
        """Caratteri digitati: aggiunti al nome durante l'inserimento in classifica."""
        if not (self.state == GameState.GAMEOVER and self.entering_name):
            return
        for ch in text.upper():
            if (ch.isalnum() or ch in " _-.") and len(self.player_name) < MAX_NAME_LENGTH:
                self.player_name += ch

    def _name_key(self, key: int) -> None:
        """Tasti speciali durante l'inserimento del nome."""
        if key == pygame.K_BACKSPACE:
            self.player_name = self.player_name[:-1]
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.last_rank = ScoreManager.add_entry(self.player_name, self.score)
            self.leaderboard = ScoreManager.load_leaderboard()
            self.entering_name = False
            self._text_input(False)
            self.sounds.play("level")
        elif key == pygame.K_ESCAPE:
            self.entering_name = False
            self._text_input(False)

    def _banner(self, text: str, color: Tuple[int, int, int], glow: Tuple[int, int, int],
                duration: float) -> None:
        """Scritta grande al centro dello schermo (boss, vittorie)."""
        self.banner_text = text
        self.banner_color = color
        self.banner_glow = glow
        self.banner_time = duration

    # ------------------------------------------------------------------
    # Effetti visivi
    # ------------------------------------------------------------------

    def _shake(self, duration: float, intensity: float) -> None:
        """Avvia (o rinforza) il tremolio dello schermo."""
        self.shake_time = max(self.shake_time, duration)
        self.shake_intensity = max(self.shake_intensity if self.shake_time > 0 else 0, intensity)

    def _flash(self, color: Tuple[int, int, int], amount: float) -> None:
        """Lampo additivo a tutto schermo."""
        self.flash = max(self.flash, amount)
        self.flash_color = color

    def _add_text(self, x: float, y: float, text: str, color: Tuple[int, int, int],
                  size: str = "small", life: float = 1.0) -> None:
        self.texts.append(FloatingText(x, y, text, color, size, life))

    def _text_center(self, text: str, color: Tuple[int, int, int]) -> None:
        self._add_text(SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 + 120, text, color, "small", 1.0)

    def update_visuals(self, dt: float) -> None:
        """
        Aggiorna tutto ciò che è solo grafico: particelle, testi, tremolio,
        animazioni della morte, scie dello scatto e menu dimostrativo.
        """
        self.time += dt
        self.banner_time = max(0.0, self.banner_time - dt)
        if self.state == GameState.PLAYING or self.state == GameState.PAUSED:
            boss_alive = any(r.boss and r.alive for r in self.rivals)
            self.music.play("boss" if boss_alive else "action")
        else:
            self.music.play("menu")
        self.music.update()
        if self.state == GameState.MENU:
            self.menu_panel_timer += dt
            if self.menu_panel_timer > 7.0:
                self.menu_panel_timer = 0.0
                self.menu_panel ^= 1
        elif self.state == GameState.PLAYING:
            for r in self.rivals:
                r.bulges = [b + dt * BULGE_SPEED for b in r.bulges if b < len(r.body) + 2]
        self.ambience.update(dt)
        self.particles.update(dt)
        for ft in self.texts:
            ft.life -= dt
            ft.y += ft.vy * dt
        self.texts = [ft for ft in self.texts if ft.life > 0]
        if self.shake_time > 0:
            self.shake_time -= dt
            self.shake_intensity *= max(0.0, 1.0 - 4.0 * dt)
        self.flash = max(0.0, self.flash - dt * 1.6)
        self.level_banner = max(0.0, self.level_banner - dt)
        self.eat_pulse = max(0.0, self.eat_pulse - dt * 4)

        target = 1.0 if (self.state == GameState.PLAYING and PowerUpType.SLOW_MOTION in self.effects) else 0.0
        self.slowmo_blend += (target - self.slowmo_blend) * min(1.0, dt * 5)

        if self.state == GameState.PLAYING:
            limit = len(self.snake.body) + 2
            self.bulges = [b + dt * BULGE_SPEED for b in self.bulges if b < limit]
            if self.dashing:
                self._emit_dash_trail()
        elif self.state == GameState.MENU:
            self._update_demo(dt)
        elif self.state == GameState.GAMEOVER:
            self._update_death(dt)

    def _emit_dash_trail(self) -> None:
        """Scia di plasma lungo il corpo durante lo scatto."""
        pts = self.renderer.compute_points(self.snake, self._alpha())
        for i in range(0, len(pts), 2):
            x, y = pts[i]
            col = COLOR_CYAN if i % 4 == 0 else COLOR_MAGENTA
            self.particles.emit_trail(x + random.uniform(-4, 4), y + random.uniform(-4, 4), col, 2.2, 0.35)

    def _update_death(self, dt: float) -> None:
        """Esplosione a catena dei segmenti, dalla testa verso la coda."""
        self.death_timer += dt
        n = len(self.death_points)
        rate = max(28.0, n / 0.9)
        target = min(n, int(self.death_timer * rate))
        while self.death_exploded < target:
            x, y = self.death_points[self.death_exploded]
            col = COLOR_GOLD if self.won else self.theme.skin.bright
            self.particles.emit_burst(x, y, col, 9, speed=(40, 200), life=(0.4, 1.0))
            self.particles.emit_burst(x, y, (255, 120, 60), 3, speed=(20, 120))
            if self.death_exploded % 4 == 0:
                self.particles.emit_sparks(x, y, (255, 220, 160), 4)
                self.particles.emit_ring(x, y, (255, 90, 60), 26, 0.35, 2)
                self._shake(0.08, 3)
            self.death_exploded += 1

    def _update_demo(self, dt: float) -> None:
        """Serpente "attract mode" del menu, guidato da una semplice IA."""
        self.demo_acc += dt
        self.demo_bulges = [b + dt * BULGE_SPEED for b in self.demo_bulges if b < len(self.demo_snake.body) + 2]
        while self.demo_acc >= 0.085:
            self.demo_acc -= 0.085
            self.demo_snake.change_direction(self._demo_direction())
            self.demo_snake.step()
            if self.demo_snake.collision_kind() is not None or len(self.demo_snake.body) > 60:
                for x, y in self.renderer.compute_points(self.demo_snake, 1.0)[::2]:
                    self.particles.emit_burst(x, y, self.theme.skin.bright, 4)
                self.demo_snake.reset((random.randint(5, GRID_WIDTH - 5), random.randint(5, GRID_HEIGHT - 5)))
                self.demo_food.generate_new(self.demo_snake.body)
                self.demo_bulges = []
            elif self.demo_snake.head == self.demo_food.position:
                self.demo_snake.grow(2)
                self.demo_bulges.append(0.0)
                cx, cy = vfx.cell_center(self.demo_food.position)
                self.particles.emit_burst(cx, cy, (255, 70, 60), 16)
                self.demo_food.generate_new(self.demo_snake.body)

    def _demo_direction(self) -> str:
        """Sceglie la mossa più vicina al cibo che non porti in un vicolo cieco."""
        snake = self.demo_snake
        body_set = set(snake.body[:-1])
        best, best_score = snake.direction, -1e9
        fx, fy = self.demo_food.position or (0, 0)
        for d, (dx, dy) in DIRECTION_VECTORS.items():
            if d == OPPOSITE[snake.direction]:
                continue
            nx, ny = snake.head[0] + dx, snake.head[1] + dy
            if not (0 <= nx < GRID_WIDTH and 0 <= ny < GRID_HEIGHT) or (nx, ny) in body_set:
                continue
            space = self._reachable((nx, ny), body_set, len(snake.body) + 4)
            score = -abs(nx - fx) - abs(ny - fy) + random.uniform(0, 0.6)
            if space < len(snake.body) + 4:
                score -= 1000 - space
            if score > best_score:
                best, best_score = d, score
        return best

    @staticmethod
    def _reachable(start: GridPosition, blocked: set, limit: int) -> int:
        """Flood fill limitato: conta le celle raggiungibili (fino a limit)."""
        seen = {start}
        stack = [start]
        while stack and len(seen) < limit:
            x, y = stack.pop()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                c = (x + dx, y + dy)
                if c not in seen and c not in blocked and 0 <= c[0] < GRID_WIDTH and 0 <= c[1] < GRID_HEIGHT:
                    seen.add(c)
                    stack.append(c)
        return len(seen)

    # ------------------------------------------------------------------
    # Rendering (View)
    # ------------------------------------------------------------------

    def _alpha(self) -> float:
        """Frazione di passo per l'interpolazione del serpente."""
        if self.state == GameState.GAMEOVER:
            return 1.0
        return vfx.clamp(self.move_accumulator / self.move_interval) if self.move_interval > 0 else 1.0

    def _wall_warnings(self) -> Dict[str, float]:
        """Intensità dell'avviso rosso per ogni lato in base alla distanza della testa."""
        if self.state != GameState.PLAYING:
            return {}
        hx, hy = self.snake.head
        d = {"left": hx, "right": GRID_WIDTH - 1 - hx, "top": hy, "bottom": GRID_HEIGHT - 1 - hy}
        pulse = 0.75 + 0.25 * math.sin(self.time * 12)
        return {k: vfx.clamp((3 - v) / 3) * pulse for k, v in d.items() if v < 3}

    def _draw_world(self) -> None:
        """Disegna il mondo di gioco (tutto ciò che trema con lo screen shake)."""
        w = self.world
        t = self.time
        w.blit(self.background, (0, 0))
        self.ambience.draw(w)
        vfx.draw_arena(w, t, self._wall_warnings(), self.theme.arena)

        if self.state == GameState.MENU:
            vfx.draw_food(w, self.demo_food, t)
            self.renderer.draw(w, self.demo_snake, vfx.clamp(self.demo_acc / 0.085), t,
                               self.demo_snake.steps + self.demo_acc / 0.085, bulges=self.demo_bulges)
            self.particles.draw(w)
            return

        for mine in self.mines:
            vfx.draw_mine(w, mine, t)
        vfx.draw_food(w, self.food, t)
        if self.bonus_food is not None:
            vfx.draw_food(w, self.bonus_food, t, golden=True)
        for p in self.power_ups:
            vfx.draw_power_up(w, p, t, POWERUP_INFO[p.type][1])
        for pel in self.pellets:
            vfx.draw_pellet(w, pel, t, (255, 150, 60))
        for r in self.rivals:
            if not r.alive:
                continue
            color = BOSS_SKIN.bright if r.boss else RIVAL_SKIN.bright
            if r.age < 1.5:
                vfx.draw_portal(w, vfx.cell_center(r.spawn_pos), t, color, 1.0 - r.age / 1.5)
            ralpha = 1.0 if self.state == GameState.GAMEOVER else vfx.clamp(r.acc / self._rival_interval(r))
            ren = self.boss_renderer if r.boss else self.rival_renderers[r.slot]
            ren.draw(w, r.snake, ralpha, t, r.snake.steps + ralpha, bulges=r.bulges)

        alpha = self._alpha()
        if self.state == GameState.GAMEOVER:
            if self.death_exploded < len(self.death_points):
                self.renderer.draw(w, self.snake, 1.0, t, self.snake.steps,
                                   skip=self.death_exploded, points=self.death_points)
        else:
            near_food = False
            if self.food.position is not None:
                hx, hy = self.snake.head
                near_food = abs(hx - self.food.position[0]) + abs(hy - self.food.position[1]) < 5
            eye = COLOR_CYAN if self.dashing else (255, 60, 200) if self.ghost_active else (255, 170, 40)
            self.renderer.draw(w, self.snake, alpha, t, self.snake.steps + alpha,
                               ghost=self.ghost_active, bulges=self.bulges,
                               head_scale=1.0 + 0.18 * self.eat_pulse, tongue_boost=near_food,
                               eye_color=eye)
            head = self.renderer.head_pos

            # Fulmini del magnete verso il cibo attirato
            if PowerUpType.MAGNET in self.effects:
                for f in (self.food, self.bonus_food):
                    if f is not None and f.position is not None:
                        hx, hy = self.snake.head
                        if max(abs(hx - f.position[0]), abs(hy - f.position[1])) <= MAGNET_RANGE:
                            vfx.draw_lightning(w, head, vfx.cell_center(f.position), (255, 90, 110))
            if self.shield_active:
                left = self.effects[PowerUpType.SHIELD]
                if left > 2 or int(t * 10) % 2 == 0:
                    vfx.draw_shield(w, head, t)
            if self.dashing:
                vfx.blit_glow(w, head, CELL_SIZE * 2.2, (0, 90, 120), 0.9)
            if PowerUpType.SPEED_BOOST in self.effects:
                vfx.blit_glow(w, head, CELL_SIZE * 1.6, (110, 50, 0), 0.8)

        self.particles.draw(w)

        for ft in self.texts:
            frac = ft.life / ft.max_life
            surf = vfx.glow_text(self.fonts[ft.size], ft.text, ft.color, vfx.scale_color(ft.color, 0.6), 4)
            surf = surf.copy()
            surf.set_alpha(int(255 * min(1.0, frac * 2)))
            w.blit(surf, surf.get_rect(center=(ft.x, ft.y)))

        # Bullet time: toni freddi e scuri
        if self.slowmo_blend > 0.01:
            k = self.slowmo_blend
            w.fill((int(255 - 90 * k), int(255 - 60 * k), 255), special_flags=pygame.BLEND_MULT)
            w.fill((0, int(6 * k), int(22 * k)), special_flags=pygame.BLEND_ADD)
        if self.flash > 0.01:
            w.fill(vfx.scale_color(self.flash_color, self.flash * 0.6), special_flags=pygame.BLEND_ADD)

    def _panel(self, w: int, h: int, alpha: int = 140) -> pygame.Surface:
        """Pannello "vetro" semitrasparente con bordo sottile (cache per dimensione)."""
        key = (w, h, alpha)
        surf = self._panel_cache.get(key)
        if surf is None:
            surf = pygame.Surface((w, h), pygame.SRCALPHA)
            pygame.draw.rect(surf, (6, 12, 16, alpha), surf.get_rect(), border_radius=12)
            pygame.draw.rect(surf, (120, 220, 200, 50), surf.get_rect(), 1, border_radius=12)
            self._panel_cache[key] = surf
        return surf

    def _draw_hud(self) -> None:
        """HUD: punti, combo, energia, record, livello ed effetti attivi."""
        s = self.screen
        t = self.time
        s.blit(self._panel(250, 96), (10, 8))
        s.blit(self.fonts["tiny"].render("PUNTI", True, COLOR_GRAY), (24, 14))
        score = vfx.glow_text(self.fonts["mid"], f"{self.score:,}".replace(",", "."), COLOR_WHITE,
                              (40, 160, 120), 6)
        s.blit(score, (24 - 12, 26 - 12))

        if self.combo > 1 and self.combo_timer > 0 and self.state != GameState.GAMEOVER:
            pulse = 1.0 + 0.08 * math.sin(t * 14)
            c = vfx.glow_text(self.fonts["mid"], f"x{self.combo}", COLOR_ORANGE, (200, 80, 0), 6)
            c = pygame.transform.rotozoom(c, 0, pulse)
            s.blit(c, c.get_rect(center=(220, 40)))
            pygame.draw.rect(s, COLOR_ORANGE, (192, 56, 56 * self.combo_timer / COMBO_WINDOW, 3))

        # Barra energia (Scatto/Nova)
        bx, by, bw, bh = 24, 68, 222, 9
        pygame.draw.rect(s, (20, 28, 34), (bx, by, bw, bh), border_radius=4)
        frac = self.energy / ENERGY_MAX
        if frac > 0:
            fill = pygame.Rect(bx, by, max(4, int(bw * frac)), bh)
            pygame.draw.rect(s, vfx.lerp_color(COLOR_CYAN, COLOR_MAGENTA, frac), fill, border_radius=4)
            pygame.draw.rect(s, (255, 255, 255), (bx + 2, by + 1, fill.width - 4, 2), border_radius=1)
        if frac >= 1.0:
            vfx.blit_glow(s, (bx + bw, by + bh / 2), 26, (120, 30, 100), 0.6 + 0.4 * math.sin(t * 8))
            lbl = vfx.glow_text(self.fonts["tiny"], "NOVA PRONTA  [E]", COLOR_MAGENTA, (150, 0, 110), 4)
            s.blit(lbl, (bx - 4, by + 6))
        elif self.dashing:
            s.blit(self.fonts["tiny"].render("SCATTO!", True, COLOR_CYAN), (bx, by + 12))
        else:
            s.blit(self.fonts["tiny"].render("ENERGIA  ·  SHIFT scatto", True, (90, 110, 120)), (bx, by + 12))

        # Pannello destro: record, livello, lunghezza
        s.blit(self._panel(170, 78), (SCREEN_WIDTH - 180, 8))
        best = vfx.glow_text(self.fonts["small"], f"RECORD {self.high_score}", COLOR_GOLD, (140, 90, 0), 4)
        s.blit(best, best.get_rect(topright=(SCREEN_WIDTH - 16, 10)))
        s.blit(self.fonts["tiny"].render(f"LIVELLO {self.level}", True, COLOR_WHITE),
               (SCREEN_WIDTH - 166, 46))
        lng = self.fonts["tiny"].render(f"LUNGHEZZA {len(self.snake.body)}", True, COLOR_GRAY)
        s.blit(lng, (SCREEN_WIDTH - 166, 64))

        # Effetti attivi al centro in alto
        active = list(self.effects.items())
        x0 = SCREEN_WIDTH / 2 - (len(active) - 1) * 22
        for i, (kind, left) in enumerate(active):
            name, color, duration = POWERUP_INFO[kind]
            vfx.draw_icon_badge(s, (x0 + i * 44, 32), kind.value, color, left / duration, t)

        boss = next((r for r in self.rivals if r.boss and r.alive), None)
        if boss is not None:
            frac = vfx.clamp((len(boss.body) - BOSS_MIN_LENGTH + 1) / (BOSS_LENGTH - BOSS_MIN_LENGTH + 1))
            boss_x, boss_y, boss_w = SCREEN_WIDTH / 2 - 160, SCREEN_HEIGHT - 30, 320
            label = vfx.glow_text(self.fonts["tiny"], "VIPERA IMPERIALE", (240, 200, 255), (140, 0, 160), 5)
            s.blit(label, label.get_rect(midbottom=(SCREEN_WIDTH / 2, boss_y + 6)))
            pygame.draw.rect(s, (25, 10, 30), (boss_x, boss_y, boss_w, 10), border_radius=5)
            if frac > 0:
                pygame.draw.rect(s, vfx.lerp_color((255, 40, 40), BOSS_SKIN.bright, frac),
                                 (boss_x, boss_y, max(6, int(boss_w * frac)), 10), border_radius=5)
            pygame.draw.rect(s, (200, 120, 230), (boss_x, boss_y, boss_w, 10), 1, border_radius=5)

        if self.banner_time > 0:
            k = min(1.0, self.banner_time / 0.4)
            scale = 1.0 + 0.06 * math.sin(t * 10)
            ban = vfx.glow_text(self.fonts["big"], self.banner_text, self.banner_color, self.banner_glow, 12)
            ban = pygame.transform.rotozoom(ban, 0, scale)
            ban.set_alpha(int(255 * k))
            s.blit(ban, ban.get_rect(center=(SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 - 60)))

        if self.level_banner > 0:
            k = vfx.clamp(self.level_banner / 0.4) if self.level_banner < 0.4 else 1.0
            ban = vfx.glow_text(self.fonts["big"], f"LIVELLO {self.level}", COLOR_WHITE, (0, 160, 140), 10)
            ban = ban.copy()
            ban.set_alpha(int(255 * k))
            s.blit(ban, ban.get_rect(center=(SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 - 120)))

    def _draw_centered(self, text: str, font: pygame.font.Font, color: Tuple[int, int, int],
                       dy: float, glow: Optional[Tuple[int, int, int]] = None) -> None:
        """Testo centrato orizzontalmente, spostato di dy dal centro verticale."""
        if glow is not None:
            surf = vfx.glow_text(font, text, color, glow, 10)
        else:
            surf = font.render(text, True, color)
        self.screen.blit(surf, surf.get_rect(center=(SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 + dy)))

    def _draw_menu(self) -> None:
        """Schermata iniziale con titolo luminoso e comandi."""
        t = self.time
        self._dim.fill((0, 0, 0, 110))
        self.screen.blit(self._dim, (0, 0))
        bob = math.sin(t * 1.5) * 6
        self._draw_centered("SNAKE", self.fonts["title"], (190, 255, 200), -150 + bob, (20, 200, 90))
        self._draw_centered("A D V A N C E D", self.fonts["mid"], COLOR_CYAN, -88 + bob, (0, 120, 160))
        if int(t * 2) % 2 == 0:
            self._draw_centered("PREMI SPAZIO PER INIZIARE", self.fonts["small"], COLOR_WHITE, -20,
                                (60, 140, 120))
        top = SCREEN_HEIGHT / 2 + 2
        if self.menu_panel == 0:
            self.screen.blit(self._panel(500, 222, 170), (SCREEN_WIDTH / 2 - 250, top))
            lines = [
                ("FRECCE / WASD", "muovi il serpente"),
                ("SHIFT (tieni)", "scatto: sfonda mine e rivali"),
                ("E / Q", "NOVA: onda d'urto a energia piena"),
                ("P / SPAZIO", "pausa"),
                ("T  /  TAB", "cambia tema  /  classifica"),
                ("M  /  F11", "audio  /  schermo intero"),
            ]
            for i, (k, v) in enumerate(lines):
                y = top + 14 + i * 33
                self.screen.blit(self.fonts["small"].render(k, True, COLOR_GOLD), (SCREEN_WIDTH / 2 - 225, y))
                self.screen.blit(self.fonts["tiny"].render(v, True, COLOR_GRAY), (SCREEN_WIDTH / 2 - 30, y + 4))
        else:
            self._draw_leaderboard(SCREEN_WIDTH / 2 - 210, top, 420, 0, 18)
        footer = f"TEMA  {self.theme.name}  [T]        RECORD  {self.high_score}"
        self._draw_centered(footer, self.fonts["small"], COLOR_GOLD, 266, (140, 90, 0))

    def _draw_gameover(self) -> None:
        """
        Overlay di fine partita (appare dopo l'esplosione): inserimento del nome
        se il punteggio entra in classifica, altrimenti statistiche e top 10.
        """
        k = vfx.clamp((self.death_timer - 0.5) / 0.6)
        if k <= 0:
            return
        self._dim.fill((0, 0, 0, int(160 * k)))
        self.screen.blit(self._dim, (0, 0))
        if k < 1:
            return
        cx = SCREEN_WIDTH / 2
        title = "HAI VINTO!" if self.won else "GAME OVER"
        self._draw_centered(title, self.fonts["title"], (255, 200, 200) if not self.won else COLOR_GOLD,
                            -205, (200, 20, 40) if not self.won else (160, 110, 0))

        if self.entering_name:
            self.screen.blit(self._panel(480, 250, 190), (cx - 240, 165))
            self._draw_centered("SEI IN CLASSIFICA!", self.fonts["mid"], COLOR_GOLD, -105, (170, 100, 0))
            self._draw_centered(f"{self.score}", self.fonts["big"], COLOR_WHITE, -50, (40, 160, 120))
            self._draw_centered("Scrivi il tuo nome", self.fonts["tiny"], COLOR_GRAY, -2)
            box = pygame.Rect(0, 0, 330, 48)
            box.center = (int(cx), 345)
            vfx.blit_glow(self.screen, box.center, 150, (0, 50, 60), 0.8)
            pygame.draw.rect(self.screen, (8, 18, 24), box, border_radius=10)
            pygame.draw.rect(self.screen, COLOR_CYAN, box, 2, border_radius=10)
            caret = "_" if int(self.time * 2.5) % 2 == 0 else " "
            txt = self.fonts["mid"].render(self.player_name + caret, True, COLOR_WHITE)
            self.screen.blit(txt, txt.get_rect(center=box.center))
            self._draw_centered("INVIO conferma    ·    ESC salta", self.fonts["tiny"], COLOR_GRAY, 92)
            return

        self.screen.blit(self._panel(330, 262, 170), (40, 170))
        self.screen.blit(self.fonts["tiny"].render("PUNTEGGIO", True, COLOR_GRAY), (62, 186))
        sc = vfx.glow_text(self.fonts["big"], f"{self.score}", COLOR_WHITE, (40, 160, 120), 8)
        self.screen.blit(sc, (62 - 16, 200 - 16))
        stats = [
            ("Lunghezza", f"{len(self.snake.body)}"),
            ("Combo massima", f"x{self.best_combo}"),
            ("Mine distrutte", f"{self.mines_destroyed}"),
            ("Rivali eliminati", f"{self.rivals_killed}"),
            ("Livello", f"{self.level}"),
        ]
        for i, (label, value) in enumerate(stats):
            y = 272 + i * 24
            self.screen.blit(self.fonts["tiny"].render(label, True, COLOR_GRAY), (62, y))
            v = self.fonts["small"].render(value, True, COLOR_WHITE)
            self.screen.blit(v, v.get_rect(topright=(348, y - 3)))
        if self.new_record and int(self.time * 3) % 2 == 0:
            rec = vfx.glow_text(self.fonts["small"], "NUOVO RECORD!", COLOR_GOLD, (180, 110, 0), 6)
            self.screen.blit(rec, rec.get_rect(center=(205, 452)))
        self._draw_leaderboard(400, 170, 360, self.last_rank)
        self._draw_centered("[R] Riavvia    [ESC] Menu", self.fonts["small"], COLOR_WHITE, 205)

    def _draw_leaderboard(self, x: float, y: float, w: int, highlight: int, row_h: int = 21) -> None:
        """Pannello con i 10 migliori punteggi; evidenzia la posizione appena ottenuta."""
        self.screen.blit(self._panel(w, 52 + row_h * 10, 170), (x, y))
        head = vfx.glow_text(self.fonts["small"], "CLASSIFICA", COLOR_GOLD, (150, 90, 0), 6)
        self.screen.blit(head, head.get_rect(midtop=(x + w / 2, y + 2)))
        for i in range(10):
            ry = y + 42 + i * row_h
            entry = self.leaderboard[i] if i < len(self.leaderboard) else None
            if highlight == i + 1:
                pulse = 0.5 + 0.5 * math.sin(self.time * 6)
                hl = pygame.Surface((w - 20, 20), pygame.SRCALPHA)
                hl.fill((60, 230, 255, int(40 + 50 * pulse)))
                self.screen.blit(hl, (x + 10, ry - 2))
            color = COLOR_GOLD if i == 0 else (215, 220, 230) if i < 3 else COLOR_GRAY
            self.screen.blit(self.fonts["tiny"].render(f"{i + 1:>2}.", True, color), (x + 18, ry))
            name = entry["name"] if entry else "- - -"
            self.screen.blit(self.fonts["tiny"].render(name, True, color), (x + 54, ry))
            if entry:
                val = self.fonts["tiny"].render(str(entry["score"]), True, color)
                self.screen.blit(val, val.get_rect(topright=(x + w - 18, ry)))

    def _draw(self) -> None:
        """
        Disegna il frame: mondo su superficie intermedia (per lo screen shake),
        poi HUD e overlay fermi sopra.
        """
        self._draw_world()
        ox = oy = 0
        if self.shake_time > 0 and self.shake_intensity > 0.5:
            i = int(self.shake_intensity)
            ox, oy = random.randint(-i, i), random.randint(-i, i)
        self.screen.fill((0, 0, 0))
        self.screen.blit(self.world, (ox, oy))

        if self.state == GameState.MENU:
            self._draw_menu()
        else:
            # L'HUD sparisce quando compare il riepilogo di fine partita
            if not (self.state == GameState.GAMEOVER and self.death_timer > 0.9):
                self._draw_hud()
            if self.state == GameState.PAUSED:
                self._dim.fill((0, 0, 0, 140))
                self.screen.blit(self._dim, (0, 0))
                self._draw_centered("PAUSA", self.fonts["title"], COLOR_WHITE, -20, (0, 140, 160))
                self._draw_centered("P o SPAZIO per continuare", self.fonts["small"], COLOR_GRAY, 50)
            elif self.state == GameState.GAMEOVER:
                self._draw_gameover()
        pygame.display.flip()

    def run(self) -> None:
        """
        Il ciclo principale del gioco: input -> logica (Delta Time) -> effetti -> rendering.
        """
        while True:
            # tick restituisce i millisecondi trascorsi; il dt viene limitato
            # così un lag (es. finestra trascinata) non fa "saltare" il serpente
            dt = min(MAX_FRAME_DT, self.clock.tick(FPS) / 1000.0)
            if not self._handle_input():
                break
            self.update(dt)
            self.update_visuals(dt)
            self._draw()

        pygame.quit()
        sys.exit()


if __name__ == '__main__':
    Game().run()
