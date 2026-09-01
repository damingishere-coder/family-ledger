# FamilyLedger V1 实施任务

## 背景

当前项目目录仅包含《家庭快捷月度统计台 PRD.md》，尚无代码。用户要求按 PRD 完成 Windows 本地优先的家庭资产月度盘点台，将项目纳入 Git/GitHub 工作流，并由 RunDock 托管生产进程。

本机 `127.0.0.1:8765` 已由 RunDock 项目 `Niuma-Publish-Worker` 使用，禁止停止、迁移或修改该项目。因此 FamilyLedger 使用相邻空闲端口 `127.0.0.1:8767`，同时通过环境变量保留端口可配置能力。

## 目标

1. 交付 PRD V1 的完整核心闭环：成员与账户、月度盘点、历史、Dashboard、导入导出、备份恢复。
2. 所有财务金额以后端整数分为准，空值与零严格区分，历史原值不被自动修正。
3. React 生产静态资源由 FastAPI 同源提供，最终只运行一个本地进程。
4. 提供 Windows 一键启动入口，并将生产进程注册到 RunDock。
5. 建立 GitHub CI，通过任务分支提交、普通 Push 并创建 PR，不自动合并。

## 允许修改范围

- 项目根目录的工程、文档、启动脚本、CI 与配置文件。
- `frontend/` React + TypeScript 前端。
- `backend/` FastAPI + SQLAlchemy + SQLite 后端及测试。
- `scripts/` 本地启动与运行脚本。
- `docs/` 参考研究、架构与使用说明。

## 禁止修改范围

- `C:\Users\10578\Documents\Ai-Clip-Workflow` 及其 RunDock 注册、端口和进程。
- 其他项目、系统代理、Codex/OpenAI 登录或认证配置。
- GitHub 仓库可见性、权限、历史和默认分支保护设置。
- PRD 明确排除的流水记账、预算、银行同步、OCR、AI、云账号、多设备、Docker、复式记账等功能。
- 任何 API Key、Token、密码、Cookie、`.env` 实际内容或浏览器数据。

## 已确定实现要求

- 后端：Python 3.12、FastAPI、SQLAlchemy 2、Pydantic、SQLite。
- 前端：React、Vite、TypeScript、React Router、Recharts；桌面优先，简洁浅色工作台风格。
- 生产监听：仅 `127.0.0.1:8767`，可用 `FAMILY_LEDGER_HOST` / `FAMILY_LEDGER_PORT` 覆盖。
- 数据目录：默认 `data/family_finance.db`；每日首次启动备份，保留最近 30 份。
- 快照条目保存当时信用额度与计入净资产规则；归档账户不进入新盘点但保留历史。
- 新盘点只带出上期金额作为参考，本期金额保持 `NULL`。
- 金额输入支持负数，Enter/上下方向键/Tab 完成键盘流转；输入停止后自动保存草稿。
- 完成盘点时不得把空白自动当成零；允许用户显式确认保留空白。
- 历史导入保留原始字段，系统重新计算并对差异、空值、疑似名称冲突给出 warning。
- 不复制参考项目源码；缺少许可证的项目只用于产品观察。

## 验收标准

- PRD 第 34 节 20 项 V1 验收标准全部具备对应实现或自动化/人工验证证据。
- 后端覆盖计算、快照、归档、导入、备份恢复测试；SQLite 完整性与外键检查通过。
- 前端构建、类型检查和关键金额/键盘逻辑测试通过。
- Windows 启动脚本能启动单进程服务，`/api/health` 与 SPA 路由返回成功。
- RunDock 中只新增 FamilyLedger 注册，不影响其他项目；验证注册 PID、祖先链、8767 监听和 HTTP 健康。
- 最终 diff 无范围外修改、敏感信息、构建产物、日志、缓存、硬编码密钥和遗留 debug/TODO。
- 任务分支完成有意义提交，远端 SHA 与本地一致，PR 指向远端真实默认分支，CI 结果明确。

## 测试命令

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
Set-Location frontend
npm run test -- --run
npm run build
Set-Location ..
.\.venv\Scripts\python.exe scripts\verify_runtime.py
```

## 返回格式

- 实现摘要与关键入口。
- 自动化测试、SQLite、HTTP、RunDock 运行证据。
- Git 初始状态、默认分支、任务分支、提交与远端 SHA、Push、PR、CI、合并状态。
- 已知限制、风险与回滚方法。

## 2026-09-01 蓝白桌面工作台重构

### 背景与目标

用户否定当前绿色、宽留白的页面视觉，并提供蓝白色 FamilyLedger 工作台参考图。本轮只还原参考图中的实际应用界面，不把外层宣传标题、四宫格和流程箭头加入产品。

### 允许修改范围

- `frontend/src/components/`、`frontend/src/pages/`、`frontend/src/lib/` 与 `frontend/src/styles.css`。
- 本任务文件及对应的前端纯逻辑测试。

### 禁止修改范围

- 后端 API、数据库结构、财务计算口径、导入导出格式和本地运行端口。
- 金额整数分、`NULL` 未填写、自动保存、盘点完成确认和账户归档保护语义。
- 新增联网字体、外部 UI 框架、多币种、云同步或银行同步。

### 已确定实现要求

- 全部六个路由统一为亮蓝主色、深蓝文字、淡蓝灰背景、白色卡片和紧凑桌面工作台布局。
- 品牌显示“家底 · FamilyLedger”，Logo 使用现有 Lucide 图标与 CSS 组合，不复制参考图资产。
- 概览使用白底 KPI、蓝色趋势图、环形资产构成和历史表格。
- 盘点增加进度条及成员双栏账户录入，同时保持键盘顺序与 550ms 自动保存。
- 历史增加年份标签和图表/表格视图切换；账户增加客户端筛选、搜索、分组表格和数据快捷区。
- 数据快捷操作抽成共享组件；数据管理和快照详情沿用同一设计系统。
- 桌面优先验证 1280、1440、1920 宽度，不实施完整手机布局。

### 验收与测试

- 前端纯逻辑测试覆盖账户组合筛选、搜索、归档显示和快照比较。
- 运行前端测试、类型检查、构建、后端测试与 `scripts/verify_runtime.py`。
- 使用临时数据库逐页检查六个路由、图表尺寸、表格溢出、盘点键盘流、自动保存、账户弹窗和数据快捷入口。
- 最终提交仅包含本轮文件，普通 Push 更新 PR #1，等待 CI；不得自动合并。
