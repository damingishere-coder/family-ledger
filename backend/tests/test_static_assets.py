from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


def test_brand_assets_are_served_without_breaking_spa_routes(tmp_path: Path):
    static_dir = tmp_path / "dist"
    brand_dir = static_dir / "brand"
    brand_dir.mkdir(parents=True)
    (static_dir / "index.html").write_text(
        '<!doctype html><div id="root"></div>', encoding="utf-8"
    )
    (brand_dir / "familyledger-logo.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"></svg>', encoding="utf-8"
    )
    (brand_dir / "favicon.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"></svg>', encoding="utf-8"
    )
    (brand_dir / "favicon-32x32.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    app = create_app(
        database_path=tmp_path / "data" / "test.db",
        backup_dir=tmp_path / "backups",
        static_dir=static_dir,
    )

    with TestClient(app) as client:
        logo = client.get("/brand/familyledger-logo.svg")
        favicon = client.get("/brand/favicon.svg")
        png = client.get("/brand/favicon-32x32.png")
        missing = client.get("/brand/missing.svg")
        history = client.get("/history")

    assert logo.status_code == 200
    assert logo.headers["content-type"].startswith("image/svg+xml")
    assert logo.text.startswith("<svg")
    assert favicon.status_code == 200
    assert favicon.headers["content-type"].startswith("image/svg+xml")
    assert png.status_code == 200
    assert png.headers["content-type"].startswith("image/png")
    assert missing.status_code == 404
    assert history.status_code == 200
    assert 'id="root"' in history.text
