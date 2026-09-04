from __future__ import annotations

from calendar import monthrange
from datetime import date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..models import Account, Snapshot, SnapshotEntry


def month_end(value: date) -> date:
    return value.replace(day=monthrange(value.year, value.month)[1])


def snapshot_month(value: date) -> str:
    return value.strftime("%Y-%m")


def snapshot_month_label(value: date) -> str:
    return f"{value.year}年{value.month:02d}月"


def default_snapshot_title(value: date) -> str:
    return f"{snapshot_month_label(value)} 家庭资产"


def completed_snapshot_for_month(
    session: Session, value: date, exclude_snapshot_id: int | None = None
) -> Snapshot | None:
    start = value.replace(day=1)
    end = month_end(value)
    statement = select(Snapshot).where(
        Snapshot.status == "completed",
        Snapshot.snapshot_date >= start,
        Snapshot.snapshot_date <= end,
    )
    if exclude_snapshot_id is not None:
        statement = statement.where(Snapshot.id != exclude_snapshot_id)
    return session.scalar(
        statement.order_by(Snapshot.snapshot_date.desc(), Snapshot.id.desc()).limit(1)
    )


def raise_month_conflict(existing: Snapshot) -> None:
    month = snapshot_month(existing.snapshot_date)
    raise HTTPException(
        status_code=409,
        detail={
            "code": "SNAPSHOT_MONTH_EXISTS",
            "message": f"{snapshot_month_label(existing.snapshot_date)}已有已完成盘点",
            "snapshot_id": existing.id,
            "snapshot_month": month,
        },
    )


def ensure_month_available(
    session: Session, value: date, exclude_snapshot_id: int | None = None
) -> None:
    existing = completed_snapshot_for_month(session, value, exclude_snapshot_id)
    if existing is not None:
        raise_month_conflict(existing)


def set_snapshot_month(session: Session, snapshot: Snapshot, value: date) -> None:
    normalized = month_end(value)
    ensure_month_available(session, normalized, snapshot.id)
    old_date = snapshot.snapshot_date
    old_auto_titles = {
        None,
        f"{old_date.isoformat()} 家庭资产",
        default_snapshot_title(old_date),
    }
    snapshot.snapshot_date = normalized
    if snapshot.title in old_auto_titles:
        snapshot.title = default_snapshot_title(normalized)


def _entry_values(account: Account) -> dict[str, object]:
    return {
        "credit_limit_cents": account.credit_limit_cents,
        "include_in_net_worth": account.include_in_net_worth,
        "member_name": account.member.display_name or account.member.name,
        "account_name": account.name,
        "institution": account.institution,
        "account_type": account.account_type,
    }


def sync_draft_accounts(session: Session, snapshot: Snapshot) -> bool:
    if snapshot.status != "draft":
        return False
    accounts = list(
        session.scalars(
            select(Account)
            .options(selectinload(Account.member))
            .where(Account.is_archived.is_(False))
            .order_by(Account.member_id, Account.sort_order, Account.id)
        ).all()
    )
    entries_by_account = {entry.account_id: entry for entry in snapshot.entries}
    changed = False
    for account in accounts:
        values = _entry_values(account)
        entry = entries_by_account.get(account.id)
        if entry is None:
            snapshot.entries.append(
                SnapshotEntry(account_id=account.id, amount_cents=None, **values)
            )
            changed = True
            continue
        for field, value in values.items():
            if getattr(entry, field) != value:
                setattr(entry, field, value)
                changed = True
    return changed


def get_snapshot_or_404(session: Session, snapshot_id: int) -> Snapshot:
    snapshot = session.scalar(
        select(Snapshot)
        .options(selectinload(Snapshot.entries))
        .where(Snapshot.id == snapshot_id)
    )
    if snapshot is None:
        raise HTTPException(status_code=404, detail="未找到该盘点")
    return snapshot


def create_or_resume_draft(
    session: Session,
    snapshot_date: date,
    title: str | None = None,
    notes: str | None = None,
) -> Snapshot:
    existing = session.scalar(
        select(Snapshot)
        .options(selectinload(Snapshot.entries))
        .where(Snapshot.status == "draft")
        .order_by(Snapshot.updated_at.desc(), Snapshot.id.desc())
        .limit(1)
    )
    if existing is not None:
        if sync_draft_accounts(session, existing):
            session.commit()
        return get_snapshot_or_404(session, existing.id)

    snapshot_date = month_end(snapshot_date)
    ensure_month_available(session, snapshot_date)
    snapshot = Snapshot(
        snapshot_date=snapshot_date,
        title=title or default_snapshot_title(snapshot_date),
        notes=notes,
        status="draft",
    )
    session.add(snapshot)
    session.flush()
    sync_draft_accounts(session, snapshot)
    session.commit()
    session.refresh(snapshot)
    return get_snapshot_or_404(session, snapshot.id)


def complete_snapshot(
    session: Session, snapshot: Snapshot, allow_incomplete: bool
) -> list[dict]:
    ensure_month_available(session, snapshot.snapshot_date, snapshot.id)
    missing = [
        {"entry_id": entry.id, "account_name": entry.account_name, "member_name": entry.member_name}
        for entry in snapshot.entries
        if entry.amount_cents is None
    ]
    if missing and not allow_incomplete:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "INCOMPLETE_ENTRIES",
                "message": f"还有 {len(missing)} 个账户尚未填写",
                "entries": missing,
            },
        )
    snapshot.status = "completed"
    session.commit()
    return missing
