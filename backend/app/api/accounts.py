from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_session
from ..models import Account, HouseholdMember
from ..schemas import AccountCreate, AccountUpdate
from ..services.serializers import account_to_dict


router = APIRouter(prefix="/accounts", tags=["accounts"])


def _get_account(session: Session, account_id: int) -> Account:
    account = session.scalar(
        select(Account)
        .options(selectinload(Account.member))
        .where(Account.id == account_id)
    )
    if account is None:
        raise HTTPException(status_code=404, detail="未找到该账户")
    return account


@router.get("")
def list_accounts(
    include_archived: bool = True, session: Session = Depends(get_session)
):
    statement = select(Account).options(selectinload(Account.member))
    if not include_archived:
        statement = statement.where(Account.is_archived.is_(False))
    accounts = session.scalars(
        statement.order_by(Account.member_id, Account.sort_order, Account.id)
    ).all()
    return [account_to_dict(account) for account in accounts]


@router.post("", status_code=201)
def create_account(payload: AccountCreate, session: Session = Depends(get_session)):
    if session.get(HouseholdMember, payload.member_id) is None:
        raise HTTPException(status_code=422, detail="所属家庭成员不存在")
    account = Account(**payload.model_dump())
    session.add(account)
    session.commit()
    return account_to_dict(_get_account(session, account.id))


@router.patch("/{account_id}")
def update_account(
    account_id: int, payload: AccountUpdate, session: Session = Depends(get_session)
):
    account = _get_account(session, account_id)
    values = payload.model_dump(exclude_unset=True)
    if "member_id" in values and session.get(HouseholdMember, values["member_id"]) is None:
        raise HTTPException(status_code=422, detail="所属家庭成员不存在")
    for field, value in values.items():
        setattr(account, field, value)
    session.commit()
    return account_to_dict(_get_account(session, account.id))


@router.post("/{account_id}/archive")
def archive_account(account_id: int, session: Session = Depends(get_session)):
    account = _get_account(session, account_id)
    account.is_archived = True
    session.commit()
    return account_to_dict(_get_account(session, account.id))


@router.post("/{account_id}/restore")
def restore_account(account_id: int, session: Session = Depends(get_session)):
    account = _get_account(session, account_id)
    account.is_archived = False
    session.commit()
    return account_to_dict(_get_account(session, account.id))
