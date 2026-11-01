"""
Test suite for the main Game engine class, ensuring integration of Snake, Food, and ScoreManager.
"""

import pygame
import pytest
from config import Direction, MOVE_INTERVAL, GRID_WIDTH
from game import Game, GameState, START_POSITION
from score_manager import ScoreManager


@pytest.fixture
def game_instance() -> Game:
    return Game()


def start(game: Game) -> None:
    game.handle_key(pygame.K_SPACE)
    assert game.state == GameState.PLAYING


def test_game_initialization(game_instance: Game):
    assert game_instance.state == GameState.MENU
    assert game_instance.score == 0
    assert game_instance.snake.head == START_POSITION
    assert game_instance.high_score == 0


def test_movement_is_time_based(game_instance: Game):
    """Il serpente avanza in base al tempo accumulato, non ai frame."""
    start(game_instance)
    game_instance.food.position = (0, 0)
    x, y = START_POSITION
    for _ in range(5):  # 5 frame brevi: tempo totale < MOVE_INTERVAL
        game_instance.update(MOVE_INTERVAL / 10)
    assert game_instance.snake.head == (x, y)
    game_instance.update(MOVE_INTERVAL)
    assert game_instance.snake.head == (x + 1, y)
    game_instance.update(MOVE_INTERVAL * 3)  # frame lungo: recupera 3 passi
    assert game_instance.snake.head == (x + 4, y)


def test_eating_food_grows_and_scores(game_instance: Game):
    """Mangiare il cibo aumenta punteggio e lunghezza, senza game over."""
    start(game_instance)
    x, y = START_POSITION
    game_instance.food.position = (x + 1, y)
    length = len(game_instance.snake.body)
    game_instance.update(MOVE_INTERVAL)
    assert game_instance.state == GameState.PLAYING
    assert game_instance.score == 10
    assert game_instance.food.position not in game_instance.snake.body
    game_instance.update(MOVE_INTERVAL)
    assert len(game_instance.snake.body) == length + 1


def test_wall_collision_game_over_saves_record(game_instance: Game):
    start(game_instance)
    game_instance.food.position = (0, 0)
    game_instance.score = 30
    game_instance.update(MOVE_INTERVAL * GRID_WIDTH)
    assert game_instance.state == GameState.GAMEOVER
    assert game_instance.high_score == 30
    assert ScoreManager.load_high_score() == 30


def test_input_handling(game_instance: Game):
    start(game_instance)
    game_instance.handle_key(pygame.K_UP)
    assert game_instance.snake.next_direction == Direction.UP

    game_instance.handle_key(pygame.K_p)
    assert game_instance.state == GameState.PAUSED
    head = game_instance.snake.head
    game_instance.update(MOVE_INTERVAL * 5)
    assert game_instance.snake.head == head  # in pausa non si muove

    game_instance.handle_key(pygame.K_p)
    assert game_instance.state == GameState.PLAYING

    game_instance.state = GameState.GAMEOVER
    game_instance.handle_key(pygame.K_ESCAPE)
    assert game_instance.state == GameState.MENU


def test_restart_after_game_over(game_instance: Game):
    start(game_instance)
    game_instance.state = GameState.GAMEOVER
    game_instance.handle_key(pygame.K_r)
    assert game_instance.state == GameState.PLAYING
    assert game_instance.snake.head == START_POSITION
    assert game_instance.score == 0


# --- Meccaniche avanzate -------------------------------------------------

from power_up import PowerUpType, Mine
from config import ENERGY_MAX, MINE_ARM_TIME


def test_shield_wraps_through_wall(game_instance: Game):
    """Lo scudo assorbe l'urto col muro: la testa riappare dal lato opposto."""
    start(game_instance)
    game_instance.food.position = (0, 0)
    game_instance.effects[PowerUpType.SHIELD] = 100.0
    x, y = START_POSITION
    steps_to_wall = GRID_WIDTH - x
    for _ in range(steps_to_wall):
        game_instance.update(MOVE_INTERVAL)
    assert game_instance.state == GameState.PLAYING
    assert game_instance.snake.head == (0, y)
    assert not game_instance.shield_active


def test_ghost_ignores_self_collision(game_instance: Game):
    start(game_instance)
    game_instance.food.position = (0, 0)
    game_instance.effects[PowerUpType.GHOST] = 100.0
    snake = game_instance.snake
    snake.body = [(5, 5), (6, 5), (6, 6), (5, 6), (4, 6)]
    snake.direction = Direction.LEFT
    snake.change_direction(Direction.DOWN)
    game_instance.update(MOVE_INTERVAL)
    assert game_instance.state == GameState.PLAYING


def test_armed_mine_kills_but_dash_smashes_it(game_instance: Game):
    start(game_instance)
    game_instance.food.position = (0, 0)
    x, y = START_POSITION
    mine = Mine((x + 1, y))
    mine.age = MINE_ARM_TIME
    game_instance.mines = [mine]
    game_instance.update(MOVE_INTERVAL)
    assert game_instance.state == GameState.GAMEOVER

    game_instance.handle_key(pygame.K_r)
    mine = Mine((x + 1, y))
    mine.age = MINE_ARM_TIME
    game_instance.mines = [mine]
    game_instance.handle_key(pygame.K_LSHIFT)
    assert game_instance.dashing
    game_instance.update(MOVE_INTERVAL)
    assert game_instance.state == GameState.PLAYING
    assert game_instance.mines == []
    assert game_instance.mines_destroyed == 1


def test_nova_needs_full_energy_and_clears_mines(game_instance: Game):
    start(game_instance)
    x, y = START_POSITION
    game_instance.mines = [Mine((x + 3, y + 3))]
    game_instance.energy = ENERGY_MAX - 1
    game_instance.handle_key(pygame.K_e)
    assert len(game_instance.mines) == 1
    game_instance.energy = ENERGY_MAX
    game_instance.handle_key(pygame.K_e)
    assert game_instance.mines == []
    assert game_instance.energy == 0


def test_magnet_pulls_food_towards_head(game_instance: Game):
    start(game_instance)
    x, y = START_POSITION
    game_instance.effects[PowerUpType.MAGNET] = 100.0
    game_instance.food.position = (x + 6, y + 4)
    game_instance.update(MOVE_INTERVAL)
    fx, fy = game_instance.food.position
    assert abs(fx - (x + 1)) + abs(fy - y) < 9


def test_visual_frame_renders_in_every_state(game_instance: Game):
    """Il rendering non deve sollevare eccezioni in nessuno stato."""
    game_instance.update_visuals(0.016)
    game_instance._draw()
    start(game_instance)
    game_instance.update(MOVE_INTERVAL)
    game_instance.update_visuals(0.016)
    game_instance._draw()
    game_instance.handle_key(pygame.K_p)
    game_instance._draw()
    game_instance.handle_key(pygame.K_p)
    game_instance._game_over(None)
    for _ in range(120):
        game_instance.update_visuals(0.016)
    game_instance._draw()


# --- Rivali, boss, classifica, temi --------------------------------------

from rival import Rival
from config import BOSS_EVERY, FOODS_PER_LEVEL
from themes import THEMES


def test_rival_dies_hitting_player_body(game_instance: Game):
    """Un rivale che sbatte contro il corpo del giocatore esplode in frammenti."""
    start(game_instance)
    game_instance.food.position = (0, 0)
    x, y = START_POSITION
    rival = Rival((x - 1, y - 3))
    rival.snake.body = [(x - 1, y - 1), (x - 1, y - 2), (x - 1, y - 3)]
    rival.snake.prev_body = list(rival.snake.body)
    rival.snake.direction = rival.snake.next_direction = Direction.DOWN
    rival.choose_direction = lambda *args, **kwargs: Direction.DOWN  # type: ignore[method-assign]
    game_instance.rivals = [rival]
    game_instance._rival_step(rival)
    assert not rival.alive
    assert game_instance.state == GameState.PLAYING
    assert game_instance.rivals_killed == 1
    assert game_instance.pellets


def test_player_hitting_rival_body_dies_unless_dashing(game_instance: Game):
    start(game_instance)
    game_instance.food.position = (0, 0)
    x, y = START_POSITION
    rival = Rival((x + 1, y + 2))
    rival.snake.body = [(x + 1, y + 2), (x + 1, y + 1), (x + 1, y), (x + 1, y - 1), (x + 1, y - 2)]
    game_instance.rivals = [rival]
    game_instance.snake.step()
    assert game_instance._player_hits_rivals()
    assert game_instance.state == GameState.GAMEOVER

    game_instance.handle_key(pygame.K_r)
    rival = Rival((x + 1, y + 2))
    rival.snake.body = [(x + 1, y + 2), (x + 1, y + 1), (x + 1, y), (x + 1, y - 1), (x + 1, y - 2)]
    game_instance.rivals = [rival]
    game_instance.dashing = True
    game_instance.snake.step()
    assert not game_instance._player_hits_rivals()
    assert len(rival.body) == 2 or not rival.alive


def test_boss_spawns_on_boss_level_and_nova_hurts_it(game_instance: Game):
    start(game_instance)
    game_instance.food.position = (0, 0)
    game_instance.level = BOSS_EVERY
    game_instance.foods_eaten = (BOSS_EVERY - 1) * FOODS_PER_LEVEL
    game_instance._update_rivals(0.0)
    bosses = [r for r in game_instance.rivals if r.boss]
    assert len(bosses) == 1
    boss = bosses[0]
    for _ in range(25):
        boss.snake.step()
    boss.snake.body = [((START_POSITION[0] + 3 + i) % GRID_WIDTH, START_POSITION[1] + 4) for i in range(20)]
    game_instance.energy = 100.0
    game_instance.handle_key(pygame.K_e)
    assert len(boss.body) < 20


def test_name_entry_saves_to_leaderboard(game_instance: Game):
    start(game_instance)
    game_instance.score = 120
    game_instance._game_over(None)
    assert game_instance.entering_name
    game_instance.player_name = ""
    game_instance.handle_text("ace")
    game_instance.handle_key(pygame.K_r)          # Durante il nome non riavvia
    assert game_instance.state == GameState.GAMEOVER
    game_instance.handle_key(pygame.K_RETURN)
    assert not game_instance.entering_name
    assert game_instance.last_rank == 1
    board = ScoreManager.load_leaderboard()
    assert board[0]["name"] == "ACE" and board[0]["score"] == 120
    assert ScoreManager.load_high_score() == 120   # Il record convive con la classifica


def test_theme_cycle_is_saved(game_instance: Game):
    first = game_instance.theme.name
    game_instance.handle_key(pygame.K_t)
    assert game_instance.theme.name != first
    assert ScoreManager.get_setting("theme") == game_instance.theme.name
    assert len(THEMES) >= 4


# --- Tunnel ----------------------------------------------------------------

from tunnel import Tunnel


def _open_tunnel(a, b) -> Tunnel:
    tun = Tunnel(a, b)
    tun.age = 1.0  # Già completamente aperto
    return tun


def test_tunnel_teleports_player_keeping_direction(game_instance: Game):
    start(game_instance)
    game_instance.food.position = (0, 0)
    x, y = START_POSITION
    exit_cell = (x + 15, y + 8)
    game_instance.tunnels = [_open_tunnel((x + 1, y), exit_cell)]
    game_instance.update(MOVE_INTERVAL)
    assert game_instance.snake.head == exit_cell
    assert game_instance.teleports == 1
    game_instance.update(MOVE_INTERVAL)
    assert game_instance.snake.head == (exit_cell[0] + 1, exit_cell[1])  # stessa direzione
    assert game_instance.state == GameState.PLAYING


def test_blocked_tunnel_exit_does_not_teleport(game_instance: Game):
    start(game_instance)
    game_instance.food.position = (0, 0)
    x, y = START_POSITION
    exit_cell = (x + 15, y + 8)
    mine = Mine(exit_cell)
    game_instance.mines = [mine]
    game_instance.tunnels = [_open_tunnel((x + 1, y), exit_cell)]
    game_instance.update(MOVE_INTERVAL)
    assert game_instance.snake.head == (x + 1, y)
    assert game_instance.state == GameState.PLAYING


def test_closed_tunnel_is_not_traversable(game_instance: Game):
    start(game_instance)
    game_instance.food.position = (0, 0)
    x, y = START_POSITION
    game_instance.tunnels = [Tunnel((x + 1, y), (x + 15, y + 8))]  # appena nato: in apertura
    game_instance.update(MOVE_INTERVAL)
    assert game_instance.snake.head == (x + 1, y)


# --- Armi -------------------------------------------------------------------

def _rival_line(cells) -> Rival:
    rival = Rival(cells[0])
    rival.snake.body = list(cells)
    rival.snake.prev_body = list(cells)
    return rival


def test_venom_shot_kills_rival_head_and_costs_energy(game_instance: Game):
    start(game_instance)
    game_instance.food.position = (0, 0)
    x, y = START_POSITION
    rival = _rival_line([(x + 6, y), (x + 6, y + 1), (x + 6, y + 2)])
    rival.interval = 999.0  # Fermo per il test
    game_instance.rivals = [rival]
    game_instance.energy = 50.0
    game_instance.handle_key(pygame.K_f)
    game_instance.handle_key_up(pygame.K_f)
    assert game_instance.energy == 50.0 - 8.0
    for _ in range(10):
        game_instance._update_projectiles(0.03)
    assert not rival.alive
    assert game_instance.projectiles == []


def test_shot_cuts_rival_body(game_instance: Game):
    start(game_instance)
    x, y = START_POSITION
    rival = _rival_line([(x + 6, y - 3), (x + 6, y - 2), (x + 6, y - 1), (x + 6, y), (x + 6, y + 1)])
    game_instance.rivals = [rival]
    game_instance.energy = 50.0
    game_instance._fire()
    for _ in range(10):
        game_instance._update_projectiles(0.03)
    assert rival.alive and len(rival.body) == 3


def test_shot_without_energy_is_denied(game_instance: Game):
    start(game_instance)
    game_instance.energy = 2.0
    game_instance._fire()
    assert game_instance.projectiles == []


def test_laser_pierces_everything_for_free(game_instance: Game):
    start(game_instance)
    x, y = START_POSITION
    r1 = _rival_line([(x + 5, y), (x + 5, y + 1), (x + 5, y + 2)])
    r2 = _rival_line([(x + 12, y), (x + 12, y - 1), (x + 12, y - 2)])
    game_instance.rivals = [r1, r2]
    game_instance.mines = [Mine((x + 9, y))]
    game_instance.effects[PowerUpType.LASER] = 5.0
    game_instance.energy = 0.0
    game_instance._fire()
    assert not r1.alive and not r2.alive
    assert game_instance.mines == []
    assert game_instance.lasers


# --- Salto --------------------------------------------------------------------

from config import JUMP_STEPS


def test_jump_clears_armed_mine_and_lands(game_instance: Game):
    start(game_instance)
    game_instance.food.position = (0, 0)
    x, y = START_POSITION
    mine = Mine((x + 2, y))
    mine.age = 5.0
    game_instance.mines = [mine]
    game_instance.handle_key(pygame.K_SPACE)
    assert game_instance.state == GameState.PLAYING   # SPAZIO non mette più in pausa
    for _ in range(JUMP_STEPS + 1):
        game_instance.update(MOVE_INTERVAL)
    assert game_instance.state == GameState.PLAYING
    assert game_instance.snake.head == (x + JUMP_STEPS + 1, y)
    assert game_instance.mines == [mine]               # Scavalcata, non distrutta


def test_landing_on_mine_still_kills(game_instance: Game):
    start(game_instance)
    game_instance.food.position = (0, 0)
    x, y = START_POSITION
    mine = Mine((x + JUMP_STEPS + 1, y))
    mine.age = 5.0
    game_instance.mines = [mine]
    game_instance.handle_key(pygame.K_SPACE)
    for _ in range(JUMP_STEPS + 1):
        game_instance.update(MOVE_INTERVAL)
    assert game_instance.state == GameState.GAMEOVER


def test_jump_over_own_body(game_instance: Game):
    start(game_instance)
    game_instance.food.position = (0, 0)
    snake = game_instance.snake
    # Serpente che punta verso il proprio corpo: senza salto sarebbe morte certa
    snake.body = [(10, 10), (11, 10), (12, 10), (12, 11), (11, 11), (10, 11), (9, 11), (8, 11), (7, 11)]
    snake.prev_body = list(snake.body)
    snake.direction = snake.next_direction = Direction.LEFT
    snake.change_direction(Direction.DOWN)
    game_instance.handle_key(pygame.K_SPACE)
    for _ in range(JUMP_STEPS + 1):
        game_instance.update(MOVE_INTERVAL)
    assert game_instance.state == GameState.PLAYING
    assert snake.head == (10, 10 + JUMP_STEPS + 1)


def test_jump_has_cooldown(game_instance: Game):
    start(game_instance)
    game_instance.handle_key(pygame.K_SPACE)
    first = game_instance.jump_start
    game_instance.update(MOVE_INTERVAL * 5)
    game_instance.handle_key(pygame.K_SPACE)
    assert game_instance.jump_start == first
    assert game_instance.jumps == 1
