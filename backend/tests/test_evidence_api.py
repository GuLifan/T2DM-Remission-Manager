"""M6-B 医学依据状态、检索、权限与隐私审计接口测试。"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import delete, select

from app.models.audit import AuditLog
from app.models.evidence import Evidence, EvidenceChunk
from app.repository import evidence as evidence_repo
from app.services.evidence_import import DEFAULT_EVIDENCE_SOURCES


@pytest.fixture(autouse=True)
def clean_evidence_api_data(client, db_session):
    """隔离每项接口测试的依据与检索审计数据。"""
    del client  # 触发 lifespan，确保迁移完成
    db_session.execute(delete(AuditLog).where(AuditLog.action == "evidence_search"))
    db_session.execute(delete(EvidenceChunk))
    db_session.execute(delete(Evidence))
    db_session.commit()
    yield
    db_session.execute(delete(AuditLog).where(AuditLog.action == "evidence_search"))
    db_session.execute(delete(EvidenceChunk))
    db_session.execute(delete(Evidence))
    db_session.commit()


def _seed_complete_library(db_session) -> None:
    """用非版权测试文本建立四份完整来源。"""
    texts = {
        "china-remission-consensus-2021": "共同检索词。糖尿病缓解需要医生核对。",
        "china-diabetes-guideline-2024": "共同检索词。指南定位内容与 HbA1c。",
        "expert-remission-consensus-2026": "common term and remission evidence.",
        "clinical-flow-locked-v1": "共同检索词。停药时间与隐私关键词ABC。",
    }
    for index, source in enumerate(DEFAULT_EVIDENCE_SOURCES, start=1):
        content = texts[source.source_key]
        evidence_repo.replace_evidence(
            db_session,
            source_key=source.source_key,
            title=source.title,
            source_type=source.source_type,
            file_name=source.relative_path.name,
            sha256=source.expected_sha256 or str(index) * 64,
            page_count=source.expected_page_count,
            text_page_count=source.expected_page_count,
            chunks=[
                evidence_repo.EvidenceChunkInput(
                    ordinal=1,
                    page_no=index if source.source_type == "pdf" else None,
                    section="九、测试章节" if source.source_type == "markdown" else None,
                    content=content,
                    search_text=content,
                    char_count=len(content),
                )
            ],
        )
    db_session.commit()


def test_evidence_endpoints_require_login(client) -> None:
    """状态和检索均不得匿名访问。"""
    assert client.get("/api/evidence/status").status_code == 401
    assert client.get("/api/evidence/search", params={"q": "缓解"}).status_code == 401


def test_status_distinguishes_not_imported_from_ready(client, doctor, db_session) -> None:
    """状态接口明确返回四份预期材料及整体是否可搜索。"""
    empty = client.get("/api/evidence/status", headers=doctor["headers"])
    assert empty.status_code == 200
    assert empty.json()["expected_count"] == 4
    assert empty.json()["indexed_count"] == 0
    assert empty.json()["searchable"] is False
    assert all(item["ready"] is False for item in empty.json()["materials"])

    _seed_complete_library(db_session)
    ready = client.get("/api/evidence/status", headers=doctor["headers"])
    assert ready.status_code == 200
    body = ready.json()
    assert body["expected_count"] == 4
    assert body["indexed_count"] == 4
    assert body["searchable"] is True
    assert body["last_imported_at"] is not None
    assert all(item["ready"] is True for item in body["materials"])


def test_search_is_blocked_until_all_sources_are_ready(client, doctor, db_session) -> None:
    """缺少任一批准来源时不得伪装成完整检索库。"""
    source = DEFAULT_EVIDENCE_SOURCES[0]
    evidence_repo.replace_evidence(
        db_session,
        source_key=source.source_key,
        title=source.title,
        source_type=source.source_type,
        file_name=source.relative_path.name,
        sha256=source.expected_sha256 or "a" * 64,
        page_count=source.expected_page_count,
        text_page_count=source.expected_page_count,
        chunks=[
            evidence_repo.EvidenceChunkInput(
                ordinal=1,
                page_no=1,
                section=None,
                content="糖尿病缓解",
                search_text="糖尿病缓解",
                char_count=6,
            )
        ],
    )
    db_session.commit()

    response = client.get(
        "/api/evidence/search",
        params={"q": "缓解"},
        headers=doctor["headers"],
    )
    assert response.status_code == 422
    assert response.json()["code"] == "EVIDENCE_NOT_READY"
    assert "尚未完整导入" in response.json()["detail"]
    audits = db_session.scalars(select(AuditLog).where(AuditLog.action == "evidence_search")).all()
    assert audits == []


def test_status_rejects_mismatched_source_metadata(client, doctor, db_session) -> None:
    """稳定键相同但标题或类型错误时不能冒充已批准材料。"""
    _seed_complete_library(db_session)
    item = db_session.scalar(
        select(Evidence).where(Evidence.source_key == DEFAULT_EVIDENCE_SOURCES[0].source_key)
    )
    assert item is not None
    item.title = "错误材料标题"
    db_session.commit()

    response = client.get("/api/evidence/status", headers=doctor["headers"])
    assert response.status_code == 200
    assert response.json()["indexed_count"] == 3
    assert response.json()["searchable"] is False


def test_search_returns_stable_plain_text_sources_and_total(client, doctor, db_session) -> None:
    """检索返回模式、总数、当前数量以及可复核页码/章节。"""
    _seed_complete_library(db_session)

    common = client.get(
        "/api/evidence/search",
        params={"q": "共同检索词", "limit": 2},
        headers=doctor["headers"],
    )
    assert common.status_code == 200, common.text
    body = common.json()
    assert body["search_mode"] == "fts5_trigram"
    assert body["materials_indexed"] == 4
    assert body["total"] == 3
    assert body["returned"] == 2
    assert len(body["items"]) == 2
    assert all("<mark>" not in item["snippet"] for item in body["items"])

    locked = client.get(
        "/api/evidence/search",
        params={"q": "停药时间"},
        headers=doctor["headers"],
    )
    assert locked.status_code == 200
    hit = locked.json()["items"][0]
    assert hit["title"] == "临床流程锁定稿 v1.0"
    assert hit["page_no"] is None
    assert hit["section"] == "九、测试章节"

    short = client.get(
        "/api/evidence/search",
        params={"q": " 缓解 "},
        headers=doctor["headers"],
    )
    assert short.status_code == 200
    assert short.json()["query"] == "缓解"
    assert short.json()["search_mode"] == "like"


def test_search_validation_uses_doctor_readable_messages(client, doctor, db_session) -> None:
    """长度与数量边界在访问仓储前拦截，并返回自然语言。"""
    _seed_complete_library(db_session)
    cases = [
        ({"q": "a"}, "至少 2 个字符"),
        ({"q": "a" * 101}, "不能超过 100"),
        ({"q": "缓解", "limit": 0}, "1 到 50"),
        ({"q": "缓解", "limit": 51}, "1 到 50"),
    ]
    for params, message in cases:
        response = client.get("/api/evidence/search", params=params, headers=doctor["headers"])
        assert response.status_code == 422
        assert message in response.json()["detail"]


def test_search_audit_excludes_query_and_content(client, doctor, db_session) -> None:
    """审计证明检索发生，但不得长期保存原始检索词或命中正文。"""
    _seed_complete_library(db_session)
    query = "隐私关键词ABC"
    response = client.get(
        "/api/evidence/search",
        params={"q": query},
        headers=doctor["headers"],
    )
    assert response.status_code == 200
    assert response.json()["total"] == 1

    audit = db_session.scalar(
        select(AuditLog).where(AuditLog.action == "evidence_search").order_by(AuditLog.id.desc())
    )
    assert audit is not None
    detail = json.loads(audit.detail or "{}")
    assert detail == {
        "query_chars": len(query),
        "search_mode": "fts5_trigram",
        "result_count": 1,
        "returned_count": 1,
    }
    assert query not in (audit.detail or "")
    assert "停药时间" not in (audit.detail or "")


def test_enabled_doctor_can_search_global_evidence(client, doctor, db_session) -> None:
    """依据为全局只读资料，普通医生不需要患者归属即可查阅。"""
    _seed_complete_library(db_session)
    registered = client.post(
        "/api/auth/register",
        json={
            "username": "evidence_reader",
            "display_name": "依据查阅医生",
            "department": "内分泌科",
            "password": "Evidence-Passw0rd",
            "password_confirm": "Evidence-Passw0rd",
        },
    )
    assert registered.status_code == 201
    login = client.post(
        "/api/auth/login",
        json={"username": "evidence_reader", "password": "Evidence-Passw0rd"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['token']}"}

    status = client.get("/api/evidence/status", headers=headers)
    search = client.get("/api/evidence/search", params={"q": "remission"}, headers=headers)
    assert status.status_code == 200
    assert status.json()["searchable"] is True
    assert search.status_code == 200
    assert search.json()["total"] == 1
