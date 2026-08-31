from __future__ import annotations

import difflib
import json
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..importers.common import ParsedSnapshot
from ..models import Account, HouseholdMember, ImportRecord, Snapshot, SnapshotEntry
from .calculations import calculate_totals


def _find_or_create_member(session: Session, name: str) -> HouseholdMember:
    member = session.scalar(select(HouseholdMember).where(HouseholdMember.name == name))
    if member is None:
        member = HouseholdMember(name=name, display_name=name)
        session.add(member)
        session.flush()
    return member


def _find_or_create_account(session: Session, member: HouseholdMember, entry) -> Account:
    account = session.scalar(
        select(Account).where(Account.member_id == member.id, Account.name == entry.account_name)
    )
    if account is None:
        account = Account(
            member_id=member.id,
            name=entry.account_name,
            institution=entry.institution,
            account_type=entry.account_type,
            credit_limit_cents=entry.credit_limit_cents,
            include_in_net_worth=entry.include_in_net_worth,
            legacy_name=entry.raw_name,
        )
        session.add(account)
        session.flush()
    return account


def import_snapshots(
    session: Session,
    parsed_snapshots: list[ParsedSnapshot],
    source_filename: str,
    source_type: str,
) -> ImportRecord:
    report: dict = {"source": source_filename, "snapshots": [], "warnings": [], "errors": []}
    success_rows = 0
    warning_rows = 0
    error_rows = 0

    for parsed in parsed_snapshots:
        existing = session.scalar(
            select(Snapshot).where(
                Snapshot.snapshot_date == parsed.snapshot_date,
                Snapshot.legacy_source == source_filename,
            )
        )
        if existing:
            warning = f"{parsed.snapshot_date.isoformat()} 已从同名来源导入，已跳过"
            report["warnings"].append(warning)
            warning_rows += 1
            continue

        snapshot = Snapshot(
            snapshot_date=parsed.snapshot_date,
            title=f"{parsed.snapshot_date.isoformat()} 家庭资产",
            status="completed",
            legacy_source=source_filename,
            legacy_summary_json=json.dumps(parsed.legacy_summary, ensure_ascii=False),
        )
        session.add(snapshot)
        session.flush()
        names_by_member: dict[str, list[str]] = defaultdict(list)

        for entry in parsed.entries:
            try:
                member = _find_or_create_member(session, entry.member_name)
                for prior_name in names_by_member[entry.member_name]:
                    ratio = difflib.SequenceMatcher(None, prior_name, entry.account_name).ratio()
                    if ratio >= 0.82 and prior_name != entry.account_name:
                        entry.warnings.append(
                            f"疑似重复账户：{prior_name} / {entry.account_name}，未自动合并"
                        )
                names_by_member[entry.member_name].append(entry.account_name)
                account = _find_or_create_account(session, member, entry)
                snapshot.entries.append(
                    SnapshotEntry(
                        account_id=account.id,
                        amount_cents=entry.amount_cents,
                        credit_limit_cents=entry.credit_limit_cents,
                        include_in_net_worth=entry.include_in_net_worth,
                        member_name=entry.member_name,
                        account_name=entry.account_name,
                        institution=entry.institution,
                        account_type=entry.account_type,
                        legacy_raw_name=entry.raw_name,
                        legacy_raw_value=entry.raw_value,
                    )
                )
                success_rows += 1
                if entry.warnings:
                    warning_rows += 1
                    report["warnings"].extend(
                        f"{parsed.snapshot_date} {entry.account_name}：{warning}"
                        for warning in entry.warnings
                    )
            except Exception as exc:  # keep a row-level import report
                error_rows += 1
                report["errors"].append(
                    f"{parsed.snapshot_date} {entry.member_name}/{entry.account_name}：{exc}"
                )

        session.flush()
        totals = calculate_totals(snapshot.entries)
        differences = []
        for key in ("total_assets_cents", "total_liabilities_cents", "net_worth_cents"):
            legacy_value = parsed.legacy_summary.get(key)
            calculated = getattr(totals, key)
            if legacy_value is not None and legacy_value != calculated:
                differences.append(
                    {"field": key, "legacy_cents": legacy_value, "calculated_cents": calculated}
                )
        if differences:
            warning_rows += 1
        report["snapshots"].append(
            {
                "date": parsed.snapshot_date.isoformat(),
                "entries": len(snapshot.entries),
                "calculated": totals.__dict__,
                "legacy_summary": parsed.legacy_summary,
                "differences": differences,
                "warnings": parsed.warnings,
            }
        )
        report["warnings"].extend(parsed.warnings)
        warning_rows += len(parsed.warnings)

    status = "success"
    if error_rows:
        status = "partial"
    elif warning_rows:
        status = "warning"
    record = ImportRecord(
        source_filename=source_filename,
        source_type=source_type,
        status=status,
        total_rows=success_rows + error_rows,
        success_rows=success_rows,
        warning_rows=warning_rows,
        error_rows=error_rows,
        report_json=json.dumps(report, ensure_ascii=False),
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def import_record_to_dict(record: ImportRecord) -> dict:
    return {
        "id": record.id,
        "source_filename": record.source_filename,
        "source_type": record.source_type,
        "imported_at": record.imported_at.isoformat(),
        "status": record.status,
        "total_rows": record.total_rows,
        "success_rows": record.success_rows,
        "warning_rows": record.warning_rows,
        "error_rows": record.error_rows,
        "report": json.loads(record.report_json),
    }
