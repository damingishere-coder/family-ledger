from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    project_root: Path
    data_dir: Path
    backup_dir: Path
    database_path: Path
    static_dir: Path
    host: str
    port: int


def load_settings() -> Settings:
    data_dir = Path(os.getenv("FAMILY_LEDGER_DATA_DIR", PROJECT_ROOT / "data")).resolve()
    backup_dir = Path(
        os.getenv("FAMILY_LEDGER_BACKUP_DIR", PROJECT_ROOT / "backups")
    ).resolve()
    return Settings(
        project_root=PROJECT_ROOT,
        data_dir=data_dir,
        backup_dir=backup_dir,
        database_path=data_dir / "family_finance.db",
        static_dir=(PROJECT_ROOT / "frontend" / "dist").resolve(),
        host=os.getenv("FAMILY_LEDGER_HOST", "127.0.0.1"),
        port=int(os.getenv("FAMILY_LEDGER_PORT", "8767")),
    )
