import json

from app.services.backups import SCHEMA_VERSION


def test_json_export_and_restore_replaces_current_data(client, create_member):
    original = create_member("原成员")
    exported = client.get("/api/export/json")
    assert exported.status_code == 200
    payload = json.loads(exported.content)
    assert payload["schema_version"] == SCHEMA_VERSION
    create_member("临时成员")
    assert len(client.get("/api/members").json()) == 2

    restored = client.post(
        "/api/restore",
        files={"file": ("backup.json", exported.content, "application/json")},
    )
    assert restored.status_code == 200, restored.text
    members = client.get("/api/members").json()
    assert [member["name"] for member in members] == [original["name"]]


def test_restore_rejects_wrong_schema_without_replacing_data(client, create_member):
    create_member("安全成员")
    invalid = {"schema_version": 999, "members": [], "accounts": [], "snapshots": [], "snapshot_entries": []}
    response = client.post(
        "/api/restore",
        files={"file": ("invalid.json", json.dumps(invalid).encode(), "application/json")},
    )
    assert response.status_code == 422
    assert [item["name"] for item in client.get("/api/members").json()] == ["安全成员"]


def test_manual_database_backup_is_created(client, create_member, tmp_path):
    create_member("备份成员")
    response = client.post("/api/backup")
    assert response.status_code == 200
    assert response.json()["filename"].endswith(".db")
