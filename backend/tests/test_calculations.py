from dataclasses import dataclass

from app.services.calculations import calculate_totals


@dataclass
class Entry:
    account_type: str
    amount_cents: int | None
    include_in_net_worth: bool = True


def test_calculates_assets_liabilities_net_worth_and_investments():
    totals = calculate_totals(
        [
            Entry("wallet", 12_345),
            Entry("investment", 250_000),
            Entry("credit_card", 30_000),
            Entry("receivable", 99_999, include_in_net_worth=False),
            Entry("other_asset", None),
        ]
    )
    assert totals.total_assets_cents == 262_345
    assert totals.total_liabilities_cents == 30_000
    assert totals.net_worth_cents == 232_345
    assert totals.investment_assets_cents == 250_000
    assert totals.completed_entries == 4
    assert totals.total_entries == 5


def test_negative_credit_card_is_preserved_in_liability_calculation():
    totals = calculate_totals([Entry("credit_card", -1_852), Entry("debit_card", 10_000)])
    assert totals.total_liabilities_cents == -1_852
    assert totals.net_worth_cents == 11_852
