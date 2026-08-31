from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class HouseholdMember(TimestampMixin, Base):
    __tablename__ = "household_members"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(120))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    accounts: Mapped[list[Account]] = relationship(
        back_populates="member", order_by="Account.sort_order"
    )


class Account(TimestampMixin, Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("household_members.id"), index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    institution: Mapped[Optional[str]] = mapped_column(String(160))
    account_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    credit_limit_cents: Mapped[Optional[int]] = mapped_column(Integer)
    billing_day: Mapped[Optional[int]] = mapped_column(Integer)
    include_in_net_worth: Mapped[bool] = mapped_column(Boolean, default=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    legacy_name: Mapped[Optional[str]] = mapped_column(String(200))

    member: Mapped[HouseholdMember] = relationship(back_populates="accounts")
    entries: Mapped[list[SnapshotEntry]] = relationship(back_populates="account")


class Snapshot(TimestampMixin, Base):
    __tablename__ = "snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    legacy_source: Mapped[Optional[str]] = mapped_column(String(260))
    legacy_summary_json: Mapped[Optional[str]] = mapped_column(Text)

    entries: Mapped[list[SnapshotEntry]] = relationship(
        back_populates="snapshot",
        cascade="all, delete-orphan",
        order_by="SnapshotEntry.id",
    )


class SnapshotEntry(TimestampMixin, Base):
    __tablename__ = "snapshot_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("snapshots.id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    amount_cents: Mapped[Optional[int]] = mapped_column(Integer)
    credit_limit_cents: Mapped[Optional[int]] = mapped_column(Integer)
    include_in_net_worth: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    legacy_raw_name: Mapped[Optional[str]] = mapped_column(String(240))
    legacy_raw_value: Mapped[Optional[str]] = mapped_column(Text)

    # Display snapshots keep historical pages stable when a current account is renamed.
    member_name: Mapped[str] = mapped_column(String(120), nullable=False)
    account_name: Mapped[str] = mapped_column(String(160), nullable=False)
    institution: Mapped[Optional[str]] = mapped_column(String(160))
    account_type: Mapped[str] = mapped_column(String(40), nullable=False)

    snapshot: Mapped[Snapshot] = relationship(back_populates="entries")
    account: Mapped[Account] = relationship(back_populates="entries")


class ImportRecord(Base):
    __tablename__ = "import_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_filename: Mapped[str] = mapped_column(String(260), nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    success_rows: Mapped[int] = mapped_column(Integer, default=0)
    warning_rows: Mapped[int] = mapped_column(Integer, default=0)
    error_rows: Mapped[int] = mapped_column(Integer, default=0)
    report_json: Mapped[str] = mapped_column(Text, default="{}")
