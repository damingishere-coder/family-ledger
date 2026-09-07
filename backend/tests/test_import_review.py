import io
import json

from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.models import Account, HouseholdMember, ImportRecord, SnapshotEntry


CSV = "盘点日期,家庭成员,账户名称,账户类型,金额\n2026-04-15,峰峰,微信,wallet,100\n2026-04-15,峰峰,支付宝,wallet,\n"


def preview(client, content=CSV):
    result = client.post('/api/import/batch/preview', files=[('files', ('history.csv', content.encode(), 'text/csv'))])
    assert result.status_code == 200, result.text
    return result.json()


def confirm(client, review, months=None):
    return client.post('/api/import/batch/confirm', json={
        'token': review['token'], 'review_id': review['review_id'], 'months': months or ['2026-04']})


def remap(client, review, owner='贤贤', kind='wallet'):
    key = review['groups'][0]['key']
    response = client.post('/api/import/batch/review', json={
        'token': review['token'], 'mappings': {key: {'member_name': owner, 'account_type': kind}}})
    assert response.status_code == 200, response.text
    return response.json()


def test_preview_read_only_then_atomic_import_and_idempotency(client):
    result = preview(client)
    assert client.get('/api/snapshots').json() == []
    assert client.get('/api/accounts').json() == []
    response = confirm(client, result)
    assert response.status_code == 200, response.text
    assert response.json()['success_rows'] == 2
    assert confirm(client, result).json()['id'] == response.json()['id']
    assert preview(client)['months'][0]['status'] == 'unchanged'
    snapshots = client.get('/api/snapshots').json()
    detail = client.get(f"/api/snapshots/{snapshots[0]['id']}").json()
    assert [e['amount_cents'] for e in detail['entries']] == [10000, None]
    report = client.get('/api/imports').json()[0]['report']
    assert len(report['entry_baselines']) == 2


def test_remapping_updates_historical_entry_without_recreating_snapshot(client):
    assert confirm(client, preview(client)).status_code == 200
    original = client.get('/api/snapshots').json()[0]['id']
    review = remap(client, preview(client))
    assert review['months'][0]['status'] == 'update'
    result = confirm(client, review)
    assert result.status_code == 200, result.text
    detail = client.get(f'/api/snapshots/{original}').json()
    assert detail['entries'][0]['member_name'] == '贤贤'
    assert detail['entries'][0]['amount_cents'] == 10000
    assert preview(client)['months'][0]['status'] == 'unchanged'


def test_manual_edits_and_manual_month_are_protected(client, create_account):
    assert confirm(client, preview(client)).status_code == 200
    snap = client.get('/api/snapshots').json()[0]
    entry = client.get(f"/api/snapshots/{snap['id']}").json()['entries'][0]
    client.put(f"/api/snapshots/{snap['id']}/entries/{entry['id']}", json={'amount_cents': 12345})
    review = remap(client, preview(client))
    assert review['months'][0]['status'] == 'conflict'
    assert confirm(client, review).status_code == 422
    assert client.get(f"/api/snapshots/{snap['id']}").json()['entries'][0]['amount_cents'] == 12345
    manual = client.post('/api/snapshots', json={'snapshot_date': '2026-05-31'}).json()
    client.post(f"/api/snapshots/{manual['id']}/complete", json={'allow_incomplete': True})
    candidate = preview(client, CSV.replace('2026-04', '2026-05'))
    assert candidate['months'][0]['status'] == 'conflict'


def test_database_drift_and_stale_review_block_writes(client):
    review = preview(client)
    changed = remap(client, review)
    assert confirm(client, review).status_code == 409
    client.post('/api/members', json={'name': '新成员'})
    assert confirm(client, changed).status_code == 409
    assert client.get('/api/snapshots').json() == []


def test_manual_account_move_is_protected_during_source_update(client):
    assert confirm(client, preview(client)).status_code == 200
    with Session(client.app.state.engine) as session:
        account = session.query(Account).filter_by(name='微信').one()
        member = HouseholdMember(name='贤贤')
        session.add(member); session.flush()
        account.member_id = member.id
        account_id = account.id
        session.commit()
    review = preview(client, CSV.replace(',100', ',200'))
    assert review['months'][0]['status'] == 'conflict'
    assert confirm(client, review).status_code == 422
    with Session(client.app.state.engine) as session:
        assert session.get(Account, account_id).member.name == '贤贤'
        assert session.query(Account).count() == 2


def test_unchanged_manual_edit_is_not_adopted_as_import_baseline(client):
    assert confirm(client, preview(client)).status_code == 200
    snap = client.get('/api/snapshots').json()[0]
    entry = client.get(f"/api/snapshots/{snap['id']}").json()['entries'][0]
    client.put(f"/api/snapshots/{snap['id']}/entries/{entry['id']}", json={'amount_cents': 20000})
    corrected = CSV.replace(',100', ',200').replace('支付宝,wallet,\n', '支付宝,wallet,50\n')
    review = preview(client, corrected)
    assert [r['status'] for r in review['months'][0]['entries']] == ['unchanged', 'update']
    assert confirm(client, review).status_code == 200
    subsequent = preview(client, corrected.replace(',200', ',300'))
    assert subsequent['months'][0]['status'] == 'conflict'
    assert confirm(client, subsequent).status_code == 422
    assert client.get(f"/api/snapshots/{snap['id']}").json()['entries'][0]['amount_cents'] == 20000


def test_corrected_source_updates_raw_evidence_and_remains_idempotent(client):
    assert confirm(client, preview(client)).status_code == 200
    corrected = CSV.replace(',100', ',200')
    review = preview(client, corrected)
    assert review['months'][0]['status'] == 'update'
    assert confirm(client, review).status_code == 200
    snapshot = client.get('/api/snapshots').json()[0]
    entry = client.get(f"/api/snapshots/{snapshot['id']}").json()['entries'][0]
    assert entry['amount_cents'] == 20000
    assert entry['legacy_raw_value'] == '200'
    assert preview(client, corrected)['months'][0]['status'] == 'unchanged'


def test_unknown_mapping_and_invalid_member_are_rejected(client):
    review = preview(client)
    response = client.post('/api/import/batch/review', json={'token': review['token'], 'mappings': {
        'unknown': {'member_name': '峰峰', 'account_type': 'wallet'}}})
    assert response.status_code == 422
    response = client.post('/api/import/batch/review', json={'token': review['token'], 'mappings': {
        review['groups'][0]['key']: {'member_name': '不存在', 'account_type': 'wallet'}}})
    assert response.status_code == 422


def test_ambiguous_loan_direction_requires_confirmation_and_legacy_route_cannot_bypass(client):
    md = '## 2026年4月15日\n### 一、大明同学明细\n借款：100\n'
    response = client.post('/api/import/batch/preview', files=[('files', ('a.md', md.encode()))])
    assert response.status_code == 200, response.text
    review = response.json()
    assert review['groups'][0]['source_member'] == '峰峰'
    assert review['months'][0]['status'] == 'needs_review'
    assert confirm(client, review).status_code == 422
    assert client.post('/api/import/legacy', files={'file': ('a.md', md.encode())}).status_code == 422
    reviewed = remap(client, review, owner='峰峰', kind='other_liability')
    assert confirm(client, reviewed).status_code == 200
    assert client.get('/api/snapshots').json()[0]['total_liabilities_cents'] == 10000


def test_multi_file_excel_priority_and_markdown_date_evidence(client):
    workbook = Workbook(); sheet = workbook.active
    sheet.title = '家庭存款明细(26.4月）'
    for row in [['2026-03-15'], [None, '招商银行', '微信', '支付宝', '总计'],
                ['大明同学存款', 100, 10, 0, 110], ['贤贤存款', 0, 20, 0, 20],
                ['大明额度', 1000], ['大明可用', 990], ['大明账单', 10],
                ['贤贤额度', 0], ['贤贤可用', 0], ['贤贤账单', 0]]:
        sheet.append(row)
    out = io.BytesIO(); workbook.save(out)
    md = '## 2026年4月15日\n### 一、大明同学明细\n| 微信 | 支付宝 |\n| -- | -- |\n| 999 | 0 |\n'
    alone = client.post('/api/import/batch/preview', files=[('files', ('a.xlsx', out.getvalue()))]).json()
    assert alone['months'][0]['status'] == 'blocked'
    response = client.post('/api/import/batch/preview', files=[('files', ('a.xlsx', out.getvalue())), ('files', ('a.md', md.encode()))])
    assert response.status_code == 200, response.text
    review = response.json()
    assert review['months'][0]['status'] == 'new', review['months'][0]['errors']
    assert review['evidence'][0]['excel_cents'] == 1000
    assert review['evidence'][0]['markdown_cents'] == 99900
    assert confirm(client, review).status_code == 200


def test_bulk_amount_update_is_all_or_nothing(client):
    assert confirm(client, preview(client)).status_code == 200
    snap = client.get('/api/snapshots').json()[0]
    entries = client.get(f"/api/snapshots/{snap['id']}").json()['entries']
    response = client.put(f"/api/snapshots/{snap['id']}/entries", json={'entries': [
        {'id': entries[0]['id'], 'amount_cents': 500, 'expected_amount_cents': 10000},
        {'id': entries[1]['id'], 'amount_cents': 500, 'expected_amount_cents': 999}]})
    assert response.status_code == 409
    assert client.get(f"/api/snapshots/{snap['id']}").json()['entries'][0]['amount_cents'] == 10000


def test_dashboard_can_select_historical_month_and_counts_entries(client):
    assert confirm(client, preview(client)).status_code == 200
    april = client.get('/api/snapshots').json()[0]['id']
    may = preview(client, CSV.replace('2026-04', '2026-05').replace(',100', ',200'))
    assert confirm(client, may, ['2026-05']).status_code == 200
    assert client.get('/api/dashboard').json()['current']['total_assets_cents'] == 20000
    selected = client.get(f'/api/dashboard?snapshot_id={april}').json()
    assert selected['current']['total_assets_cents'] == 10000
    assert selected['current']['total_entries'] == 2
    assert len(selected['periods']) == 2
    assert client.get('/api/dashboard?snapshot_id=99999').status_code == 404


def test_legacy_repair_hashes_accept_uppercase_but_require_original_entry_values(client):
    assert confirm(client, preview(client)).status_code == 200
    with Session(client.app.state.engine) as session:
        record = session.query(ImportRecord).one()
        report = json.loads(record.report_json)
        record.source_type = 'repair-xlsx'
        record.report_json = json.dumps({'source_sha256': {k: v.upper() for k, v in report['source_sha256'].items()}})
        session.commit()
    assert remap(client, preview(client))['months'][0]['status'] == 'update'
    with Session(client.app.state.engine) as session:
        entry = session.query(SnapshotEntry).first()
        entry.notes = '手工备注'
        session.commit()
    assert remap(client, preview(client))['months'][0]['status'] == 'conflict'


def test_commit_failure_rolls_back_all_months(client, monkeypatch):
    review = preview(client, CSV + CSV.split('\n', 1)[1].replace('2026-04', '2026-05'))
    from app.services import import_review
    original = import_review._find_or_create_member
    calls = 0
    def failing(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise ValueError('模拟写入失败')
        return original(*args, **kwargs)
    monkeypatch.setattr(import_review, '_find_or_create_member', failing)
    assert confirm(client, review, ['2026-04', '2026-05']).status_code == 422
    assert client.get('/api/snapshots').json() == []
    assert client.get('/api/accounts').json() == []
