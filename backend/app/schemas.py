from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ACCOUNT_TYPES = {
    "wallet",
    "debit_card",
    "credit_card",
    "investment",
    "receivable",
    "other_asset",
    "other_liability",
}


class MemberCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    display_name: str | None = Field(default=None, max_length=120)
    sort_order: int = 0


class MemberUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    display_name: str | None = Field(default=None, max_length=120)
    sort_order: int | None = None
    is_active: bool | None = None


class AccountCreate(BaseModel):
    member_id: int
    name: str = Field(min_length=1, max_length=160)
    institution: str | None = Field(default=None, max_length=160)
    account_type: str
    credit_limit_cents: int | None = None
    billing_day: int | None = Field(default=None, ge=1, le=31)
    include_in_net_worth: bool = True
    sort_order: int = 0
    notes: str | None = None

    @field_validator("account_type")
    @classmethod
    def validate_account_type(cls, value: str) -> str:
        if value not in ACCOUNT_TYPES:
            raise ValueError("不支持的账户类型")
        return value


class AccountUpdate(BaseModel):
    member_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=160)
    institution: str | None = Field(default=None, max_length=160)
    account_type: str | None = None
    credit_limit_cents: int | None = None
    billing_day: int | None = Field(default=None, ge=1, le=31)
    include_in_net_worth: bool | None = None
    sort_order: int | None = None
    notes: str | None = None

    @field_validator("account_type")
    @classmethod
    def validate_account_type(cls, value: str | None) -> str | None:
        if value is not None and value not in ACCOUNT_TYPES:
            raise ValueError("不支持的账户类型")
        return value


class SnapshotCreate(BaseModel):
    snapshot_date: date
    title: str | None = Field(default=None, max_length=200)
    notes: str | None = None


class SnapshotUpdate(BaseModel):
    snapshot_date: date | None = None
    title: str | None = Field(default=None, max_length=200)
    notes: str | None = None


class EntryUpdate(BaseModel):
    amount_cents: int | None
    notes: str | None = None


class CompleteSnapshotRequest(BaseModel):
    allow_incomplete: bool = False


class RestoreMode(BaseModel):
    mode: Literal["replace"] = "replace"


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
