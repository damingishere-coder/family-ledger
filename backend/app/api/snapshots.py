from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import extract, select
from sqlalchemy.orm import Session, selectinload

from ..database import get_session
from ..models import Snapshot, SnapshotEntry
from ..schemas import (
    CompleteSnapshotRequest,
    EntryUpdate,
    SnapshotCreate,
    SnapshotUpdate,
)
from ..services.serializers import snapshot_to_dict
from ..services.snapshots import (
    complete_snapshot,
    create_or_resume_draft,
    get_snapshot_or_404,
    set_snapshot_month,
)


router = APIRouter(prefix="/snapshots", tags=["snapshots"])


@router.get("")
def list_snapshots(
    status: str | None = Query(default=None, pattern="^(draft|completed)$"),
    year: int | None = None,
    session: Session = Depends(get_session),
):
    statement = select(Snapshot).options(selectinload(Snapshot.entries))
    if status:
        statement = statement.where(Snapshot.status == status)
    if year:
        statement = statement.where(extract("year", Snapshot.snapshot_date) == year)
    snapshots = session.scalars(
        statement.order_by(Snapshot.snapshot_date.desc(), Snapshot.id.desc())
    ).all()
    return [snapshot_to_dict(session, item, include_entries=False) for item in snapshots]


@router.get("/active-draft")
def active_draft(session: Session = Depends(get_session)):
    snapshot = session.scalar(
        select(Snapshot)
        .options(selectinload(Snapshot.entries))
        .where(Snapshot.status == "draft")
        .order_by(Snapshot.updated_at.desc(), Snapshot.id.desc())
        .limit(1)
    )
    return snapshot_to_dict(session, snapshot) if snapshot else None


@router.post("", status_code=201)
def create_snapshot(payload: SnapshotCreate, session: Session = Depends(get_session)):
    snapshot = create_or_resume_draft(
        session, payload.snapshot_date, payload.title, payload.notes
    )
    return snapshot_to_dict(session, snapshot)


@router.get("/{snapshot_id}")
def get_snapshot(snapshot_id: int, session: Session = Depends(get_session)):
    return snapshot_to_dict(session, get_snapshot_or_404(session, snapshot_id))


@router.patch("/{snapshot_id}")
def update_snapshot(
    snapshot_id: int, payload: SnapshotUpdate, session: Session = Depends(get_session)
):
    snapshot = get_snapshot_or_404(session, snapshot_id)
    values = payload.model_dump(exclude_unset=True)
    snapshot_date = values.pop("snapshot_date", None)
    if snapshot_date is not None:
        set_snapshot_month(session, snapshot, snapshot_date)
    for field, value in values.items():
        setattr(snapshot, field, value)
    session.commit()
    return snapshot_to_dict(session, get_snapshot_or_404(session, snapshot_id))


@router.put("/{snapshot_id}/entries/{entry_id}")
def update_entry(
    snapshot_id: int,
    entry_id: int,
    payload: EntryUpdate,
    session: Session = Depends(get_session),
):
    entry = session.get(SnapshotEntry, entry_id)
    if entry is None or entry.snapshot_id != snapshot_id:
        raise HTTPException(status_code=404, detail="未找到该盘点条目")
    entry.amount_cents = payload.amount_cents
    if "notes" in payload.model_fields_set:
        entry.notes = payload.notes
    session.commit()
    return snapshot_to_dict(session, get_snapshot_or_404(session, snapshot_id))


@router.post("/{snapshot_id}/complete")
def mark_completed(
    snapshot_id: int,
    payload: CompleteSnapshotRequest,
    session: Session = Depends(get_session),
):
    snapshot = get_snapshot_or_404(session, snapshot_id)
    missing = complete_snapshot(session, snapshot, payload.allow_incomplete)
    result = snapshot_to_dict(session, get_snapshot_or_404(session, snapshot_id))
    result["completed_with_blank_entries"] = missing
    return result


@router.delete("/{snapshot_id}", status_code=204)
def delete_snapshot(snapshot_id: int, session: Session = Depends(get_session)):
    snapshot = get_snapshot_or_404(session, snapshot_id)
    session.delete(snapshot)
    session.commit()
    return None
