# BOTEN 后端服务

后端基于 FastAPI 和 SQLite，为用户选配页与管理后台提供产品目录、认证、配置保存、分享码、报价和管理接口。默认监听 `127.0.0.1:8001`，静态网站使用 `8080` 端口。

## 快速启动

从项目根目录执行。

首次安装：

```powershell
py -3.8 -m venv backend\.venv
.\backend\.venv\Scripts\python.exe -m pip install -r .\backend\requirements-dev.txt
```

如果 Windows 系统代理可用于浏览器，但 pip 报 `ProxyError`，可把代理明确写成 HTTP 代理协议（端口按本机软件调整）：

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r .\backend\requirements-dev.txt --proxy http://127.0.0.1:10808
```

日常启动 API：

```powershell
.\backend\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8001
```

另开窗口启动前端：

```powershell
py -m http.server 8080
```

访问：

- API 文档：`http://127.0.0.1:8001/docs`
- 健康检查：`http://127.0.0.1:8001/api/v1/health`
- 用户端：`http://127.0.0.1:8080/`
- 后台：`http://127.0.0.1:8080/admin/`

## 数据库与初始化

数据库默认路径为 `backend/boten.db`。API 启动时会创建缺失的表和兼容字段，但不会自动导入产品目录。

全新空数据库首次导入：

```powershell
.\backend\.venv\Scripts\python.exe -m backend.seed
```

`backend.seed` 从 `js/data.js` 导入基础产品、颜色、分类、公共配置和机型映射。它会更新相同编号的数据，因此已经在管理后台维护过目录后不要反复执行。导入或升级前先备份数据库。

### Alembic 迁移

全新数据库应先执行迁移，再导入初始目录：

```powershell
.\backend\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
.\backend\.venv\Scripts\python.exe -m backend.seed
```

现有 `boten.db` 已具备当前字段但尚无 Alembic 版本记录时，先备份，再标记当前基线：

```powershell
.\backend\.venv\Scripts\python.exe -m backend.database_maintenance backup --keep 30
.\backend\.venv\Scripts\python.exe -m alembic -c alembic.ini stamp 20260831_0002
```

以后更新代码后统一执行：

```powershell
.\backend\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
```

### 备份、恢复和数据审计

```powershell
# 检查当前数据库
.\backend\.venv\Scripts\python.exe -m backend.database_maintenance check

# 创建经过 quick_check 校验的在线备份
.\backend\.venv\Scripts\python.exe -m backend.database_maintenance backup --keep 30

# 停止 API 后恢复；恢复前还会自动保存当前数据库
.\backend\.venv\Scripts\python.exe -m backend.database_maintenance restore .\backups\boten-日期.db --confirm RESTORE

# 检查翻译、价格、图片、映射和外键
.\backend\.venv\Scripts\python.exe -m backend.audit_catalog
.\backend\.venv\Scripts\python.exe -m backend.audit_catalog --json
```

创建首个管理员：

```powershell
.\backend\.venv\Scripts\python.exe -m backend.create_admin --email admin@example.com --name Administrator
```

关闭过期分享码：

```powershell
.\backend\.venv\Scripts\python.exe -m backend.cleanup
```

生产环境建议每天定时执行清理命令。

## 环境配置

| 环境变量 | 作用 | 默认值 |
| --- | --- | --- |
| `BOTEN_DATABASE_PATH` | SQLite 文件绝对路径 | `backend/boten.db` |
| `BOTEN_UPLOAD_DIR` | 后台上传的目录图片保存路径 | `uploads/catalog` |
| `BOTEN_CORS_ORIGINS` | 允许访问 API 的来源，英文逗号分隔 | 本地 8080 和 `null` |
| `BOTEN_PDF_FONT_PATH` | 可选的中文 TrueType/OpenType 字体文件路径 | 自动查找系统中文字体 |

本地未设置 CORS 环境变量时，也允许 `localhost/127.0.0.1` 的开发端口。生产环境必须显式设置网站域名，并移除 `null` 来源。

前端 API 地址在 `js/runtime-config.js` 中配置。前后端同域且由反向代理转发 `/api/` 时，将 `window.BOTEN_API_BASE` 设为空字符串；分离部署时填写完整 HTTPS API 来源。

## 权限与会话

- 游客会话有效 1 天，只能浏览，不能保存或分享。
- 注册用户会话有效 30 天，可保存、删除和分享自己的配置。
- 业务员可查看分享记录、客户联系方式、参考价，并管理自己的报价。
- 管理员可管理设备、配置、账号、分享记录和所有报价。
- 密码使用 PBKDF2-SHA256（310,000 次迭代）保存，数据库不存明文密码。
- 登录失败按 IP 和账号组合限制为 15 分钟 5 次；分享码查询限制为每分钟 30 次。

当前限流保存在单个 API 进程内。多进程或多服务器部署应改用 Redis 或在反向代理/API 网关层增加共享限流。

除注册、登录和游客会话外，请发送：

```http
Authorization: Bearer <token>
```

## API 概览

公共产品目录：

- `GET /api/v1/health`
- `GET /api/v1/products?lang=zh|en`
- `GET /api/v1/products/{product_id}?lang=zh|en`

认证：

- `POST /api/v1/auth/guest`
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `POST /api/v1/auth/logout`

用户配置：

- `GET /api/v1/configs?lang=zh|en`
- `POST /api/v1/configs`
- `PUT /api/v1/configs/{config_id}`（版本校验后覆盖保存）
- `POST /api/v1/config-shares`（1–20 项合并分享）
- `POST /api/v1/config-exports/pdf`（1–20 项合并 PDF）
- `POST /api/v1/configs/batch-archive`（批量软删除）
- `POST /api/v1/configs/pdf`（当前配置直接下载）
- `GET /api/v1/configs/{config_id}`
- `GET /api/v1/configs/{config_id}/pdf`
- `DELETE /api/v1/configs/{config_id}`
- `POST /api/v1/configs/{config_id}/share`

统一购物车（设备、维修工具与设备附件）：

- `POST /api/v1/cart/share`
- `POST /api/v1/cart/export/pdf`
- `POST /api/v1/cart/batch-archive`
- 单次最多包含 20 项设备配置、100 个购物车项目；工具和附件数量作为条目数量字段处理，不展开为重复项目。

业务员与管理员：

- `GET /api/v1/staff/shares`（分页、关键词、状态、设备和日期筛选）
- `GET /api/v1/staff/shares/{6位分享码}/preview`（不增加客户查看次数）
- `GET /api/v1/shares/{6位分享码}`
- `GET /api/v1/shares/{6位分享码}/pdf`
- `GET /api/v1/staff/reference-prices`
- `GET /api/v1/quotes`
- `POST /api/v1/quotes`
- `GET /api/v1/quotes/{quote_id}`
- `GET /api/v1/quotes/{quote_id}/pdf`
- `DELETE /api/v1/quotes/{quote_id}`

管理员：

- `GET|POST /api/v1/admin/products`
- `GET|PATCH /api/v1/admin/products/{product_id}`
- `PUT /api/v1/admin/products/{product_id}/colors`
- `PUT /api/v1/admin/products/{product_id}/options`
- `PATCH /api/v1/admin/products/{product_id}/options/{option_id}`
- `GET /api/v1/admin/config-catalog`
- `POST /api/v1/admin/media`（PNG/JPEG/WebP，最大 8 MB）
- `GET /api/v1/media/{filename}`（公开读取已上传目录图片）
- `POST|PATCH /api/v1/admin/config-catalog/categories[/{category_id}]`
- `POST|PATCH /api/v1/admin/config-catalog/options[/{option_id}]`
- `GET /api/v1/admin/config-catalog/categories/{category_id}/references`
- `DELETE /api/v1/admin/config-catalog/categories/{category_id}`
- `GET /api/v1/admin/config-catalog/options/{option_id}/references`
- `DELETE /api/v1/admin/config-catalog/options/{option_id}`
- `GET|POST /api/v1/admin/users`
- `PATCH /api/v1/admin/users/{user_id}`
- `PATCH /api/v1/admin/users/{user_id}/status`
- `GET /api/v1/admin/shares`
- `PATCH /api/v1/admin/shares/{share_id}/status`
- `DELETE /api/v1/admin/shares/{share_id}`
- `GET /api/v1/admin/audit-logs`

完整请求模型和响应结构以运行中的 `/docs` 为准。

## 主要模块

```text
backend/
├── main.py                       应用入口、CORS、公共产品接口
├── database.py                   SQLite 建表和兼容字段初始化
├── migrations/                  Alembic 数据库版本迁移
├── database_maintenance.py      校验、备份和确认式恢复
├── audit_catalog.py             目录数据质量检查
├── audit_repository.py          管理员/业务员操作审计
├── media_routes.py              管理员图片上传与公开图片读取
├── pdf_service.py               跨平台中文配置单和报价单
├── repository.py                 用户端产品目录查询与语言选择
├── auth_routes.py                注册、登录、会话和角色依赖
├── config_routes.py              保存配置、分享、报价和 PDF
├── admin_routes.py               管理员接口
├── *_repository.py               各业务领域的数据访问
├── seed.py                       从旧静态目录进行首次导入
├── create_admin.py               管理员初始化命令
├── cleanup.py                    过期分享码清理
└── boten.db                      当前本地数据库
```

## 自动化测试

测试使用临时数据库，不会修改 `backend/boten.db`：

```powershell
.\backend\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

当前 65 项测试覆盖目录初始化、迁移、登录会话、账号生命周期、客户价格字段过滤、保存配置覆盖、多设备及混合商品分享、仅工具/附件流程、冻结快照、原子批量软删除、分享模糊搜索、目录排序、历史颜色名称刷新、角色边界、V2 目录 CRUD、设备基本配置和价格方案、新旧报价兼容、客户无价 PDF 与后台价格 PDF、操作审计、图片接口、安全删除、双语无障碍名称和数据库备份恢复。生产服务器若不运行测试，可只安装 `requirements.txt`。

## PDF 下载

配置清单、合并分享配置和报价单统一由 ReportLab 在 API 进程内生成附件，不依赖浏览器打印或 Microsoft Edge。合并配置 PDF 每台设备独立编号，并在每页显示客户资料、导出时间、品牌页脚和总页数。服务优先使用项目内嵌 HarmonyOS Sans SC，并可通过 `BOTEN_PDF_FONT_PATH` 覆盖；配置较多时表格会自动分页并重复表头。

## 生产部署注意事项

- 不要直接暴露 Uvicorn 开发进程；使用 Nginx/Caddy、HTTPS 和服务管理器。
- SQLite、`uploads/` 和 `tb/` 图片需要独立备份并定期验证恢复。
- 同一 SQLite 文件不要由多台服务器共享挂载写入。
- 设置严格的 CORS、请求体大小、访问日志、错误监控和网关限流。
- 数据结构变更必须通过 `backend/migrations/` 提交，并在升级前创建数据库备份。
- 配置目录运行时不再回退到 `js/data.js`。API 或数据库异常应先修复服务，不能以静态旧数据掩盖故障。
