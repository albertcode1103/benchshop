# Python 3.12 依赖验证

当前依赖最低运行环境按 Python 3.12 验证。不要再用旧 Python 3.8 环境安装新依赖。

## 重现本机验证环境

```powershell
python -m venv backend/.venv312
backend/.venv312/Scripts/python -m pip install pip==26.2.1
backend/.venv312/Scripts/python -m pip install -r backend/requirements-dev.txt -c backend/constraints-py312.txt
backend/.venv312/Scripts/python -m pip check
backend/.venv312/Scripts/python -m pytest -q
backend/.venv312/Scripts/python -m pip_audit
```

审计失败返回非零退出码，不应自动忽略漏洞或执行自动修复。审计只覆盖已知 Python 包漏洞，不证明应用、操作系统或容器镜像安全。

## 当前记录

- API Dockerfile 已接入 constraints-py312.txt、固定 pip 26.2.1，并在安装后执行 pip check。约束只限制被 requirements 引入的包，不会额外安装开发依赖。静态契约测试通过；Linux 专属 extras 尚不在 Windows 约束文件内，仍需实际镜像构建验证，不能视为完整跨平台锁文件。
- Python 3.12.14，Windows 隔离环境。
- 首次审计：Pillow 10.4.0、pip 25.0.1、pytest 8.4.2 共 41 条已知漏洞记录。
- 升级为 Pillow 12.3.0、pip 26.2.1、pytest 9.0.3 后，pip check 通过，pip-audit 返回未发现已知漏洞。
- 修复版本完整业务回归：180 项通过、8 个子测试通过（191.75 秒），剩两条 Starlette 测试工具弃用警告。随后增加的图片解析格式限制另做专项验证；不得将自动化通过当成全部视觉和部署验收完成。
- constraints 文件记录当前环境精确版本。已在全新 Windows Python 3.12 虚拟环境 `output/local/venv-rebuild` 实际安装 requirements-dev + constraints（含 pip 26.2.1），安装成功且 pip check 无冲突。该环境就绪、迁移、报价请求边界与 PDF 分页专项共 22 项通过（45.93 秒）。Linux 专属依赖和镜像系统包仍未验证。
- 本机 API 已切换至该 Python 3.12 环境：就绪接口 ready，产品返回 7 台，首页 HTTP 200；Git 与 NAS 切换须等待验收。
