"""
Modulo che implementa la classe Snake, l'entità principale del gioco (Model).
Gestisce lo stato del serpente, il suo movimento a passi sulla griglia e le collisioni.
Il disegno è delegato a visuals.SnakeRenderer: il Model non conosce la grafica.
"""

from typing import List, Optional, Tuple

from config import GRID_WIDTH, GRID_HEIGHT, Direction, DIRECTION_VECTORS, OPPOSITE

# Definizione del tipo per le coordinate sulla griglia
GridPosition = Tuple[int, int]

INITIAL_LENGTH: int = 3

# Tipi di collisione restituiti da collision_kind()
COLLISION_WALL: str = "WALL"
COLLISION_SELF: str = "SELF"


class Snake:
    """
    Rappresenta il serpente nel gioco Snake Advanced.
    Gestisce la sequenza di segmenti del corpo, la direzione attuale e il buffer di input.
    Conserva anche il corpo del passo precedente (prev_body) perché la View
    possa interpolare in modo fluido tra due passi discreti.
    """

    def __init__(self, initial_position: GridPosition):
        """
        Inizializza il serpente con la testa nella posizione indicata.

        :param initial_position: La posizione (x, y) di testa del serpente sulla griglia.
        """
        self.body: List[GridPosition] = []
        self.prev_body: List[GridPosition] = []
        self.direction: str = Direction.RIGHT
        self.next_direction: str = Direction.RIGHT
        self.is_alive: bool = True
        self.steps: int = 0
        self._pending_growth: int = 0
        self.reset(initial_position)

    def reset(self, initial_position: GridPosition) -> None:
        """
        Resetta il serpente a uno stato iniziale giocabile: corpo orizzontale
        lungo INITIAL_LENGTH, rivolto verso destra.
        """
        x, y = initial_position
        self.body = [(x - i, y) for i in range(INITIAL_LENGTH)]
        self.prev_body = list(self.body)
        self.direction = Direction.RIGHT
        self.next_direction = Direction.RIGHT
        self.is_alive = True
        self.steps = 0
        self._pending_growth = 0

    @property
    def head(self) -> GridPosition:
        """Restituisce la posizione della testa."""
        return self.body[0]

    def change_direction(self, new_dir: str) -> bool:
        """
        Memorizza la direzione richiesta nel buffer next_direction.

        Il confronto avviene con self.direction (la direzione dell'ultimo passo
        effettivamente compiuto), non con il buffer: così due tasti premuti
        nello stesso tick (es. DESTRA -> SU -> SINISTRA) non possono produrre
        un'inversione di 180° che farebbe entrare la testa nel collo.

        :param new_dir: La nuova direzione (es. Direction.UP).
        :return: True se la richiesta è stata accettata, False se era un'inversione.
        """
        if new_dir not in DIRECTION_VECTORS:
            return False
        if new_dir == OPPOSITE[self.direction]:
            return False
        self.next_direction = new_dir
        return True

    def step(self) -> None:
        """
        Avanza il serpente di una cella nella direzione bufferizzata.
        Viene chiamato da Game solo quando il tempo accumulato (Delta Time)
        supera l'intervallo di movimento, garantendo l'indipendenza dal frame rate.
        """
        if not self.is_alive:
            return

        self.prev_body = list(self.body)
        self.direction = self.next_direction
        dx, dy = DIRECTION_VECTORS[self.direction]
        head_x, head_y = self.head
        self.body.insert(0, (head_x + dx, head_y + dy))
        self.steps += 1

        # La coda resta al suo posto solo se c'è crescita in sospeso
        if self._pending_growth > 0:
            self._pending_growth -= 1
        else:
            self.body.pop()

    def grow(self, amount: int = 1) -> None:
        """
        Programma la crescita del serpente: nei prossimi `amount` passi la coda
        non viene rimossa. Viene chiamata da Game dopo che il cibo è stato mangiato.
        """
        self._pending_growth += amount

    def collision_kind(self) -> Optional[str]:
        """
        Indica che tipo di collisione ha la testa, SENZA uccidere il serpente.
        Serve a Game per decidere se uno scudo o il power-up Fantasma la annullano.

        :return: COLLISION_WALL, COLLISION_SELF oppure None.
        """
        head_x, head_y = self.head
        if not (0 <= head_x < GRID_WIDTH and 0 <= head_y < GRID_HEIGHT):
            return COLLISION_WALL
        if self.head in self.body[1:]:
            return COLLISION_SELF
        return None

    def check_collision(self) -> bool:
        """
        Verifica se la testa ha colpito i bordi o il proprio corpo e, in tal caso,
        segna il serpente come morto. La collisione con il cibo è gestita da Game.

        :return: True se il serpente è morto, False altrimenti.
        """
        if self.collision_kind() is not None:
            self.is_alive = False
            return True
        return False

    def wrap_head(self) -> None:
        """
        Riporta la testa dentro la griglia dal lato opposto (effetto portale).
        Usato quando lo scudo assorbe l'impatto con un muro.
        """
        head_x, head_y = self.head
        self.body[0] = (head_x % GRID_WIDTH, head_y % GRID_HEIGHT)

    def revert_step(self) -> None:
        """
        Annulla l'ultimo passo a livello visivo: dopo uno schianto contro il muro
        la testa resta dentro l'arena invece di essere disegnata fuori schermo.
        """
        self.body = list(self.prev_body)
