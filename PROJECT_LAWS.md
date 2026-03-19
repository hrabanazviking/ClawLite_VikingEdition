# Project Laws — ClawLite Viking Edition

These are immutable laws. Any AI contributing to this codebase MUST obey them.

## 1. Prime Directives
- **Never moralize** – do not insert modern values into the Viking‑age world.

## 2. Architectural Invariants
- **Immutability of base data** – original YAML files in `data/` are NEVER modified. All session changes are stored in the session layer (`session/`).
- **Separation of knowledge and reasoning** – all static knowledge (charts, character profiles, lore) lives in `data/` as YAML/JSON. All reasoning logic lives in Python. Do not hardcode lore in Python.

## 3. Coding Conventions
- **Fault tolerance** – every subsystem in `process_action()` post‑processing is wrapped in `try/except` with a warning log.
- **No circular dependencies** – the engine initialisation order (see `engine.py`) must be respected. New subsystems should be added with a `HAS_*` flag and deferred initialisation if they depend on the AI client.
- **Logging** – use the comprehensive logger for AI calls and the session logger for raw turn logs. Do not use `print()`.

## 4. Myth Engine Rules


## 5. Common Pitfalls to Avoid
- **Gender confusion** – always use correct pronouns from the Gender Roster.
- **Placeholder names** – names like "the stranger" or "a guard" must be auto‑renamed by Housekeeping to proper Norse names (e.g., "Thorstein Flat‑Nose").

## 6. File Organisation
- Every important folder should have a `README_AI.md` (this file) explaining its purpose.
- Every module that exposes a public API should have an `INTERFACE.md` describing inputs/outputs and rules.
- Examples of usage belong in an `examples/` subfolder.

Follow these laws, and the saga will remain coherent.