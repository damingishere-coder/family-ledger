from __future__ import annotations

from collections import defaultdict
import csv
from datetime import date, datetime
import io
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from .common import (
    ParsedEntry,
    ParsedSnapshot,
    decode_text,
    infer_account_type,
    parse_money_to_cents,
)


ALIASES = {
    "snapshot_date": {"snapshot_date", "date", "日期", "盘点日期"},
    "member_name": {"member", "member_name", "成员", "家庭成员"},
    "account_name": {"account", "account_name", "账户", "账户名称"},
    "account_type": {"account_type", "type", "类型", "账户类型"},
    "amount": {"amount", "金额", "余额", "本期余额", "待还"},
    "amount_cents": {"amount_cents", "金额_分", "金额（分）"},
    "credit_limit": {"credit_limit", "信用额度", "额度"},
    "credit_limit_cents": {"credit_limit_cents", "信用额度_分", "信用额度（分）"},
    "include": {"include_in_net_worth", "include", "计入净资产", "是否计入家庭净资产"},
    "institution": {"institution", "机构", "机构名称"},
}


def _canonical_headers(headers: list[object]) -> dict[str, int]:
    result: dict[str, int] = {}
    for index, value in enumerate(headers):
        normalized = str(value or "").strip().lower()
        for canonical, aliases in ALIASES.items():
            if normalized in aliases:
                result[canonical] = index
    return result


def _parse_date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip().replace("/", "-").replace("年", "-").replace("月", "-").replace("日", "")
    return date.fromisoformat(text)


def rows_to_snapshots(rows: list[list[object]]) -> list[ParsedSnapshot]:
    if not rows:
        raise ValueError("表格为空")
    headers = _canonical_headers(rows[0])
    required = {"snapshot_date", "member_name", "account_name"}
    missing = required - headers.keys()
    if "amount" not in headers and "amount_cents" not in headers:
        missing.add("amount")
    if missing:
        raise ValueError(f"表格缺少必要列：{', '.join(sorted(missing))}")

    grouped: dict[date, ParsedSnapshot] = {}
    for row_number, row in enumerate(rows[1:], start=2):
        if not any(value not in (None, "") for value in row):
            continue
        try:
            snapshot_date = _parse_date(row[headers["snapshot_date"]])
            member_name = str(row[headers["member_name"]] or "").strip()
            account_name = str(row[headers["account_name"]] or "").strip()
            if not member_name or not account_name:
                raise ValueError("成员或账户名称为空")
            if "amount" in headers:
                raw_amount = row[headers["amount"]]
                amount, amount_warnings = parse_money_to_cents(raw_amount)
            else:
                raw_amount = row[headers["amount_cents"]]
                amount = None if raw_amount in (None, "") else int(raw_amount)
                amount_warnings = []
            category = (
                str(row[headers["account_type"]]).strip()
                if "account_type" in headers and headers["account_type"] < len(row)
                else None
            )
            credit_limit = None
            if "credit_limit" in headers and headers["credit_limit"] < len(row):
                credit_limit, limit_warnings = parse_money_to_cents(row[headers["credit_limit"]])
                amount_warnings.extend(limit_warnings)
            elif "credit_limit_cents" in headers and headers["credit_limit_cents"] < len(row):
                raw_limit = row[headers["credit_limit_cents"]]
                credit_limit = None if raw_limit in (None, "") else int(raw_limit)
            include = True
            if "include" in headers and headers["include"] < len(row):
                raw_include = str(row[headers["include"]] or "").strip().lower()
                include = raw_include not in {"0", "false", "否", "不计入", "no"}
            institution = (
                str(row[headers["institution"]] or "").strip() or None
                if "institution" in headers and headers["institution"] < len(row)
                else None
            )
            parsed = grouped.setdefault(snapshot_date, ParsedSnapshot(snapshot_date))
            parsed.entries.append(
                ParsedEntry(
                    member_name=member_name,
                    account_name=account_name,
                    account_type=category
                    if category in {"wallet", "debit_card", "credit_card", "investment", "receivable", "other_asset", "other_liability"}
                    else infer_account_type(account_name, category),
                    amount_cents=amount,
                    credit_limit_cents=credit_limit,
                    include_in_net_worth=include,
                    institution=institution,
                    raw_name=account_name,
                    raw_value=str(raw_amount or ""),
                    warnings=amount_warnings,
                )
            )
        except (ValueError, IndexError) as exc:
            fallback_date = next(iter(grouped), date.today())
            parsed = grouped.setdefault(fallback_date, ParsedSnapshot(fallback_date))
            parsed.warnings.append(f"第 {row_number} 行未导入：{exc}")
    if not grouped or not any(snapshot.entries for snapshot in grouped.values()):
        raise ValueError("表格中没有可导入的有效数据行")
    return [grouped[key] for key in sorted(grouped)]


def parse_csv(content: bytes) -> list[ParsedSnapshot]:
    snapshots, _encoding = parse_csv_with_encoding(content)
    return snapshots


def parse_csv_with_encoding(content: bytes) -> tuple[list[ParsedSnapshot], str]:
    text, encoding = decode_text(content)
    rows = [list(row) for row in csv.reader(io.StringIO(text))]
    return rows_to_snapshots(rows), encoding


def parse_excel(content: bytes) -> list[ParsedSnapshot]:
    workbook = None
    all_rows: list[list[object]] = []
    try:
        workbook = load_workbook(io.BytesIO(content), data_only=True, read_only=True)
        for sheet in workbook.worksheets:
            rows = [list(row) for row in sheet.iter_rows(values_only=True)]
            if not rows:
                continue
            if not all_rows:
                all_rows.extend(rows)
            else:
                all_rows.extend(rows[1:])
    except (
        BadZipFile,
        InvalidFileException,
        KeyError,
        OSError,
        EOFError,
        ParseError,
        ValueError,
    ) as exc:
        raise ValueError("Excel 文件损坏或不是有效的 XLSX/XLSM 工作簿") from exc
    finally:
        if workbook is not None:
            workbook.close()
    return rows_to_snapshots(all_rows)
