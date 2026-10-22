# Repository instructions

- Address the owner as Lifan. For a new substantive task, first ask one focused question or group until the goal is clear, propose scope and obtain approval. Do not repeat questions or permissions already resolved in the active task.
- If a private `HANDOVER.md` exists, read it first. Then read `_SPEC/CURRENT_SPEC.md` and the affected constraints. Load private handover details and historical specifications only when the current task needs them; do not reread entire conversation histories by default.
- Follow SPEC-first development. Preserve manual edits, clinical history, source provenance and approved thresholds. Comments should be detailed Chinese where helpful. Use uv and project-local `backend/.venv`; never alter global Python packages.
- Keep compatibility routes, migration history and valid clinical/security regressions. Full distributions exclude runtime data, tests, installed dependencies and private evidence originals.
- Development targets `develop`; temporary branches may use `codex/`. Each push to `main` needs Lifan's explicit authorization. Do not force push, rewrite history, push other refs, create releases or change repository settings without specific authorization.
- Commit/PR titles and descriptions use English and a GitHub noreply email. Project introductions and deployment guides provide complete English and Chinese content.
- `HANDOVER.md`, `_LOCAL_HANDOVER/`, `_LOCAL_RELEASE/` and private evidence originals are ignored local records. Never commit actual credentials, `.env`, keys, databases, logs, local machine paths, screenshots or stakeholder originals. Synthetic regression fixtures are public and must never seed deployed cases.
- Distinguish local tests, owner-reported cloud operation, persistence/restart checks and clinical acceptance. Never treat cleanup advice or suggested commands as completed actions without evidence.
