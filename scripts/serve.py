from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

import uvicorn  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="启动 FamilyLedger 本地单进程服务")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8767)
    parser.add_argument("--log-level", default="info")
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost"}:
        parser.error("V1 只允许监听 127.0.0.1 或 localhost")
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=args.port,
        log_level=args.log_level,
        access_log=True,
    )


if __name__ == "__main__":
    main()
