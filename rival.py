"""
Modulo dei serpenti rivali e del boss (Model + IA).
Un Rival riusa la classe Snake per corpo, buffer di direzione e movimento,
ma ha un proprio accumulatore di Delta Time e una propria velocità:
così i nemici restano indipendenti dal frame rate esattamente come il giocatore.

IA:
- il rivale normale insegue il cibo più vicino evitando ostacoli e vicoli ciechi;
- il boss caccia il giocatore puntando alla cella davanti alla sua testa,
  attraversa i muri (portale) e il proprio corpo.
"""

import random
from typing import Iterable, List, Optional, Set, Tuple

from config import (
    GRID_WIDTH, GRID_HEIGHT, DIRECTION_VECTORS, OPPOSITE,
    RIVAL_MOVE_INTERVAL, BOSS_MOVE_INTERVAL, BOSS_LENGTH,
)
from snake import Snake

GridPosition = Tuple[int, int]


class Rival:
    """Serpente nemico controllato dal computer."""

    def __init__(self, position: GridPosition, boss: bool = False, slot: int = 0):
        """
        :param position: Cella della testa allo spawn.
        :param boss: True per il serpente boss.
        :param slot: Indice usato dalla View per associare un renderer.
        """
        self.snake: Snake = Snake(position)
        self.boss: bool = boss
        self.slot: int = slot
        self.interval: float = BOSS_MOVE_INTERVAL if boss else RIVAL_MOVE_INTERVAL
        self.acc: float = 0.0
        self.age: float = 0.0
        self.bulges: List[float] = []
        self.alive: bool = True
        self.spawn_pos: GridPosition = position
        if boss:
            # Il boss "emerge" dal portale: cresce fino alla lunghezza piena
            self.snake.grow(BOSS_LENGTH - len(self.snake.body))

    @property
    def body(self) -> List[GridPosition]:
        """Scorciatoia per il corpo del serpente."""
        return self.snake.body

    @property
    def head(self) -> GridPosition:
        """Scorciatoia per la testa."""
        return self.snake.head

    def cut_at(self, index: int) -> List[GridPosition]:
        """
        Tronca il corpo a partire da index (testa = 0).

        :return: Le celle rimosse (diventeranno frammenti di cibo).
        """
        index = max(1, index)
        removed = self.snake.body[index:]
        self.snake.body = self.snake.body[:index]
        self.snake.prev_body = self.snake.prev_body[:index]
        self.snake._pending_growth = 0
        return removed

    def choose_direction(self, targets: Iterable[GridPosition], blocked: Set[GridPosition],
                         rng: Optional[random.Random] = None) -> str:
        """
        Sceglie la direzione verso il bersaglio più vicino, scartando le mosse
        letali e penalizzando quelle che portano in uno spazio troppo piccolo.

        :param targets: Celle obiettivo (cibo o, per il boss, la preda).
        :param blocked: Celle da evitare.
        :return: La direzione scelta (quella attuale se nessuna è sicura).
        """
        rnd = rng or random
        snake = self.snake
        targets = list(targets)
        need = min(len(snake.body) + 4, 40)
        best, best_score = snake.direction, -1e9
        for d, (dx, dy) in DIRECTION_VECTORS.items():
            if d == OPPOSITE[snake.direction]:
                continue
            nx, ny = snake.head[0] + dx, snake.head[1] + dy
            if self.boss:
                nx, ny = nx % GRID_WIDTH, ny % GRID_HEIGHT
            elif not (0 <= nx < GRID_WIDTH and 0 <= ny < GRID_HEIGHT):
                continue
            if (nx, ny) in blocked:
                continue
            if targets:
                dist = min(abs(nx - tx) + abs(ny - ty) for tx, ty in targets)
            else:
                dist = 0
            score = -dist + rnd.uniform(0, 0.8)
            space = reachable((nx, ny), blocked, need)
            if space < need:
                score -= 1000 - space
            if score > best_score:
                best, best_score = d, score
        return best


def reachable(start: GridPosition, blocked: Set[GridPosition], limit: int) -> int:
    """Flood fill limitato: conta le celle raggiungibili da start (fino a limit)."""
    seen = {start}
    stack = [start]
    while stack and len(seen) < limit:
        x, y = stack.pop()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            c = (x + dx, y + dy)
            if (c not in seen and c not in blocked
                    and 0 <= c[0] < GRID_WIDTH and 0 <= c[1] < GRID_HEIGHT):
                seen.add(c)
                stack.append(c)
    return len(seen)
