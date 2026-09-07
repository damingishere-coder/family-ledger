"""Read-only source review. No service startup, production writes or migrations."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.services.import_sources import parse_bundle
from app.services.import_review import build_review


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--files', type=Path, nargs='+', required=True)
    parser.add_argument('--mappings', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    database = args.database.resolve(strict=True)
    raw, audit = parse_bundle([(path.name, path.read_bytes()) for path in args.files])
    mappings = json.loads(args.mappings.read_text(encoding='utf-8-sig')) if args.mappings else {}
    engine = create_engine('sqlite://', creator=lambda: sqlite3.connect(database.as_uri() + '?mode=ro', uri=True))
    try:
        with Session(engine) as session:
            review, _ = build_review(session, raw, audit, mappings)
    finally:
        engine.dispose()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps({**review, **audit}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'mode': 'read-only', 'months': [{k: m[k] for k in ('month', 'status')} for m in review['months']],
        'pending_accounts': [{'key': g['key'], 'name': g['account_name'], 'member': g['source_member'],
            'direction_unclear': g['direction_unclear']} for g in review['groups'] if g['needs_review']],
        'changed_entries': sum(e['status'] == 'update' for m in review['months'] for e in m['entries']),
        'conflicts': sum(e['status'] == 'conflict' for m in review['months'] for e in m['entries'])}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
