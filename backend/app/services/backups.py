from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from ..models import Account, HouseholdMember, ImportRecord, Snapshot, SnapshotEntry


SCHEMA_VERSION = 1


def copy_database(database_path: Path, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as source, sqlite3.connect(destination) as target:
        source.backup(target)
    return destination


def create_named_backup(database_path: Path, backup_dir: Path, prefix: str = "family_finance") -> Path:
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    return copy_database(database_path, backup_dir / f"{prefix}_{stamp}.db")


def create_daily_backup(database_path: Path, backup_dir: Path, keep: int = 30) -> Path | None:
    if not database_path.exists():
        return None
    backup_dir.mkdir(parents=True, exist_ok=True)
    destination = backup_dir / f"family_finance_{date.today().isoformat()}.db"
    if not destination.exists():
        copy_database(database_path, destination)
    backups = sorted(backup_dir.glob("family_finance_????-??-??.db"), reverse=True)
    for old_backup in backups[keep:]:
        old_backup.unlink(missing_ok=True)
    return destination


def export_payload(session: Session) -> dict:
    def iso(value):
        return value.isoformat() if value is not None else None

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "members": [
            {
                "id": item.id,
                "name": item.name,
                "display_name": item.display_name,
                "sort_order": item.sort_order,
                "is_active": item.is_active,
                "created_at": iso(item.created_at),
                "updated_at": iso(item.updated_at),
            }
            for item in session.scalars(select(HouseholdMember).order_by(HouseholdMember.id))
        ],
        "accounts": [
            {
                "id": item.id,
                "member_id": item.member_id,
                "name": item.name,
                "institution": item.institution,
                "account_type": item.account_type,
                "credit_limit_cents": item.credit_limit_cents,
                "billing_day": item.billing_day,
                "include_in_net_worth": item.include_in_net_worth,
                "is_archived": item.is_archived,
                "sort_order": item.sort_order,
                "notes": item.notes,
                "legacy_name": item.legacy_name,
                "created_at": iso(item.created_at),
                "updated_at": iso(item.updated_at),
            }
            for item in session.scalars(select(Account).order_by(Account.id))
        ],
        "snapshots": [
            {
                "id": item.id,
                "snapshot_date": iso(item.snapshot_date),
                "title": item.title,
                "status": item.status,
                "notes": item.notes,
                "legacy_source": item.legacy_source,
                "legacy_summary_json": item.legacy_summary_json,
                "created_at": iso(item.created_at),
                "updated_at": iso(item.updated_at),
            }
            for item in session.scalars(select(Snapshot).order_by(Snapshot.id))
        ],
        "snapshot_entries": [
            {
                "id": item.id,
                "snapshot_id": item.snapshot_id,
                "account_id": item.account_id,
                "amount_cents": item.amount_cents,
                "credit_limit_cents": item.credit_limit_cents,
                "include_in_net_worth": item.include_in_net_worth,
                "notes": item.notes,
                "legacy_raw_name": item.legacy_raw_name,
                "legacy_raw_value": item.legacy_raw_value,
                "member_name": item.member_name,
                "account_name": item.account_name,
                "institution": item.institution,
                "account_type": item.account_type,
                "created_at": iso(item.created_at),
                "updated_at": iso(item.updated_at),
            }
            for item in session.scalars(select(SnapshotEntry).order_by(SnapshotEntry.id))
        ],
        "import_records": [
            {
                "id": item.id,
                "source_filename": item.source_filename,
                "source_type": item.source_type,
                "imported_at": iso(item.imported_at),
                "status": item.status,
                "total_rows": item.total_rows,
                "success_rows": item.success_rows,
                "warning_rows": item.warning_rows,
                "error_rows": item.error_rows,
                "report_json": item.report_json,
            }
            for item in session.scalars(select(ImportRecord).order_by(ImportRecord.id))
        ],
    }


def _parse_datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def restore_payload(session: Session, payload: dict) -> None:
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("备份版本不受支持")
    required = {"members", "accounts", "snapshots", "snapshot_entries"}
    if not required.issubset(payload):
        raise ValueError("备份缺少必要数据表")

    session.rollback()
    with session.begin():
        session.execute(delete(ImportRecord))
        session.execute(delete(SnapshotEntry))
        session.execute(delete(Snapshot))
        session.execute(delete(Account))
        session.execute(delete(HouseholdMember))

        for row in payload["members"]:
            session.add(
                HouseholdMember(
                    id=row["id"],
                    name=row["name"],
                    display_name=row.get("display_name"),
                    sort_order=row.get("sort_order", 0),
                    is_active=row.get("is_active", True),
                    created_at=_parse_datetime(row.get("created_at")),
                    updated_at=_parse_datetime(row.get("updated_at")),
                )
            )
        session.flush()
        for row in payload["accounts"]:
            session.add(Account(**{key: value for key, value in row.items() if key not in {"created_at", "updated_at"}}, created_at=_parse_datetime(row.get("created_at")), updated_at=_parse_datetime(row.get("updated_at"))))
        session.flush()
        for row in payload["snapshots"]:
            values = {key: value for key, value in row.items() if key not in {"snapshot_date", "created_at", "updated_at"}}
            session.add(Snapshot(**values, snapshot_date=date.fromisoformat(row["snapshot_date"]), created_at=_parse_datetime(row.get("created_at")), updated_at=_parse_datetime(row.get("updated_at"))))
        session.flush()
        for row in payload["snapshot_entries"]:
            session.add(SnapshotEntry(**{key: value for key, value in row.items() if key not in {"created_at", "updated_at"}}, created_at=_parse_datetime(row.get("created_at")), updated_at=_parse_datetime(row.get("updated_at"))))
        for row in payload.get("import_records", []):
            values = {key: value for key, value in row.items() if key != "imported_at"}
            session.add(ImportRecord(**values, imported_at=_parse_datetime(row.get("imported_at"))))
        session.flush()
        violations = session.execute(text("PRAGMA foreign_key_check")).all()
        if violations:
            raise ValueError(f"备份外键校验失败：{violations[:3]}")


def payload_as_json(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
