"""公网复现的定向回归：隔离库、独立数据库会话及真实API，不连接云端。"""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from test_clinical_v03_cases import v03_test_account as v03_test_account
from test_clinical_v04 import ctx, full_values, phase_values, request, setup_patient

from app.models.event import Event
from app.models.patient import Patient
from app.repository.database import SessionLocal


def start(client, account):
    pid = setup_patient(client, account)
    response = request(client, account, pid, 'full-assessment', **full_values(ctx(client, account, pid)))
    assert response.status_code == 200, response.text
    return pid


def test_event_only_save_rejects_parallel_and_stale_revision(client, v03_test_account, db_session):
    a = v03_test_account
    pid = start(client, a)
    before = client.get(f'/api/patients/{pid}', headers=a['headers']).json()['clinical_revision']
    count = db_session.scalar(select(func.count()).select_from(Event).where(Event.patient_id == pid))
    values = phase_values(ctx(client, a, pid))
    bodies = [{'input_schema_version': 'v0.4', 'expected_revision': before, 'request_id': uuid4().hex, **values} for _ in range(2)]
    def send(body):
        return client.post(f'/api/patients/{pid}/clinical-v03/phase-review', headers=a['headers'], json=body)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(send, bodies))
    assert sorted(r.status_code for r in responses) == [200, 409], [r.text for r in responses]
    db_session.expire_all()
    assert db_session.scalar(select(func.count()).select_from(Event).where(Event.patient_id == pid)) == count + 1
    assert db_session.get(Patient, pid).clinical_revision > before
    assert send({**bodies[0], 'request_id': uuid4().hex}).status_code == 409


def test_no_change_updates_are_atomic_between_independent_sessions(client, v03_test_account):
    from sqlalchemy.orm.exc import StaleDataError

    from app.repository.patients import apply_outcome
    pid = start(client, v03_test_account)
    with SessionLocal() as first, SessionLocal() as second:
        a, b = first.get(Patient, pid), second.get(Patient, pid)
        assert a.clinical_revision == b.clinical_revision
        apply_outcome(first, a, target_state='ST31', transition_ids=['T14A'])
        first.commit()
        with pytest.raises(StaleDataError):
            apply_outcome(second, b, target_state='ST31', transition_ids=['T14A'])
        second.rollback()


def test_empty_constraints_and_hidden_other_plan(client, v03_test_account):
    a = v03_test_account
    pid = setup_patient(client, a)
    values = full_values(ctx(client, a, pid))
    assert request(client, a, pid, 'full-assessment', **{**values, 'f023_constraints': []}).status_code == 422
    assert request(client, a, pid, 'full-assessment', **{**values, 'f023_constraints': ['任意未知选项']}).status_code == 422
    held = request(client, a, pid, 'full-assessment', f026_start='暂缓补充关键资料', f012_pre_tasks='核对资料',
                   regimen_source_id=values['regimen_source_id'], f029_interventions=['其他'])
    assert held.status_code == 200, held.text


def test_other_intervention_follows_plan_through_return_and_hold(client, v03_test_account):
    a = v03_test_account
    pid = setup_patient(client, a)
    values = full_values(ctx(client, a, pid))
    values.update(f029_interventions=['其他'], intervention_other='经核对的个体化干预')
    assert request(client, a, pid, 'full-assessment', **values).status_code == 200
    returned = request(client, a, pid, 'supplemental-decision', transition_id='P03A', doctor_confirmed=True,
                       reason='重大变化', evidence_summary='资料已核对')
    assert returned.status_code == 200, returned.text
    c = ctx(client, a, pid)
    assert c['carried']['intervention_other'] == '经核对的个体化干预'
    held = request(client, a, pid, 'full-assessment', f026_start='暂缓补充关键资料', f012_pre_tasks='核对新资料',
                   regimen_source_id=c['regimen']['id'], medication_review_complete=True)
    assert held.status_code == 200, held.text
    assert ctx(client, a, pid)['carried']['intervention_other'] == '经核对的个体化干预'


@pytest.mark.parametrize('transition', ['P05A','P05B'])
@pytest.mark.parametrize('reason,purpose', [('因器官获益','肾脏保护'),('因体重获益','体重管理')])
def test_benefit_return_requires_consistent_complete_regimen(client, v03_test_account, db_session, transition, reason, purpose):
    # 状态设置仅用于此API守卫单元夹具；完整临床可达性另由58转移走查验证。
    a = v03_test_account
    pid = start(client, a)
    patient = db_session.get(Patient, pid)
    patient.current_state = 'ST60'
    patient.remission_confirmed_date = date(2026,1,1)
    db_session.commit()
    c = ctx(client, a, pid)
    base = {'transition_id': transition, 'doctor_confirmed': True, 'reason': '明确原因', 'evidence_summary': '独立资料',
            'f050_med_status': reason, 'regimen_source_id': c['regimen']['id'], 'medication_review_complete': True}
    assert request(client, a, pid, 'supplemental-decision', **base).status_code == 422
    med = {'name': 'QA获益用药', 'dose': '待核对', 'status': '使用中', 'has_glucose_lowering_effect': True, 'purposes': [purpose]}
    result = request(client, a, pid, 'supplemental-decision', **base, f016_medications=[med])
    assert result.status_code == 200, result.text
    c = ctx(client, a, pid)
    p = client.get(f'/api/patients/{pid}', headers=a['headers']).json()
    assert p['has_glucose_lowering_drug'] is True
    assert c['regimen']['data']['complete'] is True
    assert c['regimen']['data']['medications'][0]['status'] == '使用中'
    assert p['remission_confirmed_date'] == '2026-01-01'


def test_future_post_date_rejected_without_event(client, v03_test_account, db_session):
    a = v03_test_account
    pid = start(client, a)
    p = db_session.get(Patient, pid)
    p.current_state = 'ST60'
    db_session.commit()
    before = db_session.scalar(select(func.count()).select_from(Event).where(Event.patient_id == pid))
    c = ctx(client, a, pid)
    r = request(client, a, pid, 'post-remission', f049_glucose='HbA1c5.9', f049_test_date='2099-01-01',
                f050_med_status='未使用', f055_glucose_state='低于糖尿病诊断阈值', risk_increase_confirmed=False,
                f012_pre_tasks='复核日期', regimen_source_id=c['regimen']['id'], medication_review_complete=True)
    assert r.status_code == 422 and '检测日期' in r.json()['detail']
    assert db_session.scalar(select(func.count()).select_from(Event).where(Event.patient_id == pid)) == before


def test_existing_drug_mismatch_needs_new_explicit_review_not_silent_repair(client, v03_test_account, db_session):
    a = v03_test_account
    pid = start(client, a)
    p = db_session.get(Patient, pid)
    p.has_glucose_lowering_drug = True
    db_session.commit()
    c = ctx(client, a, pid)
    values = phase_values(c)
    refused = request(client, a, pid, 'phase-review', **values)
    assert refused.status_code == 422 and '历史药物' in refused.json()['detail']
    db_session.refresh(p)
    assert p.has_glucose_lowering_drug is True
    saved = request(client, a, pid, 'phase-review', **values, medication_reconciliation_confirmed=True)
    assert saved.status_code == 200, saved.text
    db_session.refresh(p)
    assert p.has_glucose_lowering_drug is False


def test_original_evidence_requires_login_and_whitelist(client, doctor, tmp_path, monkeypatch):
    # 使用临时生成PDF验证同一鉴权/白名单/哈希路径，不要求公开私有医学原件。
    import hashlib
    from dataclasses import replace

    from pypdf import PdfWriter

    from app.api import evidence as evidence_api

    original = evidence_api.DEFAULT_EVIDENCE_SOURCES[0]
    path = tmp_path / 'resources' / 'evidence' / original.relative_path
    path.parent.mkdir(parents=True)
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.write(path)
    source = replace(original, expected_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    monkeypatch.setattr(evidence_api, 'PROJECT_ROOT', tmp_path)
    monkeypatch.setattr(evidence_api, 'DEFAULT_EVIDENCE_SOURCES', (source,))
    key = 'china-remission-consensus-2021'
    assert client.get(f'/api/evidence/materials/{key}/original').status_code == 401
    r = client.get(f'/api/evidence/materials/{key}/original', headers=doctor['headers'])
    assert r.status_code == 200 and r.content.startswith(b'%PDF')
    assert client.get('/api/evidence/materials/not-a-source/original', headers=doctor['headers']).status_code == 422
    path.write_bytes(b'changed source')
    assert client.get(f'/api/evidence/materials/{key}/original', headers=doctor['headers']).status_code == 422
    path.unlink()
    assert client.get(f'/api/evidence/materials/{key}/original', headers=doctor['headers']).status_code == 422


@pytest.mark.parametrize('kind', ['measurement','examination','medication_regimen','duration'])
def test_all_correction_types_append_without_rewriting_source(client, v03_test_account, kind):
    a = v03_test_account
    pid = start(client, a)
    c = ctx(client, a, pid)
    record = c['examinations'][0] if kind == 'examination' else c[{'measurement':'measurement','medication_regimen':'regimen','duration':'duration'}[kind]]
    replacement = dict(record['data'])
    if kind == 'measurement':
        replacement['weight_kg'] = 72
    elif kind == 'examination':
        replacement['value'] = 7.9
    elif kind == 'duration':
        replacement.update(years=1, months=11)
    else:
        replacement.update(complete=True, medications=[{'name':'更正药名','dose':'待核对','status':'使用中','has_glucose_lowering_effect':False,'purposes':['其他']}])
    response = client.post(f'/api/patients/{pid}/clinical-v04/corrections', headers=a['headers'], json={
        'input_schema_version':'v0.4','request_id':uuid4().hex,'expected_revision':c['patient_revision'],
        'kind':kind,'record_id':record['id'],'reason':'核对原始资料后补正','replacement':replacement})
    assert response.status_code == 200, response.text
    assert response.json()['record']['supersedes_id'] == record['id']
    after = client.get(f'/api/patients/{pid}/clinical-v04/records',headers=a['headers']).json()
    assert next(r for r in after if r['id']==record['id'])['data'] == record['data']
    assert response.json()['patient_revision'] > c['patient_revision']
