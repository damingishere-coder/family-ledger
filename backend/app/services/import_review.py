from __future__ import annotations

from dataclasses import asdict
import hashlib
import json

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ..models import Account, HouseholdMember, ImportRecord, Snapshot, SnapshotEntry
from ..schemas import ACCOUNT_TYPES
from .backups import export_payload
from .calculations import calculate_totals
from .import_sources import proposed_entries
from .imports import _reconcile, _find_or_create_member, _duplicate_entry_errors

RULE_VERSION = "source-ownership-v2"
FIELDS = ("member_name", "account_name", "account_type", "institution", "amount_cents",
          "credit_limit_cents", "include_in_net_worth")


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def database_signature(session: Session) -> str:
    payload = export_payload(session)
    payload.pop("generated_at", None)
    return digest(payload)


def values(entry) -> dict:
    return {field: getattr(entry, field) for field in FIELDS}


def identity(entry) -> tuple:
    return tuple(getattr(entry, field) for field in FIELDS[:4])


def group_key(entry) -> str:
    return digest(identity(entry))[:24]


def entry_state(entry: SnapshotEntry) -> dict:
    return {**values(entry), "account_id": entry.account_id, "notes": entry.notes,
            "legacy_raw_name": entry.legacy_raw_name, "legacy_raw_value": entry.legacy_raw_value}


def account_state(account: Account) -> dict:
    return {field: getattr(account, field) for field in (
        "member_id", "name", "account_type", "institution", "credit_limit_cents", "billing_day",
        "include_in_net_worth", "is_archived", "sort_order", "notes", "legacy_name")}


def saved_rules(session: Session) -> dict:
    result = {}
    for record in session.scalars(select(ImportRecord).order_by(ImportRecord.id)):
        report = json.loads(record.report_json)
        if report.get("rule_version") == RULE_VERSION:
            result.update(report.get("mappings", {}))
    return result


def build_review(session: Session, raw_snapshots, audit: dict, mappings: dict | None = None) -> tuple[dict, list]:
    mappings = mappings or {}
    rules = {**saved_rules(session), **mappings}
    snapshots = proposed_entries(raw_snapshots)
    valid_members = {"峰峰", "贤贤", "家庭公共", "其他"}
    valid_members.update(session.scalars(select(HouseholdMember.name)).all())
    valid_members.update(e.member_name for s in snapshots for e in s.entries if not e.ownership_unresolved)
    known_groups = {group_key(e) for s in snapshots for e in s.entries}
    if set(mappings) - known_groups:
        raise ValueError("核对内容含有未知账户，请重新预览")
    groups = {}
    for snapshot in snapshots:
        for entry in snapshot.entries:
            key = group_key(entry)
            choice = rules.get(key)
            source_member = None if entry.ownership_unresolved else entry.member_name
            if choice:
                if choice.get("member_name") not in valid_members or choice.get("account_type") not in ACCOUNT_TYPES:
                    raise ValueError("请选择有效成员和账户类型")
                entry.member_name, entry.account_type = choice["member_name"], choice["account_type"]
            needs = not choice and (entry.ownership_unresolved or entry.type_unresolved)
            setattr(entry, "review_key", key)
            setattr(entry, "needs_review", needs)
            group = groups.setdefault(key, {"key": key, "account_name": entry.account_name,
                "source_member": source_member, "member_name": entry.member_name if not needs else source_member,
                "account_type": entry.account_type, "needs_review": needs,
                "direction_unclear": entry.type_unresolved, "rule_saved": key in saved_rules_cache(session),
                "months": [], "sources": []})
            month = snapshot.snapshot_date.strftime("%Y-%m") if snapshot.snapshot_date else snapshot.source_sheet
            if month not in group["months"]:
                group["months"].append(month)
            location = f"{entry.source_filename} · {entry.source_location or snapshot.source_sheet or '明细行'}"
            if location not in group["sources"]:
                group["sources"].append(location)

    records = list(session.scalars(select(ImportRecord).order_by(ImportRecord.id)))
    baselines = {}
    legacy_verified = False
    for record in records:
        report = json.loads(record.report_json)
        baselines.update(report.get("entry_baselines", {}))
        old_hashes = {name: value.lower() for name, value in report.get("source_sha256", {}).items()}
        if record.source_type == "repair-xlsx" and old_hashes == audit["source_sha256"]:
            legacy_verified = True
    legacy_accounts = {}
    for raw in sorted(raw_snapshots, key=lambda s: str(s.snapshot_date or '')):
        if raw.status != 'importable':
            continue
        for entry in raw.entries:
            candidate = legacy_accounts.setdefault(identity(entry), {})
            candidate['include_in_net_worth'] = entry.include_in_net_worth
            if entry.credit_limit_cents is not None:
                candidate['credit_limit_cents'] = entry.credit_limit_cents
            if entry.billing_day is not None:
                candidate['billing_day'] = entry.billing_day
    retire_candidates = []
    for account in session.scalars(select(Account)):
        key = (account.member.name, account.name, account.account_type, account.institution)
        expected = legacy_accounts.get(key)
        if legacy_verified and expected and not account.notes and account.sort_order == 0 and not account.is_archived:
            if all(getattr(account, field) == expected.get(field) for field in
                   ('credit_limit_cents', 'billing_day', 'include_in_net_worth')):
                retire_candidates.append(account.id)
    existing = {s.snapshot_date.strftime("%Y-%m"): s for s in session.scalars(
        select(Snapshot).where(Snapshot.status == "completed"))}
    counts = {}
    for snapshot in snapshots:
        if snapshot.snapshot_date:
            month = snapshot.snapshot_date.strftime("%Y-%m")
            counts[month] = counts.get(month, 0) + 1
    months = []
    for raw, snapshot in zip(raw_snapshots, snapshots):
        month = snapshot.snapshot_date.strftime("%Y-%m") if snapshot.snapshot_date else None
        current = existing.get(month)
        errors = list(snapshot.blocking_errors)
        reconciliation, warnings, raw_errors = _reconcile(raw)
        if any(before.account_type != after.account_type for before, after in zip(raw.entries, snapshot.entries)):
            warnings.append("已按确认的资产或负债类型重新计算，原表汇总仅供对照")
        errors.extend(raw_errors)
        errors.extend(_duplicate_entry_errors(snapshot, require_resolved=False))
        if month and counts[month] > 1:
            errors.append("多个文件包含同月主数据，请保留一份 Excel/CSV 主来源")
        owned = current is None or current.legacy_source in audit["source_sha256"]
        rows = []
        used_ids = set()
        for old, entry in zip(raw.entries, snapshot.entries):
            matches = [] if current is None else [e for e in current.entries if identity(e) in {identity(old), identity(entry)}]
            # After a confirmed mapping, use persisted source coordinates to match
            # later remappings even when owner/type have changed.
            if current:
                source_matches = [e for e in current.entries if
                    baselines.get(str(e.id), {}).get("source_key") == getattr(entry, "review_key")]
                if source_matches:
                    matches = source_matches
            match = matches[0] if len(matches) == 1 else None
            state = "new" if current is None else "conflict"
            reason = "新月份"
            verified = False
            if current and not owned:
                reason = "手工记录或其他来源，保留原值"
            elif current and match and match.id not in used_ids:
                baseline = baselines.get(str(match.id))
                verified = bool(baseline and baseline.get("state") == entry_state(match)
                                and baseline.get("account_state") == account_state(match.account))
                if not baseline and legacy_verified:
                    # Only a source-hash-matched legacy repair can bootstrap a baseline.
                    verified = match.account_id in retire_candidates and values(match) == values(old) and not match.notes and (
                        abs((match.updated_at - match.created_at).total_seconds()) < .01)
                if values(match) == values(entry):
                    state, reason = "unchanged", "与现有记录一致"
                elif verified:
                    state, reason = "update", "来源及原值已核对，可修正归属或类型"
                else:
                    reason = "可能已手工修改或缺少可信基线，保留原值"
                used_ids.add(match.id)
            elif current and len(matches) > 1:
                reason = "现有账户匹配不唯一，保留原值"
            elif current:
                reason = "历史中找不到唯一对应条目，保留原值"
            if getattr(entry, "needs_review"):
                state, reason = "needs_review", "请选择所属成员及账户类型"
            rows.append({"key": getattr(entry, "review_key"), "entry_id": match.id if match else None,
                "source_file": entry.source_filename, "source_location": entry.source_location,
                "raw_name": entry.raw_name, "raw_value": entry.raw_value,
                "source_member": None if old.ownership_unresolved else old.member_name,
                "before": values(match) if match else None, "after": values(entry),
                "billing_day": entry.billing_day, "status": state, "reason": reason,
                "baseline_verified": verified})
        unmatched = [] if not current else [e.id for e in current.entries if e.id not in used_ids]
        if unmatched:
            warnings.append(f"现有记录另有 {len(unmatched)} 条明细，不在本次修正范围，原样保留")
        status = "unchanged"
        if snapshot.status == "ignored":
            status = "ignored"
        elif errors or snapshot.status == "blocked" or not month or not rows:
            status = "blocked"
        elif any(r["status"] == "needs_review" for r in rows):
            status = "needs_review"
        elif any(r["status"] == "conflict" for r in rows):
            status = "conflict"
        elif any(r["status"] in {"new", "update"} for r in rows):
            status = "new" if current is None else "update"
        months.append({"month": month, "source_date": str(snapshot.source_date or ''),
            "source_sheet": snapshot.source_sheet, "snapshot_id": current.id if current else None,
            "status": status, "errors": errors, "warnings": [*snapshot.warnings, *warnings],
            "source_summary": snapshot.legacy_summary,
            "calculated_summary": asdict(calculate_totals(snapshot.entries)),
            "differences": reconciliation["differences"], "entries": rows})
    return {"rule_version": RULE_VERSION, "files": list(audit["source_sha256"]),
        "groups": list(groups.values()), "members": sorted(valid_members), "months": months,
        "evidence": audit["evidence"], "mappings": {k: v for k, v in rules.items() if k in known_groups},
        "retire_candidate_ids": retire_candidates,
        "database_signature": database_signature(session)}, snapshots


def saved_rules_cache(session: Session) -> dict:
    # Scoped to one ORM session; never cache across requests or database restores.
    if "import_rules" not in session.info:
        session.info["import_rules"] = saved_rules(session)
    return session.info["import_rules"]


def commit_review(session: Session, review: dict, snapshots, selected: list[str], audit: dict) -> ImportRecord:
    if not selected or len(set(selected)) != len(selected):
        raise ValueError("请选择至少一个无冲突月份")
    months = {m["month"]: (m, s) for m, s in zip(review["months"], snapshots)}
    if any(m not in months or months[m][0]["status"] not in {"new", "update"} for m in selected):
        raise ValueError("所选月份仍需核对、存在冲突或没有变更")
    old_account_ids, created_account_ids, entry_baselines, success = set(), set(), {}, 0
    applied = []
    for month in sorted(selected):
        item, parsed = months[month]
        snapshot = session.get(Snapshot, item["snapshot_id"]) if item["snapshot_id"] else None
        if snapshot is None:
            snapshot = Snapshot(snapshot_date=parsed.snapshot_date, status="completed",
                title=f"{month} 家庭资产", legacy_source=parsed.entries[0].source_filename,
                legacy_summary_json=json.dumps({**parsed.legacy_summary,
                    "_source_date": str(parsed.source_date or ''), "_source_sheet": parsed.source_sheet}, ensure_ascii=False))
            session.add(snapshot)
            session.flush()
        for row, parsed_entry in zip(item["entries"], parsed.entries):
            if row["status"] not in {"new", "update", "unchanged"}:
                raise ValueError("条目状态改变，请重新核对")
            entry = session.get(SnapshotEntry, row["entry_id"]) if row["entry_id"] else None
            if row["status"] != "unchanged":
                member = _find_or_create_member(session, parsed_entry.member_name)
                matches = list(session.scalars(select(Account).where(Account.member_id == member.id,
                    Account.name == parsed_entry.account_name, Account.account_type == parsed_entry.account_type,
                    Account.institution == parsed_entry.institution)))
                if len(matches) > 1:
                    raise ValueError("目标账户匹配不唯一，已取消整批写入")
                account = matches[0] if matches else Account(member_id=member.id,
                    name=parsed_entry.account_name, account_type=parsed_entry.account_type,
                    institution=parsed_entry.institution, credit_limit_cents=parsed_entry.credit_limit_cents,
                    billing_day=parsed_entry.billing_day, include_in_net_worth=parsed_entry.include_in_net_worth,
                    legacy_name=parsed_entry.raw_name)
                if not matches:
                    session.add(account)
                    session.flush()
                    created_account_ids.add(account.id)
                if account.id in created_account_ids:
                    if parsed_entry.credit_limit_cents is not None:
                        account.credit_limit_cents = parsed_entry.credit_limit_cents
                    if parsed_entry.billing_day is not None:
                        account.billing_day = parsed_entry.billing_day
                    account.include_in_net_worth = parsed_entry.include_in_net_worth
                if entry is None:
                    entry = SnapshotEntry(snapshot_id=snapshot.id, account_id=account.id,
                        legacy_raw_name=parsed_entry.raw_name, legacy_raw_value=parsed_entry.raw_value,
                        **values(parsed_entry))
                    session.add(entry)
                else:
                    old_account_ids.add(entry.account_id)
                    entry.account_id = account.id
                    for field, value in values(parsed_entry).items():
                        setattr(entry, field, value)
                    entry.legacy_raw_name = parsed_entry.raw_name
                    entry.legacy_raw_value = parsed_entry.raw_value
                session.flush()
                success += 1
            assert entry is not None
            # Matching source values alone must not adopt a manual edit as a new
            # trusted baseline while another row in the same month is repaired.
            if row["status"] != "unchanged" or row["baseline_verified"]:
                entry_baselines[str(entry.id)] = {"state": entry_state(entry), "source_key": row["key"],
                    "source_file": parsed_entry.source_filename, "source_location": parsed_entry.source_location,
                    "source_sha256": audit["source_sha256"][parsed_entry.source_filename]}
        applied.append(item)
    # Retire only unused, untouched import-created accounts. Never delete history.
    for account_id in old_account_ids:
        account = session.get(Account, account_id)
        referenced = session.scalar(select(SnapshotEntry.id).where(SnapshotEntry.account_id == account_id).limit(1))
        if account and not referenced and account.legacy_name and not account.notes and (
            account_id in review.get('retire_candidate_ids', []) or abs((account.updated_at - account.created_at).total_seconds()) < .01):
            account.is_archived = True
    session.flush()
    # Newly created accounts can receive metadata from several months in this
    # transaction. Capture their final master state for every affected baseline.
    for entry_id, baseline in entry_baselines.items():
        entry = session.get(SnapshotEntry, int(entry_id))
        baseline["account_state"] = account_state(session.get(Account, entry.account_id))
    report = {**audit, "rule_version": RULE_VERSION, "mappings": review["mappings"],
        "entry_baselines": entry_baselines, "months": applied,
        "warnings": [w for m in applied for w in m["warnings"]], "errors": []}
    record = ImportRecord(source_filename="、".join(audit["source_sha256"]), source_type="review-bundle",
        status="success", total_rows=success, success_rows=success, warning_rows=len(report["warnings"]),
        error_rows=0, report_json=json.dumps(report, ensure_ascii=False))
    session.add(record)
    session.flush()
    if session.execute(text("PRAGMA foreign_key_check")).first():
        raise ValueError("数据关联校验失败，已取消整批写入")
    return record
