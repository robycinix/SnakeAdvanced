# config.py

"""
Definizione delle costanti globali e delle configurazioni del gioco Snake Advanced.
Tutti i numeri "magici" del gioco vivono qui, così Model, View e Controller
restano coerenti tra loro e il bilanciamento si regola da un unico punto.
"""

import os

# --- Configurazione della Finestra (View/Controller) ---
SCREEN_WIDTH: int = 800  # Larghezza della finestra in pixel
SCREEN_HEIGHT: int = 600 # Altezza della finestra in pixel
CELL_SIZE: int = 20      # Dimensione di una singola cella della griglia in pixel
FPS: int = 120           # Frame rate target: alto perché il rendering è interpolato

# Dimensioni della griglia in celle, derivate dalla finestra
GRID_WIDTH: int = SCREEN_WIDTH // CELL_SIZE   # 40 colonne
GRID_HEIGHT: int = SCREEN_HEIGHT // CELL_SIZE # 30 righe

# --- Velocità (Delta Time) ---
# Secondi tra un passo del serpente e il successivo: il movimento logico è a
# passi discreti sulla griglia, scanditi dal tempo accumulato e non dai frame.
MOVE_INTERVAL: float = 0.10
MIN_MOVE_INTERVAL: float = 0.05   # Velocità massima raggiungibile
SPEEDUP_PER_FOOD: float = 0.002   # Accelerazione per ogni cibo mangiato
FOODS_PER_LEVEL: int = 5          # Cibi necessari per salire di livello
MAX_FRAME_DT: float = 0.1         # Limite al dt di un frame (evita salti dopo un lag)

# --- Punteggi e Combo ---
SCORE_FOOD: int = 10
SCORE_BONUS: int = 50
SCORE_MINE: int = 25
COMBO_WINDOW: float = 3.0   # Secondi entro cui mangiare di nuovo per la combo
MAX_COMBO: int = 5          # Moltiplicatore massimo

# --- Energia, Scatto e Nova (azioni speciali del giocatore) ---
ENERGY_MAX: float = 100.0
ENERGY_START: float = 40.0
ENERGY_PER_FOOD: float = 15.0
ENERGY_PER_BONUS: float = 40.0
ENERGY_REGEN: float = 2.0        # Energia rigenerata al secondo
DASH_DRAIN: float = 45.0         # Energia consumata al secondo durante lo scatto
DASH_MIN_ENERGY: float = 10.0    # Energia minima per avviare lo scatto
DASH_FACTOR: float = 0.5         # Moltiplicatore dell'intervallo durante lo scatto
NOVA_RADIUS: float = 12.0        # Raggio (in celle) dell'onda d'urto Nova

# --- Power-up ---
SPEED_BOOST_FACTOR: float = 0.6
SLOW_MOTION_FACTOR: float = 1.8
POWERUP_LIFETIME: float = 10.0   # Secondi prima che un power-up a terra svanisca
MAX_POWERUPS: int = 2
POWERUP_SPAWN_CHANCE: float = 0.3
SHIELD_GRACE: float = 0.6        # Invulnerabilità al corpo dopo l'uso dello scudo
MAGNET_RANGE: int = 9            # Raggio (in celle) del magnete

# --- Mine e Cibo d'oro ---
MINE_FIRST_SPAWN: float = 15.0
MINE_SPAWN_INTERVAL: float = 9.0
MINE_ARM_TIME: float = 1.5       # Una mina appena comparsa non è ancora letale
MINE_LIFETIME: float = 30.0
MINE_MAX_BASE: int = 3
BONUS_SPAWN_INTERVAL: float = 18.0
BONUS_LIFETIME: float = 7.0
BONUS_GROWTH: int = 3

# --- Rivali e Boss ---
RIVAL_START_LEVEL: int = 3         # Livello da cui compaiono i serpenti rivali
RIVAL_SPAWN_INTERVAL: float = 10.0
RIVAL_MOVE_INTERVAL: float = 0.14  # I rivali sono un po' più lenti del giocatore
BOSS_MOVE_INTERVAL: float = 0.12
BOSS_EVERY: int = 5                # Un boss ogni 5 livelli
BOSS_LENGTH: int = 24
BOSS_MIN_LENGTH: int = 4           # Sotto questa lunghezza il boss è sconfitto
SCORE_RIVAL: int = 60
SCORE_BOSS: int = 500
SCORE_PELLET: int = 5
PELLET_LIFETIME: float = 10.0
MAX_PELLETS: int = 80

# --- Palette Colori (View) ---
COLOR_BLACK: tuple[int, int, int] = (0, 0, 0)
COLOR_NEON_GREEN: tuple[int, int, int] = (60, 255, 120)
COLOR_DARK_GREEN: tuple[int, int, int] = (20, 170, 20)
COLOR_RED: tuple[int, int, int] = (255, 60, 70)
COLOR_WHITE: tuple[int, int, int] = (255, 255, 255)
COLOR_GRAY: tuple[int, int, int] = (140, 150, 160)
COLOR_GRID: tuple[int, int, int] = (18, 18, 18)
COLOR_GOLD: tuple[int, int, int] = (255, 200, 60)
COLOR_CYAN: tuple[int, int, int] = (60, 230, 255)
COLOR_MAGENTA: tuple[int, int, int] = (255, 70, 200)
COLOR_ORANGE: tuple[int, int, int] = (255, 140, 40)

# Sfondo: terreno notturno scuro con leggera tinta verde-acqua
COLOR_BG_TOP: tuple[int, int, int] = (12, 20, 24)
COLOR_BG_BOTTOM: tuple[int, int, int] = (5, 9, 12)

# Pelle del serpente (pitone smeraldo): da toni scuri a toni chiari
COLOR_SKIN_DARK: tuple[int, int, int] = (14, 70, 40)
COLOR_SKIN_BRIGHT: tuple[int, int, int] = (70, 200, 95)
COLOR_SKIN_MARK: tuple[int, int, int] = (16, 44, 26)
COLOR_SKIN_MARK_EDGE: tuple[int, int, int] = (160, 200, 80)
COLOR_SKIN_SPOT: tuple[int, int, int] = (215, 235, 150)


# --- Configurazione del Gioco (Game State) ---
class Direction:
    """Direzioni possibili del serpente (stringhe per leggibilità nei test)."""
    UP: str = "UP"
    DOWN: str = "DOWN"
    LEFT: str = "LEFT"
    RIGHT: str = "RIGHT"


# Vettori di spostamento e direzioni opposte, usati dal Snake
DIRECTION_VECTORS: dict[str, tuple[int, int]] = {
    Direction.UP: (0, -1),
    Direction.DOWN: (0, 1),
    Direction.LEFT: (-1, 0),
    Direction.RIGHT: (1, 0),
}
OPPOSITE: dict[str, str] = {
    Direction.UP: Direction.DOWN,
    Direction.DOWN: Direction.UP,
    Direction.LEFT: Direction.RIGHT,
    Direction.RIGHT: Direction.LEFT,
}

# File del record accanto al codice: così non dipende dalla cartella di avvio
HIGH_SCORE_FILE: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "snake_highscore.json")
