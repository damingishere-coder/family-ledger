from datetime import date

from sqlalchemy.orm import Session

from app.models import Account, Snapshot, SnapshotEntry


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


def test_resuming_draft_syncs_accounts_without_losing_entered_values(client, create_account):
    original = create_account("测试", "wallet", member_name="峰峰")
    draft = client.post(
        "/api/snapshots", json={"snapshot_date": "2026-08-04", "title": None, "notes": None}
    ).json()
    original_entry = draft["entries"][0]
    saved = client.put(
        f"/api/snapshots/{draft['id']}/entries/{original_entry['id']}",
        json={"amount_cents": 200, "notes": "保留这条备注"},
    )
    assert saved.status_code == 200

    updated = client.patch(
        f"/api/accounts/{original['id']}",
        json={
            "name": "微信",
            "institution": "微信支付",
            "account_type": "wallet",
            "include_in_net_worth": False,
        },
    )
    assert updated.status_code == 200
    new_account = create_account("招行", "debit_card", member_name="贤贤")

    resumed = client.post(
        "/api/snapshots", json={"snapshot_date": "2026-09-01", "title": None, "notes": None}
    ).json()
    assert resumed["id"] == draft["id"]
    assert resumed["snapshot_date"] == "2026-08-31"
    assert len(resumed["entries"]) == 2
    by_account = {entry["account_id"]: entry for entry in resumed["entries"]}
    refreshed = by_account[original["id"]]
    assert refreshed["id"] == original_entry["id"]
    assert refreshed["amount_cents"] == 200
    assert refreshed["notes"] == "保留这条备注"
    assert refreshed["account_name"] == "微信"
    assert refreshed["institution"] == "微信支付"
    assert refreshed["include_in_net_worth"] is False
    assert by_account[new_account["id"]]["amount_cents"] is None

    repeated = client.post(
        "/api/snapshots", json={"snapshot_date": "2026-10-01", "title": None, "notes": None}
    ).json()
    assert [entry["account_id"] for entry in repeated["entries"]].count(new_account["id"]) == 1

    assert client.post(f"/api/accounts/{original['id']}/archive").status_code == 200
    archived_resume = client.post(
        "/api/snapshots", json={"snapshot_date": "2026-10-01", "title": None, "notes": None}
    ).json()
    archived_entry = next(
        entry for entry in archived_resume["entries"] if entry["account_id"] == original["id"]
    )
    assert archived_entry["amount_cents"] == 200

    completed = client.post(
        f"/api/snapshots/{draft['id']}/complete", json={"allow_incomplete": True}
    ).json()
    assert client.patch(f"/api/accounts/{original['id']}", json={"name": "新的当前名称"}).status_code == 200
    historical = client.get(f"/api/snapshots/{completed['id']}").json()
    assert next(
        entry for entry in historical["entries"] if entry["account_id"] == original["id"]
    )["account_name"] == "微信"


def test_monthly_draft_is_normalized_resumed_and_unique(client, create_account):
    create_account("微信", "wallet")
    draft = client.post(
        "/api/snapshots", json={"snapshot_date": "2026-08-02", "title": None, "notes": None}
    ).json()
    assert draft["snapshot_date"] == "2026-08-31"
    assert draft["title"] == "2026年08月 家庭资产"

    resumed = client.post(
        "/api/snapshots", json={"snapshot_date": "2026-09-12", "title": None, "notes": None}
    ).json()
    assert resumed["id"] == draft["id"]
    assert resumed["snapshot_date"] == "2026-08-31"

    assert client.post(
        f"/api/snapshots/{draft['id']}/complete", json={"allow_incomplete": True}
    ).status_code == 200
    conflict = client.post(
        "/api/snapshots", json={"snapshot_date": "2026-08-01", "title": None, "notes": None}
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == {
        "code": "SNAPSHOT_MONTH_EXISTS",
        "message": "2026年08月已有已完成盘点",
        "snapshot_id": draft["id"],
        "snapshot_month": "2026-08",
    }


def test_changing_or_completing_draft_rejects_existing_month(client, create_account):
    account_data = create_account("微信", "wallet")
    august = client.post(
        "/api/snapshots", json={"snapshot_date": "2026-08-15", "title": None, "notes": None}
    ).json()
    client.post(f"/api/snapshots/{august['id']}/complete", json={"allow_incomplete": True})
    september = client.post(
        "/api/snapshots", json={"snapshot_date": "2026-09-01", "title": None, "notes": None}
    ).json()

    patch_conflict = client.patch(
        f"/api/snapshots/{september['id']}", json={"snapshot_date": "2026-08-02"}
    )
    assert patch_conflict.status_code == 409
    assert patch_conflict.json()["detail"]["snapshot_id"] == august["id"]

    with Session(client.app.state.engine) as session:
        account = session.get(Account, account_data["id"])
        assert account is not None
        competing = Snapshot(
            snapshot_date=date(2026, 9, 1),
            title="并发写入的九月盘点",
            status="completed",
        )
        competing.entries.append(
            SnapshotEntry(
                account_id=account.id,
                amount_cents=300,
                credit_limit_cents=account.credit_limit_cents,
                include_in_net_worth=account.include_in_net_worth,
                member_name=account.member.display_name or account.member.name,
                account_name=account.name,
                institution=account.institution,
                account_type=account.account_type,
            )
        )
        session.add(competing)
        session.commit()
        competing_id = competing.id

    complete_conflict = client.post(
        f"/api/snapshots/{september['id']}/complete", json={"allow_incomplete": True}
    )
    assert complete_conflict.status_code == 409
    assert complete_conflict.json()["detail"]["snapshot_id"] == competing_id


def test_previous_amount_comes_from_strictly_earlier_month(client, create_account):
    account_data = create_account("微信", "wallet")
    with Session(client.app.state.engine) as session:
        account = session.get(Account, account_data["id"])
        assert account is not None
        snapshot_ids = []
        for snapshot_date, amount in (
            (date(2026, 8, 31), 100),
            (date(2026, 9, 1), 200),
            (date(2026, 9, 30), 300),
        ):
            snapshot = Snapshot(
                snapshot_date=snapshot_date,
                title=f"{snapshot_date.isoformat()} 家庭资产",
                status="completed",
            )
            snapshot.entries.append(
                SnapshotEntry(
                    account_id=account.id,
                    amount_cents=amount,
                    credit_limit_cents=account.credit_limit_cents,
                    include_in_net_worth=account.include_in_net_worth,
                    member_name=account.member.display_name or account.member.name,
                    account_name=account.name,
                    institution=account.institution,
                    account_type=account.account_type,
                )
            )
            session.add(snapshot)
            session.flush()
            snapshot_ids.append(snapshot.id)
        session.commit()

    september_late = client.get(f"/api/snapshots/{snapshot_ids[-1]}").json()
    assert september_late["entries"][0]["previous_amount_cents"] == 100
