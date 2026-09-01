from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def choose_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def fetch(url: str) -> tuple[int, bytes]:
    request = urllib.request.Request(url, headers={"User-Agent": "FamilyLedger-Runtime-Check"})
    with urllib.request.urlopen(request, timeout=2) as response:
        return response.status, response.read()


def preview_markdown(url: str) -> tuple[int, bytes]:
    boundary = "----family-ledger-runtime-check"
    content = (
        "## 2025年12月25日\n\n"
        "### 一、测试成员明细\n\n"
        "#### 钱包\n"
        "测试钱包：12.35\n"
    ).encode("utf-8")
    body = b"".join(
        [
            f"--{boundary}\r\n".encode(),
            b'Content-Disposition: form-data; name="file"; filename="runtime-check.md"\r\n',
            b"Content-Type: text/markdown\r\n\r\n",
            content,
            f"\r\n--{boundary}--\r\n".encode(),
        ]
    )
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "User-Agent": "FamilyLedger-Runtime-Check",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    with urllib.request.urlopen(request, timeout=2) as response:
        return response.status, response.read()


def main() -> int:
    port = choose_port()
    runtime_root = Path(tempfile.mkdtemp(prefix="family-ledger-runtime-"))
    try:
        environment = os.environ.copy()
        environment["FAMILY_LEDGER_DATA_DIR"] = str(runtime_root / "data")
        environment["FAMILY_LEDGER_BACKUP_DIR"] = str(runtime_root / "backups")
        command = [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "serve.py"),
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
            "--skip-frontend-build",
        ]
        process = subprocess.Popen(
            command,
            cwd=PROJECT_ROOT,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            deadline = time.monotonic() + 20
            last_error: Exception | None = None
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    stdout, stderr = process.communicate(timeout=1)
                    raise RuntimeError(
                        f"服务提前退出 code={process.returncode}\nstdout={stdout}\nstderr={stderr}"
                    )
                try:
                    health_status, health_body = fetch(
                        f"http://127.0.0.1:{port}/api/health"
                    )
                    root_status, root_body = fetch(f"http://127.0.0.1:{port}/")
                    preview_status, preview_body = preview_markdown(
                        f"http://127.0.0.1:{port}/api/import/legacy/preview"
                    )
                    imports_status, imports_body = fetch(
                        f"http://127.0.0.1:{port}/api/imports"
                    )
                    health = json.loads(health_body)
                    preview = json.loads(preview_body)
                    imports = json.loads(imports_body)
                    if health_status != 200 or health.get("service") != "family-ledger":
                        raise RuntimeError(f"健康响应身份不匹配：{health}")
                    if health.get("database_integrity") != "ok":
                        raise RuntimeError(f"数据库完整性异常：{health}")
                    if root_status != 200 or b'id="root"' not in root_body:
                        raise RuntimeError("SPA 首页未由 FastAPI 提供")
                    if preview_status != 200 or preview.get("total_rows") != 1:
                        raise RuntimeError(f"导入预览响应异常：{preview}")
                    if imports_status != 200 or imports != []:
                        raise RuntimeError("只读预览意外创建了导入记录")
                    print(
                        json.dumps(
                            {
                                "status": "ok",
                                "port": port,
                                "service": health["service"],
                                "database_integrity": health["database_integrity"],
                                "spa": "ok",
                                "import_preview": "ok",
                                "preview_persisted_records": len(imports),
                            },
                            ensure_ascii=False,
                        )
                    )
                    return 0
                except Exception as exc:  # service may still be starting
                    last_error = exc
                    time.sleep(0.25)
            raise RuntimeError(f"运行时验证超时：{last_error}")
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
    finally:
        cleanup_error: PermissionError | None = None
        for _attempt in range(20):
            try:
                shutil.rmtree(runtime_root)
                cleanup_error = None
                break
            except FileNotFoundError:
                cleanup_error = None
                break
            except PermissionError as exc:
                cleanup_error = exc
                time.sleep(0.25)
        if cleanup_error is not None:
            raise RuntimeError(f"临时运行目录清理失败：{runtime_root}") from cleanup_error


if __name__ == "__main__":
    raise SystemExit(main())
