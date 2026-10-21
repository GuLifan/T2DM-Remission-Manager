# Sealos Cloud / Devbox deployment — 0.4.2

This is the public testing build for simulated information, deployed in a Linux container runtime similar to Docker. Use a Node.js 22 Devbox, one instance and one Uvicorn worker. The following commands are for a **fresh installation**. For an existing database use the upgrade section instead; do not overwrite `.env`, keys or data.

## 1. Install the local-user tools

Open the Devbox remote terminal. Check Node.js is at least 22.12:

```bash
node --version
curl -LsSf https://astral.sh/uv/install.sh -o /tmp/etmms-uv-install.sh
sh /tmp/etmms-uv-install.sh
export PATH="$HOME/.local/bin:$PATH"
uv --version
uv python install 3.13
uv python find 3.13
```

The installer goes into the Devbox user's tool directories. Project Python dependencies go into `backend/.venv`; do not install application dependencies into a global Python. In a new terminal repeat the PATH export if uv is not on PATH.

## 2. Obtain the source

```bash
cd /home/devbox/project
git clone --branch main https://github.com/GuLifan/T2DM-Remission-Manager.git
cd T2DM-Remission-Manager
git rev-parse HEAD
```

Record the commit SHA for reproducibility. Source-download ZIPs are also usable, but do not include dependencies or built frontend files. No default administrator password exists.

## 3. Configure an independent persistent data directory

Confirm the Sealos storage/mount first. `/home/devbox/etmms-v04-data` below is an **example**, not a promise of platform persistence. Keep it outside the source checkout and do not use a public static directory.

```bash
mkdir -p /home/devbox/etmms-v04-data
chmod 700 /home/devbox/etmms-v04-data
cp backend/.env.example backend/.env
chmod 600 backend/.env
```

Edit `backend/.env` so it contains:

```dotenv
ETMMS_DEMO_MODE=true
ETMMS_DATA_DIR=/home/devbox/etmms-v04-data
ETMMS_SESSION_HOURS=8
ETMMS_LOG_LEVEL=INFO
```

Do not commit this real file. The application creates its own random signing key in the data directory; preserve it with backups. Keep the same data path and key across service restarts.

## 4. Install dependencies and build

From the repository root:

```bash
export PATH="$HOME/.local/bin:$PATH"
export UV_PYTHON=3.13
bash scripts/setup.sh
backend/.venv/bin/python --version
```

This uses `uv sync --frozen --no-dev` and `npm ci`, then builds the frontend. Do not copy a Windows `.venv` or `node_modules` to Linux.

## 5. Initialize the first administrator — fresh installs only

```bash
cd backend
uv run --no-sync python -m app.demo_cli init-admin
cd ..
```

Enter your own login name and a unique password of at least 12 characters at the prompts. Nothing is seeded into the patient list. An existing administrator must not be reinitialized.

## 6. Privately configure evidence, if authorized

Follow [EVIDENCE.md](EVIDENCE.md). The Git checkout contains only the manifest. After placing all four matching originals at their specified paths, run:

```bash
cd backend
uv run --no-sync python -m app.evidence_cli
cd ..
```

The expected results are 13, 124 and 15 PDF pages plus 15 Markdown sections. A second import reports `skipped`. Missing/mismatched files must be resolved with the operator; never bypass their hashes. Without these resources the clinical workflow remains available but evidence search is not complete. Existing upgraded databases may already contain indexes; original downloads additionally require the files.

## 7. Start and expose port 8088

```bash
bash start.sh
bash start.sh status
curl --fail http://127.0.0.1:8088/api/health
```

Expected JSON: `{"status":"ok","version":"0.4.2"}`. In Sealos network settings expose **8088**, enable public HTTPS access, and open the generated URL. Do not map 8080 unless explicitly changing the service port. Do not expose the Vite development server, data directory or resource directory.

For Devbox background operation keep `start.sh`. Closing the terminal should leave its process running; verify in the actual environment. After Devbox restarts run it again. To stop use `bash start.sh stop`. To inspect logs use the log path shown by its status output; do not publish logs.

For a managed container process use `bash entrypoint.sh` in the **foreground** instead. It uses `${PORT:-8088}`; `start.sh` uses `ETMMS_START_PORT` with default 8088. Do not start both launch modes together. Persistent volume configuration remains the operator's responsibility.

## 8. Invite doctors and verify

Log in as the administrator, open **账号管理**, and create an invitation. Save its plaintext when shown; it is not recoverable later. Open another browser profile to register a doctor. Both accounts start without patients. Confirm the doctor cannot edit dates and cannot read another user's cases. Administrator date control is under **账号管理 → 日期维护**, not the read-only clinical header.

## Existing installation upgrade and rollback

1. Record the existing code version, configured data directory and key location. Stop service using the old installation's `start.sh stop`; confirm port 8088 is no longer serving it.
2. Back up `.env` and the **entire configured data directory**, including signing key and database sidecars, to a private directory outside both old and new code trees. With service stopped, use the old backend's `python -m app.demo_cli backup --output <new-backup.db>` for an integrity-checked SQLite backup. Do not overwrite an earlier backup or publish these files.
3. Preserve the old source directory for rollback. Put the new source in a separate directory, restore the old `backend/.env`, and keep exactly the existing external data path and signing key. Run setup. **Do not run init-admin, delete tables or upload a local development database.**
4. Privately restore the four evidence files if using that feature, then run `app.evidence_cli`. Database migrations are tracked at startup/import; version 0.4.2 retains head `d04data001`.
5. Start the new code and verify health 0.4.2. Before inviting new testers, confirm existing users, current/archived cases and histories remain available. Force-refresh the browser and check both roles.
6. If rollback is needed, stop the new process first and preserve its current database for investigation. Restore the matching old code, `.env`, backed-up database and signing key together. Never run older code against an uncertain partially upgraded database or delete migration records to hide errors.

These instructions do not establish that a chosen mount survives Devbox deletion/recreation. Validate restart persistence and backups in your actual Sealos environment.

References: [uv installation](https://docs.astral.sh/uv/getting-started/installation/), [uv Python management](https://docs.astral.sh/uv/guides/install-python/), [Sealos Devbox](https://sealos.io/docs/guides/devbox/), [Sealos deployment](https://sealos.io/docs/guides/devbox/deploy/).
