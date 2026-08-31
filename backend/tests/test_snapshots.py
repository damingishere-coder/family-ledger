from datetime import date


def test_snapshot_uses_previous_as_reference_but_keeps_current_null(client, create_account):
    wallet = create_account("微信", "wallet")
    card = create_account("招商银行信用卡", "credit_card", credit_limit_cents=6_400_000)

    first = client.post(
        "/api/snapshots", json={"snapshot_date": "2026-07-31", "title": None, "notes": None}
    ).json()
    assert len(first["entries"]) == 2
    for entry in first["entries"]:
        amount = 120_000 if entry["account_id"] == wallet["id"] else 23_146
        response = client.put(
            f"/api/snapshots/{first['id']}/entries/{entry['id']}",
            json={"amount_cents": amount, "notes": None},
        )
        assert response.status_code == 200
    assert client.post(
        f"/api/snapshots/{first['id']}/complete", json={"allow_incomplete": False}
    ).status_code == 200

    second = client.post(
        "/api/snapshots", json={"snapshot_date": "2026-08-31", "title": None, "notes": None}
    ).json()
    by_account = {entry["account_id"]: entry for entry in second["entries"]}
    assert by_account[wallet["id"]]["amount_cents"] is None
    assert by_account[wallet["id"]]["previous_amount_cents"] == 120_000
    assert by_account[card["id"]]["amount_cents"] is None
    assert by_account[card["id"]]["previous_amount_cents"] == 23_146


def test_incomplete_snapshot_requires_explicit_confirmation(client, create_account):
    create_account("支付宝", "wallet")
    snapshot = client.post(
        "/api/snapshots", json={"snapshot_date": date.today().isoformat(), "title": None, "notes": None}
    ).json()
    blocked = client.post(
        f"/api/snapshots/{snapshot['id']}/complete", json={"allow_incomplete": False}
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "INCOMPLETE_ENTRIES"
    completed = client.post(
        f"/api/snapshots/{snapshot['id']}/complete", json={"allow_incomplete": True}
    )
    assert completed.status_code == 200
    assert completed.json()["entries"][0]["amount_cents"] is None


def test_archived_account_is_missing_from_new_snapshot_but_kept_in_history(client, create_account):
    account = create_account("旧银行卡", "debit_card")
    first = client.post(
        "/api/snapshots", json={"snapshot_date": "2026-06-30", "title": None, "notes": None}
    ).json()
    entry = first["entries"][0]
    client.put(
        f"/api/snapshots/{first['id']}/entries/{entry['id']}",
        json={"amount_cents": 50_000, "notes": None},
    )
    client.post(f"/api/snapshots/{first['id']}/complete", json={"allow_incomplete": False})
    assert client.post(f"/api/accounts/{account['id']}/archive").status_code == 200

    second = client.post(
        "/api/snapshots", json={"snapshot_date": "2026-07-31", "title": None, "notes": None}
    ).json()
    assert second["entries"] == []
    historical = client.get(f"/api/snapshots/{first['id']}").json()
    assert historical["entries"][0]["account_name"] == "旧银行卡"
    assert historical["entries"][0]["amount_cents"] == 50_000


def test_dashboard_uses_completed_snapshot(client, create_account):
    create_account("微信", "wallet")
    create_account("证券", "investment")
    create_account("信用卡", "credit_card")
    snapshot = client.post(
        "/api/snapshots", json={"snapshot_date": "2026-08-31", "title": None, "notes": None}
    ).json()
    amounts = {"微信": 10_000, "证券": 250_000, "信用卡": 50_000}
    for entry in snapshot["entries"]:
        client.put(
            f"/api/snapshots/{snapshot['id']}/entries/{entry['id']}",
            json={"amount_cents": amounts[entry["account_name"]], "notes": None},
        )
    client.post(f"/api/snapshots/{snapshot['id']}/complete", json={"allow_incomplete": False})
    dashboard = client.get("/api/dashboard").json()
    assert dashboard["current"]["total_assets_cents"] == 260_000
    assert dashboard["current"]["total_liabilities_cents"] == 50_000
    assert dashboard["current"]["net_worth_cents"] == 210_000
    assert dashboard["current"]["investment_assets_cents"] == 250_000
