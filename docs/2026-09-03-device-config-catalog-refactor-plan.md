# 设备目录与配置目录重构计划

> 状态：实施中；P1.3 已完成，暂停在 P2 开始前。  
> 更新日期：2026-09-03。  
> 实施范围：本地 `E:\Project\CC-Project\benchshop`，用户验收前不部署至 NAS。

> 进度更新：P0、P1.1、P1.2、P1.3 已完成并通过副本验证；工作暂停在 P2 开始前。恢复工作时先阅读 `docs/2026-09-03-catalog-refactor-progress-checkpoint.md`。

## 当前执行状态

| 阶段 | 状态 | 结果 |
| --- | --- | --- |
| P0 数据盘点 | 部分确认 | 目录业务规则已确认，设备基础价格与电源价格待确认；见 `docs/2026-09-03-p0-data-inventory.md` |
| P1 数据库与后台 API | 进行中 | P1.1 表结构、P1.2 数据复制和 P1.3 统一读取/保存/计价 API 已在副本验证；尚未迁移活动数据库或切换 UI |
| P2 后台 UI | 未开始 | 依赖 P1 |
| P3 前台、报价与 PDF | 未开始 | 依赖 P1/P2 |
| P4 回归与部署 | 未开始 | 本地验收后执行 |

## 1. 文档目的

本计划用于指导设备目录、配置目录及前台选配界面的重构。目标是统一数据模型、明确价格来源、完善中英文内容链路，并在不破坏现有数据的前提下逐步替换旧逻辑。

本阶段只做设计和实施准备，不直接执行数据库破坏性迁移。所有开发继续基于本地 E 盘源码，确认验收后再同步至 BOTEN-NAS。

## 2. 重构原则

- 设备基本配置与配置目录中的可选配置分离。
- 中文和英文内容始终使用独立字段保存，禁止运行时互相覆盖。
- 后台字段标题固定使用中文；语言切换只影响输入内容、示例和前台展示。
- 前台只展示和提交选择结果，最终价格由后端重新计算。
- 保留旧字段和旧接口兼容期，迁移确认后再清理。
- 所有保存、删除、批量修改均提供明确的中英文错误提示和审计记录。
- UI 统一遵循 `docs/website-design-system.md` 中的颜色、字体、间距、圆角和响应式规范。

## 3. 设备目录设计

### 3.1 基本资料

设备基本资料保留：

| 字段 | 要求 |
| --- | --- |
| 型号 | 必填；作为设备唯一业务标识之一 |
| 产品名称中文 | 必填 |
| 产品名称英文 | 必填或按现有数据兼容规则处理 |
| 设备概况中文 | 可选 |
| 设备概况英文 | 可选 |

新架构不再使用设备级固定“基本价格”；兼容期保留旧字段供旧接口读取，待所有消费者切换并完成金额核对后再删除。基础价格改由电机、通道或两者组合对应的价格方案决定。

### 3.2 基本配置统一模型

建议新增 `product_base_options`，只保存电机、电源和通道；颜色继续由现有 `product_colors` 独立管理：

```text
id
group_id
option_type       # motor / power / channel
name_zh
name_en
price_cny_minor   # 最小货币单位，例如分/cent
price_usd_minor
is_required
is_single_select
sort_order
enabled
created_at
updated_at
```

基本配置共同规则：

- 前台显示为纯文字圆角卡片。
- 不设置或显示业务编号、编码或专有标注；数据库仍使用稳定内部 ID 维持关联。
- 颜色、电机、电源、通道在前台均为单选。
- 每个类型可设置是否必选。
- 中英文切换只改变 `name_zh` / `name_en` 的展示，不改变选中 ID。
- 后端保存前检查设备、配置类型和选项归属关系。

### 3.3 颜色

建议使用或扩展 `product_colors`：

```text
id
product_id
name_zh
name_en
display_color
image_path
image_width
image_height
sort_order
enabled
```

功能要求：

- 后台隐藏颜色代码，标题固定为“颜色名称”。
- 输入框分别编辑中文和英文名称。
- 上传后显示缩略图，不显示文件路径。
- 支持上传、替换和删除图片。
- 每个设备至少保留一种有效颜色。
- 颜色选项文字可使用对应色调，但必须满足可读性和对比度要求。
- 前台选中颜色后切换设备主图；图片缺失时使用统一占位图并保留固定宽高。

### 3.4 电机

电机选项本身不直接保存设备基础价格，基础价格由 `product_price_variants` 按已选电机/通道组合匹配。基础配置选项中的金额字段只用于电源附加费；电机和通道保持为 0：

```text
product_price_variants.motor_option_id
product_price_variants.channel_option_id
product_price_variants.price_cny_minor
product_price_variants.price_usd_minor
```

规则：

- 一台设备可有多个电机，但只能单选。
- 当前选中的电机决定报价单设备基础价格。
- 只有一个电机时可自动选中。
- 缺少价格时后端返回明确错误，不静默按 0 计算。
- 后台每行显示名称、人民币价格、美元价格、启用状态和删除操作。
- 移动端将名称、价格、操作拆成多行，避免输入框拥挤。

示例：BT618 可配置 11kw servo 和 22kw Servo，各自维护 CNY/USD 价格；CR1016 只配置 22kw Servo。

### 3.5 电源

电源属于附加费用，不改变设备基础价格：

```text
name_zh
name_en
price_cny_minor
price_usd_minor
```

计算规则：

```text
最终设备价格 = 电机或通道基础价格 + 电源附加费用 + 可选配置价格
```

免费选项明确保存为 0，并在前台显示“免费”或对应货币的 0 值。报价单应把电源附加费用单独列出。

### 3.6 通道

通道与电机一样可以决定设备基础价格。为兼容只按电机、只按通道以及未来按电机与通道组合定价，使用价格方案表：

```text
product_price_variants
├── product_id
├── motor_option_id    # 可为空
├── channel_option_id  # 可为空
├── price_cny_minor
├── price_usd_minor
└── enabled
```

BT618 可以只按电机匹配价格，CR318Pro 可以只按通道匹配价格；若未来设备同时由电机和通道决定价格，不需要再次重构表结构。后台必须阻止重复的电机/通道组合。

### 3.7 可选配置关联

设备可选配置继续使用现有 `product_options`：

```text
product_id
config_id
enabled
sort_order
```

设备编辑支持：

- 按编号、中文名称、英文名称搜索。
- “全部 / 仅已启用”筛选。
- 从配置目录勾选已创建项目。
- 保存时只提交当前有效配置 ID。
- 后端校验配置存在、启用状态和所属关系。
- 删除配置后自动清理设备关联，禁止产生悬空引用。
- 将模糊的 `One or more options do not exist` 替换为具体的中文/英文错误信息。

电机和电源不再从可选配置目录选择。

## 4. 配置目录设计

### 4.1 顶层分类

固定三个顶层分类：

| 类型 | 中文名称 | 英文名称 |
| --- | --- | --- |
| optional | 可选配置 | Optional Configurations |
| tools | 维修工具 | Service Tools |
| accessories | 设备附件 | Accessories |

### 4.2 可选配置子分类

可选配置包含：

1. BT618机械试验台拓展功能
2. 共轨喷油器测试套件
3. HEUI 中压胎具
4. 单体泵泵喷嘴胎具
5. 共轨泵工装
6. 凸轮箱扩展功能

### 4.3 配置项目字段

为降低迁移风险，继续使用现有 `categories`、`options` 和 `product_options`，通过增量迁移补充字段，不另建一套重复目录。`categories` 增加：

```text
parent_id
catalog_type       # optional / tools / accessories
enabled
version
```

现有 `options` 保留编号、名称、英文名称、图片、描述、备注和双币参考价格，并补充：

```text
note_en
version
deleted_at
```

其中现有 `name`、`description`、`notes` 作为中文字段继续使用，现有 `name_en`、`description_en` 作为英文字段，避免大规模字段改名。可选配置的六个类别作为 `optional` 的二级分类；维修工具和设备附件可按需要继续增加二级分类。

`product_options` 继续作为设备与可选配置的关联表，但新逻辑只允许关联 `catalog_type = optional` 的项目。电机和电源迁移到设备基本配置后，不再写入该表。维修工具和设备附件不与设备建立该关联，而是作为独立目录商品进入购物车、分享和报价。

### 4.4 前台卡片

- 使用统一的图文选项卡。
- 图片采用固定比例和 `object-fit: contain`。
- 名称、描述、备注根据当前语言字段显示。
- 参考价格根据当前货币显示，并自动作为创建报价时的默认单价。
- 中英文切换不得改变卡片整体高度和列宽。
- 无图片时显示统一占位区域。
- 可选配置、维修工具、设备附件复用同一套卡片组件。

## 5. API 方案

### 5.1 后台接口

```text
GET    /api/v1/admin/products
GET    /api/v1/admin/products/{id}
PUT    /api/v1/admin/products/{id}
GET    /api/v1/admin/products/{id}/base-options
PUT    /api/v1/admin/products/{id}/base-options
GET    /api/v1/admin/config-catalog
POST   /api/v1/admin/config-catalog
PUT    /api/v1/admin/config-catalog/{id}
DELETE /api/v1/admin/config-catalog/{id}
```

### 5.2 前台接口

```text
GET /api/v1/catalog?lang=zh
GET /api/v1/catalog?lang=en
GET /api/v1/products/{id}/configuration?lang=zh
GET /api/v1/products/{id}/configuration?lang=en
```

### 5.3 报价请求

```json
{
  "product_id": "bt618",
  "motor_option_id": 12,
  "power_option_id": 18,
  "channel_option_id": null,
  "config_items": [],
  "currency": "CNY"
}
```

后端必须根据数据库重新计算基础价格、电源附加费、可选配置价格和总价，前端提交的价格只能作为显示或人工报价输入，不能直接作为最终金额依据。

## 6. UI 设计规范

- 遵循 `docs/website-design-system.md`。
- 所有模块使用统一卡片、圆角、边框和阴影。
- 标题、标签和输入框间距保持一致。
- 表格列宽固定，中英文切换不重新计算列宽。
- 编辑、保存、取消、删除按钮统一高度、内边距和焦点样式。
- 删除使用页面内确认弹窗，不使用浏览器原生弹窗。
- 错误优先显示在对应表单区域，Toast 只用于成功或非阻断性提示。
- 颜色、电机、电源、通道卡片在桌面端最多三列，窄屏自适应为一列或两列，不能出现横向溢出。
- 所有动态图片声明尺寸或 `aspect-ratio`，避免加载时页面跳动。
- 支持键盘焦点、Esc 关闭弹窗和 `prefers-reduced-motion`。

## 7. 数据迁移策略

### 阶段一：新增结构

- 新增中英文名称、描述、备注字段。
- 新增基本配置表和价格表。
- 新增配置目录类别表。
- 保留旧字段和旧关联表。

### 阶段二：数据迁移

- 原设备名称复制到中文字段。
- 已有英文翻译复制到英文字段。
- 原基本价格迁移到默认电机或通道价格。
- 原电机、电源映射转换为基本配置。
- 原配置目录按名称归类到三个顶层类别。
- 无法自动判断的记录进入待确认清单。

### 阶段三：双读兼容

- API 优先读取新字段，缺失时回退旧字段。
- 前后台逐步切换到新接口。
- 对保存结果进行新旧数据一致性检查。

### 阶段四：清理旧结构

只有在全部设备价格来源明确、配置分类完整、报价金额验证通过、NAS 备份可恢复后，才删除旧字段或旧关联表。

每次迁移前必须：

1. 生成数据库快照。
2. 执行结构检查和数据完整性检查。
3. 记录迁移版本。
4. 准备反向迁移或快照恢复方案。

## 8. 错误处理和审计

错误响应统一包含：

```json
{
  "code": "INVALID_BASE_OPTION",
  "message": "所选电机不属于当前设备",
  "message_en": "The selected motor does not belong to this device",
  "fields": ["motor_option_id"]
}
```

需要覆盖：

- 配置不存在。
- 配置已停用。
- 配置不属于当前设备。
- 电机/通道未选择。
- 价格缺失或格式错误。
- 颜色删除后没有剩余有效颜色。
- 图片上传失败。
- 中英文内容为空。
- 并发编辑产生版本冲突。

保存、删除、启用、停用、批量关联和价格修改均写入审计日志。

## 9. 测试和验收

### 功能测试

- 每台设备可以分别配置颜色、电机、电源和通道。
- 颜色只影响图片和显示名称，不参与价格。
- 电机或通道能够正确决定基础价格。
- 电源附加费正确叠加。
- 可选配置只能从配置目录中选择。
- 删除配置不会产生悬空关联或保存异常。
- 中文、英文前台显示内容一致且不互相覆盖。
- 报价单正确显示基础价格、附加费用和可选配置价格。

### UI 测试

- 桌面端：1440、1280、1024px。
- 移动端：390px。
- 浏览器缩放 200%。
- 超长中英文名称、描述和备注。
- 无图片、空列表和停用配置。
- 键盘完成搜索、编辑、保存、删除和关闭弹窗流程。
- 检查中英文切换后的列宽、卡片高度和按钮位置。

### 数据安全测试

- 迁移脚本可重复执行。
- 迁移失败可以回滚。
- 旧数据数量与新数据数量一致。
- 价格迁移前后抽样比对。
- 数据库检查命令通过。
- API 健康检查和前台报价流程通过。

## 10. 实施顺序

1. 导出并核对现有设备、配置目录和价格数据。
2. 完成数据库新增表和可回滚迁移脚本。
3. 完成后台配置目录三分类和双语字段 API。
4. 完成后台设备基本配置 API。
5. 完成设备颜色、电机、电源、通道编辑 UI。
6. 完成可选配置关联、搜索和筛选 UI。
7. 改造前台设备配置卡片和中英文渲染。
8. 接入电机/通道基础价格和电源附加费用计算。
9. 改造报价单和 PDF 数据来源。
10. 完善错误提示、权限、审计和并发保护。
11. 执行全流程回归测试和视觉验收。
12. 用户确认后备份数据库、提交 Git，再同步至 BOTEN-NAS。

## 11. 需要用户确认的决策

在开始开发前确认：

- 哪些设备只按电机、只按通道或按电机与通道组合决定基础价格。
- 可选配置是否允许针对不同设备设置独立价格覆盖。
- 配置目录的“参考价格”是否仅供展示，还是直接参与报价。
- 英文名称、描述和备注是否全部设为必填。
- 旧设备基本价格迁移到哪个默认电机或通道选项。
- 现有设备的电机/通道价格组合如何映射到新的价格方案。

未确认以上规则前，不执行破坏性字段删除和旧数据清理。


## 12. 推荐的最终技术架构

### 12.1 核心实体关系

建议将“产品”“基础配置”“目录配置”“设备可选配置”拆为四个独立层级：

```text
products
  ├─ product_colors                 # 颜色及设备主图
  ├─ product_base_option_groups     # 电机 / 电源 / 通道分组
  │    └─ product_base_options      # 每个设备自己的基础配置选项
  ├─ product_price_variants         # 电机 / 通道组合对应的基础价格
  └─ product_options                # 复用现有设备可选配置关联

categories                          # 增量扩展现有目录分类
  └─ options                        # 可选配置 / 维修工具 / 设备附件
```

这样可以避免把“电机、电源”当作普通可选配置保存，且明确设备价格与配置目录价格的责任边界。

### 12.2 建议表结构

#### 产品基础配置分组

```sql
CREATE TABLE product_base_option_groups (
  id TEXT PRIMARY KEY,
  product_id TEXT NOT NULL REFERENCES products(id),
  option_type TEXT NOT NULL CHECK (
    option_type IN ('motor', 'power', 'channel')
  ),
  pricing_role TEXT NOT NULL DEFAULT 'none' CHECK (
    pricing_role IN ('none', 'base_price', 'surcharge')
  ),
  required INTEGER NOT NULL DEFAULT 1,
  single_select INTEGER NOT NULL DEFAULT 1,
  sort_order INTEGER NOT NULL DEFAULT 0,
  enabled INTEGER NOT NULL DEFAULT 1,
  UNIQUE(product_id, option_type)
);
```

规则：

- 颜色由现有 `product_colors` 独立管理，不进入该分组。
- `motor`、`channel` 参与基础价格方案匹配，不在分组本身保存最终基础价。
- `power`：`pricing_role = surcharge`。
- 所有基础分组均单选；数据库层保留 `single_select` 是为了避免未来结构重做。

#### 产品基础配置选项

```sql
CREATE TABLE product_base_options (
  id TEXT PRIMARY KEY,
  group_id TEXT NOT NULL REFERENCES product_base_option_groups(id),
  name_zh TEXT NOT NULL,
  name_en TEXT,
  price_cny_minor INTEGER NOT NULL DEFAULT 0,
  price_usd_minor INTEGER NOT NULL DEFAULT 0,
  sort_order INTEGER NOT NULL DEFAULT 0,
  enabled INTEGER NOT NULL DEFAULT 1,
  version INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

说明：

- 电机/通道选项本身不保存最终基础价格，由价格方案表匹配。
- 电源的价格代表附加费用。
- 金额统一使用整数最小货币单位；旧数据迁移时明确执行单位转换，禁止混用元和分。
- `version` 用于防止两位管理员同时保存时互相覆盖。

#### 产品基础价格方案

```sql
CREATE TABLE product_price_variants (
  id TEXT PRIMARY KEY,
  product_id TEXT NOT NULL REFERENCES products(id),
  motor_option_id TEXT REFERENCES product_base_options(id),
  channel_option_id TEXT REFERENCES product_base_options(id),
  price_cny_minor INTEGER NOT NULL,
  price_usd_minor INTEGER NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1,
  version INTEGER NOT NULL DEFAULT 1,
  UNIQUE(product_id, motor_option_id, channel_option_id)
);
```

BT618 可只填写 `motor_option_id`，CR318Pro 可只填写 `channel_option_id`；将来同时由电机和通道决定价格时填写两者。后台保存时校验所引用选项属于当前设备及正确分组。

#### 增量扩展配置目录

不新建重复的配置目录表。通过迁移为现有 `categories` 增加 `parent_id`、`catalog_type`、`enabled`、`version`，为现有 `options` 增加 `note_en`、`version`、`deleted_at`。现有 `name/name_en`、`description/description_en`、`notes`、`price/price_usd` 继续使用，并在 API 适配层映射为统一字段。

可选配置六类项目使用 `parent_id` 形成二级分类。目录项目只允许挂在叶子分类下。

#### 设备与可选配置关联

继续使用现有 `product_options`。新保存逻辑只允许它关联 `catalog_type = optional` 的项目。维修工具和设备附件作为独立商品进入购物车、分享和报价，但不得作为设备可选配置关联。

### 12.3 约束与索引

必须增加以下约束或应用层事务检查：

- 同一设备一个 `option_type` 只能有一个分组。
- 每个价格方案的电机/通道组合必须唯一。
- 每台设备至少保留一条已启用颜色记录。
- `product_options` 只能引用已启用且类型为可选配置的项目。
- 设备基础配置保存和可选配置关联保存必须在一个事务内完成。
- 对 `product_id`、`group_id`、`category_id`、`parent_id`、`catalog_type`、`enabled` 建立查询索引。
- 所有价格保存前标准化为非负整数最小货币单位，API 层统一转换为两位小数显示。

## 13. 价格计算技术方案

### 13.1 统一价格公式

```text
设备基础价格
= 根据当前产品已选电机和通道匹配 product_price_variants

设备附加费用
= 当前产品中，价格角色为 surcharge 的已选基础配置价格之和

可选配置费用
= 已选配置目录项目的报价价格之和

配置单总价
= 设备基础价格 + 设备附加费用 + 可选配置费用
```

其中：

- 颜色永远不参与报价。
- 电机、通道或两者组合通过价格方案决定基础价格。
- 电源通常为附加费用。
- 设备可选配置是否参与报价，由配置目录项目的参考价格或未来明确的设备级价格覆盖决定。
- 报价编辑页面可以人工调整单价，但保存时必须记录“目录参考价”“调整后报价”“调整原因（可选）”。

### 13.2 价格来源优先级

建议实施以下固定优先级。基础配置价格和目录价格不得互相覆盖：

```text
人工报价单行价
  > 设备专属可选配置价格覆盖（第二阶段可选）
  > 配置目录参考价格

设备基础价 = product_price_variants 精确匹配结果
电源附加费 = product_base_options 对应电源价格
```

基础配置价格不使用配置目录价格。没有匹配价格方案或目录参考价格时必须返回明确的“价格待完善”状态，不允许静默使用 0。报价单中每行保存价格快照，后续目录价格更新不应篡改历史报价。

### 13.3 后端计算职责

后端新增单一价格计算服务，例如 `backend/pricing_service.py`：

1. 接收产品 ID、基础配置选项 ID、可选配置 ID 和货币。
2. 校验选项归属、启用状态和单选约束。
3. 查询并计算基础价格、附加费、可选配置费。
4. 返回带明细的价格快照。
5. 创建配置单、分享记录和 PDF 时复用同一服务。

禁止在购物车、报价编辑、PDF 三处各自复制计算逻辑。

### 13.4 价格明细返回格式

```json
{
  "currency": "CNY",
  "base_price": "100000.00",
  "surcharge_total": "3800.00",
  "optional_total": "12600.00",
  "grand_total": "116400.00",
  "lines": [
    {
      "kind": "base_price",
      "label": "22kw Servo",
      "amount": "100000.00"
    },
    {
      "kind": "surcharge",
      "label": "外置变压 220V-3相电",
      "amount": "3800.00"
    }
  ]
}
```

API 金额统一返回十进制字符串，避免 JSON/JavaScript 浮点误差。前端和 PDF 只使用该明细展示，不自行拼接或重新计算。

## 14. 后台 API 契约

### 14.1 设备编辑读取

```text
GET /api/v1/admin/products/{product_id}/editor?lang=zh
```

建议返回设备基本资料、基础配置分组、基础配置选项、已关联的可选配置和版本号。后台编辑读取应一次完成，避免多个请求间数据不一致。

### 14.2 原子保存设备编辑

```text
PUT /api/v1/admin/products/{product_id}/editor
```

请求示例：

```json
{
  "version": 7,
  "model": "BT618",
  "name_zh": "机械试验台",
  "name_en": "Mechanical Test Bench",
  "overview_zh": "",
  "overview_en": "",
  "base_option_groups": [
    {
      "option_type": "motor",
      "pricing_role": "base_price",
      "required": true,
      "options": [
        {
          "id": "motor-11kw",
          "name_zh": "11kw 伺服电机",
          "name_en": "11kw Servo",
          "price_cny": 0,
          "price_usd": 0,
          "enabled": true
        }
      ]
    }
  ],
  "optional_config_ids": ["config-001", "config-002"]
}
```

服务端执行顺序：

1. 校验权限和版本号。
2. 校验型号、双语名称和金额格式。
3. 校验基础配置分组规则。
4. 校验所有可选配置均存在、启用且属于 `optional`。
5. 在单一数据库事务中更新产品、基础配置、图片引用和关联表。
6. 清理被删除的基础配置和无效关联。
7. 写入审计记录。
8. 返回完整的新编辑数据和版本号。

发生冲突时返回 HTTP 409；发生字段错误时返回 HTTP 422，并逐字段返回中文和英文信息。

### 14.3 配置目录接口

```text
GET    /api/v1/admin/config-catalog?type=optional&lang=zh
POST   /api/v1/admin/config-catalog/items
PUT    /api/v1/admin/config-catalog/items/{id}
DELETE /api/v1/admin/config-catalog/items/{id}
POST   /api/v1/admin/config-catalog/categories
PUT    /api/v1/admin/config-catalog/categories/{id}
```

删除规则：

- 已关联到设备的配置项目默认不可直接物理删除。
- 后台提示关联的设备数量，并提供“停用”“从设备移除后删除”两种明确路径。
- 软删除/停用后，历史配置单、分享记录和 PDF 继续保留价格快照和名称快照。

### 14.4 错误规范

接口统一返回：

```json
{
  "code": "OPTION_NOT_AVAILABLE",
  "message": "The selected option is unavailable.",
  "fields": {
    "optional_config_ids": ["BTK1019"]
  },
  "request_id": "..."
}
```

`code` 是前端中英文翻译的稳定索引，`message` 只作为无法识别错误码时的后备信息。动态编号、字段和值通过 `fields` 提供，避免后端分别维护两套整句翻译。

前端规则：

- 422：把错误显示到具体字段或具体卡片。
- 409：提示数据已被其他人修改，提供重新加载按钮。
- 401/403：提示登录失效或无权限。
- 5xx/网络错误：提示可重试，保留用户未保存表单内容。
- 不允许显示 `[object Object]`、裸异常堆栈或不明的 `Object` 错误。

## 15. 前端实现方案

### 15.1 数据状态

前端状态以选项 ID 为唯一键，显示语言不参与选中状态：

```text
selectedBaseOptions = {
  color: "color-blue",
  motor: "motor-22kw",
  power: "power-external-220v",
  channel: null
}

selectedOptionalConfigIds = Set(["config-001", "config-002"])
```

语言切换后仅重新读取或重渲染 `name_zh/name_en`、描述和备注；不得重置上述选中状态、购物车内容或报价价格快照。

### 15.2 前台选配顺序

建议固定前台顺序：

1. 设备型号。
2. 设备主图和颜色。
3. 设备概况。
4. 电机。
5. 电源。
6. 通道（仅设备存在该分组时显示）。
7. 可选配置分类和图文卡片。
8. 当前选配摘要。
9. 保存配置到购物车。

基础配置卡片使用纯文字样式；配置目录项目使用图文卡片。两者不能混用视觉样式，避免用户误解价格性质。

### 15.3 管理后台编辑 UI

设备编辑采用四段式面板：

```text
基本资料
  型号 / 产品名称 / 设备概况

基本配置
  颜色 | 电机 | 电源 | 通道

可选配置
  搜索 / 筛选 / 分类 / 勾选列表

底部操作区
  取消 | 保存
```

实现要求：

- 标签固定中文，不随语言按钮变化。
- 每个分组在标题右侧提供“添加颜色 / 添加电机 / 添加电源 / 添加通道”。
- 选项列表使用可拖动排序或显式排序按钮；首期推荐显式上移/下移，避免拖拽在触屏设备不稳定。
- “保存”固定在编辑弹窗底部；主体内容独立滚动，避免双滚动条。
- 关闭或切换页面时，如有未保存修改需显示统一确认弹窗。
- 对被关联、停用、删除等状态提供明确数量提示。

### 15.4 前台中英文显示规则

| 数据 | 中文界面 | 英文界面 | 缺失回退 |
| --- | --- | --- | --- |
| 名称 | name_zh | name_en | 不回退中文；缺失时使用自动翻译草稿 |
| 描述 | description_zh | description_en | 不回退中文；缺失时使用自动翻译草稿 |
| 备注 | note_zh | note_en | 不回退中文；无内容则隐藏 |
| 颜色名称 | name_zh | name_en | 不回退中文；缺失时使用自动翻译草稿 |
| 类别标题 | 固定词典 | 固定词典 | 不读取后台翻译 |
| 后台字段标签 | 固定中文 | 固定中文 | 不变 |

英文界面禁止回退显示中文。迁移或新增中文内容后生成英文机器翻译草稿，并使用 `translation_status = machine_draft | reviewed` 标记状态；管理员后续可修改并标记已校对。启用英文展示前必须保证所需英文名称存在，前台不得拼接中英文造成内容割裂。

### 15.5 图片上传流程

设备原子保存接口只提交图片引用，不直接携带大文件：

1. 后台先调用临时媒体上传接口。
2. 服务端验证扩展名、MIME、尺寸和文件大小，生成缩略图。
3. 上传成功返回 `media_id`、预览地址、宽度和高度。
4. 保存设备或目录项目时提交 `media_id`。
5. 数据库事务成功后将媒体标记为已使用。
6. 定时清理超过有效期且未被引用的临时媒体。

替换图片时先保存新引用，事务成功后再清理旧文件，避免保存失败造成图片丢失。

### 15.6 统一兼容适配层

在新旧结构并存期间新增统一适配层，例如 `backend/catalog_adapter.py`：

```text
read_legacy_product()
read_new_product()
normalize_product_snapshot()
```

用户选配、购物车、分享、报价、PDF 和后台预览只能读取标准化快照，不得分别兼容新旧表。标准快照全部消费者切换完成后，才停止旧字段读取。

### 15.7 历史快照

购物车保存、分享和报价明细至少固化：

```text
source_id
source_type
code_snapshot
name_zh_snapshot
name_en_snapshot
price_minor_snapshot
currency
quantity
```

设备型号、产品名称、颜色、电机、电源和通道也保存双语名称快照。目录名称或价格更新不得改变历史报价和已生成 PDF。

## 16. 数据迁移实施计划

### 16.1 迁移前准备

1. 停止对生产数据库做结构修改，导出只读快照。
2. 执行数据库维护检查并记录结果。
3. 导出产品、颜色、电机、电源、配置目录、设备关联和报价记录 CSV。
4. 为无法自动映射的数据生成待确认清单。
5. 在本地副本完整演练迁移和回滚。

### 16.2 迁移版本建议

| 版本 | 内容 | 是否可回滚 |
| --- | --- | --- |
| 0010 | 新增基础配置分组、选项和价格方案表 | 是 |
| 0011 | 增量扩展现有 categories/options 双语、层级和状态字段 | 是 |
| 0012 | 导入旧电机、电源、通道数据；颜色继续使用原表 | 是，保留源字段 |
| 0013 | 清理并校验现有 product_options，只保留可选配置关联 | 是 |
| 0014 | 启用统一兼容适配层和新 API | 是 |
| 0015 | 启用前台与后台新 UI，并保留旧数据回退读取 | 是 |
| 0016 | 所有消费者切换后停止旧读取逻辑 | 是，可恢复旧版本 |
| 0017 | 删除废弃字段或表 | 仅在完整备份和用户确认后执行 |

### 16.3 数据映射规则

- 迁移前先确认现有 `base_price`、`price_usd`、`price` 和电机价格字段使用“元/美元”还是最小货币单位；确认后统一转换为 `*_minor`，并保存迁移前后抽样对照。禁止凭字段名称直接乘以 100。
- 原产品基本价格：迁移为默认价格方案，关联的电机/通道必须在待确认清单中人工确认。
- 现有 `product_motor_prices`：迁移为仅按电机匹配的价格方案。
- 现有颜色数据：继续保留在 `product_colors`，只补充缺失字段和完整性检查。
- 现有电源数据：转为 `power` 分组，原价格转为附加费用。
- 现有设备配置关联：仅迁移目录类型为 `optional` 的项目。
- 维修工具、设备附件：不进入设备选配，保留在目录中等待独立展示或业务使用。
- 当前专有标注：不迁移到新的基本配置；是否继续用于普通可选配置需要业务确认，历史快照始终保留。

### 16.4 迁移后自动校验

迁移脚本结束时必须输出：

- 产品数量、新旧基础配置数量、颜色数量、目录项目数量和关联数量。
- 没有基础价格决定因素的产品列表。
- 没有已启用颜色的产品列表。
- 重复编号、空名称、空价格和缺失图片列表。
- 英文名称、描述、备注缺失翻译列表。
- 悬空设备配置关联列表。
- 价格异常（负数、非数字、精度异常）列表。

只要关键列表非空，禁止切换到新 UI。

## 17. 交付阶段与验收门槛

### P0：数据盘点与样本确认

交付物：

- 当前数据库快照。
- 产品/配置目录/价格盘点表。
- 自动迁移映射和待确认清单。
- 3 个代表性产品的价格样本：BT618、CR1016、CR318Pro。

验收门槛：用户确认每个样本产品的基础价格来源、电源收费规则和中英文内容。

### P1：数据库与后台 API

交付物：

- 迁移脚本。
- 价格计算服务。
- 原子设备编辑接口。
- 配置目录三分类接口。
- 错误码与审计记录。

验收门槛：迁移可回滚；新旧数据对比通过；非法关联能返回字段级错误。

### P2：后台 UI

交付物：

- 设备基本资料、颜色、电机、电源、通道编辑界面。
- 可选配置搜索、分类和关联界面。
- 配置目录三分类及图文编辑界面。
- 统一表单错误、删除确认和未保存提示。

验收门槛：中文/英文输入内容可独立保存；设备保存不再发生笼统选项不存在错误。

### P3：前台与报价/PDF

交付物：

- 前台基本配置和图文可选配置卡片。
- 双语回退逻辑。
- 后端统一价格计算。
- 购物车、分享、报价单、PDF 使用价格快照。

验收门槛：切换电机/通道、电源、可选配置后，前台、购物车、分享、报价和 PDF 金额一致。

### P4：回归、备份和部署

交付物：

- 自动化测试补充。
- 数据完整性报告。
- UI 验收截图清单。
- Git 提交和 NAS 部署说明。

验收门槛：本地 E 盘验收通过；数据库备份已生成；用户明确确认后才部署 BOTEN-NAS。

## 18. 风险与控制措施

| 风险 | 影响 | 控制措施 |
| --- | --- | --- |
| 旧基本价格无法对应电机或通道 | 报价金额错误 | 进入待确认清单，不自动删除旧价 |
| 中英文翻译缺失 | 英文界面出现中文或空白 | 自动生成英文草稿、禁止中文回退并输出待校对报告 |
| 已删除配置仍被设备引用 | 保存失败或前台异常 | 事务清理、软删除和关联检查 |
| 多人编辑同一设备 | 数据覆盖 | version 乐观锁、409 冲突提示 |
| 前端自行算价 | 报价与 PDF 不一致 | 所有价格由后端服务计算并返回快照 |
| 目录配置误进入设备选配 | 功能边界混乱 | 只允许 optional 类型建立设备关联 |
| NAS 迁移失败 | 线上服务中断 | 本地先验证、数据库快照、Git 固定版本、可回滚 Docker 部署 |

## 19. 开发前最终确认清单

开始 P0 前，请确认以下业务规则：

1. 分别确认每台设备采用“只按电机”“只按通道”还是“电机+通道组合”价格方案。
2. 电源价格是否全部属于附加费用，不存在决定基础价格的例外。
3. 已确认：配置目录参考价格直接作为报价编辑的默认单价。
4. 可选配置是否允许为某台设备设置不同于目录参考价的价格。
5. 已确认：英文界面不允许回退中文；缺失英文先生成机器翻译草稿，后续由管理员修改。
6. 已确认：维修工具、设备附件不加入设备可选配置，但可以独立加入购物车、分享和报价。
7. 历史配置单、历史报价和历史 PDF 是否保持旧价格快照且不可因目录更新改变。
8. 已确认：普通可选配置不再支持专有标注；旧数据只保留历史快照，不进入新编辑和前台展示。

价格暂定规则：没有明确价格的数据先保存为 `0`，后台允许后续修改。报价页面必须把 0 价格项目明确显示为“价格待确认”，不能误标为免费；只有明确设置为免费的电源选项显示“免费”。
