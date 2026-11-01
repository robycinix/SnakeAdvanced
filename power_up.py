"""
Modulo che gestisce i Power-up e le Mine del gioco Snake Advanced (Model).
I Power-up danno vantaggi temporanei; le mine sono pericoli che compaiono col tempo.
Il disegno è delegato a visuals.py.
"""

from enum import Enum
from typing import Dict, Tuple

from config import (
    POWERUP_LIFETIME, MINE_ARM_TIME, MINE_LIFETIME,
    COLOR_ORANGE, COLOR_CYAN,
)

# Definizione del tipo per le coordinate sulla griglia
GridPosition = Tuple[int, int]


class PowerUpType(Enum):
    """Tipi di power-up raccoglibili."""
    SPEED_BOOST = "SPEED_BOOST"   # Aumenta la velocità temporaneamente
    SHIELD = "SHIELD"             # Assorbe un impatto (muro, corpo o mina)
    SLOW_MOTION = "SLOW_MOTION"   # Rallenta il gioco temporaneamente
    GHOST = "GHOST"               # Permette di attraversare il proprio corpo
    MAGNET = "MAGNET"             # Attira il cibo verso la testa
    TRIPLE_SHOT = "TRIPLE_SHOT"   # Il veleno parte a ventaglio (3 colpi)
    LASER = "LASER"               # Raggio perforante istantaneo, senza costo


# Nome visualizzato, colore e durata (secondi) di ogni power-up
POWERUP_INFO: Dict[PowerUpType, Tuple[str, Tuple[int, int, int], float]] = {
    PowerUpType.SPEED_BOOST: ("TURBO", COLOR_ORANGE, 4.0),
    PowerUpType.SHIELD: ("SCUDO", COLOR_CYAN, 10.0),
    PowerUpType.SLOW_MOTION: ("BULLET TIME", (150, 110, 255), 5.0),
    PowerUpType.GHOST: ("FANTASMA", (220, 220, 255), 6.0),
    PowerUpType.MAGNET: ("MAGNETE", (255, 80, 90), 8.0),
    PowerUpType.TRIPLE_SHOT: ("TRIPLO VELENO", (130, 255, 90), 10.0),
    PowerUpType.LASER: ("LASER", (255, 50, 160), 7.0),
}


class PowerUp:
    """
    Rappresenta un Power-up a terra nel mondo di gioco.
    Svanisce dopo POWERUP_LIFETIME secondi se non viene raccolto,
    così il giocatore è spinto a rischiare per prenderlo.
    """

    def __init__(self, position: GridPosition, p_type: PowerUpType):
        """
        Inizializza il Power-up.

        :param position: La posizione (x, y) sulla griglia.
        :param p_type: Il tipo di Power-up.
        """
        self.position: GridPosition = position
        self.type: PowerUpType = p_type
        self.active: bool = True
        self.duration: float = POWERUP_INFO[p_type][2]
        self.lifetime: float = POWERUP_LIFETIME
        self.age: float = 0.0

    def update(self, dt: float) -> bool:
        """
        Fa scorrere il tempo di vita a terra.

        :return: False se il power-up è scaduto.
        """
        self.age += dt
        self.lifetime -= dt
        if self.lifetime <= 0:
            self.active = False
        return self.active


class Mine:
    """
    Mina a terra: letale al contatto una volta armata.
    Appena comparsa resta disarmata per MINE_ARM_TIME secondi, così il
    giocatore ha sempre il tempo di vederla prima che diventi pericolosa.
    """

    def __init__(self, position: GridPosition):
        """
        :param position: La posizione (x, y) sulla griglia.
        """
        self.position: GridPosition = position
        self.age: float = 0.0
        self.lifetime: float = MINE_LIFETIME

    @property
    def armed(self) -> bool:
        """True quando la mina è letale."""
        return self.age >= MINE_ARM_TIME

    def update(self, dt: float) -> bool:
        """
        Fa invecchiare la mina.

        :return: False quando la mina si è esaurita e va rimossa.
        """
        self.age += dt
        return self.age < self.lifetime
