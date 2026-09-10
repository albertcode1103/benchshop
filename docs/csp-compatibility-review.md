# CSP 兼容评估（2026-09-11）

## 当前结论

目前 Nginx 未配置 CSP。不能直接启用 `script-src 'self'`：现有正常功能包含内联脚本和事件处理，需要先迁移或配置精确 hash。此次评估不修改运行策略，不扩大 API 或媒体来源权限。

## 已核对的依赖

- `admin/index.html` 的内联错误监听脚本负责提示后台加载失败。
- `js/renderer.js`、`js/catalog-marketplace.js` 的图片 `onerror` 切换占位图。
- `admin/admin.js` 的图片 `onerror` 标记缺失图片。
- 购物车、账号及后台通过 `URL.createObjectURL` 提供 PDF 下载，不能将下载链接与远程脚本来源混为一谈。
- 页面脚本及样式主要来自同源；WhatsApp 是外部导航链接，不需要因此开放脚本来源。
- 对 js/admin/account 的静态搜索未发现 eval/new Function；这不是运行时无动态执行的证明。

## 上线前验证

1. 把内联监听迁移至同源 JS，并保持图片失败回退和后台错误提示行为。
2. 清点动态 style、图片预览及实际 API 来源；仅允许必要来源。
3. 先以 Report-Only 在隔离部署进行匿名、管理员、业务员、客户流程验证。
4. 检查图片、上传预览、PDF 下载、分享和报价后，才切换强制策略。

尚未完成浏览器违规收集或 Nginx 实际策略验证；本文件仅证明静态兼容评估。
