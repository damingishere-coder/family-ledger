"""Parse related files together, preserving evidence separately from user decisions."""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import hashlib

from ..importers.common import decode_text, ParsedSnapshot
from ..importers.legacy_markdown import parse_legacy_markdown
from ..importers.tabular import parse_csv_with_encoding, parse_excel


def parse_bundle(files: list[tuple[str, bytes]]) -> tuple[list[ParsedSnapshot], dict]:
    markdown, tables = [], []
    hashes, evidence = {}, []
    dates = defaultdict(set)
    for name, content in files:
        if name in hashes:
            raise ValueError("文件名重复，请一次只选择每个来源的一份文件")
        hashes[name] = hashlib.sha256(content).hexdigest()
        suffix = name.lower().rsplit(".", 1)[-1]
        if suffix in {"md", "markdown", "txt"}:
            text, _ = decode_text(content)
            parsed = parse_legacy_markdown(text)
            for snapshot in parsed:
                if snapshot.source_date and snapshot.status != "blocked":
                    dates[snapshot.source_date.strftime("%Y-%m")].add(snapshot.source_date)
                for entry in snapshot.entries:
                    entry.source_filename = name
            markdown.extend(parsed)
        elif suffix in {"xlsx", "xlsm", "csv"}:
            tables.append((name, content, suffix))
        else:
            raise ValueError("仅支持 MD、TXT、CSV、XLSX、XLSM 文件")
    overrides = {}
    for values in dates.values():
        if len(values) == 1:
            value = next(iter(values))
            overrides[(value.year, value.month)] = value
    snapshots = []
    for name, content, suffix in tables:
        parsed = parse_excel(content, overrides) if suffix != "csv" else parse_csv_with_encoding(content)[0]
        for snapshot in parsed:
            for entry in snapshot.entries:
                entry.source_filename = name
            if snapshot.snapshot_date and len(dates[snapshot.snapshot_date.strftime("%Y-%m")]) > 1:
                snapshot.blocking_errors.append("Markdown 同月日期不唯一，请核对来源")
                snapshot.status = "blocked"
        snapshots.extend(parsed)
    table_months = {s.snapshot_date.strftime("%Y-%m") for s in snapshots if s.snapshot_date}
    for md in markdown:
        month = md.snapshot_date.strftime("%Y-%m") if md.snapshot_date else None
        if month not in table_months:
            snapshots.append(md)
            continue
        matches = [s for s in snapshots if s.snapshot_date and s.snapshot_date.strftime("%Y-%m") == month]
        if len(matches) != 1:
            continue  # Duplicate months are blocked by the review service.
        target = matches[0]
        for source in md.entries:
            candidates = [e for e in target.entries if
                e.account_type == source.account_type and e.member_name == source.member_name
                and e.account_name == source.account_name and e.institution == source.institution]
            if source.account_type == "receivable" and not source.include_in_net_worth:
                candidates = [e for e in target.entries if e.account_type == "receivable"
                              and source.amount_cents is not None and e.amount_cents == source.amount_cents
                              and (e.ownership_unresolved or e.member_name == source.member_name)]
                if len(candidates) != 1:
                    target.blocking_errors.append(f"{source.source_filename} {source.source_location}：不计入条目无法唯一匹配 Excel")
                    target.status = "blocked"
                    continue
                candidates[0].include_in_net_worth = False
                # Keep the old Excel interpretation for safe comparison against old imports.
                setattr(candidates[0], "evidenced_member", source.member_name)
                candidates[0].type_unresolved = False
            if len(candidates) == 1:
                entry = candidates[0]
                if source.billing_day:
                    if entry.billing_day and entry.billing_day != source.billing_day:
                        target.blocking_errors.append(f"{source.account_name} 同月还款日冲突")
                        target.status = "blocked"
                    entry.billing_day = source.billing_day
                evidence.append({"month": month, "account": entry.account_name,
                    "source": source.source_filename, "location": source.source_location,
                    "markdown_cents": source.amount_cents, "excel_cents": entry.amount_cents,
                    "message": "金额采用 Excel；Markdown 用于归属、还款日和计入规则核对"})
        for field, value in md.legacy_summary.items():
            if field in target.legacy_summary and target.legacy_summary[field] != value:
                target.warnings.append(f"Markdown 的原表汇总与 Excel 不一致，采用 Excel 明细重算（{md.source_date}）")
    # For older sheets without per-month repayment dates, accept only a unique
    # institution/member day from the supplied Markdown, as in the prior repair.
    days = defaultdict(set)
    for md in markdown:
        for entry in md.entries:
            if entry.billing_day and entry.institution:
                days[(entry.member_name, entry.institution)].add(entry.billing_day)
    for snapshot in snapshots:
        for entry in snapshot.entries:
            options = days[(entry.member_name, entry.institution)]
            if not entry.billing_day and len(options) == 1:
                entry.billing_day = next(iter(options))
    return snapshots, {"source_sha256": hashes, "evidence": evidence}


def proposed_entries(snapshots: list[ParsedSnapshot]) -> list[ParsedSnapshot]:
    result = deepcopy(snapshots)
    for snapshot in result:
        for entry in snapshot.entries:
            member = getattr(entry, "evidenced_member", None)
            if member:
                entry.member_name = member
                entry.ownership_unresolved = False
    return result
