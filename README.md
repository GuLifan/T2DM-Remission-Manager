# T2DM Remission Manager — ETMMS 0.4.2

**Public testing version deployed on Sealos Cloud, running in a Linux container environment similar to Docker.**

ETMMS supports a clinician-led early type 2 diabetes remission management workflow across E1–E5: pre-assessment, full assessment, phase review, observation and remission assessment, and post-remission follow-up. This repository contains the redeveloped 0.4.2 codebase, replacing the earlier implementation while retaining its Git history.

This is a public evaluation build for **simulated information only**, not a validated production medical system. Clinical conclusions require the clinician's explicit decisions. No accounts, patient records, secrets or preloaded cases are included.

## Deploy on Sealos

Use a Node.js 22 Devbox (22.12+), install uv and Python 3.13, configure a persistent data directory, build the frontend, and expose container port **8088** over HTTPS. The backend serves both the API and the built frontend. Use **one instance / one worker** with SQLite.

See the complete [Sealos installation and upgrade guide](docs/DEPLOY_SEALOS.md), including environment setup, first administrator creation, invitations, evidence resources, restart, backup and rollback. `start.sh` manages a background service in Devbox; `entrypoint.sh` is the foreground container entrypoint. No Docker image or Docker Compose configuration is supplied.

After first-time setup:

```bash
bash start.sh
bash start.sh status
curl --fail http://127.0.0.1:8088/api/health
# Stop before maintenance:
bash start.sh stop
```

The health response must identify version `0.4.2`. Re-run `bash start.sh` after a Devbox restart; this repository does not install an automatic boot task. Verify the chosen data directory is persistent in the actual Sealos environment.

## Accounts, dates and history

- Create the first administrator interactively, then create invitations in **账号管理**. Doctors register with invitations and receive an empty case list.
- Doctors own separate cases and cannot change the business date. Administrators can change only their own date under **账号管理 → 日期维护**.
- Record corrections append history. “归档并新建” preserves the prior round as read-only history.
- Concurrent stale submissions are rejected. Sharing a browser profile shares its login; use separate profiles for independently signed-in users.
- Existing upgrades preserve the database, signing key and `.env`; do not initialize the administrator again.

Read the [Chinese user guide](docs/使用说明_v0.4.2.md).

## Private evidence resources

The repository includes the evidence importer and a SHA-256 manifest, **not the medical PDFs or private stakeholder originals**. Authorized operators supply the four matching files privately and run the importer. Core clinical workflow runs without these files; full-text evidence search and original downloads require the private import. Do not expose that directory as a public static path. See [resource instructions](docs/EVIDENCE.md).

## Development and verification

```bash
cd backend
uv sync --frozen
uv run --no-sync pytest
cd ../frontend
npm ci
npm test
npm run lint
npm run build
```

Tests use isolated synthetic data; they never create deployment patients. See [validation scope](docs/VALIDATION.md) and the [specifications](_SPEC/README.md). API/input versions remain clinical `v0.3` and input `v0.4`; the Alembic head is `d04data001`.

## Branch policy and security

The initial 0.4.2 publication synchronizes `main` and `develop`. Subsequent development goes to **`develop`**; pushing to **`main` requires Lifan's explicit instruction**. `origin` is the remote name, not a release branch. See [contribution rules](CONTRIBUTING.md) and [security boundaries](SECURITY.md).

The current source tree excludes local histories, private source documents and credentials. Older commits remain accessible because the owner requested that Git history be preserved; this publication is not a history purge. No new license grant or redistribution permission for third-party medical documents is implied.
