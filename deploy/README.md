# Docker / NAS 部署指南

本目录用于将 BOTEN 配置与报价系统部署到支持 Docker Compose 的 NAS 或 Linux 服务器。当前部署由两个容器组成：

- `web`：Nginx，提供用户页面、管理后台和同域 `/api/` 反向代理；默认映射宿主机 `8080` 端口。
- `api`：FastAPI、SQLite、图片上传和 PDF 生成服务；仅在 Docker 内部网络暴露 `8001`，不会直接映射到宿主机。

业务数据不在镜像内：数据库和后台上传的图片均存放在持久化的 `data/` 目录。升级或重建容器不会删除这些数据。

## 部署前准备

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

# LAN 阶段可保留本地地址；公网部署时替换为唯一的正式 HTTPS 域名。
BOTEN_CORS_ORIGINS=http://127.0.0.1:8080,http://localhost:8080

# 可选：若自行挂载了 CJK 字体，可填写容器内路径；默认使用内置回退字体。
BOTEN_PDF_FONT_PATH=/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc
```

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
sudo docker compose build --progress=plain api
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
sudo docker compose build --progress=plain api
sudo docker compose up -d --force-recreate
```

回滚完成后，下一次正常更新前执行 `git switch main`。

## 从 Git 更新项目代码（通用说明）

更新前先备份数据。拉取或复制新代码后，在项目根目录执行：

```sh
sudo docker compose exec api python -m backend.database_maintenance backup --output-dir /data/backups --keep 30
sudo docker compose build --no-cache
sudo docker compose up -d --force-recreate
sudo docker compose ps
```

如更新了网页样式或脚本，请在浏览器按 `Ctrl+F5`（macOS 为 `Cmd+Shift+R`）刷新缓存。

如果在 FNOS 中不确定 Compose 项目路径，可从正在运行的容器取得路径：

```sh
PROJECT_DIR=$(sudo docker inspect -f '{{ index .Config.Labels "com.docker.compose.project.working_dir" }}' benchshop-web-1)
cd "$PROJECT_DIR"
sudo docker compose up -d --build
```

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
