from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol


ASSET_TYPES = {"wallet", "debit_card", "investment", "receivable", "other_asset"}
LIABILITY_TYPES = {"credit_card", "other_liability"}


class EntryLike(Protocol):
    account_type: str
    amount_cents: int | None
    include_in_net_worth: bool


@dataclass(frozen=True)
class Totals:
    total_assets_cents: int
    total_liabilities_cents: int
    net_worth_cents: int
    investment_assets_cents: int
    completed_entries: int
    total_entries: int


def calculate_totals(entries: Iterable[EntryLike]) -> Totals:
    assets = 0
    liabilities = 0
    investments = 0
    completed = 0
    total = 0

    for entry in entries:
        total += 1
        if entry.amount_cents is None:
            continue
        completed += 1
        if not entry.include_in_net_worth:
            continue
        if entry.account_type in ASSET_TYPES:
            assets += entry.amount_cents
            if entry.account_type == "investment":
                investments += entry.amount_cents
        elif entry.account_type in LIABILITY_TYPES:
            liabilities += entry.amount_cents

    return Totals(
        total_assets_cents=assets,
        total_liabilities_cents=liabilities,
        net_worth_cents=assets - liabilities,
        investment_assets_cents=investments,
        completed_entries=completed,
        total_entries=total,
    )
