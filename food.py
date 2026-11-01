"""
Modulo che implementa la classe Food (Cibo), un'entità che viene consumata dal serpente.
Gestisce la generazione della posizione del cibo tra le celle libere.
Esistono due tipi: il frutto normale e il frutto d'oro (bonus a tempo).
"""

import random
from typing import Iterable, List, Optional, Tuple

from config import (
    GRID_WIDTH, GRID_HEIGHT, SCORE_FOOD, SCORE_BONUS, ENERGY_PER_FOOD,
    ENERGY_PER_BONUS, BONUS_LIFETIME, BONUS_GROWTH, SCORE_PELLET, PELLET_LIFETIME,
)

# Definizione del tipo per le coordinate sulla griglia
GridPosition = Tuple[int, int]


class FoodKind:
    """Tipi di cibo disponibili."""
    NORMAL: str = "NORMAL"
    GOLDEN: str = "GOLDEN"
    PELLET: str = "PELLET"   # Frammento lasciato da un rivale eliminato


class Food:
    """
    Rappresenta un singolo pezzo di cibo che il serpente può consumare.
    Il tipo determina punti, crescita, energia e durata a terra.
    """

    def __init__(self, position: Optional[GridPosition], kind: str = FoodKind.NORMAL):
        """
        Inizializza il cibo con una posizione specifica sulla griglia.

        :param position: La posizione (x, y) del cibo sulla griglia.
        :param kind: FoodKind.NORMAL oppure FoodKind.GOLDEN.
        """
        self.position: Optional[GridPosition] = position
        self.kind: str = kind
        golden = kind == FoodKind.GOLDEN
        pellet = kind == FoodKind.PELLET
        self.value: int = SCORE_BONUS if golden else SCORE_PELLET if pellet else SCORE_FOOD
        self.growth: int = BONUS_GROWTH if golden else 1
        self.energy: float = ENERGY_PER_BONUS if golden else 4.0 if pellet else ENERGY_PER_FOOD
        # Il cibo normale resta a terra per sempre, quello d'oro e i frammenti scadono
        self.lifetime: Optional[float] = BONUS_LIFETIME if golden else PELLET_LIFETIME if pellet else None
        self.age: float = 0.0
        # Fase casuale: ogni frutto oscilla fuori sincrono rispetto agli altri
        self.phase: float = random.uniform(0.0, 6.28)

    def generate_new(self, snake_body: List[GridPosition],
                     blocked: Iterable[GridPosition] = ()) -> bool:
        """
        Sceglie una nuova posizione casuale tra le celle libere.
        Si estrae dalla lista delle celle libere (invece di tentare a caso in
        un ciclo infinito) così la funzione termina sempre, anche a griglia quasi piena.

        :param snake_body: La lista di coordinate del corpo del serpente.
        :param blocked: Altre celle occupate (mine, power-up, altro cibo).
        :return: False se non esiste alcuna cella libera (griglia piena = vittoria).
        """
        occupied = set(snake_body)
        occupied.update(blocked)
        free_cells = [
            (x, y)
            for x in range(GRID_WIDTH)
            for y in range(GRID_HEIGHT)
            if (x, y) not in occupied
        ]
        self.age = 0.0
        if not free_cells:
            self.position = None
            return False
        self.position = random.choice(free_cells)
        return True

    def update(self, dt: float) -> bool:
        """
        Fa invecchiare il cibo.

        :return: False se il cibo è scaduto e va rimosso.
        """
        self.age += dt
        return self.lifetime is None or self.age < self.lifetime

    @property
    def time_left(self) -> Optional[float]:
        """Secondi rimanenti prima della scadenza (None se non scade)."""
        if self.lifetime is None:
            return None
        return max(0.0, self.lifetime - self.age)

    def __str__(self) -> str:
        return f"Food({self.kind}) at {self.position}"
