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
