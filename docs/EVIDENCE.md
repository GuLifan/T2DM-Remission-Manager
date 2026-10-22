# Evidence resources / 医学依据资源

The complete release contains only the approved path/hash manifest and resource instructions. Private PDFs and stakeholder originals are not redistributed. Existing replacement retains the installed originals and the current evidence index in the configured runtime database; no reimport is required.

完整包仅包含已批准的路径/哈希清单和配置说明，不再分发私有PDF或甲方原件。现有工程替换时保留原件和运行数据库中的当前依据索引，不需要重新导入。

For an intentionally new evidence setup, privately obtain the exact four approved files, place them under `resources/evidence/` following [the manifest](../resources/evidence/manifest.json), and run the following from `backend` after configuring the intended data directory:

仅主动建立新的依据库时，从维护者私下取得四份准确原件，按[清单](../resources/evidence/manifest.json)放到`resources/evidence/`，确认目标数据目录后，在`backend`执行：

```bash
uv run --no-sync python -m app.evidence_cli
```

The importer checks hashes and expected counts:13/124/15 PDF pages and15 Markdown sections. Unchanged sources are skipped. It does not create accounts or cases. Core workflow can start without originals, but full-text evidence is incomplete until configured. Missing resources must not be replaced by arbitrary similar files.

导入校验哈希和预期数量：三份PDF为13/124/15页，Markdown为15章节；未变化来源跳过，不创建账号或病例。未配置原件时核心流程可启动，但全文依据不完整；不能用相似材料冒充缺失原件。

Search and original downloads require login. Never map resources, databases, keys or backups to anonymous static hosting; do not embed tokens in URLs.

检索及原件下载须登录。不得把资源、数据库、密钥或备份设为免登录静态资源，不在URL中放令牌。
