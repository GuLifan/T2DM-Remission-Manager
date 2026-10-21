# Private evidence configuration

Medical source originals and stakeholder materials are deliberately not redistributed through Git. Do not obtain arbitrary lookalike documents or edit the importer to accept an unreviewed file. Authorized operators must privately obtain the exact approved resources from the project owner.

The paths, sizes and SHA-256 values are in [`resources/evidence/manifest.json`](../resources/evidence/manifest.json). Place the files underneath `resources/evidence/` with exactly those relative paths. The `.gitignore` excludes originals, including the Markdown stakeholder file.

From `backend`, run `uv run --no-sync python -m app.evidence_cli`. It checks source hashes and expected page/section counts, imports each source atomically, and skips unchanged sources. The expected counts are 13 / 124 / 15 PDF pages and 15 Markdown sections. It does not initialize accounts or seed cases. Partial setup must not be described as a complete evidence library.

The importer and authenticated original-download routes are included in the repository. Core E1–E5 workflow does not require the originals to start; source search is incomplete without import. Never make this directory a web-server static alias, publish index databases, or put tokens in download URLs.

Public regression fixtures contain only the already implemented output texts and transition fields, extracted from previously verified source documents. These baselines detect unintended program changes but do not claim an independent re-audit of the private originals.

## 中文说明

医学原件和甲方内部材料不通过 Git 再分发。授权部署者须从项目维护者私下取得四份已批准原件，按 `resources/evidence/manifest.json` 所列路径、大小和 SHA-256 配置到该目录。不要下载相似文档冒充，不要绕过哈希。

在 `backend` 运行 `uv run --no-sync python -m app.evidence_cli`。预期三份 PDF 分别13、124、15页，Markdown为15个章节；重复导入跳过。该命令不初始化账号或病例。未配置时核心临床流程可运行，但全文检索不完整。不得把原件目录设为静态免登录路径。

现有0.4.2升级补丁不会覆盖资源或索引，不要求重新导入。公开回归基线只保留程序已有输出及转移，不能代替内部原件核对或医学验收。
