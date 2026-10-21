# Security and operating boundaries

This is a public testing release for simulated information. Do not use real patient information or reuse public test-fixture passwords for deployed accounts.

- Configure a private persistent data directory outside the checkout. Back up the database and signing key together; keep `.env`, logs, backups and tokens private.
- Use HTTPS at the Sealos ingress. Expose only the application port. The supported topology is one instance and one Uvicorn worker with SQLite.
- New users register by administrator invitation. Patient routes enforce ownership; administrator date maintenance affects that administrator only. Client-side hiding does not replace backend authorization.
- Never host evidence originals as anonymous static files. Import only approved hash-matched resources supplied through a private channel.
- Test fixtures use deliberately public synthetic credentials and temporary databases. These are not deployable accounts or seed data. The first real administrator is created interactively.
- Report suspected vulnerabilities privately to the repository owner through an available private channel. Do not put live credentials, patient information or exploit evidence containing private data in public issues.

No production medical validation, regulatory certification, exhaustive penetration test or capacity guarantee is asserted. Current-tree cleanup is not a purge of retained Git history; an actual credential exposed in older commits would require revocation/rotation and a separately authorized history-remediation plan.
