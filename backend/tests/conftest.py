from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(tmp_path: Path):
    app = create_app(
        database_path=tmp_path / "data" / "test.db",
        backup_dir=tmp_path / "backups",
        static_dir=tmp_path / "dist",
    )
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def create_member(client):
    def create(name: str = "大明") -> dict:
        response = client.post(
            "/api/members", json={"name": name, "display_name": name, "sort_order": 0}
        )
        assert response.status_code == 201, response.text
        return response.json()

    return create


@pytest.fixture
def create_account(client, create_member):
    members: dict[str, dict] = {}

    def create(
        name: str,
        account_type: str,
        member_name: str = "大明",
        include: bool = True,
        credit_limit_cents: int | None = None,
    ) -> dict:
        member = members.get(member_name)
        if member is None:
            member = create_member(member_name)
            members[member_name] = member
        response = client.post(
            "/api/accounts",
            json={
                "member_id": member["id"],
                "name": name,
                "institution": name,
                "account_type": account_type,
                "credit_limit_cents": credit_limit_cents,
                "billing_day": 11 if account_type == "credit_card" else None,
                "include_in_net_worth": include,
                "sort_order": 0,
                "notes": None,
            },
        )
        assert response.status_code == 201, response.text
        return response.json()

    return create
