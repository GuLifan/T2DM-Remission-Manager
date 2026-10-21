# Repository instructions

- Address the owner as Lifan. Clarify substantive requirements and obtain the owner's approval before implementation when the scope is not already authorized.
- Read `_SPEC/README.md` and the affected constraints first; update specifications before changing clinical behavior. Preserve manual changes and existing clinical data.
- Use Chinese comments where helpful. Python uses uv and a project-local `backend/.venv`; never alter the global Python environment.
- Future development targets `develop` (temporary branches may use `codex/`). Never push to `main` unless Lifan explicitly authorizes that specific publication. Do not force push or rewrite history without explicit approval.
- `origin` is a remote name. Updating any other remote branch, tags, releases, visibility or repository settings requires explicit authorization. Merely configuring a remote does not authorize publishing.
- Commit messages, PR titles and PR descriptions are English. Use a GitHub noreply commit email, not a private contact address.
- Never commit runtime data, real credentials, `.env`, keys, databases, logs, screenshots, private medical originals or stakeholder materials. Keep synthetic tests separate from deployment data.
- Do not confuse local automated checks with cloud verification, clinician acceptance or production readiness.
