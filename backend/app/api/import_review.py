from __future__ import annotations

import secrets
import threading
import time
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..database import get_session
from ..services.backups import create_named_backup
from ..services.import_sources import parse_bundle
from ..services.import_review import build_review, commit_review, database_signature, digest
from ..services.imports import import_record_to_dict

router = APIRouter(prefix="/import/batch", tags=["data"])
_lock = threading.RLock()


class ReviewRequest(BaseModel):
    token: str
    mappings: dict[str, dict[str, str]] = Field(default_factory=dict)


class ConfirmRequest(BaseModel):
    token: str
    review_id: str
    months: list[str]


def tickets(request: Request) -> dict:
    if not hasattr(request.app.state, "import_tickets"):
        request.app.state.import_tickets = {}
    cache = request.app.state.import_tickets
    for key in list(cache):
        if cache[key]["expires"] < time.monotonic():
            del cache[key]
    return cache


def ticket(request: Request, token: str) -> dict:
    value = tickets(request).get(token)
    if value is None:
        raise HTTPException(409, "预览已过期或服务已重启，请重新选择文件")
    return value


@router.post("/preview")
async def preview(request: Request, files: list[UploadFile] = File(...), session: Session = Depends(get_session)):
    if not 1 <= len(files) <= 5:
        raise HTTPException(422, "一次请选择 1 至 5 个文件")
    sources = []
    size = 0
    for file in files:
        content = await file.read(20 * 1024 * 1024 + 1)
        size += len(content)
        if len(content) > 20 * 1024 * 1024 or size > 40 * 1024 * 1024:
            raise HTTPException(413, "单文件限 20MB，本批文件合计限 40MB")
        name = Path((file.filename or "unknown").replace("\\", "/")).name
        sources.append((name, content))
    try:
        raw, audit = parse_bundle(sources)
        review, parsed = build_review(session, raw, audit)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    with _lock:
        cache = tickets(request)
        if len(cache) >= 8:
            del cache[next(iter(cache))]
        token = secrets.token_urlsafe(32)
        review_id = digest(review)
        cache[token] = {"raw": raw, "audit": audit, "review": review, "parsed": parsed,
            "review_id": review_id, "expires": time.monotonic() + 1800}
    return {**review, "token": token, "review_id": review_id}


@router.post("/review")
def review_mappings(payload: ReviewRequest, request: Request, session: Session = Depends(get_session)):
    with _lock:
        item = ticket(request, payload.token)
        if item.get("result"):
            raise HTTPException(409, "这批文件已处理，请重新预览")
        try:
            review, parsed = build_review(session, item["raw"], item["audit"], payload.mappings)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        item.update(review=review, parsed=parsed, review_id=digest(review))
        return {**review, "token": payload.token, "review_id": item["review_id"]}


@router.post("/confirm")
def confirm(payload: ConfirmRequest, request: Request, session: Session = Depends(get_session)):
    with _lock:
        item = ticket(request, payload.token)
        selection = sorted(payload.months)
        if item.get("result"):
            if selection != item["selection"] or payload.review_id != item["review_id"]:
                raise HTTPException(409, "已处理的批次不能变更选择，请重新预览")
            return item["result"]
        if payload.review_id != item["review_id"]:
            raise HTTPException(409, "核对结果已更新，请查看最新预览")
        try:
            session.execute(text("BEGIN IMMEDIATE"))
            if database_signature(session) != item["review"]["database_signature"]:
                raise HTTPException(409, "预览后数据发生变化，请重新核对后确认")
            selectable = {m["month"] for m in item["review"]["months"] if m["status"] in {"new", "update"}}
            if not selection or len(selection) != len(set(selection)) or not set(selection) <= selectable:
                raise HTTPException(422, "请选择无冲突且有变更的月份")
            backup = create_named_backup(request.app.state.database_path, request.app.state.backup_dir, "pre_import_review")
            record = commit_review(session, item["review"], item["parsed"], selection, item["audit"])
            result = {**import_record_to_dict(record), "backup_filename": backup.name,
                      "applied_months": selection}
            session.commit()
        except HTTPException:
            session.rollback()
            raise
        except ValueError as exc:
            session.rollback()
            raise HTTPException(422, str(exc)) from exc
        except Exception:
            session.rollback()
            raise
        item.update(result=result, selection=selection)
        return result
