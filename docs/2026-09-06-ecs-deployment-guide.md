# 阿里云 ECS 部署与数据库迁移指南

更新日期：2026-09-06  
适用版本：`0f870a5` 及后续版本  
目标系统：Alibaba Cloud Linux 3（OpenAnolis Edition），x86_64

## 1. 当前验证结论

- Docker Engine 与 Docker Compose 插件可正常运行。
- 项目目录为 `/opt/benchshop`，不要误用 `/root/benchshop`。
- Git LFS 3.4.1 可用，`git lfs pull` 与 `git lfs status` 已通过。
- `python:3.12-slim` 与 `nginx:1.27-alpine` 基础镜像已在 ECS 本地就绪。
- API 镜像已成功构建；首次 `pip install` 曾因网络临时失败，重试后成功。
- Web/API 已启动，`/api/v1/health` 返回 HTTP 200。
- `/data/boten.db` 通过 `backend.database_maintenance check`。
- ECS 初始数据库为空。空目录数据会让首页报 `Catalog API returned no usable products`，并中断账户入口初始化；旧账号也不会自动存在。

## 2. 部署边界

- Git 只保存源代码、迁移脚本和文档，不保存服务器私有 `.env`、业务数据库、上传文件或备份。
- API 的 `8001` 端口仅供容器内部访问，不向公网开放。
- 临时验收可开放 `8080`；正式环境应使用域名、HTTPS 和 `80/443`，随后关闭公网 `8080`。
- 数据库迁移必须使用 SQLite 在线备份，不直接复制正在写入的数据库文件。
- 替换 ECS 数据库前必须为 ECS 当前数据库创建安全备份。

## 3. 基础环境检查

```bash
docker version
docker compose version
docker image inspect python:3.12-slim >/dev/null && echo "Python OK"
docker image inspect nginx:1.27-alpine >/dev/null && echo "Nginx OK"

cd /opt/benchshop
git log -1 --oneline
git status --short
git lfs install --local
git lfs pull
git lfs status
```

若 Docker Hub 无法访问，优先使用自有 ACR。临时情况下可从已验证的同架构服务器执行 `docker save`，传输 tar 文件后在 ECS 使用 `docker load`。不要依赖不明来源的第三方镜像站。

## 4. ECS 环境配置

```bash
cd /opt/benchshop
mkdir -p data/uploads/catalog data/backups
test -f deploy/.env || cp deploy/.env.example deploy/.env
chmod 600 deploy/.env
vi deploy/.env
```

临时公网验收示例：

```dotenv
BOTEN_DATA_DIR=./data
BOTEN_CORS_ORIGINS=http://<ECS_PUBLIC_IP>:8080
BOTEN_PDF_FONT_PATH=/app/assets/fonts/harmonyos-sans/HarmonyOS_Sans_SC.ttf
```

`BOTEN_CORS_ORIGINS` 必须与浏览器实际来源完全一致，末尾不要添加 `/`。正式上线时改成最终 HTTPS 域名。

## 5. 构建、启动与检查

```bash
cd /opt/benchshop
docker compose config
docker compose up -d --build
docker compose ps

curl -sS -w '\nHTTP %{http_code}\n' \
  http://127.0.0.1:8080/api/v1/health

docker compose exec api \
  python -m backend.database_maintenance check
```

若构建失败，保留完整日志：

```bash
docker compose --progress plain build api 2>&1 \
  | tee /tmp/benchshop-api-build.log
tail -120 /tmp/benchshop-api-build.log
```

## 6. 空数据库的识别与临时管理员

查看用户数量：

```bash
docker compose exec api python -c \
  "import sqlite3; c=sqlite3.connect('/data/boten.db'); print(c.execute('select count(*) from users').fetchone()[0])"
```

确需验证空数据库时，可以创建临时管理员：

```bash
docker compose exec api python -m backend.create_admin \
  --email <ADMIN_EMAIL> \
  --name <ADMIN_NAME>
```

此操作只创建账号，不会补充设备、配置、工具、附件、分享、询价或报价数据。正式迁入完整业务数据库后，临时账号会随空数据库一起被替换。

## 7. 从 Albert-NAS 迁移完整数据库

### 7.1 在 Albert-NAS 创建一致性快照

```bash
cd /vol1/1000/Docker/benchshop
sudo docker compose exec api \
  python -m backend.database_maintenance backup \
  --output-dir /data/backups \
  --keep 30
ls -lht data/backups | head
```

把最新 `boten-*.db` 下载到受控本机，再通过 SSH/SCP 或阿里云 Workbench 上传为：

```text
/root/albert-boten.db
```

### 7.2 备份并替换 ECS 数据库

```bash
cd /opt/benchshop

docker compose exec api \
  python -m backend.database_maintenance backup \
  --output-dir /data/backups \
  --keep 30

docker compose stop web api
cp /root/albert-boten.db /opt/benchshop/data/boten.db
chmod 600 /opt/benchshop/data/boten.db
file /opt/benchshop/data/boten.db
ls -lh /opt/benchshop/data/boten.db

docker compose up -d
docker compose ps
docker compose exec api \
  python -m backend.database_maintenance check
```

### 7.3 迁移后验收

```bash
curl -sS -w '\nHTTP %{http_code}\n' \
  http://127.0.0.1:8080/api/v1/health
docker compose logs --since=10m api | tail -150
```

浏览器强制刷新后验证：

1. 原管理员、业务员和客户账号可登录。
2. 中英文设备、配置、工具和附件目录可加载。
3. 购物车、分享、询价、报价和 PDF 流程可用。
4. 历史分享、询价、报价和上传图片存在。
5. 管理后台数据库维护状态正常。

数据库不包含 `data/uploads/catalog` 中的上传图片。若 Albert-NAS 存在业务上传文件，还必须单独同步该目录，并在覆盖前备份 ECS 同名目录。

## 8. 安全与上线收尾

1. 安全组仅向管理者固定公网 IP 开放 SSH。
2. 验收期间将 `8080` 的来源限制到测试人员公网 IP。
3. 配置域名、证书和 HTTPS 反向代理。
4. 将 `BOTEN_CORS_ORIGINS` 改为最终 HTTPS 来源。
5. 关闭公网 `8080`，只保留 `80/443`。
6. 保持 `8001` 不开放公网。
7. 设置数据库与上传目录的定时异机备份，并定期执行恢复演练。

