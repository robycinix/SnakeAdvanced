"""
Configurazione condivisa di pytest: driver video/audio fittizi per eseguire
i test senza aprire finestre, e file del record isolato per ogni test.
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pytest


@pytest.fixture(autouse=True)
def isolated_high_score(tmp_path, monkeypatch):
    """Reindirizza il file del record in una cartella temporanea."""
    monkeypatch.setattr("score_manager.HIGH_SCORE_FILE", str(tmp_path / "hs.json"))
