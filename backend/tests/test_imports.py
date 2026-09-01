import io

from openpyxl import Workbook

from app.importers.legacy_markdown import parse_legacy_markdown
from app.importers.tabular import parse_csv, parse_excel


LEGACY_MARKDOWN = """
## 2025年12月25日

### 一、大明同学明细

#### 钱包 / 支付平台
微信：987.63
支付宝：

#### 信用卡
招商银行信用卡：额度 64000，待还 -18.52

#### 应收款
Momo 借款：11704

### 三、总计
总资产：12691.63
总负债：-18.52
顺差：12710.15
"""


def excel_bytes(*rows: list[object]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def test_markdown_parser_preserves_null_negative_and_receivable():
    snapshots = parse_legacy_markdown(LEGACY_MARKDOWN)
    assert len(snapshots) == 1
    entries = {entry.account_name: entry for entry in snapshots[0].entries}
    assert entries["微信"].amount_cents == 98_763
    assert entries["支付宝"].amount_cents is None
    assert entries["招商银行信用卡"].amount_cents == -1_852
    assert entries["招商银行信用卡"].credit_limit_cents == 6_400_000
    assert entries["Momo 借款"].account_type == "receivable"


def test_markdown_import_creates_snapshot_and_report(client):
    response = client.post(
        "/api/import/legacy",
        files={"file": ("history.md", LEGACY_MARKDOWN.encode("utf-8"), "text/markdown")},
    )
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["success_rows"] == 4
    snapshots = client.get("/api/snapshots?status=completed").json()
    assert len(snapshots) == 1
    detail = client.get(f"/api/snapshots/{snapshots[0]['id']}").json()
    assert any(entry["legacy_raw_value"] for entry in detail["entries"])


def test_markdown_preview_is_read_only_and_supports_gb18030(client):
    response = client.post(
        "/api/import/legacy/preview",
        files={"file": ("history.md", LEGACY_MARKDOWN.encode("gb18030"), "text/markdown")},
    )
    assert response.status_code == 200, response.text
    preview = response.json()
    assert preview["source_type"] == "markdown"
    assert preview["detected_encoding"] == "gb18030"
    assert preview["total_snapshots"] == 1
    assert preview["total_rows"] == 4
    assert preview["importable_rows"] == 4
    assert client.get("/api/imports").json() == []
    assert client.get("/api/snapshots").json() == []


def test_csv_parser_supports_blank_and_negative():
    content = "盘点日期,家庭成员,账户名称,账户类型,金额\n2026-01-31,大明,微信,wallet,12.35\n2026-01-31,大明,信用卡,credit_card,-18.52\n2026-01-31,大明,空账户,other_asset,\n"
    snapshots = parse_csv(content.encode("utf-8"))
    assert [item.amount_cents for item in snapshots[0].entries] == [1_235, -1_852, None]


def test_excel_parser_uses_same_tabular_contract():
    content = excel_bytes(
        ["盘点日期", "家庭成员", "账户名称", "账户类型", "金额"],
        ["2026-02-28", "贤贤", "投资账户", "investment", "1000.01"],
    )
    snapshots = parse_excel(content)
    assert snapshots[0].entries[0].amount_cents == 100_001


def test_csv_preview_and_import_endpoints_support_gb18030(client):
    content = (
        "盘点日期,家庭成员,账户名称,账户类型,金额\n"
        "2026-01-31,大明,微信,wallet,12.35\n"
    ).encode("gb18030")
    preview_response = client.post(
        "/api/import/tabular/preview",
        files={"file": ("history.csv", content, "text/csv")},
    )
    assert preview_response.status_code == 200, preview_response.text
    preview = preview_response.json()
    assert preview["detected_encoding"] == "gb18030"
    assert preview["total_rows"] == 1
    assert client.get("/api/imports").json() == []

    import_response = client.post(
        "/api/import/tabular",
        files={"file": ("history.csv", content, "text/csv")},
    )
    assert import_response.status_code == 200, import_response.text
    assert import_response.json()["success_rows"] == 1


def test_excel_preview_is_read_only_then_imports_and_reports_duplicate(client):
    content = excel_bytes(
        ["盘点日期", "家庭成员", "账户名称", "账户类型", "金额"],
        ["2026-02-28", "贤贤", "投资账户", "investment", "1000.01"],
    )
    files = {"file": ("history.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    preview_response = client.post("/api/import/tabular/preview", files=files)
    assert preview_response.status_code == 200, preview_response.text
    assert preview_response.json()["importable_rows"] == 1
    assert client.get("/api/imports").json() == []

    import_response = client.post("/api/import/tabular", files=files)
    assert import_response.status_code == 200, import_response.text
    assert import_response.json()["success_rows"] == 1

    duplicate_response = client.post("/api/import/tabular/preview", files=files)
    assert duplicate_response.status_code == 200, duplicate_response.text
    duplicate = duplicate_response.json()
    assert duplicate["duplicate_snapshots"] == 1
    assert duplicate["importable_rows"] == 0
    assert duplicate["snapshots"][0]["will_skip"] is True


def test_import_preview_rejects_invalid_or_unsupported_files(client):
    broken_excel = client.post(
        "/api/import/tabular/preview",
        files={"file": ("broken.xlsx", b"not-an-excel-file", "application/octet-stream")},
    )
    assert broken_excel.status_code == 422
    assert "Excel 文件损坏" in broken_excel.json()["detail"]

    empty_rows = "盘点日期,家庭成员,账户名称,金额\n无效日期,,,\n".encode("utf-8")
    no_valid_rows = client.post(
        "/api/import/tabular/preview",
        files={"file": ("empty.csv", empty_rows, "text/csv")},
    )
    assert no_valid_rows.status_code == 422
    assert "没有可导入的有效数据行" in no_valid_rows.json()["detail"]

    unsupported = client.post(
        "/api/import/tabular/preview",
        files={"file": ("legacy.xls", b"old-excel", "application/vnd.ms-excel")},
    )
    assert unsupported.status_code == 422
    assert "不支持旧版 XLS" in unsupported.json()["detail"]


def test_import_preview_enforces_upload_limit(client):
    response = client.post(
        "/api/import/legacy/preview",
        files={"file": ("large.md", b"x" * (20 * 1024 * 1024 + 1), "text/markdown")},
    )
    assert response.status_code == 413


def test_exported_amount_columns_do_not_multiply_cents_by_one_hundred():
    content = "snapshot_date,member_name,account_name,account_type,amount,amount_cents\n2026-03-31,大明,微信,wallet,12.35,1235\n"
    snapshots = parse_csv(content.encode("utf-8"))
    assert snapshots[0].entries[0].amount_cents == 1_235


def test_cents_only_column_is_read_as_cents():
    content = "snapshot_date,member_name,account_name,account_type,amount_cents\n2026-03-31,大明,微信,wallet,1235\n"
    snapshots = parse_csv(content.encode("utf-8"))
    assert snapshots[0].entries[0].amount_cents == 1_235
