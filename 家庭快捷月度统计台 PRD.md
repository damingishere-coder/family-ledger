# 家庭快捷月度统计台 PRD

> 项目暂定名：Family Finance Desk / 家庭快捷月度统计台  
> 产品形态：Windows 本地运行 + 浏览器网页端  
> 核心定位：家庭资产快照、快速月度盘点、净资产趋势统计  
> V1 原则：简单、快速、本地优先、数据安全，不做传统复杂记账软件

---

# 1. 项目背景

目前家庭资产主要通过两种方式进行统计：

1. 早期使用 iPhone 备忘录手工记录；
2. 后期逐渐迁移到 Excel；
3. 两种载体的核心统计逻辑基本一致。

历史统计的核心不是记录每一笔消费，而是定期进行一次完整的家庭资产盘点。

每次盘点主要包含：

- 家庭成员；
- 微信余额；
- 支付宝余额；
- 储蓄卡余额；
- 信用卡额度；
- 信用卡当前需还款；
- 证券 / 投资账户；
- 借款 / 应收款等特殊项目；
- 家庭总资产；
- 家庭总负债；
- 顺差。

其中：

**顺差 = 家庭总资产 - 家庭总负债**

新系统中建议统一称为：

**家庭净资产**

界面可显示：

> 家庭净资产  
> 原统计表中的“顺差”

---

# 2. 产品定位

本项目不是传统的：

> 每天记录早餐 15 元、打车 30 元、购物 200 元

这类流水记账软件。

本项目的核心场景是：

> 用户每隔一段时间打开系统，对所有银行卡、微信、支付宝、信用卡和投资账户进行一次余额更新，系统自动计算当前家庭资产状况。

理想体验：

> 打开系统 → 新建本月盘点 → 连续输入各账户金额 → 保存 → 自动生成本月家庭资产报告。

目标：

**3～5 分钟完成一次家庭资产盘点。**

---

# 3. V1 核心目标

V1 只解决以下问题：

1. 快速完成家庭资产盘点；
2. 自动计算家庭总资产；
3. 自动计算家庭总负债；
4. 自动计算家庭净资产；
5. 保存每一次历史资产快照；
6. 展示净资产长期变化趋势；
7. 管理家庭成员和账户；
8. 导入历史数据；
9. 支持本地备份和恢复。

---

# 4. V1 明确不做

为了防止项目不断膨胀，以下功能 V1 禁止开发：

- 每日消费流水记账；
- 消费分类；
- 月度预算；
- 预算提醒；
- 银行 API；
- 微信 / 支付宝自动读取；
- 信用卡自动同步；
- 股票实时行情；
- OCR；
- AI 自动记账；
- AI 财务分析；
- 云端账号系统；
- 多设备同步；
- 手机 App；
- 微信小程序；
- Docker；
- 复杂权限系统；
- 复式记账；
- 财务 ERP 功能。

除非核心 V1 已完成，否则不要自行添加上述功能。

---

# 5. 核心用户流程

## 5.1 第一次使用

进入系统：

→ 创建 / 导入家庭成员  
→ 创建 / 导入账户  
→ 导入历史资产数据  
→ 进入 Dashboard

历史数据导入完成后，用户第一次进入系统就应该能够看到过去的净资产趋势，而不是空白 Dashboard。

---

# 5.2 日常使用

用户点击：

**新建本月盘点**

系统：

1. 获取最近一次资产快照；
2. 获取当前所有启用账户；
3. 自动复制账户结构；
4. 显示上期金额作为参考；
5. 用户只需要填写本期金额。

例如：

| 账户 | 上期 | 本期 |
|---|---:|---:|
| 微信 | ¥987.63 | 输入框 |
| 支付宝 | ¥0.01 | 输入框 |
| 招商银行 | ¥14.10 | 输入框 |
| 平安银行 | ¥39.66 | 输入框 |
| 工商银行 | ¥6,693.01 | 输入框 |

用户输入：

`1200`

按 Enter。

自动跳至下一账户。

继续：

`300`

Enter。

一路完成全部账户。

---

# 6. 信息架构

左侧导航保持简单，只允许以下一级入口：

```text
家庭快捷月度统计台

├── 概览
├── 开始盘点
├── 历史记录
├── 账户管理
└── 数据管理
```

不要增加大量二级菜单。

---

# 7. 页面结构

# 7.1 概览 Dashboard

路由：

```text
/
```

页面最上方显示：

**家庭资产概览**

右上角：

**＋ 新建本月盘点**

---

## 第一部分：核心指标

四张 KPI 卡片：

### 家庭净资产

```text
¥59,812.18
较上期 +¥19,420.25
```

### 家庭总资产

```text
¥82,959.09
```

### 家庭总负债

```text
¥23,146.91
```

### 投资资产

```text
¥26,481.30
```

净资产最突出。

---

## 第二部分：净资产趋势

折线图。

X 轴：

盘点月份。

例如：

```text
2025/01
2025/02
2025/03
……
2026/08
```

可切换：

- 净资产；
- 总资产；
- 总负债。

默认：

**净资产**

---

## 第三部分：资产构成

展示：

- 微信 / 支付宝；
- 银行存款；
- 投资；
- 应收款；
- 其他。

可以使用环形图或简单横向比例条。

不要堆大量图表。

---

## 第四部分：家庭成员

例如：

```text
大明

资产：¥xxxxx
负债：¥xxxxx
净资产：¥xxxxx
```

```text
贤贤

资产：¥xxxxx
负债：¥xxxxx
净资产：¥xxxxx
```

---

## 第五部分：最近盘点

展示最近 5～10 条。

| 日期 | 总资产 | 总负债 | 净资产 | 环比 |
|---|---:|---:|---:|---:|
| 2026/08/31 | | | | |
| 2026/07/xx | | | | |
| 2026/06/xx | | | | |

点击可查看详情。

---

# 7.2 开始盘点

路由：

```text
/snapshot/new
```

这是整个产品最重要的页面。

设计优先级高于 Dashboard。

---

## 顶部

```text
新建资产盘点

盘点月份：[2026年08月]

已完成 8 / 27 个账户

[保存草稿] [完成盘点]
```

月份允许修改，但每个自然月最多保留一份已完成盘点。

没有未完成草稿时默认当前自然月；存在旧草稿时优先继续旧草稿。

---

# 7.3 成员区域

按照成员分组。

例如：

## 大明

### 钱包 / 支付平台

| 账户 | 上期余额 | 本期余额 | 变化 |
|---|---:|---:|---:|
| 微信 | 987.63 | 输入框 | 自动 |
| 支付宝 | 0.01 | 输入框 | 自动 |

### 储蓄卡

| 银行 | 上期 | 本期 | 变化 |
|---|---:|---:|---:|
| 招商银行 | | 输入框 | |
| 平安银行 | | 输入框 | |
| 交通银行 | | 输入框 | |
| 工商银行 | | 输入框 | |
| 建设银行 | | 输入框 | |

### 信用卡

| 银行 | 额度 | 上期待还 | 本期待还 |
|---|---:|---:|---:|
| 招商银行 | 64000 | | 输入框 |
| 平安银行 | 28000 | | 输入框 |
| 广州银行 | 46000 | | 输入框 |
| 建设银行 | 15000 | | 输入框 |

然后：

## 贤贤

采用同样结构。

---

# 7.4 快速输入体验

必须重点实现键盘交互。

输入金额后：

**Enter → 下一个输入框**

支持：

```text
Tab
Shift + Tab
Enter
↑
↓
```

目标是用户可以完全不碰鼠标完成盘点。

金额输入支持：

```text
0
12
12.35
-18.52
```

信用卡允许负数。

历史数据中存在负数待还，所以禁止使用：

```text
min=0
```

限制。

---

# 7.5 自动保存

填写过程中自动保存草稿。

建议：

输入停止 300～800ms 后 debounce 保存。

顶部显示：

```text
已自动保存
```

刷新浏览器不能丢失当前盘点。

---

# 7.6 自动计算

用户绝对不能手工填写：

- 小计；
- 总资产；
- 总负债；
- 净资产。

全部由系统自动计算。

页面底部实时显示：

```text
本期资产      ¥82,959.09

本期负债      ¥23,146.91

家庭净资产    ¥59,812.18
```

---

# 8. 历史记录

路由：

```text
/history
```

顶部：

```text
历史资产
```

---

## 趋势区域

默认展示：

**家庭净资产趋势**

支持切换：

```text
净资产
总资产
总负债
```

---

## 历史列表

| 日期 | 总资产 | 总负债 | 净资产 | 环比 |
|---|---:|---:|---:|---:|

支持：

- 按年份筛选；
- 点击查看；
- 编辑；
- 删除。

删除需要二次确认。

---

# 9. 历史快照详情

路由：

```text
/snapshots/:id
```

展示：

```text
2026年2月15日家庭资产

总资产
总负债
净资产
```

然后按照：

```text
成员
  ├── 钱包
  ├── 银行
  ├── 投资
  └── 信用卡
```

展示完整详情。

增加：

**与上期比较**

例如：

```text
招商银行

上期：¥1,273.28
本期：¥14.10
变化：-¥1,259.18
```

---

# 10. 账户管理

路由：

```text
/accounts
```

按照家庭成员分组。

---

## 账户类型

统一支持：

```text
wallet
debit_card
credit_card
investment
receivable
other_asset
other_liability
```

中文：

- 钱包 / 支付平台；
- 储蓄卡；
- 信用卡；
- 投资账户；
- 应收款；
- 其他资产；
- 其他负债。

---

## 新建账户

字段：

```text
所属成员
账户名称
机构名称
账户类型
信用额度（信用卡可填）
还款日（信用卡可填）
是否计入家庭净资产
备注
排序
```

例如：

```text
所属成员：大明

机构：招商银行

账户名称：招商银行信用卡

类型：信用卡

额度：64000

还款日：11

计入家庭净资产：是
```

---

# 11. 账户归档

账户不能直接因为“不用了”而删除。

支持：

**归档账户**

归档后：

- 历史快照继续显示；
- 新建盘点默认不再出现。

这能保证历史数据完整。

---

# 12. 特殊资产处理

例如：

```text
借款待收回
```

归类：

```text
receivable
```

增加：

```text
是否计入家庭净资产
```

例如：

```text
Momo 借款

金额：11704

计入净资产：否
```

如果关闭：

系统保存该金额，但：

**不进入家庭总资产计算。**

---

# 13. 计算规则

所有金额统一使用 Decimal。

不要使用 JS 浮点数直接进行最终财务计算。

建议后端使用：

```text
Decimal
```

数据库使用：

```text
NUMERIC / INTEGER cents
```

推荐：

**以“分”为单位存 INTEGER。**

例如：

```text
59812.18
```

存储：

```text
5981218
```

---

## 总资产

```text
所有：

asset 类型
AND
include_in_net_worth = true

金额之和
```

---

## 总负债

```text
所有：

liability 类型
AND
include_in_net_worth = true

金额之和
```

信用卡属于 liability。

允许出现负数。

---

## 家庭净资产

```text
net_worth =
total_assets - total_liabilities
```

---

## 投资资产

```text
account_type = investment
AND
include_in_net_worth = true
```

---

# 14. 数据库结构

数据库：

```text
SQLite
```

数据库文件建议：

```text
/data/family_finance.db
```

---

# 14.1 household_members

```sql
household_members
```

字段：

```text
id                  INTEGER PRIMARY KEY
name                TEXT NOT NULL
display_name        TEXT
sort_order          INTEGER DEFAULT 0
is_active           BOOLEAN DEFAULT TRUE
created_at          DATETIME
updated_at          DATETIME
```

---

# 14.2 accounts

```sql
accounts
```

字段：

```text
id                      INTEGER PRIMARY KEY

member_id               INTEGER NOT NULL

name                    TEXT NOT NULL

institution             TEXT

account_type            TEXT NOT NULL

credit_limit_cents      INTEGER NULL

billing_day             INTEGER NULL

include_in_net_worth    BOOLEAN DEFAULT TRUE

is_archived             BOOLEAN DEFAULT FALSE

sort_order              INTEGER DEFAULT 0

notes                   TEXT

legacy_name             TEXT NULL

created_at              DATETIME

updated_at              DATETIME
```

account_type 枚举：

```text
wallet
debit_card
credit_card
investment
receivable
other_asset
other_liability
```

---

# 14.3 snapshots

一条记录代表：

**某个自然月的一次家庭资产盘点。**

```text
id

snapshot_date

title

status

notes

legacy_source

legacy_summary_json

created_at

updated_at
```

status：

```text
draft
completed
```

legacy_source 示例：

```text
2025年咱家资产情况明细表.md
```

---

# 14.4 snapshot_entries

保存某次盘点中每一个账户的金额。

字段：

```text
id

snapshot_id

account_id

amount_cents

credit_limit_cents

include_in_net_worth

notes

legacy_raw_name

legacy_raw_value

created_at

updated_at
```

注意：

这里保存：

```text
credit_limit_cents
include_in_net_worth
```

的快照。

原因：

信用额度以及统计规则未来可能变化。

历史记录不能因为账户后来修改而改变。

---

# 14.5 import_records

记录历史导入情况。

字段：

```text
id

source_filename

source_type

imported_at

status

total_rows

success_rows

warning_rows

error_rows

report_json
```

source_type：

```text
markdown
xlsx
csv
json
```

---

# 15. 数据关系

```text
household_members
        │
        └── accounts
                │
                └── snapshot_entries
                        │
                        └── snapshots
```

即：

一个家庭成员：

拥有多个账户。

一个账户：

拥有多个历史金额记录。

一次 Snapshot：

包含很多账户金额。

---

# 16. 历史数据迁移

现有数据非常重要。

V1 必须考虑历史迁移。

目标：

将：

```text
2025 年备忘录数据
2026 年备忘录数据
现有 Excel 数据
```

全部转换成 Snapshot。

---

# 16.1 Markdown 导入

历史 Markdown 大致结构：

```text
## 2025年12月25日

### 一、大明同学明细

微信
支付宝

储蓄卡

信用卡

### 二、贤贤宝贝明细

...

### 三、总计
```

编写专门的：

```text
legacy_md_importer
```

解析：

```text
日期
成员
账户
金额
额度
待还
历史汇总
```

---

# 16.2 历史数据绝对禁止自动修正

旧数据可能存在：

- 银行名称输入差异；
- “中信银行 / 自信银行”等不同写法；
- 11号 / 11日；
- 信用额度发生变化；
- 小计缺失；
- 空白值；
- 信用卡负数；
- 手工小计与明细相加不一致。

导入程序：

**不得偷偷替用户修正。**

必须：

```text
保留原始值
+
重新计算系统值
+
产生 Warning
```

例如：

```text
历史记录总负债：37399.15

系统按明细重新计算：
xxxxx

差异：
xxxx

状态：
待核对
```

---

# 16.3 空值规则

历史数据：

```text
空白
```

必须导入：

```text
NULL
```

不能默认：

```text
0
```

因为：

没有填写 ≠ 余额为 0。

---

# 16.4 名称标准化

允许系统提示：

```text
发现可能重复账户：

中信银行
自信银行

是否视为同一个账户？
```

但是不能自动合并。

---

# 16.5 信用额度变化

同一张信用卡额度可能变化。

账户表保存：

**当前额度**

snapshot_entry 保存：

**当时额度**

因此历史页面可以正确显示历史额度。

---

# 17. 数据管理

路由：

```text
/data
```

功能：

### 导入

支持：

```text
Excel
CSV
JSON
历史 Markdown
```

### 导出

支持：

```text
Excel
CSV
JSON
```

### 完整备份

点击：

**备份全部数据**

生成：

```text
family-finance-backup-2026-08-31.json
```

---

# 18. 自动备份

数据库建议每天首次启动时：

自动复制：

```text
family_finance.db
```

到：

```text
/backups/
```

例如：

```text
family_finance_2026-08-31.db
```

保留：

最近 30 个备份。

防止误删或数据库损坏。

---

# 19. 技术方案

V1 推荐：

## Frontend

```text
React
Vite
TypeScript
Tailwind CSS
shadcn/ui
Recharts
```

---

## Backend

```text
Python
FastAPI
SQLAlchemy 2
Pydantic
```

---

## Database

```text
SQLite
```

---

# 20. 本地运行方式

最终用户不应该：

```text
npm run dev
python xxx
docker compose
```

才能打开。

Windows 根目录提供：

```text
启动家庭统计台.bat
```

用户双击以后：

```text
启动本地服务

↓

自动打开浏览器

↓

http://127.0.0.1:8765
```

---

# 21. 推荐生产运行结构

开发阶段：

```text
Vite
+
FastAPI
```

生产阶段：

先：

```text
npm run build
```

生成 React 静态资源。

FastAPI：

同时负责：

```text
/api/*
```

以及：

```text
React dist
```

最终只启动一个本地服务。

---

# 22. 网络与隐私

默认只监听：

```text
127.0.0.1
```

不要：

```text
0.0.0.0
```

V1：

- 不上传数据；
- 不接第三方统计 SDK；
- 不使用 Google Analytics；
- 不使用远程数据库；
- 不要求账号；
- 不要求互联网连接。

核心功能必须断网可用。

---

# 23. UI 风格

目标：

```text
简洁
现代
高级
清爽
桌面工作台感
```

不要：

```text
传统银行系统
传统 ERP
Excel 风
花里胡哨金融 App
大面积渐变
大量彩色卡片
```

布局可以参考现代 SaaS Dashboard。

推荐：

浅色背景。

卡片：

```text
白色
细边框
轻阴影
圆角适中
```

金额数字突出。

---

# 24. Desktop First

当前主要使用：

Windows 浏览器。

设计尺寸优先：

```text
1440 × 900
1920 × 1080
```

最低适配：

```text
1280
```

暂时不花大量时间做手机 UI。

只需要保证页面不会完全错乱。

---

# 25. GitHub 参考项目

开发前主动研究以下 GitHub 项目。

目的：

**借鉴设计和实现思路，不是直接照搬。**

---

## 25.1 Azqato/net-worth-tracker

仓库：

```text
Azqato/net-worth-tracker
```

这是本项目业务逻辑最接近的参考。

重点研究：

```text
Monthly Net Worth
资产分类
净资产趋势
历史月份
Chart.js 图表
Excel 导入导出
浏览器本地运行
```

特别参考：

```text
Dashboard 信息层级
Net Worth Trend
资产分类展示
历史数据组织方式
```

它本身技术非常轻：

```text
HTML
CSS
Vanilla JS
Chart.js
SheetJS
```

不要直接以它的技术架构作为本项目架构。

我们需要 SQLite 保存长期历史数据。

---

# 25.2 wealthfolio/wealthfolio

仓库：

```text
wealthfolio/wealthfolio
```

重点研究：

```text
Dashboard
账户体系
Net Worth
投资账户
资产结构
账户详情
历史趋势
Local-first
```

主要学习：

**UI 和信息架构。**

尤其参考：

```text
账户卡片
资产汇总
净资产
历史趋势图
金融数据的视觉层级
```

不要直接 Fork 后大改。

该项目体系明显比本项目复杂。

不要引入：

```text
Tauri
Rust
投资行情
Broker Sync
插件系统
多币种复杂体系
```

到 V1。

---

# 25.3 actualbudget/actual

仓库：

```text
actualbudget/actual
```

重点研究：

```text
Local-first
账户管理
本地数据
数据导入
备份
Web App
桌面端体验
```

主要学习：

**Local-first 产品设计思想。**

不要引入：

```text
Envelope Budget
复杂预算
Transaction Ledger
日常流水
```

到本项目 V1。

---

# 25.4 firefly-iii/firefly-iii

仓库：

```text
firefly-iii/firefly-iii
```

只作为辅助参考。

重点看：

```text
账户组织
Financial Dashboard
报表结构
数据导入
```

不要学习其整体产品复杂度。

特别禁止因为参考 Firefly III 而加入：

```text
复式记账
Transaction Rule
Budget
Recurring Transaction
复杂财务 API
```

V1 不需要。

---

# 26. GitHub 参考原则

在正式写 UI 前：

先浏览以上项目。

整理：

```text
/docs/reference-research.md
```

记录：

### 每个项目

```text
值得借鉴什么
不应该借鉴什么
可以参考的页面
可以参考的数据结构
```

然后再开始设计本项目。

不要直接复制第三方源码。

如果使用任何第三方源码：

必须检查 License。

---

# 27. 建议目录结构

```text
family-finance-desk/

├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   ├── features/
│   │   │   ├── dashboard/
│   │   │   ├── snapshots/
│   │   │   ├── accounts/
│   │   │   └── data-management/
│   │   ├── hooks/
│   │   ├── api/
│   │   ├── utils/
│   │   └── types/
│   └── package.json
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── importers/
│   │   ├── database/
│   │   └── main.py
│   └── tests/
│
├── data/
│   └── family_finance.db
│
├── backups/
│
├── docs/
│   ├── PRD.md
│   ├── reference-research.md
│   ├── database.md
│   └── import-report.md
│
├── scripts/
│   ├── start.py
│   └── backup.py
│
├── 启动家庭统计台.bat
│
└── README.md
```

---

# 28. 核心 API

V1 至少需要：

```text
GET    /api/dashboard

GET    /api/members
POST   /api/members
PATCH  /api/members/:id

GET    /api/accounts
POST   /api/accounts
PATCH  /api/accounts/:id
POST   /api/accounts/:id/archive

GET    /api/snapshots
GET    /api/snapshots/:id

POST   /api/snapshots
PATCH  /api/snapshots/:id

PUT    /api/snapshots/:id/entries/:entryId

POST   /api/snapshots/:id/complete

POST   /api/import/legacy
POST   /api/import/excel

GET    /api/export/json
GET    /api/export/excel

POST   /api/backup
POST   /api/restore
```

---

# 29. 新建盘点逻辑

调用：

```text
POST /api/snapshots
```

后端：

1. 创建 Snapshot；
2. 找到最近一次 completed Snapshot；
3. 查询所有未归档账户；
4. 为每个账户生成 snapshot_entry；
5. 返回上一期金额；
6. 前端进入快速填写模式。

注意：

**不要直接复制上一期金额成为本期金额。**

否则用户可能忘记修改某个账户。

应该：

```text
previous_amount = 1000

current_amount = NULL
```

界面：

```text
上期 ¥1000
本期 [请输入]
```

这样更安全。

---

# 30. 完成盘点校验

点击：

**完成盘点**

如果还有 NULL：

提示：

```text
还有 3 个账户尚未填写

招商银行
工商银行信用卡
支付宝

[返回填写]

[将空白保留并完成]
```

不能默认当成 0。

---

# 31. 数据质量提示

系统应该能检测：

### 异常变化

例如：

```text
上期 ¥1000
本期 ¥100000
```

显示轻量提醒：

```text
较上期变化较大，请确认金额。
```

但不要阻止保存。

---

# 32. 历史数据校验

历史导入以后：

运行一次：

```text
Legacy Data Validation
```

检查：

- 原历史总资产；
- 原历史总负债；
- 原顺差；
- 系统重新计算结果。

如果不一致：

标记：

```text
warning
```

不要修改原始记录。

---

# 33. 测试要求

至少覆盖以下测试。

## Calculation

```text
总资产计算
总负债计算
净资产计算
include_in_net_worth
信用卡负数
NULL
```

## Snapshot

```text
创建 Snapshot
复制账户结构
读取上一期金额
归档账户
历史账户不丢失
```

## Import

```text
Markdown 日期解析
成员解析
银行卡解析
信用卡解析
空值解析
负数解析
特殊应收款解析
```

## Backup

```text
导出
恢复
数据库备份
```

---

# 34. V1 验收标准

只有满足以下条件，V1 才算完成。

### 1

系统可以在 Windows 本地一键启动。

### 2

浏览器打开即可使用。

### 3

完全断网情况下核心功能正常。

### 4

可以创建家庭成员。

### 5

可以创建和管理账户。

### 6

可以新建一次资产盘点。

### 7

新建盘点自动显示所有现有账户。

### 8

可以看到上一期金额。

### 9

用户输入金额后按 Enter 自动进入下一项。

### 10

资产、负债、净资产全部实时自动计算。

### 11

可以保存草稿。

### 12

刷新页面草稿不会消失。

### 13

完成后生成历史快照。

### 14

Dashboard 展示当前：

```text
总资产
总负债
净资产
投资资产
```

### 15

可以看到历史净资产折线图。

### 16

归档账户不会破坏历史数据。

### 17

可以导出 JSON 完整备份。

### 18

可以恢复 JSON 备份。

### 19

可以将至少现有 Markdown 历史数据迁移成 Snapshot。

### 20

历史数据存在异常时：

```text
提示
而不是擅自修改
```

---

# 35. 开发顺序

不要同时开发全部功能。

按照以下顺序执行。

## Phase 0：参考项目研究

研究：

```text
Azqato/net-worth-tracker
wealthfolio/wealthfolio
actualbudget/actual
firefly-iii/firefly-iii
```

产出：

```text
docs/reference-research.md
```

---

## Phase 1：基础工程

完成：

```text
React
FastAPI
SQLite
数据库模型
API
本地启动
```

---

## Phase 2：账户体系

完成：

```text
家庭成员
账户 CRUD
账户归档
账户排序
```

---

## Phase 3：资产盘点

这是核心。

完成：

```text
新建盘点
上一期数据
快速输入
键盘操作
实时计算
草稿
完成盘点
```

---

## Phase 4：Dashboard

完成：

```text
四个 KPI
净资产趋势
资产构成
最近记录
```

---

## Phase 5：历史

完成：

```text
历史列表
详情
与上期比较
编辑
```

---

## Phase 6：历史数据迁移

优先：

```text
Markdown
```

然后：

```text
Excel
```

生成导入报告。

---

## Phase 7：备份与数据安全

完成：

```text
JSON 导出
JSON 恢复
数据库自动备份
异常恢复
```

---

## Phase 8：UI 打磨

最后再统一处理：

```text
布局
间距
字体
金额视觉层级
响应式
动画
空状态
Loading
Toast
```

禁止在功能尚未稳定之前大量修改 UI。

---

# 36. Codex 开发要求

你现在作为该项目的主开发 Agent。

不要只根据 PRD 直接生成大量代码。

先完成：

```text
1. 阅读整个 PRD

2. 研究指定 GitHub 参考项目

3. 输出 reference-research.md

4. 根据 PRD 建立合理的数据模型

5. 建立项目骨架

6. 逐 Phase 开发

7. 每完成一个 Phase：
   - 运行测试
   - 检查实际页面
   - 检查数据库
   - 检查 diff
   - 修复问题

8. 再进入下一个 Phase
```

发现 PRD 与历史数据冲突时：

**优先保护原始历史数据。**

禁止自行“纠正”用户过去的记录。

遇到无法确定的数据：

```text
保留原值
标记 warning
等待人工核对
```

---

# 37. 产品最终目标

这个项目最终需要做到：

用户每个月不再：

```text
复制备忘录
找 Excel
逐个计算
手工填写小计
计算总负债
计算总资产
再算顺差
```

而是：

```text
打开家庭快捷月度统计台

↓

新建本月盘点

↓

逐个输入账户余额

↓

连续按 Enter

↓

3～5 分钟完成

↓

系统自动生成：

家庭总资产
家庭总负债
家庭净资产
成员资产
资产构成
历史趋势
```

**V1 的最高优先级不是“功能多”，而是让这一次月度盘点足够快、足够稳定、足够舒服。**
