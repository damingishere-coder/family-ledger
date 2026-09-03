from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import create_sqlite_engine  # noqa: E402
from app.importers.common import ParsedSnapshot  # noqa: E402
from app.importers.legacy_markdown import parse_legacy_markdown  # noqa: E402
from app.importers.tabular import parse_excel  # noqa: E402
from app.models import Account, HouseholdMember, ImportRecord, Snapshot, SnapshotEntry  # noqa: E402
from app.services.backups import create_named_backup  # noqa: E402
from app.services.imports import _reconcile, import_snapshots  # noqa: E402


TARGET_MONTHS = {
    (2024, 8), (2024, 9),
    *((2025, month) for month in (*range(1, 11), 12)),
    (2026, 1), (2026, 2),
    *((2026, month) for month in range(4, 9)),
}
BLOCKED_MONTHS = {(2024, 10), (2024, 11), (2024, 12)}
FORBIDDEN_ACCOUNT_NAMES = {"小记", "小计", "家庭总余额", "家庭存款", "11号", "11日"}
COMPLETED_MONTH_INDEX = "uq_snapshots_completed_natural_month"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _json_hash(payload: object) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest().upper()


def database_state(session: Session) -> dict:
    snapshot_models = session.scalars(select(Snapshot).order_by(Snapshot.id)).all()
    account_models = session.scalars(select(Account).order_by(Account.id)).all()
    entry_models = session.scalars(select(SnapshotEntry).order_by(SnapshotEntry.id)).all()
    member_models = session.scalars(select(HouseholdMember).order_by(HouseholdMember.id)).all()
    import_models = session.scalars(select(ImportRecord).order_by(ImportRecord.id)).all()
    snapshots = [
        {
            "id": item.id, "date": item.snapshot_date.isoformat(),
            "status": item.status, "legacy_source": item.legacy_source,
            "entries": len(item.entries),
        }
        for item in snapshot_models
    ]
    imports = [
        {
            "id": item.id, "source": item.source_filename, "status": item.status,
            "rows": [item.total_rows, item.success_rows, item.warning_rows, item.error_rows],
        }
        for item in import_models
    ]
    members = [item.name for item in member_models]
    draft_values = [
        [entry.snapshot_id, entry.member_name, entry.account_name, entry.amount_cents]
        for entry in session.scalars(
            select(SnapshotEntry)
            .join(Snapshot, Snapshot.id == SnapshotEntry.snapshot_id)
            .where(Snapshot.status == "draft", SnapshotEntry.amount_cents.is_not(None))
            .order_by(SnapshotEntry.id)
        ).all()
    ]
    payload = {
        "counts": {
            "members": session.scalar(select(func.count()).select_from(HouseholdMember)),
            "accounts": session.scalar(select(func.count()).select_from(Account)),
            "snapshots": session.scalar(select(func.count()).select_from(Snapshot)),
            "entries": session.scalar(select(func.count()).select_from(SnapshotEntry)),
            "imports": session.scalar(select(func.count()).select_from(ImportRecord)),
        },
        "members": members, "snapshots": snapshots,
        "imports": imports, "draft_non_null_values": draft_values,
    }
    signature_basis = {
        **payload,
        "member_rows": [
            [item.id, item.name, item.display_name, item.sort_order, item.is_active]
            for item in member_models
        ],
        "account_rows": [
            [
                item.id, item.member_id, item.name, item.institution, item.account_type,
                item.credit_limit_cents, item.billing_day, item.include_in_net_worth,
                item.is_archived, item.sort_order, item.notes, item.legacy_name,
            ]
            for item in account_models
        ],
        "snapshot_rows": [
            [
                item.id, item.snapshot_date.isoformat(), item.title, item.status,
                item.notes, item.legacy_source, item.legacy_summary_json,
            ]
            for item in snapshot_models
        ],
        "entry_rows": [
            [
                item.id, item.snapshot_id, item.account_id, item.amount_cents,
                item.credit_limit_cents, item.include_in_net_worth, item.notes,
                item.legacy_raw_name, item.legacy_raw_value, item.member_name,
                item.account_name, item.institution, item.account_type,
            ]
            for item in entry_models
        ],
        "import_rows": [
            [
                item.id, item.source_filename, item.source_type,
                item.imported_at.isoformat(), item.status, item.total_rows,
                item.success_rows, item.warning_rows, item.error_rows, item.report_json,
            ]
            for item in import_models
        ],
    }
    payload["signature"] = _json_hash(signature_basis)
    return payload


def parse_sources(excel_path: Path, markdown_paths: list[Path]) -> tuple[list[ParsedSnapshot], dict]:
    markdown_snapshots: list[ParsedSnapshot] = []
    for path in markdown_paths:
        markdown_snapshots.extend(parse_legacy_markdown(path.read_text(encoding="utf-8-sig")))
    overrides = {
        (snapshot.source_date.year, snapshot.source_date.month): snapshot.source_date
        for snapshot in markdown_snapshots
        if snapshot.source_date is not None
    }
    snapshots = parse_excel(excel_path.read_bytes(), overrides)

    billing_days: dict[tuple[str, str], set[int]] = defaultdict(set)
    for snapshot in markdown_snapshots:
        for entry in snapshot.entries:
            if entry.account_type == "credit_card" and entry.institution and entry.billing_day:
                billing_days[(entry.member_name, entry.institution)].add(entry.billing_day)
    conflicts = {key: sorted(values) for key, values in billing_days.items() if len(values) != 1}
    if conflicts:
        raise ValueError(f"Markdown 还款日存在冲突：{conflicts}")
    resolved_days = {key: next(iter(values)) for key, values in billing_days.items()}
    for snapshot in snapshots:
        for entry in snapshot.entries:
            if entry.account_type == "credit_card" and entry.institution:
                entry.billing_day = resolved_days.get((entry.member_name, entry.institution))

    importable_months = {
        (snapshot.snapshot_date.year, snapshot.snapshot_date.month)
        for snapshot in snapshots
        if snapshot.status == "importable" and snapshot.snapshot_date is not None
    }
    blocked_months = {
        (snapshot.snapshot_date.year, snapshot.snapshot_date.month)
        for snapshot in snapshots
        if snapshot.status == "blocked" and snapshot.snapshot_date is not None
    }
    if importable_months != TARGET_MONTHS:
        raise ValueError(
            f"可靠月份集合不符合预期：缺少 {sorted(TARGET_MONTHS - importable_months)}，"
            f"多出 {sorted(importable_months - TARGET_MONTHS)}"
        )
    if not BLOCKED_MONTHS.issubset(blocked_months):
        raise ValueError(f"2024-10~12 未全部按日期冲突阻止：{sorted(blocked_months)}")
    reconciliation_errors = {
        snapshot.source_sheet: _reconcile(snapshot)[2]
        for snapshot in snapshots
        if snapshot.status == "importable" and _reconcile(snapshot)[2]
    }
    if reconciliation_errors:
        raise ValueError(f"存在无法解释的金额残差：{reconciliation_errors}")
    excel_by_month = {
        (snapshot.snapshot_date.year, snapshot.snapshot_date.month): snapshot
        for snapshot in snapshots
        if snapshot.snapshot_date is not None
    }
    markdown_summary_checks: list[dict] = []
    for markdown_snapshot in markdown_snapshots:
        if markdown_snapshot.source_date is None:
            continue
        key = (markdown_snapshot.source_date.year, markdown_snapshot.source_date.month)
        excel_snapshot = excel_by_month.get(key)
        if excel_snapshot is None:
            continue
        differences = []
        for field in ("total_assets_cents", "total_liabilities_cents", "net_worth_cents"):
            markdown_value = markdown_snapshot.legacy_summary.get(field)
            excel_value = excel_snapshot.legacy_summary.get(field)
            if markdown_value is not None and excel_value is not None and markdown_value != excel_value:
                differences.append({
                    "field": field, "markdown_cents": markdown_value,
                    "excel_source_cents": excel_value,
                    "residual_cents": markdown_value - excel_value,
                })
        markdown_summary_checks.append({
            "month": f"{key[0]:04d}-{key[1]:02d}",
            "status": "warning" if differences else "matched",
            "differences": differences,
            "resolution": (
                "Markdown 为日期和二次核对来源；金额仍以已通过内部汇总校验的 Excel 唯一明细为准"
                if differences else None
            ),
        })
    return snapshots, {
        "markdown_dates": sorted(value.isoformat() for value in overrides.values()),
        "billing_days": {
            f"{member}/{institution}": day
            for (member, institution), day in sorted(resolved_days.items())
        },
        "importable_months": [f"{year:04d}-{month:02d}" for year, month in sorted(importable_months)],
        "blocked_months": [f"{year:04d}-{month:02d}" for year, month in sorted(blocked_months)],
        "ignored_sheets": [snapshot.source_sheet for snapshot in snapshots if snapshot.status == "ignored"],
        "markdown_summary_checks": markdown_summary_checks,
        "warnings": {
            snapshot.source_sheet or str(snapshot.snapshot_date): _reconcile(snapshot)[1]
            for snapshot in snapshots
            if snapshot.status == "importable" and _reconcile(snapshot)[1]
        },
    }


def _source_hashes(excel_path: Path, markdown_paths: list[Path]) -> dict[str, str]:
    return {path.name: sha256_file(path) for path in [excel_path, *markdown_paths]}


def build_preview(
    database_path: Path, excel_path: Path, markdown_paths: list[Path],
) -> tuple[dict, list[ParsedSnapshot]]:
    if not database_path.is_file():
        raise ValueError(f"数据库不存在：{database_path}")
    if not excel_path.is_file() or any(not path.is_file() for path in markdown_paths):
        raise ValueError("一个或多个来源附件不存在")
    snapshots, source_audit = parse_sources(excel_path, markdown_paths)
    engine = create_sqlite_engine(database_path)
    try:
        with Session(engine) as session:
            state = database_state(session)
    finally:
        engine.dispose()
    source_names = {path.name for path in markdown_paths}
    bad_snapshots = [item for item in state["snapshots"] if item["legacy_source"] in source_names]
    august_drafts = [
        item for item in state["snapshots"]
        if item["status"] == "draft" and item["date"].startswith("2026-08-")
    ]
    preserved_september = [
        item for item in state["snapshots"]
        if item["status"] == "completed" and item["date"].startswith("2026-09-")
        and item["legacy_source"] is None
    ]
    report = {
        "mode": "dry-run", "generated_at": datetime.now().astimezone().isoformat(),
        "database": str(database_path.resolve()),
        "database_state": state, "source_sha256": _source_hashes(excel_path, markdown_paths),
        "source_audit": source_audit,
        "planned_changes": {
            "supersede_import_sources": sorted(source_names),
            "remove_bad_snapshot_ids": [item["id"] for item in bad_snapshots],
            "replace_august_draft_ids": [item["id"] for item in august_drafts],
            "preserve_september_snapshot_ids": [item["id"] for item in preserved_september],
            "rebuild_months": source_audit["importable_months"],
        },
    }
    if len(bad_snapshots) != 13:
        report.setdefault("blocking_errors", []).append(
            f"预期 13 个错误 Markdown 快照，实际 {len(bad_snapshots)} 个"
        )
    if len(august_drafts) != 1:
        report.setdefault("blocking_errors", []).append(
            f"预期 1 个 2026-08 草稿，实际 {len(august_drafts)} 个"
        )
    if len(preserved_september) != 1:
        report.setdefault("blocking_errors", []).append(
            f"预期 1 个非导入的 2026-09 完成快照，实际 {len(preserved_september)} 个"
        )
    return report, snapshots


def _already_applied(session: Session, markdown_names: set[str]) -> bool:
    bad_count = session.scalar(
        select(func.count()).select_from(Snapshot).where(Snapshot.legacy_source.in_(markdown_names))
    )
    superseded = session.scalar(
        select(func.count()).select_from(ImportRecord).where(
            ImportRecord.source_filename.in_(markdown_names), ImportRecord.status == "superseded"
        )
    )
    repaired = session.scalar(
        select(func.count()).select_from(ImportRecord).where(
            ImportRecord.source_filename == "账单.xlsx", ImportRecord.source_type == "repair-xlsx"
        )
    )
    return bad_count == 0 and superseded == len(markdown_names) and repaired >= 1


def apply_repair(
    report: dict, expected_report: dict, snapshots: list[ParsedSnapshot],
    database_path: Path, backup_dir: Path, markdown_paths: list[Path],
) -> dict:
    markdown_names = {path.name for path in markdown_paths}
    if expected_report.get("source_sha256") != report["source_sha256"]:
        raise ValueError("来源附件 SHA-256 与只读预演报告不一致")
    engine = create_sqlite_engine(database_path)
    backup_path: Path | None = None
    try:
        with Session(engine) as session:
            if _already_applied(session, markdown_names):
                return {**report, "mode": "apply", "status": "already_applied"}
            if report.get("blocking_errors"):
                raise ValueError("；".join(report["blocking_errors"]))
            expected_signature = expected_report.get("database_state", {}).get("signature")
            if not expected_signature or report["database_state"]["signature"] != expected_signature:
                raise ValueError("数据库状态自只读预演后已漂移，停止写入")
            session.rollback()
            backup_path = create_named_backup(database_path, backup_dir, "pre_import_repair")
            if database_state(session)["signature"] != expected_signature:
                raise ValueError("备份期间数据库状态发生变化，停止写入")
            session.rollback()

            with session.begin():
                old_records = session.scalars(
                    select(ImportRecord).where(ImportRecord.source_filename.in_(markdown_names))
                ).all()
                if len(old_records) != len(markdown_names):
                    raise ValueError(f"预期两条 Markdown 导入记录，实际 {len(old_records)} 条")
                for record in old_records:
                    old_report = json.loads(record.report_json or "{}")
                    old_report["superseded_by"] = "historical-import-repair"
                    old_report["superseded_at"] = datetime.now().astimezone().isoformat()
                    record.report_json = json.dumps(old_report, ensure_ascii=False)
                    record.status = "superseded"

                removed_snapshots = session.scalars(
                    select(Snapshot).where(Snapshot.legacy_source.in_(markdown_names))
                ).all()
                august_drafts = session.scalars(
                    select(Snapshot).where(
                        Snapshot.status == "draft",
                        Snapshot.snapshot_date >= date(2026, 8, 1),
                        Snapshot.snapshot_date <= date(2026, 8, 31),
                    )
                ).all()
                candidate_account_ids = {
                    entry.account_id
                    for snapshot in [*removed_snapshots, *august_drafts]
                    for entry in snapshot.entries
                }
                for snapshot in [*removed_snapshots, *august_drafts]:
                    session.delete(snapshot)
                session.flush()

                importable = [snapshot for snapshot in snapshots if snapshot.status == "importable"]
                import_snapshots(
                    session, importable, "账单.xlsx", "repair-xlsx", commit=False,
                    extra_report={
                        "source_sha256": report["source_sha256"],
                        "repair_source_audit": report["source_audit"],
                    },
                )
                session.flush()

                for account_id in candidate_account_ids:
                    referenced = session.scalar(
                        select(func.count()).select_from(SnapshotEntry).where(SnapshotEntry.account_id == account_id)
                    )
                    if not referenced:
                        account = session.get(Account, account_id)
                        if account is not None:
                            session.delete(account)
                session.flush()
                for member in session.scalars(select(HouseholdMember).where(HouseholdMember.name == "大明")).all():
                    account_count = session.scalar(
                        select(func.count()).select_from(Account).where(Account.member_id == member.id)
                    )
                    if not account_count:
                        session.delete(member)
                session.flush()

                completed = session.scalars(
                    select(Snapshot).where(Snapshot.status == "completed").order_by(Snapshot.snapshot_date)
                ).all()
                if len(completed) != 21:
                    raise ValueError(f"修复后应有 21 个完成快照，实际 {len(completed)} 个")
                month_keys = [(item.snapshot_date.year, item.snapshot_date.month) for item in completed]
                if len(month_keys) != len(set(month_keys)):
                    raise ValueError("修复后仍存在同一自然月的重复完成快照")
                session.execute(text(
                    f"CREATE UNIQUE INDEX IF NOT EXISTS {COMPLETED_MONTH_INDEX} "
                    "ON snapshots (strftime('%Y-%m', snapshot_date)) "
                    "WHERE status = 'completed'"
                ))
                all_member_names = list(session.scalars(select(HouseholdMember.name)).all())
                member_names = set(all_member_names)
                if len(all_member_names) != 3 or member_names != {"峰峰", "贤贤", "家庭公共"}:
                    raise ValueError(f"修复后成员集合不正确：{sorted(all_member_names)}")
                bad_accounts = [
                    name for name in session.scalars(select(Account.name)).all()
                    if name.strip().isdigit()
                    or re.fullmatch(r"\d{1,2}[号日]", name.strip())
                    or name in FORBIDDEN_ACCOUNT_NAMES
                ]
                if bad_accounts:
                    raise ValueError(f"修复后仍存在错误账户名：{sorted(set(bad_accounts))}")
                malformed_bank_accounts = list(session.scalars(
                    select(Account.name).where(
                        Account.account_type == "debit_card",
                        ~Account.name.endswith("储蓄卡"),
                    )
                ).all()) + list(session.scalars(
                    select(Account.name).where(
                        Account.account_type == "credit_card",
                        ~Account.name.endswith("信用卡"),
                    )
                ).all())
                if malformed_bank_accounts:
                    raise ValueError(f"银行账户命名未标准化：{sorted(set(malformed_bank_accounts))}")
                alipay_entries = session.scalar(
                    select(func.count()).select_from(SnapshotEntry).join(
                        Snapshot, Snapshot.id == SnapshotEntry.snapshot_id
                    ).where(
                        Snapshot.legacy_source == "账单.xlsx",
                        SnapshotEntry.account_name == "支付宝",
                    )
                )
                if alipay_entries != 40:
                    raise ValueError(f"重建历史应有 40 条支付宝字段，实际 {alipay_entries} 条")
                credit_limits = session.scalar(
                    select(func.count()).select_from(SnapshotEntry).join(
                        Snapshot, Snapshot.id == SnapshotEntry.snapshot_id
                    ).where(
                        Snapshot.legacy_source == "账单.xlsx",
                        SnapshotEntry.account_type == "credit_card",
                        SnapshotEntry.credit_limit_cents.is_not(None),
                    )
                )
                if not credit_limits:
                    raise ValueError("重建历史丢失了信用额度字段")
                violations = session.execute(text("PRAGMA foreign_key_check")).all()
                if violations:
                    raise ValueError(f"外键校验失败：{violations[:3]}")
    finally:
        engine.dispose()

    with sqlite3.connect(database_path) as connection:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        raise ValueError(f"SQLite 完整性校验失败：{integrity}")
    final_engine = create_sqlite_engine(database_path)
    try:
        with Session(final_engine) as session:
            final_state = database_state(session)
    finally:
        final_engine.dispose()
    return {
        **report, "mode": "apply", "status": "applied",
        "backup_path": str(backup_path.resolve()) if backup_path else None,
        "final_database_state": final_state, "integrity_check": integrity,
    }


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="只读预演或事务化修复 FamilyLedger 错误历史导入")
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--excel", type=Path, required=True)
    parser.add_argument("--markdown", type=Path, action="append", required=True)
    parser.add_argument("--backup-dir", type=Path, default=PROJECT_ROOT / "backups" / "import-repair")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-report", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    if len(args.markdown) != 2:
        raise ValueError("必须提供两个 Markdown 来源文件")
    report, snapshots = build_preview(args.database, args.excel, args.markdown)
    if args.apply:
        if args.expected_report is None:
            raise ValueError("正式应用必须提供 --expected-report，防止数据库漂移")
        expected = json.loads(args.expected_report.read_text(encoding="utf-8"))
        report = apply_repair(
            report, expected, snapshots, args.database, args.backup_dir, args.markdown,
        )
    output_path = args.report
    if output_path is None:
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        output_path = args.backup_dir / f"import_repair_{report['mode']}_{stamp}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "mode": report["mode"], "status": report.get("status", "ready"),
        "report": str(output_path.resolve()),
        "database_signature": report["database_state"]["signature"],
        "blocking_errors": report.get("blocking_errors", []),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
