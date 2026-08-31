# FamilyLedger / 家庭快捷月度统计台

FamilyLedger 是 Windows 本地运行的家庭资产月度盘点工具。它不是日常流水记账软件：每隔一段时间更新微信、支付宝、银行卡、信用卡、投资和应收款余额，系统自动保存快照并计算家庭净资产趋势。

## 已实现的 V1

- 家庭成员与七类账户管理、排序、归档和恢复。
- 新建本期盘点，显示上一期金额但本期保持空白。
- Enter、方向键、Tab 快速录入，550ms 自动保存草稿。
- 整数分计算总资产、总负债、净资产和投资资产；空值与零严格区分。
- Dashboard、趋势图、资产构成、成员汇总、历史列表与详情编辑。
- Markdown、CSV、XLSX 历史导入，保留原始值和差异警告。
- JSON 完整备份/恢复，CSV/XLSX 导出，每日 SQLite 自动备份。
- FastAPI 同源提供 React 构建产物，核心功能不依赖互联网。

## 一键启动

双击根目录的 `启动家庭统计台.bat`。首次运行会在项目内创建 `.venv`、安装本地依赖并构建前端，随后打开：

```text
http://127.0.0.1:8767
```

PRD 的示例端口 `8765` 已被本机现有 RunDock 项目 `Niuma-Publish-Worker` 占用。为避免破坏现有服务，FamilyLedger 使用 `8767`。V1 始终只绑定 `127.0.0.1`。

## 开发

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt

Set-Location frontend
npm install
npm run dev
```

生产构建与后端：

```powershell
Set-Location frontend
npm run build
Set-Location ..
.\.venv\Scripts\python.exe scripts\serve.py --host 127.0.0.1 --port 8767
```

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
Set-Location frontend
npm run test -- --run
npm run build
Set-Location ..
.\.venv\Scripts\python.exe scripts\verify_runtime.py
```

CSV/Excel 表头见 [docs/import-format.md](docs/import-format.md)，参考研究见 [docs/reference-research.md](docs/reference-research.md)，系统边界见 [docs/architecture.md](docs/architecture.md)。

## 数据位置

- SQLite：`data/family_finance.db`
- 自动与手动备份：`backups/`
- 前端静态资源：`frontend/dist/`

上述数据库、备份与构建产物均不会提交到 Git。建议定期把完整 JSON 备份复制到项目目录外的安全位置。
