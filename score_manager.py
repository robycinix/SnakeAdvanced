"""
Modulo responsabile della persistenza dei dati del gioco Snake:
record, classifica dei 10 migliori punteggi con nome e preferenze (tema, ultimo nome).
Tutto vive in un unico file JSON (config.HIGH_SCORE_FILE): ogni scrittura
legge prima il file e aggiorna solo le proprie chiavi, così nessun dato
viene cancellato da un salvataggio parziale.
"""

import json
from datetime import date
from typing import Any, Dict, List

from config import HIGH_SCORE_FILE

LEADERBOARD_SIZE: int = 10
MAX_NAME_LENGTH: int = 12


class ScoreManager:
    """
    Gestisce salvataggio e caricamento di record, classifica e preferenze.
    Tutti i metodi sono statici: non c'è stato in memoria, la fonte di verità è il file.
    """

    # ------------------------------------------------------------------
    # Accesso al file
    # ------------------------------------------------------------------

    @staticmethod
    def _load_data() -> Dict[str, Any]:
        """
        Legge l'intero file JSON.

        :return: Il dizionario dei dati, vuoto se il file manca o è corrotto.
        """
        try:
            with open(HIGH_SCORE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError:
            print(f"ERRORE: File {HIGH_SCORE_FILE} è corrotto. Dati azzerati.")
            return {}
        except OSError as e:
            print(f"ERRORE: impossibile leggere {HIGH_SCORE_FILE}: {e}")
            return {}

    @staticmethod
    def _update_data(changes: Dict[str, Any]) -> bool:
        """
        Unisce `changes` ai dati esistenti e riscrive il file.

        :return: True se la scrittura è riuscita.
        """
        data = ScoreManager._load_data()
        data.update(changes)
        try:
            with open(HIGH_SCORE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            return True
        except OSError as e:
            print(f"ERRORE: impossibile salvare {HIGH_SCORE_FILE}: {e}")
            return False

    # ------------------------------------------------------------------
    # Record
    # ------------------------------------------------------------------

    @staticmethod
    def load_high_score() -> int:
        """
        Legge il punteggio record.

        :return: Il record come intero; 0 se assente o non valido.
        """
        value = ScoreManager._load_data().get('high_score', 0)
        return value if isinstance(value, int) and value >= 0 else 0

    @staticmethod
    def save_high_score(score: int) -> bool:
        """
        Salva il punteggio fornito come nuovo record, se è superiore al precedente.

        :param score: Il punteggio corrente da salvare.
        :return: True se il record è stato aggiornato, False altrimenti.
        """
        if not isinstance(score, int) or score < 0:
            print("ERRORE: Il punteggio fornito non è un intero positivo.")
            return False
        if score <= ScoreManager.load_high_score():
            return False
        return ScoreManager._update_data({"high_score": score, "last_updated": date.today().isoformat()})

    @staticmethod
    def get_current_high_score() -> int:
        """Restituisce il punteggio record attuale."""
        return ScoreManager.load_high_score()

    # ------------------------------------------------------------------
    # Classifica
    # ------------------------------------------------------------------

    @staticmethod
    def load_leaderboard() -> List[Dict[str, Any]]:
        """
        Restituisce la classifica ordinata per punteggio decrescente.
        Le voci malformate vengono scartate invece di far fallire il gioco.
        """
        raw = ScoreManager._load_data().get('leaderboard', [])
        board = [e for e in raw if isinstance(e, dict) and isinstance(e.get('score'), int)
                 and isinstance(e.get('name'), str)] if isinstance(raw, list) else []
        board.sort(key=lambda e: e['score'], reverse=True)
        return board[:LEADERBOARD_SIZE]

    @staticmethod
    def qualifies(score: int) -> bool:
        """True se il punteggio entra nella top 10."""
        if score <= 0:
            return False
        board = ScoreManager.load_leaderboard()
        return len(board) < LEADERBOARD_SIZE or score > board[-1]['score']

    @staticmethod
    def add_entry(name: str, score: int) -> int:
        """
        Inserisce un punteggio in classifica e ricorda il nome per la prossima volta.

        :return: La posizione ottenuta (1 = primo), 0 se non è entrato.
        """
        name = (name.strip() or "ANONIMO")[:MAX_NAME_LENGTH].upper()
        board = ScoreManager.load_leaderboard()
        entry = {"name": name, "score": score, "date": date.today().isoformat()}
        board.append(entry)
        board.sort(key=lambda e: e['score'], reverse=True)
        board = board[:LEADERBOARD_SIZE]
        rank = next((i + 1 for i, e in enumerate(board) if e is entry), 0)
        ScoreManager._update_data({"leaderboard": board, "last_name": name})
        return rank

    # ------------------------------------------------------------------
    # Preferenze
    # ------------------------------------------------------------------

    @staticmethod
    def get_setting(key: str, default: Any = None) -> Any:
        """Legge una preferenza salvata (es. 'theme', 'last_name')."""
        return ScoreManager._load_data().get(key, default)

    @staticmethod
    def set_setting(key: str, value: Any) -> bool:
        """Salva una preferenza."""
        return ScoreManager._update_data({key: value})
