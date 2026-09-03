# BOTEN 柴油试验台在线配置与报价系统

这是一个面向客户、业务员和管理员的全栈选配系统。客户可以在线选择设备及工装、保存方案并生成分享码；业务员可以查看客户方案、制作双币种报价并下载 PDF；管理员负责设备、配置、账号和全部报价数据。

## 当前成果

截至 2026-09-01，项目已经具备可本地运行和联调的完整主流程：

- 用户端支持 7 个设备型号，按机型独立映射颜色、电机、供电和可选工装。
- 配置目录包含 CRI、HEUI、EUI/EUP、CRP、Cambox Extension 等分类；当前示例数据库有 8 个分类、75 个配置项和 175 条机型映射。
- 单个机型可以为共享配置分别填写中文和英文专属说明，避免提示影响其他设备。
- 中英文切换会保留当前设备和已选配置；设备、分类、配置名称及描述从后台数据库读取。
- 手机端提供紧凑导航、配置抽屉、关闭按钮及悬浮查看按钮。
- 注册要求姓名、邮箱、国际格式手机号和密码；登录可选择邮箱或手机号，游客可浏览，保存和分享时必须登录。
- 登录用户可保存多套配置、管理购物车，并生成有效期 90 天的 6 位分享码。
- 管理后台包含设备目录、配置目录、分享记录、报价管理和账号管理。
- 设备与配置可分别维护中文/英文内容、人民币/美元参考价、图片和启用状态；配置与颜色图片可在后台直接上传。
- 用户配置、分享配置和报价单均由后端生成可直接下载的跨平台中文 PDF，不再依赖浏览器打印或 Windows Edge。
- 业务员可查看分享用户的联系方式和详细配置，按 CNY/USD 自动填价或手动调价，保存并下载报价 PDF。
- 管理员可查看全部报价和账号，业务员只可管理自己的报价。
- 管理后台新增操作审计，记录管理员和业务员成功的写入操作，但不记录密码和表单正文。
- 已提供数据库在线备份、完整性检查、确认式恢复和目录数据质量审计命令。
- 已建立 26 项自动化测试，覆盖迁移、认证、配置分享、历史颜色名称刷新、双语覆盖、角色权限、目录 CRUD、PDF、操作审计、图片接口、安全删除和备份恢复。
- 管理后台编辑卡片已统一弹窗尺寸、边距、字号和输入框规格；设备编辑、配置分类、配置条目和添加设备分别采用适合内容量的卡片布局。
- 配置目录分类的“更多”菜单支持稳定的纵向展开和层级显示；配置条目编辑改为单列字段，编号、名称、描述和备注不会互相挤压。
- 设备编辑的配置模块采用搜索、筛选、展开/折叠分层布局；筛选位于左侧，展开/折叠位于右侧，标注和展开类操作按钮保持中文显示。
- 编辑卡片中的中文/英文切换只切换输入框示例及对应内容，字段标题保持中文；中英文数据分别提交并保存。
- 后台登录 Logo 已修复原始比例，目录编辑卡片增加必填项定位、语言按钮状态和关闭后的焦点恢复。
- 用户端选择设备型号后会将设备标题定位到固定导航栏下方；选择颜色会自动折叠设备概况并回到相同定位，系统启用“减少动态效果”时不使用平滑滚动。
- 已使用 `tb/pricelist.xlsx` 安全导入 67 个可匹配配置的人民币和美元参考价格；无法匹配的 8 项保持原值，导入前数据库备份和操作审计均已保留。
- 设备与配置目录的双语字段已从本地安全备份恢复并验证 API 输出；修复脚本可重复执行，默认先预览差异再写入。
- 设备目录的 Excel 导入、导出入口目前已从后台界面屏蔽，待完整的预览、校验、确认导入流程验收后再开放；相关 API 不作为日常操作入口。

当前 `backend/boten.db` 是目录和业务数据的唯一运行时数据源。`js/data.js` 只保留初始化导入资料和用户端本地相册资源，不再作为产品文字的离线回退；API 不可用时页面会明确报错，避免显示过期或语言错误的数据。

## 角色权限

| 角色 | 主要权限 |
| --- | --- |
| 游客 | 浏览设备和进行临时选配 |
| 用户 | 注册/登录、保存配置、购物车、生成分享码 |
| 业务员 | 普通用户全部功能、设备与配置目录管理、查询分享记录、查看客户信息、管理自己的报价、下载报价 PDF |
| 管理员 | 业务员全部能力，以及设备、配置、账号和全部报价管理 |

## 技术栈

- 用户端与管理端：原生 HTML、CSS、JavaScript，无前端构建步骤
- API：FastAPI + Uvicorn
- 数据库：SQLite + Alembic 版本迁移
- 认证：Bearer 会话令牌，PBKDF2-SHA256 密码散列
- 字体：用户端、管理后台和 PDF 统一使用项目内嵌的 HarmonyOS Sans；浏览器和 NAS 不依赖系统字体。字体授权见 `assets/fonts/harmonyos-sans/LICENSE.txt`。
- PDF：ReportLab 后端生成，优先使用项目内嵌的 HarmonyOS Sans SC，缺失时回退系统中文字体或内置中文字体

## 本地运行

本地开发最低支持 Python 3.8，推荐 Python 3.12；Docker API 镜像固定使用 Python 3.12。所有命令都应在项目根目录执行。

首次安装：

```powershell
Set-Location E:\Project\CC-Project\benchshop
py -3.8 -m venv backend\.venv
.\backend\.venv\Scripts\python.exe -m pip install -r .\backend\requirements-dev.txt
```

仅当创建全新的空数据库时，才执行初始化导入：

```powershell
.\backend\.venv\Scripts\python.exe -m backend.seed
```

> `backend.seed` 会读取 `js/data.js` 并覆盖同编号的基础目录字段。已经通过后台维护过 `backend/boten.db` 后，不要把它当作日常启动命令反复执行。部署或迁移前应先备份数据库。

如数据库中还没有管理员账号：

```powershell
.\backend\.venv\Scripts\python.exe -m backend.create_admin --email admin@example.com --name Administrator
```

日常启动需要两个 PowerShell 窗口。

窗口 1，启动 API（8001）：

```powershell
Set-Location E:\Project\CC-Project\benchshop
.\backend\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8001
```

窗口 2，启动静态网站（8080）：

```powershell
Set-Location E:\Project\CC-Project\benchshop
py -m http.server 8080
```

访问地址：

- 用户选配页：`http://127.0.0.1:8080/`
- 管理后台：`http://127.0.0.1:8080/admin/`
- API 文档：`http://127.0.0.1:8001/docs`
- 健康检查：`http://127.0.0.1:8001/api/v1/health`

不要直接双击 `index.html` 以 `file://` 方式运行。用户端目录必须从 API 获取。

常用维护命令：

```powershell
# 运行自动化测试
.\backend\.venv\Scripts\python.exe -m unittest discover -s tests -v

# 备份并保留最近 30 份
.\backend\.venv\Scripts\python.exe -m backend.database_maintenance backup --keep 30

# 检查目录翻译、价格、图片和映射
.\backend\.venv\Scripts\python.exe -m backend.audit_catalog
```

## 项目结构

```text
.
├── index.html                 用户选配入口
├── admin/                    管理员/业务员后台
├── css/                      用户端样式、响应式和打印样式
├── js/
│   ├── runtime-config.js     API 地址配置
│   ├── catalog-api.js        后台目录加载与语言参数
│   ├── data.js               首次导入数据和本地相册资源
│   ├── language.js           用户端静态界面短文本翻译
│   ├── auth.js               注册、登录和会话
│   ├── cart.js               已保存配置、购物车和分享
│   └── ...                   状态、渲染、价格和 PDF 下载逻辑
├── backend/                  FastAPI、SQLite、仓储及维护脚本
├── tests/                    后端自动化测试
├── alembic.ini               数据库迁移配置
├── backups/                  本地数据库备份（不会提交到 Git）
├── uploads/                  后台上传的目录图片（不会提交到 Git）
├── tb/                       原始设备图片、配置图片、Excel/PDF 资料
├── codex.md                  历史开发与问题处理记录
└── README.md
```

## 数据维护约定

- 设备型号、标题、描述、启用状态和双币种价格在“设备目录”维护。
- 公共配置分类和配置项在“配置目录”维护，再在设备编辑卡片中选择该机型可用项。
- 共用图片和配置资料可以复用，但机型可选范围必须通过 `product_options` 单独映射。
- 机型专属提示写入设备与配置的中英文映射覆盖，不要直接修改共享配置说明。
- 配置与设备颜色图片可在编辑卡片直接上传 PNG/JPEG/WebP（最大 8 MB），也可填写已有相对路径。
- 删除配置时会先检查设备引用；配置分类必须为空才能删除，电机和供电基础分类不可删除。
- 用户端静态按钮/提示翻译位于 `js/language.js`；产品和配置业务文字由数据库提供。
- 批量价格资料优先保留在 `tb/` 并先执行编号匹配预览；当前可用的一次性资料为 `tb/pricelist.xlsx`，未匹配的编号不得自动新增或改写。
- 如目录中文显示异常，可先执行 `python -m backend.repair_catalog_translations` 查看差异；确认来源备份正确后再加 `--apply`。脚本只恢复双语文字字段，不修改价格、图片、映射和报价历史。

## 部署准备

### 2026-09-01 群晖部署状态

最新代码与数据库已在群晖 `BOTEN_NAS` 的 `/volume1/docker/benchshop` 启动验证：`api` 容器状态为 `healthy`，`web` 容器已运行并通过宿主机 `8080` 端口提供服务。局域网验收使用 `http://<NAS-IP>:8080/`，管理后台使用 `http://<NAS-IP>:8080/admin/`。

本次首次启动曾因“表结构已存在但 Alembic 版本记录落后”而失败。已在核对现有表结构后以 `docker compose run --rm --no-deps --entrypoint python api -m alembic stamp 20260901_0005` 修正记录，再执行 `docker compose up -d --force-recreate` 成功启动。此操作只更新迁移版本，不会重建或删除业务数据。

当前代码适合本地验证。部署到外网前至少需要：

1. 选择 Linux 或 Windows 服务器并安装受支持的 Python。
2. 将 `backend/boten.db`、`uploads/` 和业务图片目录做独立、定时、可恢复的备份。
3. 使用 Nginx/Caddy 提供静态文件、HTTPS，并把同域 `/api/` 反向代理到 Uvicorn。
4. 用服务管理器运行 API（systemd、Supervisor 或 Windows Service），不要用开发终端长期托管。
5. 设置 `BOTEN_DATABASE_PATH` 和严格的 `BOTEN_CORS_ORIGINS`；生产环境不要允许 `null` 来源。
6. 将 `js/runtime-config.js` 的 API 地址改为生产地址；同域反向代理时可设为空字符串。
7. 每天运行 `python -m backend.cleanup` 关闭过期分享码，并监控磁盘、日志和 API 健康状态。

更详细的后端和接口说明见 [backend/README.md](backend/README.md)。

## 已知限制与建议路线

- 数据库仍是单机 SQLite；迁移文件已建立，多人高并发或多实例部署时仍建议迁移 PostgreSQL。
- 图片上传已可用，但尚无裁剪、对象存储、重复图片检测和失效文件自动清理流程。
- 登录和分享限流保存在单个 API 进程内；生产环境应使用 Redis 或网关限流。
- 当前自动化测试集中在后端核心流程，并辅以浏览器人工回归；仍需引入可持续运行的浏览器端到端测试、结构化应用日志和 CI/CD。
- 后台 UI 的桌面端和移动端关键断点已完成第一轮调整，仍需在 1440px、1024px 和 390px 视口下完成最终人工验收。
- 目录结构与外键审计已无错误；已导入价格资料中可匹配的 67 项双币种参考价，剩余 8 项和部分配置图片仍待业务资料确认后填写。
- Excel 批量维护的前端入口尚未达到可用标准，现阶段保持隐藏，避免不完整流程影响正式目录数据。
- 可继续增加客户资料/公司抬头、报价有效期、税率折扣、报价状态流转、邮件发送和分享码撤回记录。

## 浏览器支持

推荐使用最新版 Chrome 或 Edge；Firefox 和 Safari 可完成常规选配，打印/PDF 效果需单独验证。

设备资料以 `tb/` 中的源文件和最终业务确认结果为准。
