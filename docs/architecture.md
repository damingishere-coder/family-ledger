# FamilyLedger V1 架构

## 运行结构

```text
浏览器
  │  http://127.0.0.1:8767
  ▼
FastAPI 单进程
  ├─ /api/*              JSON API
  ├─ /assets/*           React 构建资源
  └─ 其他路径            React SPA
  │
  ▼
SQLite data/family_finance.db
  └─ 每日备份 backups/family_finance_YYYY-MM-DD.db
```

开发阶段由 Vite 提供热更新并代理 `/api`；生产阶段只由 FastAPI 监听 `127.0.0.1`。

## 模块边界

- `backend/app/api/`：HTTP 输入校验、状态码与响应模型。
- `backend/app/models.py`：成员、账户、快照、快照条目、导入记录。
- `backend/app/services/`：计算、快照、Dashboard、导入、导出和备份恢复。
- `backend/app/importers/`：Markdown 与表格解析，只输出原始记录和 warning。
- `frontend/src/pages/`：五个一级入口与快照详情。
- `frontend/src/lib/`：API 客户端、整数分金额工具和键盘导航。

## 财务口径

- 资产类型：`wallet`、`debit_card`、`investment`、`receivable`、`other_asset`。
- 负债类型：`credit_card`、`other_liability`。
- 金额以整数分保存，`NULL` 表示未填写，`0` 表示用户明确填写零。
- 总资产与总负债只汇总 `include_in_net_worth=true` 且金额非空的条目。
- 家庭净资产 = 总资产 - 总负债；负债金额允许为负数。
- 历史条目保存账户名、机构、类型、成员名、信用额度与计入口径的快照副本，当前账户变更不回写历史。

## 数据安全

- SQLite 启用外键、WAL 与 busy timeout。
- 每天首次启动使用 SQLite backup API 生成一致性备份，最多保留 30 份。
- 恢复完整 JSON 前先生成回滚备份，并在一个事务中重建数据。
- 导入不自动纠正名称、空值、负数或汇总差异；所有异常进入导入报告。
- 默认只绑定环回地址，不包含统计 SDK、远程数据库或账号体系。

## 端口与 RunDock

- PRD 示例端口 `8765` 已被现有 `Niuma-Publish-Worker` 占用。
- FamilyLedger 固定注册为 `127.0.0.1:8767`，避免改变其他项目。
- RunDock 启动脚本为项目 `.venv` 中的 Python，工作目录为项目根目录，启用自动重启并以 `/api/health` 验证。
