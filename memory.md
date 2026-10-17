# Memory - 统一账号识别服务

> 创建时间: 2026-09-22 17:30:00
> 最后修改: 2026-09-28 16:16:58
> 版本: V_1.4
> 适用对象: 本项目所有智能体
> 核心目标: 记录项目核心状态、踩坑经验、可复用流程与规则
> 文档描述: 智能体常记忆，含 [vault] 项目状态 / [rule] 规则 / [skill] 流程 / [eval] 失败案例 / [hooks] 校验手段

## 大纲

1. [vault] 项目当前状态
2. [rule] 需牢记的规则
3. [skill] 可复用流程
4. [eval] 失败案例与教训
5. [hooks] 自动化校验手段

***

## [vault] 项目当前状态

- **管理后台重构已完成**（2026-09-22）：由 Vue 单页应用改为基于 `workdesktop-ai@1.2.0`（2026-09-28 由 1.1.0 升级；UMD，`window.WorkDesktop`）+ Vue 3 + ElementPlus 的**多页架构**，16 个页面（登录 + 租户端 9 + 超管端 6）；已启用 `fashion` 时尚皮肤（主色 #cd3c1d）。
- 页面路由由 [config/urls.py](file:///e:\framework\Unified account identification service\code\unified_auth\config\urls.py) 的 `ADMIN_PANEL_ROUTES` 统一注册，模板在 `apps/admin_panel/templates/admin_panel/`，公共层在 `apps/admin_panel/static/admin_panel/js/common.js`，第三方库全部本地化于 `static/admin_panel/vendor/`。
- 旧单页文件（index.html / admin.js / admin.css，含 `code/unified_auth/static/` 下 collectstatic 产物）已删除；`/admin-panel/` 根路径 302 到 dashboard。
- 验证结论：16 页面 HTTP 200；smoke 脚本 21 项接口全通（含超管 impersonate 进入/退出链路）；pytest **289 passed / 5 skipped**；`manage.py check` 通过。
- 测试服务器约定端口：**8100**；测试用 Python 环境为 `C:\Program Files\python`（Python 3.8，含 pytest/Django），运行服务器可用 `C:\Python313`。

## [rule] 需牢记的规则

- **超管认证不走 User 模型**：超管账号在环境变量 `SUPERADMIN_ACCOUNTS`（JSON 数组）中配置，登录走 `POST /api/v1/admin/login`，匹配成功后 token payload 带 `is_superadmin: True`；`middlewares/admin_auth.py` 对 `/api/v1/superadmin/` 前缀仅认 payload 中的该标志，否则 403（code=-10201）。自建 is_superuser 数据库用户**不能**访问超管 API。
- **租户上下文**：超管 token 无租户上下文，直接调 `/api/v1/admin/*` 租户接口会 404（code=-10602 "租户不存在"），属预期；需先 `POST /api/v1/superadmin/impersonate/<tenant_id>` 换租户 token。
- 统一响应协议 `{code, message, data}`：业务失败也返回 HTTP 200（code≠0）；token 失效码 -10001/-10002；权限不足 -10201。
- `Tenant.status` 是布尔；`User.status` 是 0/1，前端 Switch 取值时注意区分。
- 报表接口 `POST /api/v1/superadmin/report/tenants|apps` 为 POST 且从 `request.data` 取搜索参数；common.js 拦截器负责把 `param` 对象平铺进 query（GET）或 body（POST）。
- 审计导出 `GET /api/v1/superadmin/audit-logs/export` 仅支持 action/actor/date_from/date_to，**不支持 tenant_id**。

## [skill] 可复用流程

- **workdesktop-ai 页面范式**（标杆：`users.html`）：base.html 继承布局 → WdSearchPanel（`head-refresh-datagrid` 自动驱动同组表格）→ WdDataGrid（`api/rowKey/tools/rowActions`，POST 接口必须显式 `api-method="post"`）→ drawer + WdDataForm（`mode/api/submitApi/submitKeys`，submitKeys 为逗号字符串）→ 状态切换用 WdSwitch（切换即请求，失败自动回滚）。全局 componentDefault 已设 `apiMethod:'get', border:true, stripe:true`。
- **新页面开发顺序**：读 urls.py 确认路由 → 读 views.py 确认接口参数与返回字段 → 按范式写页面 → 起 8100 服务器验证 HTTP 200 + smoke 接口联通。
- **列表数据兼容**：common.js 拦截器对 keys=['users','apps','logs','tenants','records','items','activities','tags','roles','departments'] 自动追加 `d.list`，分页响应直接可用。
- **el-card → wd-panel 改造规则**（2026-09 全量执行，13 模板 23 处）：WdPanel props 为 `{title, description, collapsible, opened, shadow:'hover', border:true}`，渲染 `.wd-panel` / `.wd-panel__header`（含 extra slot）/ `.wd-panel__content`。转换映射：①简单容器直接换标签（`shadow="never"` 保留）；②纯文本 `#header` → `title` prop（动态文本用 `:title`）；③标题+控件的复合 header → `title` prop + 控件放 `#extra` slot；④组件型 header（如 el-tag）→ `<template #title>` slot。排除：纯展示卡（dashboard 统计卡、login 登录卡）不改。改造后注意清理无元素引用的死样式（如 `.card-head`）。
- **401 全局接管模式**（2026-09-28 上线，全部改动在 common.js）：①本地配置 `response.exception: { showTips:false }` 关掉库默认异常提示；②`AdminUI.start` 内、`createApp` **之前**注册 `WorkDesktop.request.on` 守卫——`apiFail` 且 code 为 -10001/-10002、或 `apiException` 且 `error.response.status===401`，均调 `promptRelogin()`（ElMessageBox.confirm "登录状态已过期，请重新登录"，先清凭证，确认/取消都跳登录页，`reloginPrompting` 标志并发去重）；非 401 异常弹 error message；③`window.unhandledrejection` 兜底静默 401 rejection（组件内部未 catch）。关键机制：UMD 导出 `K.request=he, K.http=he`，模块级单例——组件（WdDataGrid 等）内部请求与 `WorkDesktop.request` 是同一实例，全局 `on(fn)` 能收到组件请求事件。验证脚本 `temp/pw_verify_401_prompt.py`（三场景：分页触发 401 弹框跳登录 / reload 首屏 401 弹框 / 错密码回归不弹框）。
- **皮肤系统**（1.1.1+，`theme.skin` 一键套用）：在 `window.workDesktopConfig` 加 `theme: { skin: 'fashion' }` 即可（UMD 直引场景 install 前声明生效）；覆盖优先级 `cssVars > colors > skin`。1.2.0 实际 `listSkins()` 返回 **10 套**：default / fashion / business / tech / cyberpunk / chinese / flat / cool / governance / **apple**——注意 llms.txt 与 CHANGELOG 写的"11 套"已过时（neumorphism、gradient 已移除，apple 新增，文档未同步；fashion 主色 #cd3c1d）。辅助 API：`SKIN_PRESETS` / `getSkinPreset(key)` / `listSkins()`；皮肤经组件级令牌回退链（`var(--wd-panel-bg, var(--wd-bg-color, #fff))`）作用于 WdPanel/WdDataGrid/WdStation 等，EP 派生色阶（light-3/5/7/8/9、dark-2）由语义主色自动推导。验证：对比 `getComputedStyle(:root)` 的 `--el-color-primary` 与 `getSkinPreset('fashion').theme.colors.primary`（脚本 `temp/pw_verify_skin.py`）。升级 vendor 文件渠道：`https://unpkg.com/workdesktop-ai@<version>/dist/index.umd.js` + `dist/style.css`（curl 直拉比整包下载稳）。

## [eval] 失败案例与教训

- **report/apps 按调用量排序 500**（2026-09 修复）：`call_count` 是内存聚合值而非模型字段，却被列入 ORM `order_by` 白名单导致 FieldError。修复：白名单收窄，内存排序分支兜底。教训：排序白名单只放真实模型字段。
- **用自建 DB 超管用户调超管 API 全 403**：误把 is_superuser 当超管体系。见 [rule] 第 1 条——超管认 env 账号 + token payload 标志。
- **CSV 导出按 JSON 解析报错**：导出响应为 text/csv（utf-8-sig 带 BOM），smoke 脚本需按 Content-Type 分支处理。
- **PowerShell 内联 node -e 双引号转义陷阱**：Windows 下用 `String.fromCharCode(34)` 或改写临时脚本文件，避免引号地狱。
- **`options-props` 是无效 prop，下拉/复选框无声空白**（2026-09 修复）：workdesktop-ai 全库没有任何组件接受 `optionsProps`（UMD 0 匹配），模板写了会被静默忽略，组件收不到 api 从不动请求，面板空白且无报错。正确用法是直接传 `api` / `text-prop` / `value-prop` / `:data-source`。响应结构由 common.js 拦截器的 `roles/tags/departments/tenants → list` 注入兜底。教训：用库组件前先查 UMD 源码确认 prop 名，无效 prop Vue 不会报错。
- **WdDataGrid 的 `:row-actions` 无定制插槽**：行内操作由库内部渲染为平铺 link 按钮。要用 el-button-group 包裹，必须弃用 row-actions 配置，改模板内显式 `<el-table-column label="操作">` + `@click="onRowAction({command, row})"` 复用既有 JS。
- **401 接管三连坑**（2026-09-28 逐一实锤）：①**守卫注册时序**——Vue 3 子组件 mounted 先于父组件，守卫若写在自己 app 的 mounted 里会漏掉 WdDataGrid 首屏自动请求的 401 事件，必须在 `createApp` 之前注册；②**WdSearchPanel 搜索去重**——搜索参数未变化时点"搜索"库内去重不发请求（0 请求 0 事件，与 token 无关），验证 401 要用分页点击（分页必发请求）；③**库 reject 的 Error 无 response**——`Sn.executeRequest` 最终 reject 的是重新包装的 Error，`reason.response` 为 undefined，`unhandledrejection` 兜底判断需同时匹配 `reason.message` 中的 `status code 401`（axios 标准文案），否则 preventDefault 不生效、Playwright pageerror 照样报。

## [hooks] 自动化校验手段

- 全接口 smoke：[temp/smoke_admin_api.py](file:///e:\framework\Unified account identification service\temp\smoke_admin_api.py)（登录 → 超管 14 项 → 租户抽查 → impersonate 链路，真实 HTTP 验证，验证完即弃的临时脚本）。
- 页面批量 200：PowerShell `Invoke-WebRequest` 循环 16 个 `/admin-panel/*` 路径。
- 回归测试：`& "C:\Program Files\python\python.exe" -m pytest tests/ -q`（系统 `python` 是 3.13 无 pytest，注意用 3.8 解释器）。
- 改后端视图后：`python manage.py check` + 相关 smoke 项复跑。

***

## 版本变化

- V_1.0（2026-09-22）：初版，记录管理后台 workdesktop-ai 多页重构的完整结论与经验。
- V_1.1（2026-09-22）：新增 [eval] 两条——`options-props` 无效 prop 导致选项组件无声空白、WdDataGrid row-actions 无插槽的 el-button-group 改造方案。
- V_1.2（2026-09-24）：新增 [skill] el-card → wd-panel 四类转换映射规则（简单容器/文本 header/复合 header/组件 header）及排除范围。
- V_1.3（2026-09-28）：新增 [skill] 401 全局接管模式（守卫双通道 + 并发去重 + unhandledrejection 兜底，UMD 单例机制）；新增 [eval] 401 接管三连坑（守卫须早于 createApp 注册、搜索按钮去重不发请求、库 reject 的 Error 无 response 需按 message 匹配）。
- V_1.4（2026-09-28）：workdesktop-ai 1.1.0 → 1.2.0（vendor 两文件替换，事件/tips/dedup 机制兼容，401 守卫回归通过）；启用 fashion 时尚皮肤。[skill] 新增皮肤系统用法（含 1.2.0 实际 10 套皮肤与文档"11 套"的差异、unpkg 直拉升级渠道）。
