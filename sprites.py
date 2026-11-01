"""
Modulo per la gestione degli Sprite del gioco.
"""

import pygame
from config import CELL_SIZE, COLOR_NEON_GREEN, COLOR_DARK_GREEN, COLOR_RED, COLOR_WHITE

class Sprite:
    """
    Classe base per gli oggetti grafici nel gioco.
    """
    def __init__(self, color: tuple, x: int, y: int):
        self.x = x
        self.y = y
        self.color = color
        self.rect = pygame.Rect(x * CELL_SIZE, y * CELL_SIZE, CELL_SIZE, CELL_SIZE)

    def draw(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, self.color, self.rect)
        pygame.draw.rect(surface, (0, 0, 0), self.rect, 1) # Bordo nero
