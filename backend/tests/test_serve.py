from __future__ import annotations

import os
from pathlib import Path

import pytest

from scripts import serve


def configure_frontend(monkeypatch, tmp_path: Path) -> tuple[Path, Path]:
    frontend = tmp_path / "frontend"
    source = frontend / "src" / "main.tsx"
    index = frontend / "dist" / "index.html"
    source.parent.mkdir(parents=True)
    index.parent.mkdir(parents=True)
    source.write_text("source", encoding="utf-8")
    index.write_text("build", encoding="utf-8")
    monkeypatch.setattr(serve, "FRONTEND_DIR", frontend)
    monkeypatch.setattr(serve, "FRONTEND_INDEX", index)
    return source, index


def test_frontend_build_is_skipped_when_dist_is_current(monkeypatch, tmp_path):
    source, index = configure_frontend(monkeypatch, tmp_path)
    os.utime(source, ns=(1_000_000_000, 1_000_000_000))
    os.utime(index, ns=(2_000_000_000, 2_000_000_000))
    monkeypatch.setattr(
        serve.subprocess,
        "run",
        lambda *args, **kwargs: pytest.fail("不应构建"),
    )

    serve.ensure_frontend_build()


def test_frontend_build_runs_when_source_is_newer(monkeypatch, tmp_path):
    source, index = configure_frontend(monkeypatch, tmp_path)
    (index.parents[1] / "node_modules").mkdir()
    os.utime(index, ns=(1_000_000_000, 1_000_000_000))
    os.utime(source, ns=(2_000_000_000, 2_000_000_000))
    calls = []
    monkeypatch.setattr(serve.shutil, "which", lambda _name: "npm.cmd")

    def fake_run(command, cwd, check):
        calls.append((command, cwd, check))

    monkeypatch.setattr(serve.subprocess, "run", fake_run)

    serve.ensure_frontend_build()

    assert calls == [(["npm.cmd", "run", "build"], index.parents[1], True)]


def test_frontend_build_runs_when_public_asset_is_newer(monkeypatch, tmp_path):
    source, index = configure_frontend(monkeypatch, tmp_path)
    public_asset = index.parents[1] / "public" / "brand" / "favicon.svg"
    public_asset.parent.mkdir(parents=True)
    public_asset.write_text("<svg />", encoding="utf-8")
    (index.parents[1] / "node_modules").mkdir()
    os.utime(source, ns=(1_000_000_000, 1_000_000_000))
    os.utime(index, ns=(2_000_000_000, 2_000_000_000))
    os.utime(public_asset, ns=(3_000_000_000, 3_000_000_000))
    calls = []
    monkeypatch.setattr(serve.shutil, "which", lambda _name: "npm.cmd")

    def fake_run(command, cwd, check):
        calls.append((command, cwd, check))

    monkeypatch.setattr(serve.subprocess, "run", fake_run)

    serve.ensure_frontend_build()

    assert calls == [(["npm.cmd", "run", "build"], index.parents[1], True)]


def test_stale_frontend_without_dependencies_fails_clearly(monkeypatch, tmp_path):
    source, index = configure_frontend(monkeypatch, tmp_path)
    os.utime(index, ns=(1_000_000_000, 1_000_000_000))
    os.utime(source, ns=(2_000_000_000, 2_000_000_000))

    with pytest.raises(SystemExit, match="前端依赖尚未安装"):
        serve.ensure_frontend_build()
