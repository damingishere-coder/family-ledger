from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_session
from ..models import HouseholdMember
from ..schemas import MemberCreate, MemberUpdate
from ..services.serializers import member_to_dict


router = APIRouter(prefix="/members", tags=["members"])


@router.get("")
def list_members(include_inactive: bool = True, session: Session = Depends(get_session)):
    statement = select(HouseholdMember)
    if not include_inactive:
        statement = statement.where(HouseholdMember.is_active.is_(True))
    members = session.scalars(
        statement.order_by(HouseholdMember.sort_order, HouseholdMember.id)
    ).all()
    return [member_to_dict(member) for member in members]


@router.post("", status_code=201)
def create_member(payload: MemberCreate, session: Session = Depends(get_session)):
    member = HouseholdMember(**payload.model_dump())
    session.add(member)
    session.commit()
    session.refresh(member)
    return member_to_dict(member)


@router.patch("/{member_id}")
def update_member(
    member_id: int, payload: MemberUpdate, session: Session = Depends(get_session)
):
    member = session.get(HouseholdMember, member_id)
    if member is None:
        raise HTTPException(status_code=404, detail="未找到该家庭成员")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(member, field, value)
    session.commit()
    session.refresh(member)
    return member_to_dict(member)
