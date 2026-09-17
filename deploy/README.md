# Docker / NAS 部署指南

当前执行约定以 [项目执行规则](../docs/project-execution-rules.md) 为准；以下历史路径示例必须与实际目标核对。

## 2026-09-17 工作台与目录待部署交接

本轮涉及用户端目录备注过滤、报价每次保存留存快照及历史详情接口，以及工作台备注、询价布局和历史预览/应用界面。复用现有表，无本轮新增迁移；先更新兼容 API，再发布前端。8082 连接 NAS 旧 API 时，前端可更新但接口过滤与完整历史功能不会自动生效。功能范围、既有测试证据及发布后检查见 [本轮汇总](../docs/2026-09-17-workbench-update.md)。未记录本轮 NAS 部署完成，发布前仍需确认完整候选差异并遵守下方门禁。

## 2026-09-14 分享与 PDF 待部署交接

本批由用户单独部署，当前未记录部署或 NAS 验收完成。涉及 Web 备注行与导出入口、API 分享列表 `note` 响应扩展，以及三类 PDF 的备注模块和双行时间页脚；无本批新增迁移或依赖。仅更新前端不能启用 NAS 新 PDF 排版。文件范围、兼容行为、测试证据和部署后检查见 [分享与 PDF 更新记录](../docs/2026-09-14-share-pdf-update.md)。实际发布仍须比较目标基线，确认是否包含其他尚未发布的变化。

## 2026-09-13 正式数据与发布门禁（优先执行）

本机运行状态更新：前端代理已切换为默认 NAS 上游，命令 `python -m deploy.local_dev_server`，本机入口 `http://127.0.0.1:8082`（仅回环监听）；旧 8081 为显式 isolated 模式。页面注入 NAS 正式数据可写提示，API 请求无自动回退或重试。此修改仅本机部署工具，不需更新 NAS API 或数据库；以下“尚待配置”是原则制定时历史描述。

- NAS 为正式数据源。本机前端默认架构为连接 NAS API，允许账号权限内的真实保存/删除/上传/发送；此代理模式尚待配置，不代表当前 8081 已连接 NAS。
- 普通发布只更新代码和静态资源，**不再同步或覆盖本机产品、账号、数据库及上传目录**。API/数据库调试用隔离副本，正式数据只在 NAS 维护。
- 每次发布先核对实际部署基线与目标版本，分别报告 API 和数据库是否变化。检查接口/模型/权限/后端行为及依赖、schema、Alembic、入口升级逻辑；无 Git 以文件哈希核对，无法确认则停止。
- 比较后必须标记构建方式。HTML/CSS/JavaScript、既有静态图片等小型前端修改走快速部署，只使用正常 Docker 缓存并重建 `web`；单一 API 源码修改且无依赖、镜像定义或结构变化时只重建 `api`。不得把 `--no-cache` 当作每次部署的固定参数。
- 增量清单必须以 Git 差异为起点并补齐引用和构建依赖，不能只手工挑选页面上最明显的文件。前端至少检查 HTML 引用的 CSS/JavaScript、CSS 引用的图片/字体和运行时模块；范围不确定时扫描全部 Git 跟踪的 Web 运行文件。部署前比较本机候选与 NAS 源码，部署后比较 NAS 源码与容器文件，三层 SHA-256 一致后才可验收。
- Dockerfile、基础镜像、依赖/约束、构建上下文、入口脚本或 Compose 构建配置改变，或者部署后哈希证明缓存未纳入新文件时，才对受影响服务使用 `--no-cache`。能只重建一个服务时不得全量重建两个服务。
- 有 API 或数据库变更时，必须先提醒用户：变更内容、兼容风险、当前/目标 revision、是否停机、演练结果、备份及回退方案；取得明确确认后才能发布。**API 容器启动会自动迁移，不能先执行 up/build 再提醒。**
- 纯前端仅重建 web；后端/结构变更先兼容旧页面，再发布新页面。破坏性变更单独安排维护，不能以代码回滚代替数据回退。
- 每次 NAS 部署命令结束后必须主动提醒用户检查 API 及相关服务，并给出可直接执行的验证命令。最低验证范围为容器状态、相关服务日志、`/api/v1/ready`、候选文件或接口版本一致性以及受影响页面/流程；API 更新追加关键接口验证，数据库更新追加 revision、完整性、外键和必要业务数据验证。验证证据未返回前只能标记为“部署已执行、待验收”，不能报告部署完成。
- 以下 Git/Compose 示例均受此门禁约束；不能直接复制执行绕过检查。本机数据打包工具及历史专项合并步骤不是普通发版的数据导入方式。
- 这是发布时必须执行的规则与检查清单，尚无自动提醒/CI 门禁程序。本次仅文档更新，不修改服务或正式数据库。

发布前须向用户填写：源/目标代码版本；API 变更及兼容性；数据库当前/目标 revision 与变更；验证结果；备份/回退；维护窗口；待确认事项。发布后记录实际生效版本及未验收内容。

### 构建模式选择

先比较文件清单和 SHA-256，再选择下面的最小充分命令。

纯前端快速部署：

```sh
sudo docker compose build --progress=plain web
sudo docker compose up -d --no-deps --force-recreate web
```

仅后端源码变化且确认无依赖、Dockerfile、入口和数据库结构变化：

```sh
sudo docker compose build --progress=plain api
sudo docker compose up -d --no-deps --force-recreate api
```

前后端均有已确认变化时分别正常构建；API 仍须遵守数据库发布门禁。只有依赖或镜像定义变化、需要从零验证，或部署后文件/API 哈希与候选不一致且确认由缓存造成时，才执行：

```sh
sudo docker compose build --no-cache --progress=plain <受影响服务>
```

无缓存重建后仍须验证，不能将 `--no-cache` 本身视为部署成功证据。

### 每次 NAS 部署后的强制提醒与验证

部署执行者在构建和 `up` 完成后必须主动提醒用户运行与本次影响范围匹配的检查，不能等待用户发现异常。通用最低检查如下：

```sh
sudo docker compose ps
sudo docker compose logs --tail=100 <本次更新的服务>
curl -fsS "http://127.0.0.1:8080/api/v1/ready"
```

纯前端发布还应核对容器内静态文件 SHA-256，并提示用户强制刷新后检查受影响页面和交互；API 发布应验证本次变更涉及的关键接口；数据库发布应只读核对 Alembic revision、`PRAGMA quick_check`、外键及必要业务数据。检查结果必须与候选版本和预期行为一致。任何检查失败均保留为“待验收/发布异常”，先诊断或回退，不宣布完成。

本目录用于将 BOTEN 配置与报价系统部署到支持 Docker Compose 的 NAS 或 Linux 服务器。当前部署由两个容器组成：

- `web`：Nginx，提供用户页面、管理后台和同域 `/api/` 反向代理；默认映射宿主机 `8080` 端口。
- `api`：FastAPI、SQLite、图片上传和 PDF 生成服务；仅在 Docker 内部网络暴露 `8001`，不会直接映射到宿主机。

业务数据不在镜像内：数据库和后台上传的图片均存放在持久化的 `data/` 目录。升级或重建容器不会删除这些数据。

## 历史开发阶段专项同步要求（已废止为默认流程）

本节保留 2026-09-12 专项合并依据；2026-09-13 起不得据此常规覆盖 NAS。另行数据导入必须重新取得明确授权和策略确认。

每次发布必须同时核对代码、静态资源、目录数据和上传图片；仅 Git 更新或容器重建不代表数据已同步。

| 内容 | 长期保存与同步方式 |
| --- | --- |
| Logo、字体、页面使用的产品静态图 | 纳入 Git/Git LFS；目标机拉取 LFS 实体文件，重建 web 和 api |
| PSD、Excel、原图压缩包等设计源资料 | 独立备份，不作为网站发布资源；不因扩展名是 PNG 就自动把原图目录全部发布 |
| 设备、颜色、配置类别、工具、附件、映射、价格及图片引用 | 以本机为准新增或覆盖已确认对应记录，NAS 独有项保留；不是 Git 文件，不能依靠拉代码更新 |
| 后台上传的图片 | 随目录数据同步至 data/uploads/catalog，保留相对路径并核对文件哈希；不得只复制数据库 |
| 用户账号 | 本机新增或覆盖已确认同一账号的资料、凭据哈希、角色与状态；NAS 独有账号保留，不复制会话令牌，凭据/权限变化须失效旧会话 |
| 购物车、分享、询价、报价及历史快照等业务数据 | NAS 原数据及关联保留，不使用本机内容覆盖或顺带导入本机测试记录 |

2026-09-12 最新确认：**本机产品信息和用户账号新增或覆盖同一记录，NAS 独有记录保留；禁止直接替换 NAS 全库。** 本次仅更新规则，不表示已有相应同步工具或已经完成同步，也不进行双向 SQLite 文件同步。
实际执行须先确认目标主机和运行中的数据卷，并分别备份本机与 NAS 数据库及图片。在隔离副本比较迁移版本、结构、记录与图片引用，输出新增、本机覆盖、相同、NAS 独有和待确认冲突清单。已确认同一产品/账号的字段差异按本机覆盖；身份或 ID 对应不明确、唯一编号碰撞、跨目录归属及图片路径冲突须先解决，不能自动合并为同一实体。源库引用的图片缺失时必须中止，不能发布断链数据。
正式应用前再次比较 NAS 变化并验证幂等、事务、外键、图片完整性和失败回退；保留 NAS 独有记录，不以本机缺失为删除理由。最后验证引用、数量、数据库完整性及页面/PDF。详细约束以 [项目执行规则](../docs/project-execution-rules.md#3-nas-数据迁移与兼容性合并) 为准。
NAS 与 ECS 必须分别有目标配置、备份和同步结果，不得把服务器私有 .env 或数据库放入 Git。
任何上传或验证失败均不得报告发布完成；远端独有及历史引用图片不自动删除。同路径异内容图片不得覆盖旧实体，须完成路径映射和引用验证。恢复工具仅用于已授权回退或应用已核验的合并结果，不能以恢复本机源库绕过合并；禁止直接复制运行中的 SQLite 文件覆盖。

## 部署前准备

### 可复用的本机发布预检与打包

在本机项目根目录执行（不访问或修改 NAS/ECS）：

```powershell
.\backend\.venv312\Scripts\python.exe -m deploy.release_bundle --check --database backend/boten.db --uploads uploads/catalog
```

预检没有阻断项、相关代码与图片经用户授权提交，且暂停源端编辑后，使用一个不存在的私有输出目录生成发布包：

```powershell
.\backend\.venv312\Scripts\python.exe -m deploy.release_bundle --database backend/boten.db --uploads uploads/catalog --output tmp/release-NEW-ID
```

输出 `release.tar.gz`、`manifest.json` 和数据库快照。归档内 `code/` 为代码与静态资源，`data/boten.db` 为在线备份，`data/uploads/catalog/` 为上传目录；数据库和上传图片不得复制到 Web 静态根目录。包含账号等私有信息，发布包不能进入 Git、公共共享链接或公开站点。

工作区未清理、引用图片未跟踪/缺失、LFS 指针、非法路径、数据库损坏、源文件在归档中变化都会阻断。输出目录已存在时拒绝覆盖。失败输出保留供检查，重试使用新目录，不把失败包用于发布。

该命令**不会**传输文件、替换远端数据库或重建容器。正式传输仍需核验目标与维护窗口、备份远端、校验清单，再按下方恢复流程执行；不自动删除远端独有文件。

### 目标环境准备

1. NAS/Linux 已安装 Docker Engine 与 Docker Compose v2，并可执行 `docker compose version`。
2. 已将项目代码复制或克隆到服务器，例如群晖：`/volume1/docker/benchshop`。
3. 将当前运行中的业务数据迁移到部署目录：

   ```text
   data/
   ├── boten.db
   └── uploads/
       └── catalog/
   ```

   `boten.db` 包含设备、配置、账号、分享码和报价单；请务必迁移。若有已上传的目录图片，也必须复制 `uploads/catalog/`。
4. 不要提交或同步本机的 `deploy/.env`；它是服务器私有配置，已被 Git 忽略。

## 首次部署

在项目根目录执行。下面示例使用 NAS 默认的相对数据目录 `./data`：

   ```sh
cd /volume1/docker/benchshop
cp deploy/.env.example deploy/.env
```

编辑 `deploy/.env`：

```ini
# 数据卷位置；可使用绝对路径，例如 /vol1/docker/Benchshop/data
BOTEN_DATA_DIR=./data

# LAN 阶段填写浏览器实际访问的 NAS 来源；公网部署时替换为正式 HTTPS 来源。
BOTEN_CORS_ORIGINS=http://192.168.31.69:8080

# 默认使用随镜像内嵌的 HarmonyOS Sans SC；仅在需要替换 PDF 字体时修改。
BOTEN_PDF_FONT_PATH=/app/assets/fonts/harmonyos-sans/HarmonyOS_Sans_SC.ttf
```

Compose 明确设置 `BOTEN_ENV=production`。必须替换示例域名；空值、`null`、通配符、含路径或凭据的地址会拒绝启动。来源不带末尾斜杠。NAS IP 改变时同步更新此配置。本机直接运行且不设置生产环境时保留开发规则。

启动统一执行 Alembic 升级，已有数据库升级前自动在线备份至数据目录中的 `migration-backups/`；就绪检查验证迁移版本和目录表可读。无迁移版本的历史库会拒绝自动升级，需要先确认基线，不能直接 stamp 跳过。请将备份目录纳入 NAS 备份策略。

确认 `data/boten.db` 已就位后启动：

```sh
docker compose up -d --build
docker compose ps
```

预期状态为 `api` 显示 `healthy`，`web` 为 `running`。首次启动会自动执行 Alembic 数据库迁移。

LAN 访问地址：

```text
http://<NAS-LAN-IP>:8080/
http://<NAS-LAN-IP>:8080/admin/
http://<NAS-LAN-IP>:8080/api/v1/health
```

## 从 Git 更新（BOTEN-NAS 推荐流程）

BOTEN-NAS 已验证可通过 IPv4 访问 GitHub，但 Linux 不支持 Windows 的
`schannel` SSL 后端。首次配置或出现 SSL 错误时，只需在项目目录设置一次：

```sh
cd /volume1/docker/benchshop
git config --local http.sslBackend openssl
git lfs install --local
```

每次从本机确认并推送到 GitHub 后，按以下顺序更新。数据库不在 Git 中，更新前会先生成备份：

```sh
cd /volume1/docker/benchshop
git fetch --ipv4 origin
git merge --ff-only origin/main
git lfs pull
sudo docker compose exec api python -m backend.database_maintenance backup --output-dir /data/backups --keep 30
sudo docker compose build --progress=plain web api
sudo docker compose up -d --force-recreate
sudo docker compose ps
```

确认 `api` 为 `healthy`、`web` 为 `Up` 后再访问 `http://<NAS-IP>:8080/`。
若更新前服务尚未运行，先执行备份命令会失败，此时可跳过该行，但应确认
`data/boten.db` 已有独立备份。若 `git fetch` 报 `schannel`，重新执行上面的
`git config`；若提示 IPv6 连接失败，保留 `--ipv4`。

### 回滚到上一版本

不要使用 `git reset --hard` 覆盖未确认的数据。先查看可用提交，再按指定提交构建：

```sh
git log --oneline -10
git checkout <已确认的提交或标签>
sudo docker compose build --progress=plain web api
sudo docker compose up -d --force-recreate
```

回滚完成后，下一次正常更新前执行 `git switch main`。

## 从 Git 更新项目代码（通用说明）

更新前先备份数据。拉取或复制新代码后，在项目根目录执行：

```sh
sudo docker compose exec api python -m backend.database_maintenance backup --output-dir /data/backups --keep 30
sudo docker compose build --progress=plain web api
sudo docker compose up -d --force-recreate
sudo docker compose ps
```

上例是前后端均确认变化时的正常缓存构建。不要例行追加 `--no-cache`；先按“构建模式选择”判断，必要时仅对受影响服务无缓存重建。

如更新了网页样式或脚本，请在浏览器按 `Ctrl+F5`（macOS 为 `Cmd+Shift+R`）刷新缓存。

如果在 FNOS 中不确定 Compose 项目路径，可从正在运行的容器取得路径：

```sh
PROJECT_DIR=$(sudo docker inspect -f '{{ index .Config.Labels "com.docker.compose.project.working_dir" }}' benchshop-web-1)
cd "$PROJECT_DIR"
sudo docker compose up -d --build
```

## 本机产品与账号同步至 NAS（开发阶段）

旧“恢复本机全库备份到 NAS”的发布流程已废止，不能用于当前规则。Git 更新代码、镜像重建、目录/账号同步分别验收，不能互相替代。

1. 核实两端实际数据库和上传目录，取得一致性备份；仅在隔离副本处理结构兼容和记录映射。
2. 生成新增、覆盖、相同、NAS 独有及冲突清单。同一产品/账号以本机为准；NAS 独有数据与业务历史全部保留。身份对应、引用或图片冲突未解决时停止应用。
3. 在隔离副本演练合并，检查用户唯一性、角色、密码哈希兼容性、目录层级、价格、关联、图片、版本、幂等及失败回退。不得在日志中输出密码哈希或令牌。
4. 正式发布需另行授权，并在维护窗口重新核对 NAS 变化、冻结有关写入后应用经验证的合并结果。合并执行工具尚须确认支持本规则；不得直接调用源库恢复命令冒充同步。
5. 验收设备/配置/工具/附件、两种语言目录、账号登录与权限、NAS 独有记录、历史分享/询价/报价及 PDF 图片完整性，确认未重写旧业务数据后才可报告完成。

## 数据备份、检查与恢复

常用维护命令：

```sh
# 查看实时日志
docker compose logs -f api
docker compose logs -f web

# 检查 SQLite 完整性
docker compose exec api python -m backend.database_maintenance check

# 创建并只保留最近 30 份备份
docker compose exec api python -m backend.database_maintenance backup --output-dir /data/backups --keep 30

# 清理超过 90 天的分享码
docker compose exec api python -m backend.cleanup
```

建议在 NAS 任务计划中每天运行最后两条命令，并把整个 `data/` 目录复制至另一块磁盘或异地存储。备份文件只存在同一块磁盘不等于可恢复备份。

恢复数据库时，先停止服务，再按程序的确认式恢复命令执行：

```sh
docker compose down
docker compose run --rm --entrypoint python api -m backend.database_maintenance restore /data/backups/<备份文件名> --confirm RESTORE
docker compose up -d
```

恢复前，维护脚本会额外保存当前数据库；恢复后使用 `database_maintenance check` 验证。

## 常见问题

### 页面显示“无法加载设备目录”

依次检查：

```sh
docker compose ps
curl -i http://127.0.0.1:8080/api/v1/health
docker compose logs --tail=100 api
```

API 不需要单独开放 `8001`。用户页面应通过同域的 `http://<NAS-IP>:8080/api/` 访问 API。

### Nginx 显示 403 Forbidden

通常是通过 SMB 复制的静态文件权限过严。当前 `Dockerfile.web` 已在构建时修正读取权限。执行：

```sh
docker compose build --no-cache web
docker compose up -d --force-recreate web
```

### 镜像拉取超时或 401

先确认 NAS 能访问 Docker Hub，再检查 Docker 镜像镜像站或 HTTP/HTTPS 代理配置。不要把失效的镜像地址写入项目的 Dockerfile 或 Compose 文件。镜像已成功拉取后，日常启动不依赖代理；只有构建和更新镜像时需要。

## 公网与 HTTPS（准备完成后再启用）

当前 Compose 配置用于 LAN 验证，端口映射是 `8080:80`。在 NAS 已配置域名和 HTTPS 反向代理后：

1. 将 `docker-compose.yml` 的 `web.ports` 改为 `127.0.0.1:8080:80`。
2. 将 `BOTEN_CORS_ORIGINS` 改为唯一的正式来源，例如 `https://benchshop.example.com`。
3. NAS 反向代理将正式域名转发到 `http://127.0.0.1:8080`。
4. 路由器/安全组只对外开放 HTTPS `443`（需要 HTTP 跳转时再开放 `80`）；不要对外开放 `8001` 或 NAS 管理端口。
5. 验证登录、分享码、报价、PDF、图片上传和手机端页面均正常后再正式开放。

Nginx 已处理 `/api/` 的内部代理，因此外部反向代理不要额外创建 `/api` 规则；只需转发整个站点，并保留 `Host` 与 `X-Forwarded-*` 头。

## 安全边界与限制

- 本部署适合单台服务器和单个 SQLite 写入实例；不要让多台 API 容器共享并写入同一个 `boten.db`。
- 账号、数据库、上传图片和 `deploy/.env` 不提交 Git。生产服务器上应定期更新管理员密码并限制 SSH 来源。
- 认证和分享接口已有基础限流；多实例或高并发生产环境应改用 Redis/网关级限流。
- 后续若访问量或协作人数显著增长，应先迁移到托管 MySQL/PostgreSQL，再扩展为多 API 实例。
