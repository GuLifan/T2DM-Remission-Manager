# Changelog

## 0.4.2 — 2026-10-21

Redeveloped public testing version for Sealos Cloud and a Linux container environment similar to Docker. Replaces the previous branch content while retaining Git history.

- Fix revision locking for same-value decisions and concurrent clinical updates.
- Bind requests to the verified browser identity and block stale drafts after identity/date changes.
- Enforce complete and consistent P05 medication plans and explicit reconciliation of conflicting historical facts.
- Carry forward other-intervention descriptions and avoid hidden-field validation for deferred plans.
- Require valid management constraints and show action-specific confirmation summaries.
- Support approved evidence import and authenticated original downloads, with private source originals supplied separately.
- Improve narrow-screen navigation, modal cancellation and keyboard focus behavior.
- Reject E5 detection dates later than the acting user's effective date, on both client and server.
- Keep doctor dates read-only; administrator maintenance changes that administrator's own date only.

Clinical contract v0.3, input schema v0.4 and database head d04data001 remain. Existing clinical history is preserved. Source publication excludes local records and private originals, supplies minimal public regression baselines, and uses a generic initial administrator display name.

The public-source publication pins Vite 8.3.3 to address editor-launch security advisories in the earlier development-tool lockfile. This changes the source rebuild toolchain; it does not rewrite the separately delivered Sealos ZIP or alter clinical rules.
