"""
Modulo dei tunnel di teletrasporto (Model).
Un tunnel è una coppia di imboccature collegate: entrando in una con la testa
si riemerge dall'altra mantenendo la direzione. I tunnel compaiono a caso,
restano aperti per un tempo limitato e poi collassano.
Funzionano per il giocatore e per i rivali.
"""

from typing import Optional, Tuple

from config import TUNNEL_LIFETIME

GridPosition = Tuple[int, int]

OPEN_TIME: float = 0.7    # Secondi di apertura (non ancora attraversabile)
CLOSE_TIME: float = 1.0   # Secondi di chiusura finale (non più attraversabile)


class Tunnel:
    """Coppia di portali collegati."""

    def __init__(self, a: GridPosition, b: GridPosition, color_index: int = 0):
        """
        :param a: Prima imboccatura.
        :param b: Seconda imboccatura.
        :param color_index: Indice del colore (coppie diverse = colori diversi).
        """
        self.a: GridPosition = a
        self.b: GridPosition = b
        self.color_index: int = color_index
        self.age: float = 0.0
        self.lifetime: float = TUNNEL_LIFETIME

    def update(self, dt: float) -> bool:
        """
        Fa scorrere il tempo.

        :return: False quando il tunnel è collassato e va rimosso.
        """
        self.age += dt
        return self.age < self.lifetime

    @property
    def openness(self) -> float:
        """Apertura 0..1: cresce allo spawn e cala durante il collasso (per la View)."""
        opening = min(1.0, self.age / OPEN_TIME)
        closing = min(1.0, max(0.0, (self.lifetime - self.age) / CLOSE_TIME))
        return min(opening, closing)

    @property
    def active(self) -> bool:
        """True se il tunnel è attraversabile (completamente aperto)."""
        return OPEN_TIME <= self.age <= self.lifetime - CLOSE_TIME

    def other_end(self, pos: GridPosition) -> Optional[GridPosition]:
        """
        :return: L'imboccatura opposta se pos è un'imboccatura, altrimenti None.
        """
        if pos == self.a:
            return self.b
        if pos == self.b:
            return self.a
        return None
