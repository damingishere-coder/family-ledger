from __future__ import annotations

import difflib
from datetime import date
import json
from collections import defaultdict

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ..importers.common import ParsedSnapshot, month_end, normalize_member_name
from ..models import Account, HouseholdMember, ImportRecord, Snapshot, SnapshotEntry
from .calculations import calculate_totals


def _month_key(value) -> tuple[int, int]:
    return value.year, value.month


def _find_or_create_member(session: Session, name: str) -> HouseholdMember:
    name = normalize_member_name(name)
    member = session.scalar(select(HouseholdMember).where(HouseholdMember.name == name))
    if member is None:
        member = HouseholdMember(name=name, display_name=name)
        session.add(member)
        session.flush()
    return member


def _find_or_create_account(session: Session, member: HouseholdMember, entry) -> Account:
    query = select(Account).where(
        Account.member_id == member.id,
        Account.account_type == entry.account_type,
        Account.name == entry.account_name,
    )
    if entry.institution:
        query = query.where(Account.institution == entry.institution)
    else:
        query = query.where(Account.institution.is_(None))
    matches = list(session.scalars(query.order_by(Account.id)).all())
    if len(matches) > 1:
        raise ValueError(
            f"账户匹配不唯一：{member.name}/{entry.account_type}/{entry.account_name}/{entry.institution or '-'}"
        )
    account = matches[0] if matches else None
    if account is None:
        account = Account(
            member_id=member.id, name=entry.account_name,
            institution=entry.institution, account_type=entry.account_type,
            credit_limit_cents=entry.credit_limit_cents,
            billing_day=entry.billing_day,
            include_in_net_worth=entry.include_in_net_worth,
            legacy_name=entry.raw_name,
        )
        session.add(account)
        session.flush()
    else:
        account.name = entry.account_name
        if entry.institution is not None:
            account.institution = entry.institution
        if entry.credit_limit_cents is not None:
            account.credit_limit_cents = entry.credit_limit_cents
        if entry.billing_day is not None:
            account.billing_day = entry.billing_day
        account.include_in_net_worth = entry.include_in_net_worth
    return account


def _reconcile(parsed: ParsedSnapshot) -> tuple[dict, list[str], list[str]]:
    totals = calculate_totals(parsed.entries)
    calculated = totals.__dict__
    differences: list[dict] = []
    warnings: list[str] = []
    blocking: list[str] = []
    other_liabilities = sum(
        entry.amount_cents or 0
        for entry in parsed.entries
        if entry.account_type == "other_liability" and entry.include_in_net_worth
    )
    receivables = sum(
        entry.amount_cents or 0
        for entry in parsed.entries
        if entry.account_type == "receivable" and entry.include_in_net_worth
    )
    reclassified_investments = sum(
        entry.amount_cents or 0
        for entry in parsed.entries
        if entry.account_type == "investment" and "京东金融" in entry.account_name
    )
    auxiliary = parsed.legacy_summary.get("ignored_auxiliary_totals_cents") or 0
    auxiliary_candidates = {
        value
        for name, value in parsed.legacy_summary.items()
        if name.startswith("auxiliary_detail_") and isinstance(value, int)
    }
    if auxiliary:
        auxiliary_candidates.add(auxiliary)
    for key in ("total_assets_cents", "total_liabilities_cents", "net_worth_cents"):
        source_value = parsed.legacy_summary.get(key)
        if source_value is None:
            continue
        calculated_value = calculated[key]
        if source_value == calculated_value:
            continue
        residual = source_value - calculated_value
        explained = False
        reason = None
        if key == "total_liabilities_cents" and source_value + other_liabilities == calculated_value:
            explained, reason = True, "来源账单小计未含其他负债"
        elif key == "total_liabilities_cents" and residual == reclassified_investments and reclassified_investments:
            explained, reason = True, "来源公式把京东金融列为负债，按确认规则改归投资"
        elif key == "total_assets_cents" and residual == -(receivables + reclassified_investments) and (receivables or reclassified_investments):
            explained, reason = True, "来源汇总排除了待收欠款或把京东金融列为负债"
        elif key == "net_worth_cents" and residual == -(receivables + 2 * reclassified_investments) and (receivables or reclassified_investments):
            explained, reason = True, "来源净值沿用旧的待收欠款排除或京东金融负债分类"
        elif abs(residual) in {abs(value) for value in auxiliary_candidates if value}:
            explained, reason = True, "来源汇总包含重复辅助公式"
        differences.append({
            "field": key, "source_cents": source_value,
            "calculated_cents": calculated_value, "residual_cents": residual,
            "explained": explained, "reason": reason,
        })
        message = f"{key} 来源 {source_value}，按唯一明细计算 {calculated_value}，差额 {residual}"
        if explained:
            warnings.append(f"{message}（{reason}）")
        elif parsed.layout == "legacy-family-monthly-matrix":
            blocking.append(f"无法解释的汇总差异：{message}")
        else:
            warnings.append(message)
    return {"calculated": calculated, "differences": differences}, warnings, blocking


def _completed_months(session: Session) -> set[tuple[int, int]]:
    return {
        _month_key(value)
        for value in session.scalars(
            select(Snapshot.snapshot_date).where(Snapshot.status == "completed")
        ).all()
    }


def _duplicate_entry_errors(parsed: ParsedSnapshot) -> list[str]:
    seen: set[tuple[str, str, str, str | None]] = set()
    errors: list[str] = []
    for entry in parsed.entries:
        key = (entry.member_name, entry.account_type, entry.account_name, entry.institution)
        if key in seen:
            errors.append(f"同一快照存在重复账户：{entry.member_name}/{entry.account_name}")
        seen.add(key)
    return errors


def import_snapshots(
    session: Session,
    parsed_snapshots: list[ParsedSnapshot],
    source_filename: str,
    source_type: str,
    *,
    commit: bool = True,
    extra_report: dict | None = None,
) -> ImportRecord:
    report: dict = {
        "source": source_filename, "snapshots": [], "warnings": [], "errors": [],
        **(extra_report or {}),
    }
    success_rows = warning_rows = 0
    if commit and session.get_bind().dialect.name == "sqlite":
        session.execute(text("BEGIN IMMEDIATE"))
    completed_months = _completed_months(session)
    importable: list[ParsedSnapshot] = []

    for parsed in parsed_snapshots:
        if parsed.status in {"blocked", "ignored"} or parsed.snapshot_date is None:
            report["snapshots"].append({
                "date": parsed.snapshot_date.isoformat() if parsed.snapshot_date else None,
                "source_date": parsed.source_date.isoformat() if parsed.source_date else None,
                "layout": parsed.layout, "source_sheet": parsed.source_sheet,
                "status": parsed.status, "blocking_errors": parsed.blocking_errors,
                "warnings": parsed.warnings,
            })
            report["warnings"].extend(parsed.warnings)
            report["errors"].extend(parsed.blocking_errors)
            continue
        key = _month_key(parsed.snapshot_date)
        if key in completed_months:
            report["warnings"].append(
                f"{parsed.snapshot_date:%Y-%m} 已有完成快照，已按自然月跳过"
            )
            continue
        duplicate_errors = _duplicate_entry_errors(parsed)
        if duplicate_errors:
            raise ValueError("；".join(duplicate_errors))
        reconciliation, reconcile_warnings, reconcile_blocking = _reconcile(parsed)
        if reconcile_blocking:
            raise ValueError("；".join(reconcile_blocking))
        importable.append(parsed)
        completed_months.add(key)

    if not importable:
        raise ValueError("预览中没有可导入的工作表或自然月")
    importable.sort(key=lambda item: item.snapshot_date or date.min)

    for parsed in importable:
        assert parsed.snapshot_date is not None
        stored_date = month_end(parsed.snapshot_date)
        audit_summary = {
            **parsed.legacy_summary,
            "_source_date": parsed.source_date.isoformat() if parsed.source_date else None,
            "_source_sheet": parsed.source_sheet,
            "_layout": parsed.layout,
        }
        snapshot = Snapshot(
            snapshot_date=stored_date,
            title=f"{stored_date:%Y-%m} 家庭资产",
            status="completed", legacy_source=source_filename,
            legacy_summary_json=json.dumps(audit_summary, ensure_ascii=False),
        )
        session.add(snapshot)
        session.flush()
        names_by_member: dict[str, list[str]] = defaultdict(list)
        for entry in parsed.entries:
            member = _find_or_create_member(session, entry.member_name)
            for prior_name in names_by_member[member.name]:
                ratio = difflib.SequenceMatcher(None, prior_name, entry.account_name).ratio()
                if ratio >= 0.82 and prior_name != entry.account_name:
                    entry.warnings.append(f"疑似重复账户：{prior_name} / {entry.account_name}，未自动合并")
            names_by_member[member.name].append(entry.account_name)
            account = _find_or_create_account(session, member, entry)
            snapshot.entries.append(SnapshotEntry(
                account_id=account.id, amount_cents=entry.amount_cents,
                credit_limit_cents=entry.credit_limit_cents,
                include_in_net_worth=entry.include_in_net_worth,
                member_name=member.name, account_name=entry.account_name,
                institution=entry.institution, account_type=entry.account_type,
                legacy_raw_name=entry.raw_name,
                legacy_raw_value=entry.raw_value,
            ))
            success_rows += 1
            if entry.warnings:
                warning_rows += len(entry.warnings)
                report["warnings"].extend(
                    f"{stored_date} {entry.account_name}：{warning}" for warning in entry.warnings
                )
        session.flush()
        reconciliation, reconcile_warnings, _ = _reconcile(parsed)
        item_warnings = [*parsed.warnings, *reconcile_warnings]
        warning_rows += len(item_warnings)
        report["warnings"].extend(item_warnings)
        report["snapshots"].append({
            "date": stored_date.isoformat(),
            "source_date": parsed.source_date.isoformat() if parsed.source_date else None,
            "layout": parsed.layout, "source_sheet": parsed.source_sheet,
            "status": "imported", "entries": len(snapshot.entries),
            "source_summary": parsed.legacy_summary,
            **reconciliation, "warnings": item_warnings,
        })

    error_rows = len(report["errors"])
    record = ImportRecord(
        source_filename=source_filename, source_type=source_type,
        status="warning" if warning_rows or report["warnings"] or error_rows else "success",
        total_rows=success_rows, success_rows=success_rows,
        warning_rows=warning_rows, error_rows=error_rows,
        report_json=json.dumps(report, ensure_ascii=False),
    )
    session.add(record)
    session.flush()
    if commit:
        session.commit()
        session.refresh(record)
    return record


def preview_snapshots(
    session: Session,
    parsed_snapshots: list[ParsedSnapshot],
    source_filename: str,
    source_type: str,
    detected_encoding: str | None = None,
) -> dict:
    completed_months = _completed_months(session)
    preview_months = set(completed_months)
    snapshot_items: list[dict] = []
    warnings: list[str] = []
    total_rows = importable_rows = duplicate_snapshots = 0

    for parsed in parsed_snapshots:
        row_count = len(parsed.entries)
        total_rows += row_count
        status = parsed.status
        blocking_errors = list(parsed.blocking_errors)
        blocking_errors.extend(_duplicate_entry_errors(parsed))
        item_warnings = list(parsed.warnings)
        reconciliation, reconcile_warnings, reconcile_blocking = _reconcile(parsed)
        item_warnings.extend(reconcile_warnings)
        blocking_errors.extend(reconcile_blocking)
        if blocking_errors:
            status = "blocked"
        if status == "importable" and parsed.snapshot_date is not None:
            month_key = _month_key(parsed.snapshot_date)
            if month_key in preview_months:
                status = "duplicate"
                duplicate_snapshots += 1
                item_warnings.append("该自然月已有完成快照，确认时将跳过")
            else:
                importable_rows += row_count
                preview_months.add(month_key)
        label = parsed.snapshot_date.isoformat() if parsed.snapshot_date else parsed.source_sheet or "未知来源"
        warnings.extend(f"{label}：{warning}" for warning in item_warnings)
        warnings.extend(f"{label}：{error}" for error in blocking_errors)
        snapshot_items.append({
            "snapshot_date": parsed.snapshot_date.isoformat() if parsed.snapshot_date else None,
            "source_date": parsed.source_date.isoformat() if parsed.source_date else None,
            "row_count": row_count, "will_skip": status != "importable",
            "layout": parsed.layout, "source_sheet": parsed.source_sheet,
            "status": status, "blocking_errors": blocking_errors,
            "source_summary": parsed.legacy_summary,
            "calculated_summary": reconciliation["calculated"],
            "differences": reconciliation["differences"],
            "warnings": item_warnings,
        })

    return {
        "source_filename": source_filename, "source_type": source_type,
        "detected_encoding": detected_encoding,
        "total_snapshots": len(parsed_snapshots), "total_rows": total_rows,
        "importable_rows": importable_rows,
        "duplicate_snapshots": duplicate_snapshots,
        "blocked_snapshots": sum(item["status"] == "blocked" for item in snapshot_items),
        "ignored_snapshots": sum(item["status"] == "ignored" for item in snapshot_items),
        "warning_rows": len(warnings), "warnings": warnings,
        "snapshots": snapshot_items,
    }


def import_record_to_dict(record: ImportRecord) -> dict:
    return {
        "id": record.id, "source_filename": record.source_filename,
        "source_type": record.source_type, "imported_at": record.imported_at.isoformat(),
        "status": record.status, "total_rows": record.total_rows,
        "success_rows": record.success_rows, "warning_rows": record.warning_rows,
        "error_rows": record.error_rows, "report": json.loads(record.report_json),
    }
