from __future__ import annotations

import csv
import io
import json
from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_session
from ..importers.common import ParsedSnapshot, decode_text
from ..importers.legacy_markdown import parse_legacy_markdown
from ..importers.tabular import parse_csv_with_encoding, parse_excel
from ..models import ImportRecord, Snapshot, SnapshotEntry
from ..services.backups import (
    create_named_backup,
    export_payload,
    payload_as_json,
    restore_payload,
)
from ..services.imports import import_record_to_dict, import_snapshots, preview_snapshots


router = APIRouter(tags=["data"])
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


def _download(content: bytes, media_type: str, filename: str) -> Response:
    encoded = quote(filename)
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"},
    )


async def _read_upload(file: UploadFile) -> bytes:
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="文件超过 20MB 限制")
    return content


def _suffix(filename: str) -> str:
    return filename.lower().rsplit(".", 1)[-1] if "." in filename else ""


def _parse_legacy_upload(
    content: bytes, filename: str
) -> tuple[list[ParsedSnapshot], str, str]:
    if _suffix(filename) not in {"md", "markdown", "txt"}:
        raise ValueError("历史文本仅支持 MD、MARKDOWN 或 TXT 文件")
    text, encoding = decode_text(content)
    return parse_legacy_markdown(text), "markdown", encoding


def _parse_tabular_upload(
    content: bytes, filename: str
) -> tuple[list[ParsedSnapshot], str, str | None]:
    suffix = _suffix(filename)
    if suffix == "csv":
        snapshots, encoding = parse_csv_with_encoding(content)
        return snapshots, "csv", encoding
    if suffix in {"xlsx", "xlsm"}:
        return parse_excel(content), "xlsx", None
    raise ValueError("仅支持 CSV、XLSX 或 XLSM 表格，不支持旧版 XLS")


@router.post("/import/legacy/preview")
async def preview_legacy(
    file: UploadFile = File(...), session: Session = Depends(get_session)
):
    content = await _read_upload(file)
    filename = file.filename or "legacy.md"
    try:
        snapshots, source_type, encoding = _parse_legacy_upload(content, filename)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return preview_snapshots(session, snapshots, filename, source_type, encoding)


@router.post("/import/tabular/preview")
async def preview_tabular(
    file: UploadFile = File(...), session: Session = Depends(get_session)
):
    content = await _read_upload(file)
    filename = file.filename or "import.csv"
    try:
        snapshots, source_type, encoding = _parse_tabular_upload(content, filename)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return preview_snapshots(session, snapshots, filename, source_type, encoding)


@router.post("/import/legacy")
async def import_legacy(
    file: UploadFile = File(...), session: Session = Depends(get_session)
):
    content = await _read_upload(file)
    filename = file.filename or "legacy.md"
    try:
        snapshots, source_type, _encoding = _parse_legacy_upload(content, filename)
        record = import_snapshots(session, snapshots, filename, source_type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return import_record_to_dict(record)


@router.post("/import/tabular")
async def import_tabular(
    file: UploadFile = File(...), session: Session = Depends(get_session)
):
    content = await _read_upload(file)
    filename = file.filename or "import.csv"
    try:
        snapshots, source_type, _encoding = _parse_tabular_upload(content, filename)
        record = import_snapshots(session, snapshots, filename, source_type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return import_record_to_dict(record)


@router.get("/imports")
def list_imports(session: Session = Depends(get_session)):
    records = session.scalars(
        select(ImportRecord).order_by(ImportRecord.imported_at.desc(), ImportRecord.id.desc())
    ).all()
    return [import_record_to_dict(record) for record in records]


@router.get("/export/json")
def export_json(session: Session = Depends(get_session)):
    filename = f"family-finance-backup-{date.today().isoformat()}.json"
    return _download(payload_as_json(export_payload(session)), "application/json", filename)


def _export_rows(session: Session) -> list[list[object]]:
    rows: list[list[object]] = [[
        "snapshot_date",
        "member_name",
        "account_name",
        "institution",
        "account_type",
        "amount",
        "amount_cents",
        "credit_limit_cents",
        "include_in_net_worth",
        "status",
    ]]
    results = session.execute(
        select(Snapshot, SnapshotEntry)
        .join(SnapshotEntry, SnapshotEntry.snapshot_id == Snapshot.id)
        .order_by(Snapshot.snapshot_date, SnapshotEntry.id)
    )
    for snapshot, entry in results:
        amount = f"{entry.amount_cents / 100:.2f}" if entry.amount_cents is not None else ""
        rows.append([
            snapshot.snapshot_date.isoformat(),
            entry.member_name,
            entry.account_name,
            entry.institution or "",
            entry.account_type,
            amount,
            entry.amount_cents if entry.amount_cents is not None else "",
            entry.credit_limit_cents if entry.credit_limit_cents is not None else "",
            entry.include_in_net_worth,
            snapshot.status,
        ])
    return rows


@router.get("/export/csv")
def export_csv(session: Session = Depends(get_session)):
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerows(_export_rows(session))
    return _download(
        ("\ufeff" + output.getvalue()).encode("utf-8"),
        "text/csv; charset=utf-8",
        f"family-finance-{date.today().isoformat()}.csv",
    )


@router.get("/export/excel")
def export_excel(session: Session = Depends(get_session)):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "家庭资产"
    for row in _export_rows(session):
        sheet.append(row)
    sheet.freeze_panes = "A2"
    output = io.BytesIO()
    workbook.save(output)
    return _download(
        output.getvalue(),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        f"family-finance-{date.today().isoformat()}.xlsx",
    )


@router.post("/backup")
def backup_now(request: Request, session: Session = Depends(get_session)):
    session.commit()
    path = create_named_backup(request.app.state.database_path, request.app.state.backup_dir)
    return {"status": "ok", "filename": path.name, "path": str(path)}


@router.post("/restore")
async def restore_backup(
    request: Request,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    content = await _read_upload(file)
    try:
        payload = json.loads(content.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail="JSON 备份文件无效") from exc
    rollback_path = create_named_backup(
        request.app.state.database_path, request.app.state.backup_dir, "pre_restore"
    )
    try:
        restore_payload(session, payload)
    except (ValueError, KeyError, TypeError) as exc:
        session.rollback()
        raise HTTPException(
            status_code=422,
            detail=f"恢复失败，原数据库已保留在 {rollback_path.name}：{exc}",
        ) from exc
    return {"status": "ok", "rollback_backup": rollback_path.name}
