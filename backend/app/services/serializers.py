from __future__ import annotations

import json
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Account, HouseholdMember, Snapshot, SnapshotEntry
from .calculations import ASSET_TYPES, calculate_totals


def member_to_dict(member: HouseholdMember) -> dict:
    return {
        "id": member.id,
        "name": member.name,
        "display_name": member.display_name,
        "sort_order": member.sort_order,
        "is_active": member.is_active,
        "created_at": member.created_at.isoformat(),
        "updated_at": member.updated_at.isoformat(),
    }


def account_to_dict(account: Account) -> dict:
    return {
        "id": account.id,
        "member_id": account.member_id,
        "member_name": account.member.display_name or account.member.name,
        "name": account.name,
        "institution": account.institution,
        "account_type": account.account_type,
        "credit_limit_cents": account.credit_limit_cents,
        "billing_day": account.billing_day,
        "include_in_net_worth": account.include_in_net_worth,
        "is_archived": account.is_archived,
        "sort_order": account.sort_order,
        "notes": account.notes,
        "legacy_name": account.legacy_name,
        "created_at": account.created_at.isoformat(),
        "updated_at": account.updated_at.isoformat(),
    }


def previous_amounts(
    session: Session, snapshot: Snapshot
) -> tuple[Snapshot | None, dict[int, int | None]]:
    previous = session.scalars(
        select(Snapshot)
        .where(
            Snapshot.status == "completed",
            Snapshot.id != snapshot.id,
            Snapshot.snapshot_date <= snapshot.snapshot_date,
        )
        .order_by(Snapshot.snapshot_date.desc(), Snapshot.id.desc())
        .limit(1)
    ).first()
    if previous is None:
        return None, {}
    return previous, {entry.account_id: entry.amount_cents for entry in previous.entries}


def entry_to_dict(entry: SnapshotEntry, previous_amount: int | None = None) -> dict:
    delta = (
        entry.amount_cents - previous_amount
        if entry.amount_cents is not None and previous_amount is not None
        else None
    )
    large_change = False
    if delta is not None:
        baseline = max(abs(previous_amount or 0), 10_000)
        large_change = abs(delta) >= 100_000 and abs(delta) >= baseline * 5
    return {
        "id": entry.id,
        "snapshot_id": entry.snapshot_id,
        "account_id": entry.account_id,
        "member_name": entry.member_name,
        "account_name": entry.account_name,
        "institution": entry.institution,
        "account_type": entry.account_type,
        "amount_cents": entry.amount_cents,
        "previous_amount_cents": previous_amount,
        "change_cents": delta,
        "large_change_warning": large_change,
        "credit_limit_cents": entry.credit_limit_cents,
        "include_in_net_worth": entry.include_in_net_worth,
        "notes": entry.notes,
        "legacy_raw_name": entry.legacy_raw_name,
        "legacy_raw_value": entry.legacy_raw_value,
    }


def snapshot_to_dict(session: Session, snapshot: Snapshot, include_entries: bool = True) -> dict:
    totals = calculate_totals(snapshot.entries)
    previous, amounts = previous_amounts(session, snapshot)
    result = {
        "id": snapshot.id,
        "snapshot_date": snapshot.snapshot_date.isoformat(),
        "title": snapshot.title,
        "status": snapshot.status,
        "notes": snapshot.notes,
        "legacy_source": snapshot.legacy_source,
        "legacy_summary": json.loads(snapshot.legacy_summary_json)
        if snapshot.legacy_summary_json
        else None,
        "created_at": snapshot.created_at.isoformat(),
        "updated_at": snapshot.updated_at.isoformat(),
        "previous_snapshot_id": previous.id if previous else None,
        **totals.__dict__,
    }
    if include_entries:
        result["entries"] = [
            entry_to_dict(entry, amounts.get(entry.account_id)) for entry in snapshot.entries
        ]
    return result


def dashboard_to_dict(session: Session) -> dict:
    snapshots = list(
        session.scalars(
            select(Snapshot)
            .where(Snapshot.status == "completed")
            .order_by(Snapshot.snapshot_date.asc(), Snapshot.id.asc())
        ).all()
    )
    if not snapshots:
        return {
            "current": None,
            "change_from_previous_cents": None,
            "trend": [],
            "composition": [],
            "members": [],
            "recent": [],
        }

    summaries = [snapshot_to_dict(session, item, include_entries=False) for item in snapshots]
    latest = snapshots[-1]
    latest_totals = calculate_totals(latest.entries)
    previous_net = summaries[-2]["net_worth_cents"] if len(summaries) > 1 else None

    composition_totals: dict[str, int] = defaultdict(int)
    member_buckets: dict[str, dict[str, int]] = defaultdict(
        lambda: {"assets_cents": 0, "liabilities_cents": 0}
    )
    category_map = {
        "wallet": "钱包 / 支付平台",
        "debit_card": "银行存款",
        "investment": "投资",
        "receivable": "应收款",
        "other_asset": "其他资产",
    }
    for entry in latest.entries:
        if entry.amount_cents is None or not entry.include_in_net_worth:
            continue
        if entry.account_type in ASSET_TYPES:
            composition_totals[category_map.get(entry.account_type, "其他资产")] += (
                entry.amount_cents
            )
            member_buckets[entry.member_name]["assets_cents"] += entry.amount_cents
        else:
            member_buckets[entry.member_name]["liabilities_cents"] += entry.amount_cents

    return {
        "current": latest_totals.__dict__,
        "snapshot_id": latest.id,
        "snapshot_date": latest.snapshot_date.isoformat(),
        "change_from_previous_cents": latest_totals.net_worth_cents - previous_net
        if previous_net is not None
        else None,
        "trend": [
            {
                "id": item["id"],
                "date": item["snapshot_date"],
                "total_assets_cents": item["total_assets_cents"],
                "total_liabilities_cents": item["total_liabilities_cents"],
                "net_worth_cents": item["net_worth_cents"],
            }
            for item in summaries
        ],
        "composition": [
            {"name": key, "amount_cents": value}
            for key, value in composition_totals.items()
        ],
        "members": [
            {
                "name": name,
                **values,
                "net_worth_cents": values["assets_cents"]
                - values["liabilities_cents"],
            }
            for name, values in member_buckets.items()
        ],
        "recent": list(reversed(summaries[-10:])),
    }
