from __future__ import annotations

from dataclasses import dataclass, field
from calendar import monthrange
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


TEXT_ENCODINGS = ("utf-8-sig", "gb18030")


@dataclass
class ParsedEntry:
    member_name: str
    account_name: str
    account_type: str
    amount_cents: int | None
    credit_limit_cents: int | None = None
    include_in_net_worth: bool = True
    institution: str | None = None
    raw_name: str | None = None
    raw_value: str | None = None
    warnings: list[str] = field(default_factory=list)
    billing_day: int | None = None
    source_sheet: str | None = None
    source_location: str | None = None


@dataclass
class ParsedSnapshot:
    snapshot_date: date | None
    entries: list[ParsedEntry] = field(default_factory=list)
    legacy_summary: dict[str, int | None] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    source_date: date | None = None
    layout: str = "flat"
    source_sheet: str | None = None
    status: str = "importable"
    blocking_errors: list[str] = field(default_factory=list)


MEMBER_ALIASES = {
    "大明": "峰峰",
    "大明同学": "峰峰",
    "贤贤宝贝": "贤贤",
}

INSTITUTION_ALIASES = {"自信银行": "中信银行"}


def month_end(value: date) -> date:
    return date(value.year, value.month, monthrange(value.year, value.month)[1])


def normalize_member_name(value: str) -> str:
    name = value.strip()
    return MEMBER_ALIASES.get(name, name)


def normalize_institution(value: str | None) -> str | None:
    if value is None:
        return None
    name = value.strip()
    if not name:
        return None
    return INSTITUTION_ALIASES.get(name, name)


def normalized_account_name(account_type: str, name: str, institution: str | None) -> str:
    institution = normalize_institution(institution)
    if name.strip().lower() == "黄金etf":
        return "黄金ETF"
    if account_type == "debit_card" and institution:
        return f"{institution}储蓄卡"
    if account_type == "credit_card" and institution:
        return f"{institution}信用卡"
    return name.strip()


def decode_text(content: bytes) -> tuple[str, str]:
    for encoding in TEXT_ENCODINGS:
        try:
            return content.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise ValueError("文本文件编码无法识别，请保存为 UTF-8 或 GB18030 后重试")


def parse_money_to_cents(raw: object) -> tuple[int | None, list[str]]:
    warnings: list[str] = []
    if raw is None:
        return None, warnings
    text = str(raw).strip()
    if not text or text.lower() in {"null", "none", "n/a", "-", "—", "未填", "空白"}:
        return None, warnings
    negative_parentheses = text.startswith("(") and text.endswith(")")
    cleaned = (
        text.replace(",", "")
        .replace("¥", "")
        .replace("￥", "")
        .replace("元", "")
        .replace(" ", "")
    )
    if negative_parentheses:
        cleaned = f"-{cleaned[1:-1]}"
    try:
        value = Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError(f"无法识别金额：{text}") from exc
    rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if rounded != value:
        warnings.append(f"金额 {text} 超过两位小数，系统按分四舍五入为 {rounded}")
    return int(rounded * 100), warnings


def infer_account_type(name: str, category: str | None = None) -> str:
    text = f"{category or ''} {name}".lower()
    if "待报销" in text or "待还款" in text or "应收" in text or "借款" in text or "待收" in text:
        return "receivable"
    if "待还姑姑" in text:
        return "other_liability"
    if "信用" in text or "待还" in text or "liability" in text or "负债" in text:
        return "credit_card" if "卡" in text or "信用" in text else "other_liability"
    if any(token in text for token in ("投资", "证券", "股票", "基金", "黄金etf", "京东金融")):
        return "investment"
    if "微信" in text or "支付宝" in text or "钱包" in text or "wallet" in text:
        return "wallet"
    if "储蓄" in text or "借记" in text or "银行" in text or "debit" in text:
        return "debit_card"
    if "其他负债" in text:
        return "other_liability"
    return "other_asset"
