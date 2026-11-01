"""
Modulo delle armi del serpente (Model).
Il proiettile si muove in coordinate continue (unità = celle) con il Delta Time,
così può viaggiare anche in diagonale (sparo a ventaglio) restando
indipendente dal frame rate. La collisione si risolve sulla cella attraversata.
"""

import math
from typing import Optional, Tuple

from config import SHOT_LIFETIME

GridPosition = Tuple[int, int]


class Projectile:
    """Sputo di veleno: vola dritto finché colpisce qualcosa o si esaurisce."""

    def __init__(self, x: float, y: float, vx: float, vy: float):
        """
        :param x: Posizione orizzontale in celle (es. 10.5 = centro della cella 10).
        :param y: Posizione verticale in celle.
        :param vx: Velocità orizzontale in celle al secondo.
        :param vy: Velocità verticale in celle al secondo.
        """
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.life: float = SHOT_LIFETIME
        self.alive: bool = True
        self.last_cell: Optional[GridPosition] = self.cell
        self.warped: bool = False

    @property
    def cell(self) -> GridPosition:
        """Cella della griglia in cui si trova il proiettile."""
        return (math.floor(self.x), math.floor(self.y))

    def sub_steps(self, dt: float) -> int:
        """
        Numero di sotto-passi per il frame: al massimo mezza cella per passo,
        così un proiettile veloce non "salta" un bersaglio sottile.
        """
        dist = math.hypot(self.vx, self.vy) * dt
        return max(1, math.ceil(dist / 0.5))
