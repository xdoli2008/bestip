# Repository Guidelines

## Project Structure & Module Organization

- `main.py`: entry point (calls `src/core/ip_tester_pro.py`).
- `src/`: Python package code
  - `src/core/`: core testing flow (two-phase testing, scoring, output)
  - `src/config/`: configuration loading/validation
  - `src/analyzers/`: statistics + proxy scoring
  - `src/utils/`: helpers (e.g., URL target fetching)
- `data/input/`: input lists (`testip.txt`, optional `custom.txt`)
- `data/output/`: generated results (`best.txt`, `ip.txt`, `result_pro.md/.txt`)
- `docs/`: technical notes (see `docs/TECHNICAL.md`)

## Build, Test, and Development Commands

- Run locally: `python main.py` (Windows shortcut: `run.bat`).
- Optional dependency for YAML config: `pip install pyyaml`.
- Config workflow:
  - Copy: `copy config.example.yaml config.yaml` (Windows) / `cp config.example.yaml config.yaml`
  - Edit `config.yaml` (look for `test_mode`, URL/custom inputs, streaming settings).

## Coding Style & Naming Conventions

- Python, 4-space indentation, UTF-8 source files.
- Keep imports package-based (e.g., `from src.config.config import load_config`).
- Prefer `snake_case` for modules/functions and descriptive names for config keys.
- Keep paths repo-relative; avoid hard-coded absolute paths.
- Be careful with cross-platform behavior (ping output parsing, Windows encoding).

## Testing Guidelines

- This repo currently uses lightweight script-style checks:
  - `python test_yaml_config.py` validates config loading.
  - `python test_streaming.py` validates streaming test wiring.
- If adding new tests, keep them fast and runnable via plain `python ...` unless you
  introduce a framework consistently across the project.

## Commit & Pull Request Guidelines

- Commit messages follow a Conventional Commits-style pattern in history:
  `feat: ...`, `fix: ...`, `refactor: ...` (keep the summary short and imperative).
- PRs should include:
  - What changed and why (especially for scoring/report logic).
  - How to reproduce (commands + sample input path).
  - Any config keys added/changed (update `config.example.yaml` when applicable).
- Avoid committing personal URLs/secrets in `config.yaml`; prefer examples in
  `config.example.yaml`. Avoid committing generated outputs in `data/output/`
  unless intentionally updating sample artifacts.
