"""
Temi grafici del gioco (View).
Un tema definisce l'ambiente (sfondo, macchie di luce, bordo, lucciole) e la
pelle del serpente del giocatore. Le pelli dei rivali e del boss sono fisse,
così si riconoscono sempre a colpo d'occhio indipendentemente dal tema.
"""

from dataclasses import dataclass
from typing import List, Tuple

Color = Tuple[int, int, int]


@dataclass(frozen=True)
class SkinPalette:
    """Colori della pelle di un serpente."""
    dark: Color      # Tono più scuro (coda, bande)
    bright: Color    # Tono più chiaro (dorso illuminato)
    mark: Color      # Selle dorsali e strisce sulla testa
    spot: Color      # Macchie laterali chiare
    eye: Color       # Bagliore degli occhi


@dataclass(frozen=True)
class Theme:
    """Ambiente grafico completo."""
    name: str
    bg_top: Color
    bg_bottom: Color
    blobs: Tuple[Color, Color, Color]   # Macchie di luce sul terreno
    grain: Color                        # Tinta della granulosità
    checker: Color                      # Tinta della scacchiera
    arena: Color                        # Colore del bordo
    mote: Color                         # Lucciole
    skin: SkinPalette


THEMES: List[Theme] = [
    Theme("GIUNGLA", (12, 20, 24), (5, 9, 12),
          ((10, 26, 20), (6, 18, 26), (14, 22, 14)), (1, 2, 2), (3, 5, 5), (0, 70, 80), (120, 200, 140),
          SkinPalette((14, 70, 40), (70, 200, 95), (16, 44, 26), (215, 235, 150), (255, 170, 40))),
    Theme("DESERTO", (34, 25, 16), (14, 9, 5),
          ((40, 28, 12), (30, 20, 10), (44, 34, 16)), (2, 2, 1), (5, 4, 2), (110, 70, 10), (255, 190, 110),
          SkinPalette((95, 60, 25), (220, 175, 100), (70, 38, 16), (250, 232, 185), (255, 120, 30))),
    Theme("NEON", (12, 5, 28), (2, 2, 10),
          ((30, 0, 50), (0, 18, 50), (40, 0, 40)), (2, 1, 3), (5, 3, 9), (160, 0, 140), (255, 120, 255),
          SkinPalette((0, 55, 95), (40, 225, 255), (110, 0, 150), (255, 130, 255), (255, 60, 220))),
    Theme("ABISSO", (2, 20, 34), (0, 4, 12),
          ((0, 26, 44), (0, 34, 40), (8, 16, 44)), (1, 2, 3), (2, 5, 8), (0, 90, 140), (120, 230, 255),
          SkinPalette((12, 32, 75), (80, 150, 235), (6, 16, 42), (205, 240, 255), (120, 255, 220))),
]

# Pelli fisse dei nemici
RIVAL_SKIN = SkinPalette((85, 10, 22), (225, 55, 65), (40, 0, 10), (255, 205, 120), (255, 230, 60))
BOSS_SKIN = SkinPalette((40, 0, 55), (175, 45, 210), (18, 0, 28), (255, 220, 80), (255, 40, 40))


def theme_by_name(name: str) -> Theme:
    """Restituisce il tema col nome indicato (il primo se non esiste)."""
    for theme in THEMES:
        if theme.name == name:
            return theme
    return THEMES[0]
