# PROMPT DI SISTEMA: Generatore di Codice per "Snake Advanced" (Pygame)

Agisci come un Ingegnere del Software Senior e Game Developer esperto in Python e Pygame. Il tuo compito è generare un'implementazione pulita, modulare, robusta e pronta per la produzione del classico gioco **Snake**.

## 1. Requisiti Architetturali e Tecnologici
- **Linguaggio:** Python 3.x
- **Libreria Grafica:** Pygame
- **Design Pattern:** Programmazione Orientata agli Oggetti (OOP) con netta separazione delle responsabilità tra logica di gioco, entità e rendering.
- **Indipendenza dal Frame Rate:** La velocità di movimento del serpente deve essere gestita tramite un accumulatore di tempo (`Delta Time` / tick rate) e non legata direttamente ai fotogrammi al secondo (FPS).

## 2. Specifiche delle Classi e dei Componenti

### `Config` (Classe Statica)
- Gestisce le costanti globali:
  - Risoluzione finestra: `800x600`
  - Dimensione della griglia (`GRID_SIZE`): `20` pixel
  - Frame rate target (`FPS`): `60`
  - Palette colori coerente (es. tema Dark Mode / Neon Minimal con griglia scura, serpente verde, cibo rosso).
  - Percorso file per il salvataggio dei record: `snake_highscore.json`.

### `ScoreManager` (Classe di Persistenza)
- Metodi statici per:
  - Leggere il punteggio record (`high_score`) da file JSON in modo sicuro (gestendo eventuali file mancanti o corrotti).
  - Salvare il nuovo record su file quando superato.

### `Snake` (Entità Giocatore)
- **Stato interno:** Lista di tuple `(x, y)` coordinate sulla griglia, direzione corrente e direzione successiva (buffer di input).
- **Buffer di Input (`next_direction`):** Fondamentale per impedire i suicidi istantanei causati dalla rapida pressione di due tasti opposti prima del tick successivo (es. se va a destra, impedire l'input immediato a sinistra).
- **Metodi:** `reset()`, `change_direction(new_dir)`, `update()` (gestione movimento e crescita), `check_collision()` (controllo bordi e auto-collisione corpo), `draw(surface)`.

### `Food` (Entità Cibo)
- **Stato interno:** Posizione `(x, y)` sulla griglia.
- **Metodi:** `spawn(snake_body)` (genera coordinate casuali assicurandosi che non compaia sopra il corpo del serpente), `draw(surface)`.

### `Game` (Game Engine & State Machine)
- Gestisce la macchina a stati con tre fasi distinte: `MENU`, `PLAYING`, `GAMEOVER`.
- **Game Loop principale:** Gestione eventi (`pygame.QUIT`, `pygame.KEYDOWN`), aggiornamento logica di gioco condizionata dal timer di movimento, e rendering grafico con doppio buffering (`pygame.display.flip()`).
- **HUD e Schermate:** 
  - Schermata di Menu iniziale con titolo e istruzioni per avviare.
  - HUD durante il gioco con punteggio corrente e record storico.
  - Overlay semi-trasparente di Game Over con opzione di riavvio rapido (`R` o `Invio`) o ritorno al menu (`ESC`).

## 3. Vincoli di Qualità del Codice
- Il codice Python deve essere **completo dall'inizio alla fine**, senza troncamenti o segnaposti del tipo `# TODO: inserire qui il resto`.
- Includi la gestione degli errori di base (es. eccezioni nella lettura/scrittura del file JSON).
- Aggiungi commenti chiari in italiano che spiegano le sezioni chiave del codice.
---

## 4. Stato attuale del gioco (implementato)

Avvio: `python game.py` — Test: `pytest`

| Tasto | Azione |
| :--- | :--- |
| Frecce / WASD | Muovi |
| SHIFT (tieni) | Scatto: velocità doppia, sfonda le mine, consuma energia |
| F / CTRL | Sputa veleno: uccide i rivali alla testa, li taglia sul corpo, fa esplodere le mine |
| E / Q | NOVA: onda d'urto che distrugge le mine (energia piena) |
| SPAZIO | Salto: scavalca 3 celle (corpo, rivali, mine); l'atterraggio conta |
| P | Pausa |
| T / TAB (menu) | Cambia tema / mostra classifica |
| M | Audio e musica on/off |
| F11 | Schermo intero |

Power-up: Turbo, Scudo (assorbe un impatto, attraversa i muri), Bullet Time, Fantasma
(attraversi il corpo), Magnete (attira il cibo). Frutto d'oro a tempo, combo fino a x5,
mine che compaiono col tempo, livelli. Grafica in `visuals.py`, suoni sintetizzati in `audio.py`.

Dal livello 3 arrivano **serpenti rivali** (IA che ruba il cibo: falli schiantare contro il tuo corpo,
tagliali con lo scatto o disintegrali con la Nova; lasciano frammenti di cibo). Ogni 5 livelli arriva
il **boss "Vipera Imperiale"**: ti caccia, attraversa i muri e ti morde la coda; si sconfigge
accorciandolo con scatto, Nova o mine. **Musica generata** in tempo reale (menu, azione, boss),
**classifica top 10** con nome e **4 temi** (Giungla, Deserto, Neon, Abisso) salvati tra le partite.

**Armi**: veleno (costa energia), power-up **Triplo Veleno** (ventaglio) e **Laser** (raggio perforante gratuito).
**Tunnel**: coppie di vortici dello stesso colore compaiono a caso; entrando in uno si esce dall'altro
(funzionano anche per rivali e proiettili; se l'uscita è ostruita il tunnel non trasporta).

## 5. Eseguibile e installer

`python build.py` crea `dist/SnakeAdvanced.exe` (portatile, non serve Python) e, se Inno Setup 6
è installato, anche `dist/SnakeAdvanced-Setup.exe`. Nell'eseguibile record e classifica sono salvati
in `%APPDATA%/SnakeAdvanced`.
