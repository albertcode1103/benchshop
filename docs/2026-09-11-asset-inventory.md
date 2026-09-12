# 2026-09-11 本机静态资源盘点

基线提交：09f0131。仅扫描本机 E:/Project/CC-Project/benchshop；数据库以 SQLite mode=ro 打开，不移动、删除资源，不改数据库、不访问 NAS、不提交 Git。

## 结论

### 后续审核：已加入暂存区（尚未提交）

用户授权“审核跟踪”后，对 65 张数据库引用的 tb/configpic 图片逐项执行 Pillow 文件验证、路径范围检查及 Git LFS 属性检查，全部通过。总大小 10,115,966 字节（约 9.65 MiB）。仅这 65 张图片加入 Git 暂存区，未移动或改名；其他 16 张配置图及原始表格保持未跟踪。

逐项核对暂存区 LFS 指针的 SHA-256/size 与工作区实体一致，且本地 .git/lfs/objects 中 65 个对象存在、哈希匹配。此验证不代表远程 LFS 已上传；本次未提交、推送、部署或修改数据库。下列“未跟踪”统计为审核前盘点基线。后续仍需提交及远程 LFS/新克隆验证。

1. 当前本机可用不代表 Git 克隆后完整：数据库识别到的 93 个图片引用全部存在，其中 65 张 tb/configpic 图片尚未跟踪。应优先纳入发布资源管理，暂不改路径。
2. 三份字体及 tb/site/BOTEN.png、tb/site/LOGO.png 已跟踪；扫描资源未发现未还原的 Git LFS 指针。
3. 对 93 个引用及三份字体、两个 Logo 共 98 个 URL 执行本机 8081 HTTP HEAD 检查，全部 200。此结果不等同于图片解码、字体实际渲染或 NAS 验收。
4. 数据库完整性、外键检查通过，迁移为 20260911_0030。

## 文件库存

| 目录 | 图片/字体文件数 | 字节数 | 说明 |
| --- | ---: | ---: | --- |
| assets | 7 | 21,274,819 | 4 个 SVG、3 份 TTF；许可证另计 |
| tb | 133 | 112,048,637 | 混合产品发布图片与素材 |
| uploads/catalog | 0 | 0 | 当前默认上传目录无本次扫描类型文件；不能因此取消持久化 |

扫描扩展名：png/jpg/jpeg/webp/svg/ico/ttf/woff/woff2/otf。不包含原始 Excel、设计稿、备份、临时目录。

tb/configpic 中有 81 张 PNG，65 张被数据库扫描识别引用；其余 16 张只是“数据库未识别引用”，不能直接认定无用，仍需核对源码、动态路径及外部用途。

## 字体、Logo 与部署链路

- assets/fonts/harmonyos-sans/HarmonyOS_Sans.ttf：342,076 字节。
- assets/fonts/harmonyos-sans/HarmonyOS_Sans_Italic.ttf：308,632 字节。
- assets/fonts/harmonyos-sans/HarmonyOS_Sans_SC.ttf：20,617,156 字节。
- 三份字体均由 css/main.css 引用，PDF 使用随项目提供的 SC 字体；LICENSE.txt 已跟踪，具体分发义务仍需核对。
- .gitattributes 已覆盖 PNG/JPG/TTF 的 LFS；未来使用 WEBP/WOFF2/OTF 时需另行确认管理策略。
- Web Dockerfile 复制 assets、tb；API Dockerfile 复制 assets/fonts 和 tb/site/BOTEN.png。仅从 Git 构建会漏掉当前未跟踪图片；从整个工作目录构建可能正常，造成环境差异。
- uploads 被 Git 与 Docker 构建排除，需要与数据库一起做持久化备份。现有发布工具会携带上传目录，但数据库引用的未跟踪图片会阻止发布。
- 本机工作区的 Web Dockerfile 已明确保留 `assets/fonts/harmonyos-sans/LICENSE.txt`；API 镜像本来就复制整个字体目录。该修复尚未提交或构建镜像，Linux 镜像内的实际文件验收仍待后续授权。

## 数据库未引用的 16 张配置图片

本轮以数据库 JSON 引用和源码中的完整相对路径分别扫描。16 张图片均不在数据库引用中；源码仅保留同编号的旧 `js/data.js` 产品名称，并引用另一套 `tb/tbconfig/HEUI/*.jpg` 路径，未直接引用这些 PNG。因此它们统一标记为 **用途待确认**，不移动、不删除、不纳入本次提交。

- 命名款：`BTE-7021`、`BTE-7022`、`BTE-7024`、`BTE-7030`、`BTE-7048`、`BTE-7058`、`BTE-7069`、`BTE-7078` 的原图 PNG。
- 原始导出款：`file_000000001af8820985a75c2fe694d0fc`、`file_000000002dd4822fa4c653acf7691e6f`、`file_000000003d948206b73fe1ca55622f5f`、`file_0000000062088209af2d2adfaad5ba16`、`file_00000000cd0481f8a1b8debe132203f1`、`file_00000000dcb481f59b638584ff86e916`、`file_00000000eb0c820c98fa4ab57065de22`、`file_00000000fddc8209b664b9e8d9d836ef` 的 PNG。

## 完全相同的图片（SHA-256 分组）

以下各组内容相同，但用途和引用可能不同，不删除、不自动改写历史快照：

- tb/CR1016/1-main/CR1016红色.png ↔ tb/tbpic/CR1016/CR1016红色.png
- tb/CR1016/1-main/CR1016绿色.png ↔ tb/tbpic/CR1016/CR1016绿色.png
- tb/tbdetail/BT618/BT618.png ↔ tb/tbpic/BT618/BT618.png
- tb/tbdetail/CR318C/CR318C.png ↔ tb/tbpic/CR318C/CR318C.png
- tb/tbdetail/CR318H/CR318H.png ↔ tb/tbpic/CR318H/CR318H.png
- tb/tbdetail/CR318S/CR318S.png ↔ tb/tbpic/CR318S/CR318S.png
- tb/tbdetail/CR518/CR518.png ↔ tb/tbpic/CR518/CR518.png

## 后续整理顺序（未执行）

- [x] 审核 65 张已引用配置图并加入 Git LFS 暂存区，保持原路径；远程 LFS 与新克隆实体校验仍待推送授权。
- [x] 为其余 16 张配置图建立用途待确认记录，不以未被数据库引用作为删除依据。
- [x] 核对随库许可文本，并使 Web 发布镜像保留必要声明；实际镜像检查仍待后续发布验收。
- [ ] 扩充发布预检：页面/CSS 动态资源、字体可读性、大小写敏感路径、图片解码及清单哈希。
- [ ] 在隔离的新克隆与容器中验证主页、后台、中英文 PDF，再验证 NAS；不直接操作运行中数据。

## 盘点边界

数据库扫描复用 deploy/release_bundle.py 的递归 JSON 引用识别，覆盖识别到的历史快照，但仅识别该工具支持的路径前缀与图片扩展名。尚未穷尽外部 URL、所有源码字符串、动态拼接路径及大小写敏感文件系统验证。本报告不是全站资源零遗漏证明。
