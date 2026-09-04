# BOTEN 购物车、合并分享与 PDF 升级计划

日期：2026-09-03  
状态：核心功能已实施并通过本地验收（2026-09-03）  
适用范围：本地 E 盘源码与本地数据库；确认后再同步 Git 和 NAS

## 实施结果摘要

本计划已在本地 E 盘项目完成以下内容：

- 当前选配区只保留“保存配置到购物车”，修改模式下切换为“保存修改”。
- 购物车支持全选/多选、返回主界面修改并覆盖、合并分享、合并 PDF 和批量软删除。
- 已删除的购物车项目不再出现在列表中，已生成的历史分享继续使用冻结快照。
- 新增保存配置版本号、归档时间、多设备分享主从结构及历史分享迁移。
- 合并 PDF 已实现客户名称、邮箱或手机号、导出时间、品牌页脚、总页数、设备分组以及每台设备独立编号。
- 后台分享记录支持分页、关键词、状态、设备型号和创建日期筛选；后台预览不增加客户查看次数。
- 后台支持关闭和重新启用未过期分享；分享、PDF、报价和关闭等关键操作写入审计。
- 购物车批量操作失败改为在对应操作区显示中英文提示；历史选项失效时必须确认移除后才能继续修改。

本地数据与验证结果：

- 迁移版本：`20260903_0009 (head)`。
- 迁移前备份：`backend/backups/boten-20260903-093703-772233.db`。
- 数据库完整性检查通过。
- 自动化回归：49 项全部通过。
- PDF 已实际渲染检查中英文、跨页表头、每页页眉页脚与 `Page x / y` 总页数；并修复设备分页边界和中文页眉溢出。
- 用户端桌面页面已人工检查购物车布局、勾选状态、编辑回填与覆盖保存。

尚未执行：Git 提交、GitHub 推送、albert-nas 或 BOTEN-NAS 同步；仍需用户最终验收后单独执行。

## 1. 项目目标

本次升级将用户端配置流程统一为“先保存到购物车，再从购物车进行后续操作”：

1. 当前选配区域只保留“保存配置到购物车”。
2. 已保存配置可以重新载入主界面修改，并覆盖原购物车记录。
3. 购物车支持勾选一台或多台设备，统一执行分享、合并 PDF 和删除。
4. PDF 增加客户资料、导出时间、页码和规范的中英文内容，并支持多设备合并。
5. 统一购物车所有中英文标题、按钮、状态和错误提示。
6. 升级后台分享记录查询、预览、关闭、报价和审计流程。
7. 历史分享和报价不再因用户修改或删除购物车配置而丢失或改变。

## 2. 实施原则

- 不直接覆盖历史分享内容；创建分享时冻结配置快照。
- “从购物车删除”采用软删除，不级联删除历史分享和报价。
- 所有批量接口必须验证配置归属，禁止跨用户读取或操作。
- 单次最多处理 20 台设备，防止超大请求和 PDF 生成耗时失控。
- 批量写操作必须使用数据库事务：全部成功或全部失败。
- 中文界面只输出中文业务标签，英文界面只输出英文业务标签；品牌名、设备型号和配置编号不翻译。
- 所有破坏性操作提供确认窗口；接口失败时保留用户当前勾选状态。
- 数据库迁移前必须执行备份和完整性检查。

## 3. 用户端交互设计

### 3.1 当前选配区域

移除以下入口：

- 分享当前配置
- 导出 PDF

只保留一个主按钮：

| 状态 | 中文 | 英文 |
|---|---|---|
| 新建 | 保存配置到购物车 | Save Configuration to Cart |
| 修改 | 保存修改 | Save Changes |
| 请求中 | 保存中… | Saving… |

新建成功后刷新购物车数量并打开购物车。修改成功后保持原配置 ID，不新增记录。

### 3.2 购物车标题与工具栏

建议将抽屉标题从“我的购物车”调整为：

- 中文：已保存配置
- 英文：Saved Configurations

标题栏下方增加选择工具栏：

- 全选复选框
- 已选择数量
- 全部配置数量

示例：`已选择 2 / 5 项`、`2 of 5 Selected`。

### 3.3 配置卡片

每张卡片包含：

1. 左上角完整可点击的选择框与标签。
2. 设备型号和设备名称。
3. 外观颜色、电机配置、电源配置。
4. 各可选配置分类及数量。
5. “修改”和“查看详情”两个单条操作。

分享和删除不再放在单张卡片内，避免与批量操作重复。

卡片本身不承担勾选行为，防止用户点击“修改/详情”时误选；只允许点击复选框及其标签改变选择状态。

### 3.4 底部批量操作栏

购物车底部固定操作栏包含：

- 分享所选 / Share Selected
- 导出合并 PDF / Export Combined PDF
- 删除所选 / Remove Selected

规则：

- 未选择任何配置时，三个按钮均禁用。
- 分享和 PDF 为正常操作；删除使用危险操作样式。
- 手机端允许两行排布，并为最后一张卡片预留底部空间。
- 删除前显示具体数量，例如“确定从购物车删除 3 项配置？”。
- 删除失败时不清除勾选状态。

### 3.5 修改并覆盖配置

操作流程：

1. 用户点击某张配置卡片的“修改”。
2. 获取该配置的最新详情和版本号。
3. 关闭购物车，将设备、颜色、电机、电源及所有可选配置载入主界面。
4. 滚动到设备标题下方，并显示编辑状态条。
5. 状态条显示“正在修改：BOTEN CR1016”，提供“取消修改”。
6. 主按钮切换为“保存修改”。
7. 保存成功后覆盖原记录，购物车数量保持不变。
8. 保存失败时保留页面选择，并在按钮附近显示可操作的错误信息。

切换设备、修改另一条配置或关闭页面时，如当前修改尚未保存，应显示未保存提示。

如果历史配置中的选项已经停用或删除：

- 主界面显示“1 项历史配置已不可用”。
- 不静默替换为其他配置。
- 用户必须确认移除不可用项目后才能保存。

## 4. 前端状态与文件调整

### 4.1 状态结构

在现有配置状态之外增加：

```javascript
editingConfig = {
  id: "saved-config-id",
  version: 2,
  updatedAt: "2026-09-03T10:00:00Z"
}

selectedCartIds = new Set()
```

新增状态方法：

- `loadSavedSnapshot(savedConfig)`：把已保存配置载入主界面。
- `beginConfigEdit(savedConfig)`：进入修改模式。
- `cancelConfigEdit()`：退出修改模式并恢复普通新建状态。
- `toggleCartSelection(id)`：切换单条勾选。
- `selectAllCartItems()`：全选可见配置。
- `clearCartSelection()`：清除选择。

### 4.2 预计修改文件

- `index.html`：移除即时分享/PDF；增加编辑状态条、购物车工具栏和批量操作区。
- `js/state.js`：支持载入保存快照和编辑上下文。
- `js/cart.js`：购物车多选、编辑回填、覆盖保存、批量分享/PDF/删除。
- `js/pdf.js`：移除主界面即时 PDF，仅保留购物车合并导出调用。
- `js/language.js`：集中管理购物车、批量操作和错误提示翻译。
- `css/components.css`：卡片复选框、编辑状态条、固定批量操作栏和移动端布局。

## 5. API 设计

### 5.1 查询配置详情

继续使用：

```http
GET /api/v1/configs/{config_id}?lang=zh
```

响应增加 `version`，并返回可用于编辑的标准化选择数据。

### 5.2 覆盖修改配置

```http
PUT /api/v1/configs/{config_id}
Content-Type: application/json
```

请求：

```json
{
  "name": "BOTEN CR1016 配置",
  "product_id": "cr1016",
  "color": "green",
  "selections": {
    "motor": "motor-option-id",
    "voltage": "voltage-option-id",
    "cri": ["option-1", "option-2"]
  },
  "lang": "zh",
  "version": 2
}
```

服务端处理：

1. 验证配置属于当前用户且未归档。
2. 验证版本号与数据库一致。
3. 重新验证颜色、电机、电源及可选配置。
4. 重新计算电机对应的人民币和美元基础价格。
5. 更新快照、更新时间及版本号。

版本冲突返回 HTTP `409`：

```json
{
  "error": {
    "code": "SAVED_CONFIG_VERSION_CONFLICT"
  },
  "detail": "该配置已在其他窗口修改，请重新加载后再保存"
}
```

### 5.3 创建单设备或多设备分享

```http
POST /api/v1/config-shares
```

请求：

```json
{
  "config_ids": ["config-1", "config-2"],
  "lang": "zh"
}
```

返回：

```json
{
  "id": "share-id",
  "code": "123456",
  "item_count": 2,
  "expires_at": "2026-12-02T10:00:00Z"
}
```

要求：

- `config_ids` 去重后必须为 1–20 项。
- 所有配置必须属于当前用户且未归档。
- 按请求顺序冻结设备快照。
- 分享内容创建后不受购物车后续修改影响。
- 保留原 `/configs/{id}/share` 一段时间兼容旧前端，内部转调新服务。

### 5.4 合并 PDF

```http
POST /api/v1/config-exports/pdf
```

请求：

```json
{
  "config_ids": ["config-1", "config-2"],
  "lang": "en"
}
```

响应为 `application/pdf`。文件名建议：

```text
BOTEN-configurations-20260903-173000.pdf
```

### 5.5 批量从购物车删除

不建议在 `DELETE` 请求中发送 JSON Body，采用：

```http
POST /api/v1/configs/batch-archive
```

请求：

```json
{
  "config_ids": ["config-1", "config-2"]
}
```

返回：

```json
{
  "archived_count": 2
}
```

接口在一个事务中完成软删除。`GET /configs` 默认不返回已归档项目。

## 6. 数据库设计

建议新增迁移：`202609xx_0009_cart_bundle_sharing.py`。

### 6.1 `saved_configs` 新增字段

```sql
version INTEGER NOT NULL DEFAULT 1;
archived_at TEXT NULL;
```

用途：

- `version`：防止多窗口覆盖修改。
- `archived_at`：从购物车移除但保留历史业务关联。

### 6.2 `config_shares` 新增字段

```sql
title TEXT NOT NULL DEFAULT '';
language TEXT NOT NULL DEFAULT 'zh';
customer_name TEXT NOT NULL DEFAULT '';
customer_email TEXT NOT NULL DEFAULT '';
item_count INTEGER NOT NULL DEFAULT 1;
```

客户信息在创建分享时冻结，保证历史分享和 PDF 可追溯。

### 6.3 新建 `config_share_items`

```sql
CREATE TABLE config_share_items (
    id TEXT PRIMARY KEY,
    share_id TEXT NOT NULL REFERENCES config_shares(id) ON DELETE CASCADE,
    config_id TEXT REFERENCES saved_configs(id) ON DELETE SET NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    display_name TEXT NOT NULL DEFAULT '',
    snapshot_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_config_share_items_share
ON config_share_items(share_id, sort_order);
```

`snapshot_json` 是不可变快照。即使保存配置被修改、归档或后续目录内容变化，历史分享仍保持原内容。

### 6.4 历史数据迁移

对每条旧 `config_shares`：

1. 读取其 `config_id` 对应的 `saved_configs.snapshot_json`。
2. 创建一条 `config_share_items`。
3. `sort_order = 0`、`item_count = 1`。
4. 从原用户记录填充客户姓名和邮箱。
5. 保留原 `config_id` 字段供旧版本兼容。

迁移后检查：

- 每条分享至少有一个分享项目。
- `item_count` 与关联项目数一致。
- 分享码无重复。
- 不产生孤立分享项目。

## 7. PDF 版式与翻译

### 7.1 页面尺寸

- A4 纵向。
- 左右边距 15 mm。
- 顶部为固定页头，底部为固定页脚。
- 表格跨页时重复表头。
- 设备标题和至少两行内容保持在同一页，避免孤立标题。

### 7.2 页头

每页显示：

- 客户名称 / Customer
- 客户邮箱 / Email
- 导出时间 / Exported At

用户没有邮箱时显示手机号；游客不再从用户端生成配置 PDF。

### 7.3 页脚

左侧固定显示：

```text
BOTEN DIESEL TEST BENCH
```

右侧显示：

- 中文：`第 1 / 4 页`
- 英文：`Page 1 / 4`

ReportLab 需要实现保存页面状态的 `NumberedCanvas`，生成文档后再写入总页数。

### 7.4 设备内容

每台设备独立显示：

```text
设备 1 / Device 1
BOTEN CR1016
共轨试验台综合一体机
```

设备信息表包含：

- 设备型号
- 设备名称
- 外观颜色
- 电机配置
- 电源配置

电机和电源不再重复出现在下方可选配置表。

### 7.5 已选配置

表格列：

| 中文 | 英文 |
|---|---|
| 序号 | No. |
| 类别 | Category |
| 配置编号 | Code |
| 配置名称 | Configuration |
| 专有标注 | Note |

每台设备的配置序号独立从 `1` 开始。合并 PDF 中第二台设备重新从 `1` 排序，不延续上一台序号。

### 7.6 PDF 翻译字典

在后端建立单独的 `PDF_COPY`，不再在字符串中混用“设备 / Device”这类双语标签。

日期使用服务端时区和语言格式化：

- 中文：`2026年9月3日 17:30`
- 英文：`Sep 3, 2026, 17:30`

设备型号、配置编号、BOTEN 品牌名保持原文。

## 8. 后台分享管理升级

### 8.1 列表查询

```http
GET /api/v1/admin/shares
    ?page=1
    &page_size=20
    &query=123456
    &status=active
    &product_id=cr1016
    &created_from=2026-09-01
    &created_to=2026-09-30
```

业务员使用同一查询服务，但不获得管理员专属关闭权限。

搜索范围：

- 分享码
- 客户名称
- 客户邮箱
- 客户手机号
- 设备型号

列表增加：

- 设备数量
- 设备型号摘要
- 创建人
- 创建时间
- 过期时间
- 客户查看次数
- 最后查看时间
- 当前状态

### 8.2 后台预览

新增：

```http
GET /api/v1/staff/shares/{code}/preview?lang=zh
```

后台预览不增加 `view_count`。只有明确的客户访问事件才计入查看次数，避免管理员查询和生成报价污染统计。

### 8.3 分享状态操作

建议使用：

```http
PATCH /api/v1/admin/shares/{share_id}/status
```

请求：

```json
{
  "active": false
}
```

关闭操作应幂等：重复关闭仍返回当前已关闭状态，不返回误导性的失败。

### 8.4 合并分享报价

后台打开合并分享时：

- 按设备分组展示。
- 每台设备生成一条基础设备价格项目。
- 该设备的选配项目排列在其下方。
- 自动填价时按人民币或美元分别读取参考价格。
- 报价保存时冻结分享快照和报价项目。

报价表建议后续增加：

```text
source_share_id
source_snapshot_json
```

避免购物车配置变动后影响已保存报价。

### 8.5 审计日志

以下操作写入审计：

- 创建分享
- 后台关闭或恢复分享
- 导出分享 PDF
- 从分享创建报价
- 删除或关闭报价

审计详情只记录必要 ID、数量和结果，不保存密码、Token 或完整个人敏感信息。

## 9. 错误代码与提示

建议新增结构化错误代码：

| 错误代码 | 中文提示 | 英文提示 |
|---|---|---|
| `SAVED_CONFIG_NOT_FOUND` | 配置不存在或已被删除 | Configuration not found or removed |
| `SAVED_CONFIG_VERSION_CONFLICT` | 配置已在其他窗口修改，请重新加载 | Configuration changed in another window. Reload and try again |
| `CONFIG_SELECTION_INVALID` | 部分选项已不可用，请重新选择 | Some options are no longer available. Review your selection |
| `BATCH_SELECTION_EMPTY` | 请至少选择一项配置 | Select at least one configuration |
| `BATCH_SELECTION_LIMIT` | 每次最多处理 20 项配置 | You can process up to 20 configurations at a time |
| `CONFIG_ACCESS_DENIED` | 无权操作该配置 | You do not have access to this configuration |
| `PDF_GENERATION_FAILED` | PDF 生成失败，请稍后重试 | PDF generation failed. Try again later |
| `SHARE_CREATION_FAILED` | 分享码生成失败，请重试 | Could not create a share code. Try again |

错误应显示在对应操作栏附近并使用 `aria-live="polite"`；不能只使用笼统的浏览器 `alert()`。

## 10. 安全、性能与并发

- 所有配置 ID 都在服务端重新验证归属关系。
- 批量接口限制 1–20 项并去重。
- PDF 生成设置超时和最大配置项目数量。
- 创建分享、批量归档和覆盖更新使用事务。
- 修改配置采用 `version` 乐观锁。
- 分享码继续保持唯一索引和有效期。
- 管理后台列表使用服务端分页，不一次加载全部记录。
- 多设备详情按需加载，避免列表接口返回完整快照。
- PDF 和分享请求期间按钮显示进行中状态，并防止重复提交。

## 11. 实施阶段

### 阶段 A：数据库和服务层（P1）

- 新增迁移、版本号、软删除及分享项目表。
- 迁移历史分享数据。
- 增加配置覆盖更新服务。
- 增加批量归档、合并分享和合并 PDF 服务。
- 为新服务增加权限、事务和错误代码测试。

### 阶段 B：购物车交互（P1）

- 当前选配区只保留保存按钮。
- 增加购物车多选和批量操作栏。
- 增加配置编辑回填、取消和覆盖保存。
- 增加未保存修改保护。
- 完成手机端和键盘操作。

### 阶段 C：PDF（P1）

- 重构为单设备和多设备共用渲染器。
- 增加客户页头、导出时间、总页码。
- 分离设备信息和可选配置。
- 每台设备独立编号。
- 完成中英文 PDF 词典和字体检查。

### 阶段 D：后台分享与报价（P2）

- 增加分页、筛选和搜索。
- 增加多设备分享预览。
- 区分后台预览与真实查看次数。
- 支持合并分享生成报价。
- 完善审计记录。

### 阶段 E：兼容、验收和文档（P1）

- 验证旧单设备分享码。
- 验证旧保存配置和旧报价读取。
- 备份并演练数据库迁移与回滚。
- 更新 README、API 文档和 NAS 部署说明。
- 用户确认后提交 Git，再同步 BOTEN-NAS。

## 12. 测试清单

### 后端测试

- 新建和覆盖保存配置。
- 版本冲突返回 409。
- 禁止操作其他用户配置。
- 批量请求空数组、重复 ID、超过 20 项。
- 批量归档全部成功或全部回滚。
- 分享快照在原配置修改后保持不变。
- 归档配置后历史分享和报价仍可读取。
- 旧分享迁移后仍可查询和导出。
- 后台预览不增加查看次数。
- 数据库无孤立分享项目。

### 前端测试

- 新建配置只显示保存入口。
- 修改后购物车数量不增加、配置 ID 不变。
- 取消修改恢复普通新建模式。
- 单选、全选、取消全选状态正确。
- 批量操作失败后保持勾选。
- 删除需要确认。
- 中英文切换后按钮、标题、数量和错误提示完整。
- 纯键盘完成勾选、修改、分享、导出和关闭购物车。
- 390、768、1024、1440 px 无遮挡或横向溢出。

### PDF 测试

- 分别导出 1、2、10、20 台设备。
- 中文和英文分别渲染。
- 客户名称、邮箱和时间正确。
- 手机号回退逻辑正确。
- 每台设备配置序号独立从 1 开始。
- 电机和电源只出现在设备信息中。
- 长设备名、长配置名、长标注和空配置均正常。
- 跨页表头、总页数和页脚正确。
- PDF 字体在 Windows、本地 Docker 和群晖容器中一致。

## 13. 数据迁移与回滚

实施前：

1. 执行 `database_maintenance check`。
2. 创建数据库备份并记录文件校验值。
3. 停止写入或进入短暂维护窗口。
4. 执行 Alembic 升级。
5. 校验历史分享项目数量和外键完整性。

回滚条件：

- 历史分享迁移数量不一致。
- 出现孤立分享项目。
- 旧分享码无法查询。
- 用户配置数量异常。
- PDF 服务无法正常启动。

回滚方式：停止服务，恢复迁移前数据库备份，再切回上一 Git 提交。禁止在生产数据库上手工删除新表后继续运行。

## 14. 验收标准

- 当前选配界面只有一个保存按钮。
- 保存配置可从购物车重新编辑并覆盖。
- 购物车支持多选、全选、分享、PDF 和批量删除。
- 删除购物车配置不破坏历史分享和报价。
- 合并分享可在后台按设备查看。
- PDF 页头、页脚、总页码和客户信息完整。
- 中文 PDF 不出现未翻译的英文界面标签；英文 PDF 不出现乱码中文标签。
- 每台设备配置序号独立排序。
- 后台预览不增加客户查看次数。
- 旧数据、旧分享码和旧报价继续可用。
- 全部自动化测试、数据库检查和人工响应式验收通过。

## 15. 待确认边界

开始开发前需要最终确认以下产品规则：

1. “从购物车删除”按本方案解释为软删除，历史分享和报价继续保留。
2. 分享内容在生成时冻结，后续修改购物车不会自动更新旧分享。
3. 单次合并上限为 20 台设备。
4. 英文 PDF 业务标签只显示英文，不采用中英双语并排。
5. 合并分享需要支持后台生成一份包含多台设备的报价单。
