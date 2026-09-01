from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
FRONTEND_DIR = PROJECT_ROOT / "frontend"
FRONTEND_INDEX = FRONTEND_DIR / "dist" / "index.html"
sys.path.insert(0, str(BACKEND_DIR))

import uvicorn  # noqa: E402


def _frontend_inputs() -> list[Path]:
    inputs = [
        FRONTEND_DIR / "index.html",
        FRONTEND_DIR / "package.json",
        FRONTEND_DIR / "package-lock.json",
        FRONTEND_DIR / "vite.config.ts",
    ]
    inputs.extend(FRONTEND_DIR.glob("tsconfig*.json"))
    source_dir = FRONTEND_DIR / "src"
    if source_dir.exists():
        inputs.extend(path for path in source_dir.rglob("*") if path.is_file())
    return [path for path in inputs if path.exists()]


def ensure_frontend_build() -> None:
    inputs = _frontend_inputs()
    latest_input = max((path.stat().st_mtime_ns for path in inputs), default=0)
    build_time = FRONTEND_INDEX.stat().st_mtime_ns if FRONTEND_INDEX.exists() else 0
    if build_time >= latest_input:
        return

    if not (FRONTEND_DIR / "node_modules").exists():
        raise SystemExit("前端依赖尚未安装，请先双击“启动家庭统计台.bat”完成初始化")
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if npm is None:
        raise SystemExit("检测到前端资源已过期，但未找到 npm；请安装 Node.js 后重试")

    print("检测到前端资源已更新，正在重新生成本地网页…", flush=True)
    try:
        subprocess.run([npm, "run", "build"], cwd=FRONTEND_DIR, check=True)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"前端网页构建失败（退出码 {exc.returncode}），服务未启动") from exc
    if not FRONTEND_INDEX.exists():
        raise SystemExit("前端构建命令已结束，但未生成 dist/index.html，服务未启动")


def main() -> None:
    parser = argparse.ArgumentParser(description="启动 FamilyLedger 本地单进程服务")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8767)
    parser.add_argument("--log-level", default="info")
    parser.add_argument(
        "--skip-frontend-build",
        action="store_true",
        help="仅供隔离验证使用：跳过前端资源新旧检查",
    )
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost"}:
        parser.error("V1 只允许监听 127.0.0.1 或 localhost")
    if not args.skip_frontend_build:
        ensure_frontend_build()
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=args.port,
        log_level=args.log_level,
        access_log=True,
    )


if __name__ == "__main__":
    main()
