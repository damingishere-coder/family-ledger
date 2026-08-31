from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_session
from ..services.serializers import dashboard_to_dict


router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def dashboard(session: Session = Depends(get_session)):
    return dashboard_to_dict(session)
