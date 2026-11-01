"""
Script di build di Snake Advanced.

    python build.py

1. genera l'icona e la grafica dell'installer (build/) disegnandole con il
   renderer del gioco: pannello laterale, logo, sfondo e i fotogrammi del
   serpente che sostituisce la barra di avanzamento;
2. crea l'eseguibile portatile dist/SnakeAdvanced.exe con PyInstaller
   (un solo file, nessuna console, Python non necessario sul PC di destinazione);
3. se Inno Setup 6 è installato, crea l'installer dist/SnakeAdvanced-Setup.exe
   (collegamenti nel menu Start/desktop e disinstallazione da Windows).
"""

import math
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(ROOT, "build")
ART = os.path.join(BUILD, "installer")
DIST = os.path.join(ROOT, "dist")
APP_NAME = "SnakeAdvanced"

PROGRESS_FRAMES = 25          # Deve coincidere con FRAMES in installer/snake_advanced.iss
PROGRESS_SIZE = (480, 64)
LARGE_SIZES = [(164, 314), (205, 393), (246, 471), (328, 628)]   # 100/125/150/200% DPI
SMALL_SIZES = [55, 69, 83, 110]


def _init_pygame():
    """Pygame senza finestra visibile: serve solo per disegnare."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import pygame
    pygame.init()
    pygame.display.set_mode((800, 600))
    return pygame


def make_icon() -> str:
    """Disegna l'icona con pygame e la converte in .ico multi-risoluzione con Pillow."""
    pygame = _init_pygame()
    from PIL import Image
    import visuals

    os.makedirs(BUILD, exist_ok=True)
    png = os.path.join(BUILD, "icon.png")
    ico = os.path.join(BUILD, "icon.ico")
    pygame.image.save(visuals.make_icon(256), png)
    Image.open(png).save(ico, sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    print(f"[1/4] Icona creata: {ico}")
    return ico


def _progress_frame(pygame, vfx, renderer, index: int):
    """
    Un fotogramma della "barra" di avanzamento: una pista scura su cui il
    serpente si allunga da sinistra verso destra mangiando le mele.
    """
    w, h = PROGRESS_SIZE
    canvas = pygame.Surface((800, 600))
    canvas.fill((7, 13, 16))
    ox, oy = 160, 268
    track = pygame.Rect(ox, oy, w, h)
    pygame.draw.rect(canvas, (9, 20, 22), track, border_radius=14)
    for gx in range(ox + 10, ox + w, 20):
        pygame.draw.line(canvas, (14, 30, 30), (gx, oy + 6), (gx, oy + h - 6))
    pygame.draw.rect(canvas, (40, 110, 90), track, 2, border_radius=14)

    p = index / (PROGRESS_FRAMES - 1)
    head_x = ox + 34 + p * (w - 62)
    mid = oy + h / 2

    # Mele lungo il percorso: spariscono quando la testa le raggiunge
    for f in (0.25, 0.5, 0.75, 1.0):
        fx = ox + 34 + f * (w - 62)
        if head_x < fx - 10:
            vfx.blit_glow(canvas, (fx, mid), 22, (110, 18, 22), 1.0)
            ball = vfx.shaded_ball(8, (225, 40, 50), 0.6)
            canvas.blit(ball, ball.get_rect(center=(fx, mid)))
            pygame.draw.line(canvas, (90, 55, 20), (fx, mid - 8), (fx + 2, mid - 13), 2)
            pygame.draw.polygon(canvas, (60, 170, 60), [(fx + 1, mid - 11), (fx + 6, mid - 15),
                                                        (fx + 9, mid - 12), (fx + 4, mid - 9)])

    # Corpo: dalla testa verso sinistra, con leggera ondulazione
    pts = []
    x = head_x
    while x >= ox + 10 or len(pts) < 3:
        pts.append((x, mid + 6 * math.sin(x / 24.0)))
        x -= 21
    renderer.draw(canvas, None, 1.0, 0.1, head_x / 20.0, points=pts, tongue_boost=True)
    return canvas.subsurface(track).copy()


def _large_image(pygame, vfx, themes, w: int = 246, h: int = 471):
    """Pannello verticale: titolo luminoso e serpente che sale verso di esso."""
    canvas = pygame.Surface((800, 600))
    canvas.blit(vfx.build_background(themes.THEMES[0]), (0, 0))
    ox, oy = 277, 64
    area = pygame.Rect(ox, oy, w, h)
    # Velatura scura in alto per far risaltare il titolo
    shade = pygame.Surface((w, 170), pygame.SRCALPHA)
    for i in range(170):
        pygame.draw.line(shade, (0, 0, 0, int(170 * (1 - i / 170))), (0, i), (w, i))
    canvas.blit(shade, (ox, oy))

    title_font = pygame.font.SysFont("bahnschrift,segoeui,arial", 54, bold=True)
    sub_font = pygame.font.SysFont("bahnschrift,segoeui,arial", 19, bold=True)
    title = vfx.glow_text(title_font, "SNAKE", (190, 255, 200), (20, 200, 90), 9)
    sub = vfx.glow_text(sub_font, "A D V A N C E D", (60, 230, 255), (0, 120, 160), 6)
    canvas.blit(title, title.get_rect(center=(ox + w / 2, oy + 52)))
    canvas.blit(sub, sub.get_rect(center=(ox + w / 2, oy + 96)))

    # Mela davanti alla testa
    fx, fy = ox + w * 0.68, oy + 150
    vfx.blit_glow(canvas, (fx, fy), 30, (110, 18, 22), 1.0)
    apple = vfx.shaded_ball(10, (225, 40, 50), 0.6)
    canvas.blit(apple, apple.get_rect(center=(fx, fy)))
    pygame.draw.polygon(canvas, (60, 170, 60), [(fx + 1, fy - 12), (fx + 7, fy - 17), (fx + 10, fy - 13), (fx + 4, fy - 10)])

    # Serpente a "S" dal basso verso l'alto, testa rivolta verso la mela
    pts = []
    y = oy + 196.0
    while y < oy + h + 30:
        pts.append((ox + w / 2 + 62 * math.sin((y - oy - 196) / 52.0), y))
        y += 22
    ren = vfx.SnakeRenderer(themes.THEMES[0].skin, 1.6)
    ren.draw(canvas, None, 1.0, 0.1, 0.0, points=pts, tongue_boost=True, bulges=[5.0])
    pygame.draw.rect(canvas, (60, 230, 130), area, 1)
    return canvas.subsurface(area).copy()


def make_installer_art() -> None:
    """Genera tutte le immagini usate da installer/snake_advanced.iss."""
    pygame = _init_pygame()
    import visuals as vfx
    import themes

    os.makedirs(ART, exist_ok=True)

    large = _large_image(pygame, vfx, themes)
    for (w, h) in LARGE_SIZES:
        pygame.image.save(pygame.transform.smoothscale(large, (w, h)), os.path.join(ART, f"wizard_large_{w}.png"))

    logo = vfx.make_icon(220)
    for s in SMALL_SIZES:
        pygame.image.save(pygame.transform.smoothscale(logo, (s, s)), os.path.join(ART, f"wizard_small_{s}.png"))

    back = vfx.build_background(themes.THEMES[0])
    back.fill((150, 150, 150), special_flags=pygame.BLEND_MULT)   # Più scuro: il testo resta leggibile
    pygame.image.save(back, os.path.join(ART, "wizard_back.png"))

    renderer = vfx.SnakeRenderer(themes.THEMES[0].skin, 1.25)
    for i in range(PROGRESS_FRAMES):
        frame = _progress_frame(pygame, vfx, renderer, i)
        pygame.image.save(frame, os.path.join(ART, f"progress_{i:02d}.bmp"))
    print(f"[2/4] Grafica installer creata in: {ART}")


def build_exe(icon: str) -> str:
    """Crea l'eseguibile a file singolo con PyInstaller."""
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", APP_NAME,
        "--icon", icon,
        "--distpath", DIST,
        "--workpath", os.path.join(BUILD, "pyinstaller"),
        "--specpath", BUILD,
        # Moduli presenti nell'ambiente ma inutili al gioco: esclusi per alleggerire
        "--exclude-module", "tkinter",
        "--exclude-module", "matplotlib",
        "--exclude-module", "pytest",
        "--exclude-module", "IPython",
        "--exclude-module", "torch",
        "--exclude-module", "pandas",
        "--exclude-module", "PIL",
        os.path.join(ROOT, "game.py"),
    ]
    subprocess.run(cmd, check=True, cwd=ROOT)
    exe = os.path.join(DIST, f"{APP_NAME}.exe")
    size = os.path.getsize(exe) / (1024 * 1024)
    print(f"[3/4] Eseguibile creato: {exe} ({size:.1f} MB)")
    return exe


def find_iscc() -> str:
    """Percorso del compilatore Inno Setup (stringa vuota se non installato)."""
    candidates = [
        shutil.which("iscc") or "",
        os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Inno Setup 6", "ISCC.exe"),
        os.path.join(os.environ.get("ProgramFiles", ""), "Inno Setup 6", "ISCC.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Inno Setup 6", "ISCC.exe"),
    ]
    return next((c for c in candidates if c and os.path.isfile(c)), "")


def build_installer() -> None:
    """Compila installer/snake_advanced.iss se Inno Setup è disponibile."""
    iscc = find_iscc()
    if not iscc:
        print("[4/4] Inno Setup non trovato: installer saltato "
              "(installalo con: winget install JRSoftware.InnoSetup).")
        return
    subprocess.run([iscc, os.path.join(ROOT, "installer", "snake_advanced.iss")], check=True, cwd=ROOT)
    print(f"[4/4] Installer creato: {os.path.join(DIST, APP_NAME + '-Setup.exe')}")


if __name__ == "__main__":
    only_installer = "--installer-only" in sys.argv
    icon = make_icon()
    make_installer_art()
    if not only_installer:
        build_exe(icon)
    build_installer()
