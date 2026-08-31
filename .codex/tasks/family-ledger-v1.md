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
