from __future__ import annotations

from dataclasses import dataclass, field
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


@dataclass
class ParsedSnapshot:
    snapshot_date: date
    entries: list[ParsedEntry] = field(default_factory=list)
    legacy_summary: dict[str, int | None] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


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
    if "信用" in text or "待还" in text or "liability" in text or "负债" in text:
        return "credit_card" if "卡" in text or "信用" in text else "other_liability"
    if "投资" in text or "证券" in text or "股票" in text or "基金" in text:
        return "investment"
    if "应收" in text or "借款" in text or "待收" in text:
        return "receivable"
    if "微信" in text or "支付宝" in text or "钱包" in text or "wallet" in text:
        return "wallet"
    if "储蓄" in text or "借记" in text or "银行" in text or "debit" in text:
        return "debit_card"
    if "其他负债" in text:
        return "other_liability"
    return "other_asset"
