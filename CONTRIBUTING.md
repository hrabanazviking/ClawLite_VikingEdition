# Contributing to ClawLite

Thanks for contributing.

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
pytest -q
```

If `dev` extras are available in `pyproject.toml`, prefer:

```bash
pip install -e ".[dev]"
```

## Project principles

- Simple and auditable architecture
- Predictable runtime behavior
- Documentation aligned with real code
- Secure-by-default behavior for personal use

## Recommended flow

1. Open an issue (bug/proposal) before large changes.
2. Create a focused branch (`feat/...`, `fix/...`, `docs/...`).
3. Make small changes per module.
4. Update tests when behavior changes.
5. Run local validation:
   - `pytest -q`
   - smoke tests for changed commands (`clawlite --help`, `clawlite start`, `clawlite run`)
6. Open a PR with context, risk, and test evidence.

## Good first issues

- Start with issues labeled `good first issue` or `help wanted`.
- Prefer small, isolated scopes: docs clarity, tests for existing behavior, small CLI UX fixes, or non-breaking refactors.
- Keep one logical change per PR to make review and rollback straightforward.
- If the issue is unclear, add a short implementation plan in the issue/PR before coding.

## Quality standards

- Do not break core commands: `start`, `run`, `onboard`, `cron`, `skills`.
- Do not introduce API regressions in `/v1/chat` and `/v1/cron/*` without a documented migration.
- Never commit secrets/tokens/private keys.
- Always update docs if CLI/API/operational flow changes.

## PR checklist

- [ ] Scope and goal are clear
- [ ] Tests were run and reported
- [ ] Docs updated
- [ ] No credentials in the diff
