# Public repository constraints — 0.4.2

This repository is a curated publication of the redeveloped ETMMS 0.4.2 application.

- Product 0.4.2; clinical contract v0.3; input schema v0.4; database head d04data001.
- Single Linux instance, FastAPI, one Uvicorn worker, SQLite; built frontend served by the same application on port 8088.
- Sealos Cloud / Devbox is the deployment target. Its Linux container runtime is similar to Docker; this repository does not provide a Docker image or claim Docker/Compose verification.
- Public testing uses simulated information only. No patient records, accounts, credentials or runtime data are shipped. Administrators and doctors start with zero cases.
- Administrators alone may change their own business date under Account management / Date maintenance. Doctors use the system date. The backend enforces this boundary.
- Preserve migration history, clinical events, archived rounds, audit records and existing data during upgrades. Never run init-admin during an existing installation upgrade.
- Do not silently repair historical medication facts or bypass explicit clinical confirmation, revision checks, ownership checks or idempotency.
- Private stakeholder documents and medical source originals are excluded from Git. The evidence manifest and importer remain unchanged; authorized operators supply matching originals privately. Absence does not disable the clinical workflow, but full-text evidence is unavailable until imported.
- Regression fixtures contain only synthetic test inputs and minimal frozen program-output/transition baselines. They are never loaded as deployment patients. Public baseline tests do not replace internal original-document comparison or clinical acceptance.
- Runtime application behavior is the verified 0.4.2 implementation; publication removes the personal name from the initial administrator display name only. No clinical or authorization rule is changed.
- Publication dependency audit requires Vite 8.3.3, a compatible development-tool security patch for GHSA-587h-7wmj-h5pm and related editor-launch advisories. The existing Sealos ZIP is not rewritten; public source rebuilds use the patched lockfile and undergo frontend regression again.
- Do not claim local checks prove Linux deployment, persistence after Devbox restart, medical correctness, production readiness or cloud acceptance.
- This publication is authorized to update main and develop while preserving their existing history. No force push, history rewrite, visibility change, tag or Release is authorized. Future development targets develop; main updates require a new explicit instruction.
