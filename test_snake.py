"""
Test suite for the Snake entity class, ensuring core logic adheres to project constraints.
"""

import pytest
from config import Direction, GRID_WIDTH, GRID_HEIGHT
from snake import Snake, INITIAL_LENGTH


@pytest.fixture
def snake_instance() -> Snake:
    return Snake((5, 5))


def test_snake_initialization(snake_instance: Snake):
    """Verifica che il serpente venga inizializzato correttamente."""
    assert snake_instance.body == [(5, 5), (4, 5), (3, 5)]
    assert snake_instance.direction == Direction.RIGHT
    assert snake_instance.next_direction == Direction.RIGHT
    assert snake_instance.is_alive


def test_snake_step_moves_and_keeps_length(snake_instance: Snake):
    """Un passo sposta la testa di una cella e mantiene la lunghezza."""
    snake_instance.step()
    assert snake_instance.body == [(6, 5), (5, 5), (4, 5)]


def test_snake_grow(snake_instance: Snake):
    """Dopo grow il passo successivo non rimuove la coda."""
    snake_instance.grow()
    snake_instance.step()
    assert len(snake_instance.body) == INITIAL_LENGTH + 1
    snake_instance.step()
    assert len(snake_instance.body) == INITIAL_LENGTH + 1


@pytest.mark.parametrize("head, direction", [
    ((GRID_WIDTH - 1, 5), Direction.RIGHT),
    ((5, 0), Direction.UP),
])
def test_snake_collision_boundary(snake_instance: Snake, head, direction):
    """Uscire dalla griglia uccide il serpente."""
    snake_instance.body = [head]
    snake_instance.direction = snake_instance.next_direction = direction
    snake_instance.step()
    assert snake_instance.check_collision()
    assert not snake_instance.is_alive


def test_snake_bottom_edge_is_inside(snake_instance: Snake):
    """L'ultima riga della griglia è giocabile (la griglia non è quadrata)."""
    snake_instance.body = [(5, GRID_HEIGHT - 1)]
    assert not snake_instance.check_collision()


def test_snake_collision_self(snake_instance: Snake):
    """La testa che entra nel corpo uccide il serpente."""
    # Serpente arrotolato che va a sinistra: girando giù la testa entra in (5, 6)
    snake_instance.body = [(5, 5), (6, 5), (6, 6), (5, 6), (4, 6)]
    snake_instance.direction = Direction.LEFT
    assert snake_instance.change_direction(Direction.DOWN)
    snake_instance.step()
    assert snake_instance.check_collision()
    assert not snake_instance.is_alive


def test_snake_reversal_blocked(snake_instance: Snake):
    """Un'inversione di 180° viene rifiutata."""
    assert not snake_instance.change_direction(Direction.LEFT)
    assert snake_instance.next_direction == Direction.RIGHT


def test_snake_buffer_prevents_reversal_within_one_tick(snake_instance: Snake):
    """
    DESTRA -> SU -> SINISTRA nello stesso tick non deve produrre un'inversione:
    il confronto avviene con la direzione dell'ultimo passo, non col buffer.
    """
    assert snake_instance.change_direction(Direction.UP)
    assert not snake_instance.change_direction(Direction.LEFT)
    snake_instance.step()
    assert snake_instance.head == (5, 4)
    assert not snake_instance.check_collision()
