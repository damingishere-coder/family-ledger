from __future__ import annotations

import re
from datetime import date

from .common import (
    ParsedEntry,
    ParsedSnapshot,
    infer_account_type,
    month_end,
    normalize_institution,
    normalize_member_name,
    normalized_account_name,
    parse_money_to_cents,
)


DATE_RE = re.compile(r"(?P<year>20\d{2})\s*年\s*(?P<month>\d{1,2})\s*月\s*(?P<day>\d{1,2})\s*[日号]?")
NUMBER_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")
CATEGORY_WORDS = (
    "钱包", "支付平台", "储蓄卡", "借记卡", "信用卡", "投资", "证券",
    "应收", "待收", "其他资产", "其他负债",
)
SUMMARY_KEYS = {
    "家庭总余额": "total_assets_cents", "总资产": "total_assets_cents",
    "家庭总负债": "total_liabilities_cents", "总负债": "total_liabilities_cents",
    "净资产": "net_worth_cents", "顺差": "net_worth_cents",
}
SKIP_NAMES = {"账户", "银行", "名称", "项目", "合计", "小计", "小记", "总计", "家庭总余额"}
SHARED_INVESTMENTS = {"黄金etf", "基金", "京东金融"}


def _member_from_heading(line: str) -> str | None:
    if not line.lstrip().startswith("#") or "明细" not in line:
        return None
    text = re.sub(r"^#+\s*", "", line).strip()
    text = re.sub(r"^[一二三四五六七八九十0-9]+[、.．]\s*", "", text)
    text = re.sub(r"(同学|宝贝)?\s*(资产)?明细.*$", "", text).strip(" ：:")
    return normalize_member_name(text) if text else None


def _table_cells(line: str) -> list[str] | None:
    raw = line.strip()
    if not raw.startswith("|"):
        return None
    return [cell.strip() for cell in raw.strip("|").split("|")]


def _is_separator(cells: list[str]) -> bool:
    return bool(cells) and all(not cell or set(cell) <= {"-", ":", " "} for cell in cells)


def _entry(
    *, member: str, name: str, account_type: str, amount_raw: object,
    line_number: int, institution: str | None = None,
    credit_limit_raw: object | None = None, billing_day: int | None = None,
    include: bool = True,
) -> ParsedEntry:
    amount, warnings = parse_money_to_cents(amount_raw)
    credit_limit = None
    if credit_limit_raw is not None:
        credit_limit, limit_warnings = parse_money_to_cents(credit_limit_raw)
        warnings.extend(limit_warnings)
    institution = normalize_institution(institution)
    return ParsedEntry(
        member_name=normalize_member_name(member),
        account_name=normalized_account_name(account_type, name, institution),
        account_type=account_type, amount_cents=amount,
        credit_limit_cents=credit_limit, include_in_net_worth=include,
        institution=institution, billing_day=billing_day, raw_name=name,
        raw_value="" if amount_raw is None else str(amount_raw), source_location=f"第 {line_number} 行",
        warnings=warnings,
    )


def _parse_account_line(line: str, member: str, category: str | None, line_number: int) -> ParsedEntry | None:
    raw = line.strip()
    if not raw or raw.startswith("#") or raw.startswith("---") or raw.startswith("|"):
        return None
    match = NUMBER_RE.search(raw)
    if match is None:
        blank_match = re.match(r"(?P<name>[^：:]+)[：:]\s*$", raw)
        if not blank_match:
            return None
        name, value_text = blank_match.group("name").strip(), ""
    else:
        name, value_text = raw[:match.start()].strip(" ：:|-，,"), match.group(0)
    if not name or name in SKIP_NAMES or any(token in name for token in SUMMARY_KEYS):
        return None
    limit_match = re.search(r"额度[^\d+\-]*([-+]?\d[\d,]*(?:\.\d+)?)", raw)
    debt_match = re.search(r"待还[^\d+\-]*([-+]?\d[\d,]*(?:\.\d+)?)", raw)
    if debt_match:
        value_text = debt_match.group(1)
    account_type = infer_account_type(name, category)
    institution = None
    if account_type in {"credit_card", "debit_card"}:
        institution = re.sub(r"(信用卡|储蓄卡|借记卡).*$", "", name).strip()
    return _entry(
        member=(
            "家庭公共"
            if account_type in {"receivable", "other_liability"} or name.lower() in SHARED_INVESTMENTS
            else member
        ),
        name=name, account_type=account_type, amount_raw=value_text,
        line_number=line_number, institution=institution,
        credit_limit_raw=limit_match.group(1) if limit_match else None,
        include="不计入总数" not in name,
    )


def _append_table_row(
    snapshot: ParsedSnapshot, member: str, headers: list[str], cells: list[str], line_number: int,
) -> None:
    first = cells[0] if cells else ""
    if first in {"小记", "小计", "合计", "总计"}:
        return
    if headers[:2] == ["微信", "支付宝"]:
        if first in {"证券/投资账户", "证券", "投资账户"}:
            snapshot.entries.append(_entry(
                member=member, name="证券/投资账户", account_type="investment",
                amount_raw=cells[1] if len(cells) > 1 else "", line_number=line_number,
            ))
            return
        for index, name in enumerate(headers[:2]):
            snapshot.entries.append(_entry(
                member=member, name=name, account_type="wallet",
                amount_raw=cells[index] if index < len(cells) else "", line_number=line_number,
            ))
        return
    if headers and headers[0] in {"储蓄卡", "借记卡"}:
        institution = cells[1] if len(cells) > 1 else ""
        if institution:
            snapshot.entries.append(_entry(
                member=member, name=institution, account_type="debit_card",
                amount_raw=cells[2] if len(cells) > 2 else "", institution=institution,
                line_number=line_number,
            ))
        return
    if headers and headers[0] == "信用卡":
        institution = cells[1] if len(cells) > 1 else ""
        if not institution:
            return
        if infer_account_type(institution) == "receivable":
            snapshot.entries.append(_entry(
                member="家庭公共", name=institution, account_type="receivable",
                amount_raw=cells[3] if len(cells) > 3 else "", line_number=line_number,
                include="不计入总数" not in institution,
            ))
            return
        day_match = re.search(r"(\d{1,2})", first)
        snapshot.entries.append(_entry(
            member=member, name=institution, account_type="credit_card",
            amount_raw=cells[3] if len(cells) > 3 else "", institution=institution,
            credit_limit_raw=cells[2] if len(cells) > 2 else "",
            billing_day=int(day_match.group(1)) if day_match else None,
            line_number=line_number,
        ))
        return
    if len(cells) >= 2 and first:
        account_type = infer_account_type(first)
        target_member = (
            "家庭公共"
            if account_type in {"receivable", "other_liability"} or first.lower() in SHARED_INVESTMENTS
            else member
        )
        snapshot.entries.append(_entry(
            member=target_member, name=first, account_type=account_type,
            amount_raw=cells[-1], line_number=line_number,
            include="不计入总数" not in first,
        ))


def parse_legacy_markdown(content: str) -> list[ParsedSnapshot]:
    snapshots: list[ParsedSnapshot] = []
    current: ParsedSnapshot | None = None
    member: str | None = None
    category: str | None = None
    table_headers: list[str] | None = None

    for line_number, line in enumerate(content.splitlines(), start=1):
        date_match = DATE_RE.search(line)
        if date_match and line.lstrip().startswith("#"):
            try:
                source_date = date(
                    int(date_match.group("year")), int(date_match.group("month")), int(date_match.group("day"))
                )
            except ValueError:
                if current:
                    current.blocking_errors.append(f"第 {line_number} 行日期无效：{line.strip()}")
                    current.status = "blocked"
                continue
            current = ParsedSnapshot(
                snapshot_date=month_end(source_date), source_date=source_date, layout="markdown-horizontal"
            )
            snapshots.append(current)
            member = category = None
            table_headers = None
            continue
        if current is None:
            continue
        possible_member = _member_from_heading(line)
        if possible_member:
            member, category, table_headers = possible_member, None, None
            continue
        if line.lstrip().startswith("#") and "总计" in line:
            member = category = None
            table_headers = None
            continue

        cells = _table_cells(line)
        if cells is not None:
            if _is_separator(cells):
                continue
            if cells and (cells[:2] == ["微信", "支付宝"] or cells[0] in {"储蓄卡", "借记卡", "信用卡"}):
                table_headers = cells
                continue
            if member and table_headers:
                try:
                    _append_table_row(current, member, table_headers, cells, line_number)
                except ValueError as exc:
                    current.blocking_errors.append(f"第 {line_number} 行：{exc}")
                    current.status = "blocked"
                continue
            if len(cells) >= 2:
                summary_key = next((key for text, key in SUMMARY_KEYS.items() if text in cells[0]), None)
                if summary_key:
                    try:
                        amount, money_warnings = parse_money_to_cents(cells[-1])
                        current.legacy_summary[summary_key] = amount
                        current.warnings.extend(money_warnings)
                    except ValueError as exc:
                        current.blocking_errors.append(f"第 {line_number} 行：{exc}")
                        current.status = "blocked"
                continue

        stripped = re.sub(r"^#+\s*", "", line).strip()
        if any(word in stripped for word in CATEGORY_WORDS) and not NUMBER_RE.search(stripped):
            category, table_headers = stripped, None
            continue
        for label, key in SUMMARY_KEYS.items():
            if label in stripped:
                amount_match = NUMBER_RE.search(stripped)
                if amount_match:
                    amount, money_warnings = parse_money_to_cents(amount_match.group(0))
                    current.legacy_summary[key] = amount
                    current.warnings.extend(money_warnings)
                break
        else:
            if member:
                try:
                    entry = _parse_account_line(line, member, category, line_number)
                except ValueError as exc:
                    current.blocking_errors.append(f"第 {line_number} 行：{exc}")
                    current.status = "blocked"
                else:
                    if entry:
                        current.entries.append(entry)

    if not snapshots:
        raise ValueError("未在 Markdown 中找到形如 2025年12月25日 的盘点日期标题")
    for snapshot in snapshots:
        if not snapshot.entries:
            snapshot.warnings.append("该日期未解析出账户明细")
    if not any(snapshot.entries for snapshot in snapshots):
        raise ValueError("Markdown 中没有可导入的账户明细")
    return snapshots
