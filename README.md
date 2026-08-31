# BOTEN 柴油试验台在线配置与报价系统

这是一个面向客户、业务员和管理员的全栈选配系统。客户可以在线选择设备及工装、保存方案并生成分享码；业务员可以查看客户方案、制作双币种报价并下载 PDF；管理员负责设备、配置、账号和全部报价数据。

## 当前成果

截至 2026-08-31，项目已经具备可本地运行和联调的完整主流程：

- 用户端支持 7 个设备型号，按机型独立映射颜色、电机、供电和可选工装。
- 配置目录包含 CRI、HEUI、EUI/EUP、CRP、Cambox Extension 等分类；当前示例数据库有 8 个分类、75 个配置项和 175 条机型映射。
- 单个机型可以为共享配置分别填写中文和英文专属说明，避免提示影响其他设备。
- 中英文切换会保留当前设备和已选配置；设备、分类、配置名称及描述从后台数据库读取。
- 手机端提供紧凑导航、配置抽屉、关闭按钮及悬浮查看按钮。
- 支持邮箱或手机号注册登录；游客可浏览，保存和分享时必须登录。
- 登录用户可保存多套配置、管理购物车，并生成有效期 90 天的 6 位分享码。
- 管理后台包含设备目录、配置目录、分享记录、报价管理和账号管理。
- 设备与配置可分别维护中文/英文内容、人民币/美元参考价、图片和启用状态；配置与颜色图片可在后台直接上传。
- 业务员可查看分享用户的联系方式和详细配置，按 CNY/USD 自动填价或手动调价，保存并下载报价 PDF。
- 管理员可查看全部报价和账号，业务员只可管理自己的报价。
- 已提供数据库在线备份、完整性检查、确认式恢复和目录数据质量审计命令。
- 已建立 11 项核心后端自动化测试，覆盖迁移、认证、配置分享、双语覆盖、权限、图片接口、安全删除和备份恢复。

当前 `backend/boten.db` 是目录和业务数据的唯一运行时数据源。`js/data.js` 只保留初始化导入资料和用户端本地相册资源，不再作为产品文字的离线回退；API 不可用时页面会明确报错，避免显示过期或语言错误的数据。

## 角色权限

| 角色 | 主要权限 |
| --- | --- |
| 游客 | 浏览设备和进行临时选配 |
| 用户 | 注册/登录、保存配置、购物车、生成分享码 |
| 业务员 | 查询全部分享记录、查看客户信息、管理自己的报价、下载报价 PDF |
| 管理员 | 业务员全部能力，以及设备、配置、账号和全部报价管理 |

## 技术栈

- 用户端与管理端：原生 HTML、CSS、JavaScript，无前端构建步骤
- API：FastAPI + Uvicorn
- 数据库：SQLite + Alembic 版本迁移
- 认证：Bearer 会话令牌，PBKDF2-SHA256 密码散列
- PDF：报价单由后端直接生成并下载；用户配置清单仍使用浏览器打印/另存为 PDF

## 本地运行

要求 Python 3.8 或更高版本。所有命令都应在项目根目录执行。

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
│   └── ...                   状态、渲染、价格和打印逻辑
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

## 部署准备

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
- 用户配置清单仍通过浏览器打印，建议复用后端 PDF 服务实现一键下载。
- 后端报价 PDF 优先调用服务器上的 Edge；应改成跨平台 HTML-to-PDF 方案并嵌入中文字体。
- 登录和分享限流保存在单个 API 进程内；生产环境应使用 Redis 或网关限流。
- 当前自动化测试集中在后端核心流程，仍需补充浏览器端到端测试、结构化日志、操作审计和 CI/CD。
- 数据审计已发现部分 CRP 英文名称和多数参考价格/图片尚未填写，并存在少量历史孤立业务记录，需要业务确认后修复。
- 可继续增加客户资料/公司抬头、报价有效期、税率折扣、报价状态流转、邮件发送和分享码撤回记录。

## 浏览器支持

推荐使用最新版 Chrome 或 Edge；Firefox 和 Safari 可完成常规选配，打印/PDF 效果需单独验证。

设备资料以 `tb/` 中的源文件和最终业务确认结果为准。
