# Private evidence configuration

Medical source originals and stakeholder materials are deliberately not redistributed through Git. Do not obtain arbitrary lookalike documents or edit the importer to accept an unreviewed file. Authorized operators must privately obtain the exact approved resources from the project owner.

The paths, sizes and SHA-256 values are in [`resources/evidence/manifest.json`](../resources/evidence/manifest.json). Place the files underneath `resources/evidence/` with exactly those relative paths. The `.gitignore` excludes originals, including the Markdown stakeholder file.

From `backend`, run `uv run --no-sync python -m app.evidence_cli`. It checks source hashes and expected page/section counts, imports each source atomically, and skips unchanged sources. The expected counts are 13 / 124 / 15 PDF pages and 15 Markdown sections. It does not initialize accounts or seed cases. Partial setup must not be described as a complete evidence library.

The importer and authenticated original-download routes are included in the repository. Core E1–E5 workflow does not require the originals to start; source search is incomplete without import. Never make this directory a web-server static alias, publish index databases, or put tokens in download URLs.

Public regression fixtures contain only the already implemented output texts and transition fields, extracted from previously verified source documents. These baselines detect unintended program changes but do not claim an independent re-audit of the private originals.
