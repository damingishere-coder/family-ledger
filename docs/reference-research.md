# FamilyLedger 参考项目研究

研究日期：2026-08-31

本研究只提炼产品与架构思路，不复制第三方源码、样式资源或品牌资产。许可证信息来自各 GitHub 仓库元数据与 README；若许可证不明确，按“不可复用源码”处理。

## 结论摘要

FamilyLedger 应保持一个很窄的产品中心：以“家庭净资产”为首要数字，以“3～5 分钟完成一次盘点”为首要交互，以本地 SQLite、可恢复备份和历史快照为数据底座。

采用的共同原则：

- 首页只保留净资产、总资产、总负债、投资资产四个核心指标。
- 账户按成员与资产类型分组，归档不破坏历史。
- 趋势图只在净资产、总资产、总负债之间切换。
- 数据导入必须产生可检查报告，原值与系统计算值并存。
- 本地优先、无需账号、核心功能断网可用。

明确不采用：

- 交易流水、预算、账本规则、复式记账。
- 行情、券商同步、多币种估值、收益率算法。
- 云同步、插件、移动端、Docker、自托管集群。
- 参考项目的源码、组件实现、品牌与图标资源。

## Azqato/net-worth-tracker

来源：[GitHub 仓库](https://github.com/Azqato/net-worth-tracker)

仓库是浏览器端的月度净资产统计工具，采用 HTML/CSS/Vanilla JS、Chart.js 与 SheetJS，数据不需要服务端。GitHub 仓库元数据未声明许可证，因此只允许观察产品表现，不复制代码。

值得借鉴：

- 以月度净资产为中心，而不是以流水为中心。
- 折线图和资产类别构成的组合足以回答大部分概览问题。
- Excel 导入导出入口应靠近数据管理，而不是占据主导航。
- 完全本地、无账号的低摩擦首次使用体验。

不应该借鉴：

- 浏览器内存/文件作为唯一长期存储，不适合需要可靠历史与恢复的家庭数据。
- CDN 依赖会破坏严格断网要求。
- 单文件数据模型难以表达成员、账户归档、当期信用额度与导入警告。

可参考页面与结构：Dashboard 的数字层级、月度趋势、资产类别构成、历史月份列表。FamilyLedger 改用 SQLite 关系模型，并由后端负责最终计算。

## wealthfolio/wealthfolio

来源：[GitHub README](https://github.com/wealthfolio/wealthfolio/blob/main/README.md)

Wealthfolio 是 local-first 的投资与净资产管理产品，数据保存在本机；仓库许可证为 AGPL-3.0，品牌资产另有商标限制。

值得借鉴：

- 账户卡片、账户分组、净资产总数与细分列表之间的视觉层级。
- “当前估值”和“历史快照”职责分离，历史展示不应被当前账户配置反向改写。
- 隐藏/归档账户仍保留在历史汇总范围的思想。
- 统一由后端提供汇总结果，前端主要负责展示与交互。

不应该借鉴：

- Rust/Tauri、投资持仓、行情、券商同步、收益率、资产配置、多币种与插件系统。
- 面向投资组合的复杂导航和多层筛选。

可参考页面与结构：净资产 Dashboard、账户列表、账户详情的摘要区与历史图。FamilyLedger 只保留家庭成员、账户类型和月度金额。

## actualbudget/actual

来源：[GitHub README](https://github.com/actualbudget/actual/blob/master/README.md)、[MIT License](https://github.com/actualbudget/actual/blob/master/LICENSE.txt)

Actual 是 TypeScript/React 的 local-first 财务工具，仓库使用 MIT 许可证。

值得借鉴：

- local-first 产品应把本地数据作为主状态，而不是离线缓存。
- 导入、导出、备份与恢复是一组完整的数据可携带能力。
- 桌面端键盘操作、稳定的表单状态和清晰的保存反馈。
- 数据文件版本化，恢复前验证结构并保留回滚点。

不应该借鉴：

- Envelope Budget、交易账本、同步服务器、多设备协同与复杂预算规则。
- 大型 monorepo 与插件式架构。

可参考页面与结构：账户管理、数据导入/导出、设置内的数据安全操作。FamilyLedger 将这些压缩为一个“数据管理”页面。

## firefly-iii/firefly-iii

来源：[GitHub README](https://github.com/firefly-iii/firefly-iii/blob/main/readme.md)

Firefly III 是功能完整的自托管个人财务系统，仓库使用 AGPL-3.0。

值得借鉴：

- 账户类型使用稳定机器枚举，显示名称与业务类型分离。
- 导入作为可追踪任务，记录成功、警告和错误数量。
- 报表先给摘要，再允许查看具体账户明细。
- REST API 与展示层分离，便于测试财务计算。

不应该借鉴：

- 复式记账、交易规则、预算、周期交易、认证、2FA、复杂 API 与部署体系。
- 大量报表和图表，不符合 3～5 分钟盘点的目标。

可参考页面与结构：账户组织、导入报告、报表摘要。FamilyLedger 不实现交易与权限体系。

## 对 FamilyLedger 的落地决定

1. 后端以整数分存储并计算所有金额，前端也使用字符串解析为整数分，不用浮点金额做最终计算。
2. `snapshot_entries` 固化当期信用额度、是否计入净资产、账户与成员显示信息，保证历史语义稳定。
3. Dashboard 由一个汇总 API 返回，避免多请求拼装造成口径不一致。
4. 导入器只做可解释解析：原始名称与原始值完整保存，名称差异只提示、不合并。
5. JSON 是完整备份/恢复格式；CSV/XLSX 是便于查看与迁移的表格格式。
6. 生产环境不依赖任何 CDN 或在线服务，React 构建产物由 FastAPI 同源提供。
