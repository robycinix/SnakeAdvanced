"""
Script di build di Snake Advanced.

    python build.py

1. genera l'icona (build/icon.ico) disegnandola con il renderer del gioco;
2. crea l'eseguibile portatile dist/SnakeAdvanced.exe con PyInstaller
   (un solo file, nessuna console, Python non necessario sul PC di destinazione);
3. se Inno Setup 6 è installato, crea l'installer dist/SnakeAdvanced-Setup.exe
   (collegamenti nel menu Start/desktop e disinstallazione da Windows).
"""

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(ROOT, "build")
DIST = os.path.join(ROOT, "dist")
APP_NAME = "SnakeAdvanced"


def make_icon() -> str:
    """Disegna l'icona con pygame e la converte in .ico multi-risoluzione con Pillow."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import pygame
    from PIL import Image

    pygame.init()
    pygame.display.set_mode((800, 600))
    import visuals

    os.makedirs(BUILD, exist_ok=True)
    png = os.path.join(BUILD, "icon.png")
    ico = os.path.join(BUILD, "icon.ico")
    pygame.image.save(visuals.make_icon(256), png)
    Image.open(png).save(ico, sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    pygame.quit()
    print(f"[1/3] Icona creata: {ico}")
    return ico


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
    print(f"[2/3] Eseguibile creato: {exe} ({size:.1f} MB)")
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
        print("[3/3] Inno Setup non trovato: installer saltato "
              "(installalo con: winget install JRSoftware.InnoSetup).")
        return
    subprocess.run([iscc, os.path.join(ROOT, "installer", "snake_advanced.iss")], check=True, cwd=ROOT)
    print(f"[3/3] Installer creato: {os.path.join(DIST, APP_NAME + '-Setup.exe')}")


if __name__ == "__main__":
    build_exe(make_icon())
    build_installer()
