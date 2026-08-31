from __future__ import annotations

import re
from datetime import date

from .common import ParsedEntry, ParsedSnapshot, infer_account_type, parse_money_to_cents


DATE_RE = re.compile(r"(?P<year>20\d{2})\s*年\s*(?P<month>\d{1,2})\s*月\s*(?P<day>\d{1,2})\s*[日号]?")
NUMBER_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")
CATEGORY_WORDS = (
    "钱包",
    "支付平台",
    "储蓄卡",
    "借记卡",
    "信用卡",
    "投资",
    "证券",
    "应收",
    "其他资产",
    "其他负债",
)


def _member_from_heading(line: str) -> str | None:
    if not line.lstrip().startswith("#") or "明细" not in line:
        return None
    text = re.sub(r"^#+\s*", "", line).strip()
    text = re.sub(r"^[一二三四五六七八九十0-9]+[、.．]\s*", "", text)
    text = re.sub(r"(同学|宝贝)?\s*(资产)?明细.*$", "", text).strip(" ：:")
    return text or None


def _parse_account_line(
    line: str, member: str, category: str | None
) -> ParsedEntry | None:
    raw = line.strip()
    if not raw or raw.startswith("#") or raw.startswith("---"):
        return None
    if raw.startswith("|"):
        cells = [cell.strip() for cell in raw.strip("|").split("|")]
        if len(cells) < 2 or all(set(cell) <= {"-", ":"} for cell in cells if cell):
            return None
        name = cells[0]
        value_text = next((cell for cell in reversed(cells[1:]) if NUMBER_RE.search(cell)), "")
    else:
        match = NUMBER_RE.search(raw)
        if match is None:
            # A named account with an explicitly blank value must remain NULL.
            blank_match = re.match(r"(?P<name>[^：:]+)[：:]\s*$", raw)
            if blank_match:
                name = blank_match.group("name").strip()
                value_text = ""
            else:
                return None
        else:
            name = raw[: match.start()].strip(" ：:|-，,")
            value_text = match.group(0)
    if not name or name in {"账户", "银行", "名称", "项目", "合计", "小计"}:
        return None
    if any(word == name for word in CATEGORY_WORDS):
        return None
    if any(token in name for token in ("总资产", "总负债", "净资产", "顺差", "总计")):
        return None

    credit_limit = None
    if "额度" in raw:
        limit_match = re.search(r"额度[^\d+\-]*([-+]?\d[\d,]*(?:\.\d+)?)", raw)
        if limit_match:
            credit_limit, _ = parse_money_to_cents(limit_match.group(1))
    if "待还" in raw:
        debt_match = re.search(r"待还[^\d+\-]*([-+]?\d[\d,]*(?:\.\d+)?)", raw)
        if debt_match:
            value_text = debt_match.group(1)

    try:
        amount, warnings = parse_money_to_cents(value_text)
    except ValueError as exc:
        return ParsedEntry(
            member_name=member,
            account_name=name,
            account_type=infer_account_type(name, category),
            amount_cents=None,
            raw_name=name,
            raw_value=raw,
            warnings=[str(exc)],
        )
    legacy_name = name
    name = re.sub(r"[：:]?\s*额度\s*$", "", name).strip()
    return ParsedEntry(
        member_name=member,
        account_name=name,
        account_type=infer_account_type(name, category),
        amount_cents=amount,
        credit_limit_cents=credit_limit,
        institution=name.replace("信用卡", "").replace("储蓄卡", "").strip() or None,
        raw_name=legacy_name,
        raw_value=raw,
        warnings=warnings,
    )


def parse_legacy_markdown(content: str) -> list[ParsedSnapshot]:
    snapshots: list[ParsedSnapshot] = []
    current: ParsedSnapshot | None = None
    member: str | None = None
    category: str | None = None

    for line_number, line in enumerate(content.splitlines(), start=1):
        date_match = DATE_RE.search(line)
        if date_match and line.lstrip().startswith("#"):
            try:
                parsed_date = date(
                    int(date_match.group("year")),
                    int(date_match.group("month")),
                    int(date_match.group("day")),
                )
            except ValueError:
                if current:
                    current.warnings.append(f"第 {line_number} 行日期无效：{line.strip()}")
                continue
            current = ParsedSnapshot(snapshot_date=parsed_date)
            snapshots.append(current)
            member = None
            category = None
            continue
        if current is None:
            continue

        possible_member = _member_from_heading(line)
        if possible_member:
            if "总计" in possible_member:
                member = None
            else:
                member = possible_member
            category = None
            continue

        stripped = re.sub(r"^#+\s*", "", line).strip()
        if any(word in stripped for word in CATEGORY_WORDS) and not NUMBER_RE.search(stripped):
            category = stripped
            continue

        for label, key in (
            ("总资产", "total_assets_cents"),
            ("总负债", "total_liabilities_cents"),
            ("净资产", "net_worth_cents"),
            ("顺差", "net_worth_cents"),
        ):
            if label in stripped:
                amount_match = NUMBER_RE.search(stripped)
                if amount_match:
                    amount, warnings = parse_money_to_cents(amount_match.group(0))
                    current.legacy_summary[key] = amount
                    current.warnings.extend(warnings)
                break
        else:
            if member:
                entry = _parse_account_line(line, member, category)
                if entry:
                    current.entries.append(entry)

    if not snapshots:
        raise ValueError("未在 Markdown 中找到形如 2025年12月25日 的盘点日期标题")
    for snapshot in snapshots:
        if not snapshot.entries:
            snapshot.warnings.append("该日期未解析出账户明细")
    return snapshots
