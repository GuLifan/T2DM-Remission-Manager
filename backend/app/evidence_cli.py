"""从部署包白名单导入依据；不初始化账号，不读取其他目录或改写病例。"""
import json
from dataclasses import asdict

from app.config import PROJECT_ROOT
from app.repository.database import SessionLocal
from app.repository.migrations import run_migrations
from app.services.evidence_import import DEFAULT_EVIDENCE_SOURCES, import_evidence_source


def main():
    run_migrations()
    with SessionLocal() as db:
        for source in DEFAULT_EVIDENCE_SOURCES:
            result = import_evidence_source(db, source_root=PROJECT_ROOT / "resources" / "evidence", source=source)
            print(json.dumps(asdict(result), ensure_ascii=False))


if __name__ == "__main__":
    main()
