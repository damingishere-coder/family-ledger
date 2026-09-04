# 历史数据导入预览与反馈修复

## 背景

当前 Markdown、CSV、XLSX 解析器和正式导入接口已经存在，但前端在选择文件后立即提交，只有页面顶部通知，没有解析进度、确认步骤或就近错误反馈。RunDock 还会直接执行 `scripts/serve.py`，可能在源码更新后继续提供旧的 `frontend/dist`。

## 目标

- 将导入改为“选择文件 → 只读预览 → 用户确认 → 正式导入”。
- 让解析中、失败、导入中和完成状态始终可见。
- 兼容 UTF-8-SIG 与 GB18030 的 Markdown/CSV 文本。
- 确保 RunDock 直接启动时不会提供过期前端资源。

## 允许修改范围

- `backend/app/api/data.py`
- `backend/app/importers/` 与 `backend/app/services/imports.py`
- `backend/tests/test_imports.py`、`backend/tests/test_serve.py`
- `frontend/src/components/DataActionsPanel.tsx`
- `frontend/src/lib/api.ts`、`frontend/src/pages/DataPage.tsx`、`frontend/src/types.ts`、`frontend/src/styles.css`
- 必要的前端测试、测试配置与锁文件
- `scripts/serve.py`、`scripts/verify_runtime.py`
- `docs/import-format.md`、`README.md`

## 禁止修改范围

- 不修改或导入 `data/family_finance.db`。
- 不修改备份内容、现有用户数据或数据库结构。
- 不支持旧版 `.xls`，不引入第三方 Provider 或外部上传。
- 不重启 8767 正式服务，不部署或合并 PR，除非用户后续明确确认。

## 已确定实现要求

- 新增 `/api/import/legacy/preview` 与 `/api/import/tabular/preview`，预览不得写数据库。
- 前端保留所选 `File`，确认时重新提交现有正式导入接口；不保存服务端临时文件。
- 预览展示文件名、来源类型、编码、快照数、有效行数、日期明细、重复来源和警告。
- 无有效数据、损坏工作簿、错误扩展名和超过 20MB 均返回可读中文错误。
- 运行入口按源码/清单与 `dist/index.html` 的修改时间判断是否需要重新构建。

## 验收标准

- 选择有效 `.md` 或 `.xlsx/.xlsm` 后出现预览，确认前数据库计数不变。
- 确认后写入一次并显示最终统计；取消不写入。
- 无效文件在预览窗口内显示明确原因并可重新选择。
- RunDock 直接执行 `serve.py` 时能自动刷新过期前端构建。
- 所有后端、前端测试、类型检查、构建和隔离运行时验证通过。

## 测试命令

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
Set-Location frontend
npm test -- --run
npm run typecheck
npm run build
Set-Location ..
.\.venv\Scripts\python.exe scripts\verify_runtime.py
```

## 返回格式

报告改动摘要、测试命令与结果、数据安全验证、Git/PR/CI 状态，以及正式服务是否重启。
