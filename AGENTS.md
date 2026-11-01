# AGENTS.md - Project Configuration and Conventions

This file defines the core conventions, architectural decisions, and required commands for the "Snake Advanced" Pygame project. Agents are expected to adhere to these standards to ensure code consistency and maintainability.

## 🛠️ Required Commands
Since no explicit `Makefile` or CI config was found, the following commands are assumed based on standard Python/Pygame project practices. These should be confirmed by inspecting `pyproject.toml`, `setup.py`, or the CI workflow.

| Operation | Command (PowerShell/Terminal) | Notes |
| :--- | :--- | :--- |
| **Build** | `python -m build` or `pip install -e .` | Creates distribution packages (`sdist`, `wheel`). |
| **Test** | `pytest` | Assumes `pytest` is installed and tests are discoverable. |
| **Lint** | `pylint .` or `black .` | `pylint` for general code quality; `black` for formatting enforcement. |
| **Type-Check** | `mypy .` | Ensures static type hints are correct across the codebase. |

## 🏛️ Architecture Overview
The project follows a strict **Model-View-Controller/Game Loop** pattern implemented using **Object-Oriented Programming (OOP)** in Python.

- **Model:** Entities (`Snake`, `Food`) hold state and business logic.
- **View:** The `Game` class handles the rendering logic to the Pygame `Surface`.
- **Controller/Engine:** The `Game` class orchestrates state transitions and the main game loop.

## 📜 Conventions & Gotchas
1. **Code Completeness:** All modules **must** be 100% complete. Placeholders like `# TODO: ...` should only be used for *future* planned features, not for incomplete current functionality.
2. **Movement Logic:** All movement must be calculated based on **Delta Time** accumulation within the `Game` loop, ensuring frame-rate independence.
3. **Snake Buffer:** The `Snake` class *must* use a `next_direction` buffer to prevent instantaneous 180-degree reversals (e.g., pressing Up then Down instantly), which bypasses standard collision checks.
4. **Documentation:** Key classes and methods must be documented using **Italian** docstrings explaining *what* the code does and *why* it does it.

---
*Last Updated: 2026-11-01*