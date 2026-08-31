from __future__ import annotations

from datetime import date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..models import Account, Snapshot, SnapshotEntry


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
        return existing

    accounts = list(
        session.scalars(
            select(Account)
            .options(selectinload(Account.member))
            .where(Account.is_archived.is_(False))
            .order_by(Account.member_id, Account.sort_order, Account.id)
        ).all()
    )
    snapshot = Snapshot(
        snapshot_date=snapshot_date,
        title=title or f"{snapshot_date.isoformat()} 家庭资产",
        notes=notes,
        status="draft",
    )
    session.add(snapshot)
    session.flush()
    for account in accounts:
        snapshot.entries.append(
            SnapshotEntry(
                account_id=account.id,
                amount_cents=None,
                credit_limit_cents=account.credit_limit_cents,
                include_in_net_worth=account.include_in_net_worth,
                member_name=account.member.display_name or account.member.name,
                account_name=account.name,
                institution=account.institution,
                account_type=account.account_type,
            )
        )
    session.commit()
    session.refresh(snapshot)
    return get_snapshot_or_404(session, snapshot.id)


def complete_snapshot(
    session: Session, snapshot: Snapshot, allow_incomplete: bool
) -> list[dict]:
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
