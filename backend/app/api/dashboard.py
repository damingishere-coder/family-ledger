from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_session
from ..services.serializers import dashboard_to_dict


router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def dashboard(snapshot_id: int | None = None, session: Session = Depends(get_session)):
    try:
        return dashboard_to_dict(session, snapshot_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
