# Memory - 统一账号识别服务

> 创建时间: 2026-09-22 17:30:00
> 最后修改: 2026-11-27 12:00:00
> 版本: V_1.12
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

- **管理后台重构已完成**（2026-09-22）：由 Vue 单页应用改为基于 `workdesktop-ai@1.2.18`（UMD，`window.WorkDesktop`）+ Vue 3 + ElementPlus 的**多页架构**，16 个页面（登录 + 租户端 9 + 超管端 6）；皮肤为默认（fashion 已于 2026-11-25 移除）；全站组件尺寸 `small`（base.html 用 `el-config-provider size="small"` 包裹，本项目 vendored EP 无 mini 枚举）。
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
- **登录失败提示（2026-11-25）**：后端登录失败返回 HTTP 400/403 → 走 axios 异常分支，`.catch` 静默且库会弹内置"网络异常"MessageBox（英文 axios message）。**坑：common.js 的 `response.exception.showTips:false` 深合并到库内后未生效**（原因未深究），但请求级 `tipsConfig.exception` 优先级最高有效——登录请求第三参传 `{ tipsConfig: { exception: { showTips: false } } }` 抑制内置弹窗，再用 `WorkDesktop.request.on` 的 apiException 事件取 `evt.error.response.data.message` 弹 ElMessage。此模式可用于其他需要自定义 HTTP 错误提示的场景。
- **wd-station 侧边栏收起后无法展开（库 bug，2026-11-25 已绕过）**：库内 `Te=computed(()=>props.collapsed||rt)`，点击 `Bo()` 先 `rt=!Te` 再 `emit('update:collapsed',Te)`——emit 取 computed 即时值，受控模式下被旧的 props.collapsed 支配，第二次点击 emit 的仍是 true，v-model 卡死在收起态。**只要传 v-model:collapsed 必踩**。绕过方案：不传 collapsed prop（非受控），`@update:collapsed` 同步状态；侧边栏 logo 展开横版/收起方形的切换用 aside 的 `is-collapsed` 类**纯 CSS 驱动**（勿依赖 JS 状态，静态 JS 缓存会导致切换失效）。
- **品牌素材已接入**（2026-11-25）：`resource/` 三张原图（icon/logo/logo-word，深蓝 UAIS）经 Pillow 处理输出到 `static/admin_panel/img/`——favicon.ico(16/32/48)、logo-word.png（深蓝横版，登录卡片+侧边栏展开态）、logo-mark.png（深蓝方形，侧边栏收起态）、*-white.png 白色版备用。**注意：默认皮肤侧边栏是浅米色底（rgba(251,247,240,0.72)），必须用深蓝版 logo**（曾误用白色版导致看不清；库 CSS 中那段深色 aside 白字样式是皮肤覆盖样式，默认皮肤不适用）。接入方式：wd-station 用 `#logo` 插槽注入图片（logo prop 只支持图标名不支持图片 URL）；展开/收起用 stationCollapsed v-show 切换两张图。
- **邀请注册页品牌自定义**（2026-11-25 上线）：租户级 4 个字段 `Tenant.invite_brand_name / invite_welcome / invite_theme_color / invite_logo`（migration accounts.0012）。管理端入口在邀请码页右上「注册页外观」抽屉（`/api/v1/admin/invite-brand` GET/PUT，主题色校验 `#RRGGBB`，logo 存 data URI 上限 30 万字符，前端 canvas 压到 360×120 再存，不走文件存储）。公开接口 `GET /api/v1/public/invite/<code>` 返回 `brand{name,welcome,theme_color,logo}`，`name` 未配时回退租户名；邀请页用 CSS 变量 `--brand-color` 着色、logo 加载成功才隐藏默认信封图标。
- **DataGrid `height="fix"` 布局方案**（2026-11-25 上线，7 个单表格页；2026-11-27 扩展 tab 页）：库内 fix 计算取 datagrid **直接父级**的当前高度，故必须让 `.wd-panel__body` 获得定高。方案：base.html 公共样式 + 页面两处标记——①内容块根包 `<div class="page-flex">`（height:100% flex column）；②表格 panel 加 `grid-panel` 类（flex:1，内部 `.wd-panel__content` / `__content-inner` / `__body` 链全部 flex 定高）。生效后 grid 高度精确 = body clientHeight − 44（body padding 22×2），窗口 resize 与搜索面板收起/展开均由库内 ResizeObserver 自动重算。注意 `.wd-panel__body` 不是 panel 根的直接子级（中间隔 content/content-inner 两层），CSS 选择器必须用后代选择器。**tab 页扩展（users/roles）**：`grid-panel` 在 el-tab-pane 内隔两层，`.page-flex > .grid-panel` 直接子级选择器不命中 → panel 高度 auto → fix 首算取内容高度（首屏不占满、切 tab 后重算才正常）。修复：把 el-tabs 中间层接入 flex 链——`.page-flex > .el-tabs { flex:1; min-height:0; display:flex; flex-direction:column; }`，header `flex:none`，`.el-tabs__content { flex:1; min-height:0; }`，`.el-tab-pane { height:100%; display:flex; flex-direction:column; }`，且 `.grid-panel` 系列选择器全部改为 `.page-flex` 后代形式（仅命中带 grid-panel 类的 panel，其他页面安全）。实测 fix 公式全局一致：**table height = grid panel body clientHeight − 126**（126 ≈ body padding 44 + toolbar 50 + 表头 32），applications 单表格页对照同为 126。tab 页内搜索面板占位（~100px）会使该 tab 表格天然比无搜索面板的 tab 矮，属预期。验证脚本 `temp/pw_verify_tab_height.py`（判据：panel 底边=pane 底边=page-flex 底边 + 表格高度符合公式，13/13 PASS）。
- **401 全局接管模式**（2026-09-28 上线，全部改动在 common.js）：①本地配置 `response.exception: { showTips:false }` 关掉库默认异常提示；②`AdminUI.start` 内、`createApp` **之前**注册 `WorkDesktop.request.on` 守卫——`apiFail` 且 code 为 -10001/-10002、或 `apiException` 且 `error.response.status===401`，均调 `promptRelogin()`（ElMessageBox.confirm "登录状态已过期，请重新登录"，先清凭证，确认/取消都跳登录页，`reloginPrompting` 标志并发去重）；非 401 异常弹 error message；③`window.unhandledrejection` 兜底静默 401 rejection（组件内部未 catch）。关键机制：UMD 导出 `K.request=he, K.http=he`，模块级单例——组件（WdDataGrid 等）内部请求与 `WorkDesktop.request` 是同一实例，全局 `on(fn)` 能收到组件请求事件。验证脚本 `temp/pw_verify_401_prompt.py`（三场景：分页触发 401 弹框跳登录 / reload 首屏 401 弹框 / 错密码回归不弹框）。
- **皮肤系统**（1.1.1+，`theme.skin` 一键套用）：在 `window.workDesktopConfig` 加 `theme: { skin: 'fashion' }` 即可（UMD 直引场景 install 前声明生效）；覆盖优先级 `cssVars > colors > skin`。1.2.0 实际 `listSkins()` 返回 **10 套**：default / fashion / business / tech / cyberpunk / chinese / flat / cool / governance / **apple**——注意 llms.txt 与 CHANGELOG 写的"11 套"已过时（neumorphism、gradient 已移除，apple 新增，文档未同步；fashion 主色 #cd3c1d）。辅助 API：`SKIN_PRESETS` / `getSkinPreset(key)` / `listSkins()`；皮肤经组件级令牌回退链（`var(--wd-panel-bg, var(--wd-bg-color, #fff))`）作用于 WdPanel/WdDataGrid/WdStation 等，EP 派生色阶（light-3/5/7/8/9、dark-2）由语义主色自动推导。验证：对比 `getComputedStyle(:root)` 的 `--el-color-primary` 与 `getSkinPreset('fashion').theme.colors.primary`（脚本 `temp/pw_verify_skin.py`）。升级 vendor 文件渠道：`https://unpkg.com/workdesktop-ai@<version>/dist/index.umd.js` + `dist/style.css`（curl 直拉比整包下载稳）。
- **两页合并为一页 tab 块范式**（2026-11-27，users+user-groups / roles+tags）：①`el-tab-pane lazy` + 表格 `:active="activeTab==='xxx'"` 双保险——lazy 解决隐藏容器中 `height="fix"` 首算为 0 且切回不重算的问题，:active 控制数据懒加载；②**WdDataGrid 的 toolbar slot 渲染在内置 tools.add「新增」按钮之前**（UMD 源码 slot → add → 导出），要在新增右侧插按钮必须禁用内置 add（`:tools="{ refresh: true }"`）并在 slot 自绘 `<el-button type="primary">` + Plus 图标；③合并两个 Vue app 时重名冲突清单：data 的 `drawerVisible/formMode/formRules`、methods 的 `openCreate/openEdit/onDelete/onRowAction/fmtTime`、`ref="gridRef"`——次要页统一加前缀（group*/tag*），方法重命名后同步改刷新引用的 `$refs`；④页面标题/tips 文案与菜单名同步更新，`AdminUI.start` 的 activePath 保持原主页面路径。
- **WdDataGrid 多选成员管理范式（勾选即保存，2026-11-27）**：用户组成员 drawer 用带复选框的 WdDataGrid 替代 el-select 多选。核心是 **dataSource 本地全量模式**——`:data-source="memberRows" :with-pager="false" with-selection row-key="id" selection-key="id" v-model="memberIds"`，打开 drawer 并行拉全量用户（GET users page_size=1000，users_view 的 page_size 无 clamp）与组成员；**先赋 memberSavedIds 再赋 memberIds**（watch 比对相等即跳过），userAllOptions 到位后库内 watch(dataSource) 自动回显勾选（程序性回显被库内 $ 标志抑制，不 emit）。勾选/取消 emit 全量 selection → watch(memberIds, deep) 与 memberSavedIds 排序比对，不同则 400ms debounce PUT 全量 user_ids（成功 savedIds=快照+刷新组表格；失败 reloadMembers 回滚）。**不能用分页模式**：其他页已选成员不在当前 selection，任何勾选 emit 的全量 selection 会静默挤掉跨页成员；本地全量 + computed 关键词过滤（username/nickname/phone）则 selection 始终无损，筛选前后勾选由 reserve-selection（依赖 row-key）保持。drawer @closed 先清状态再置空 memberGroup（watch guard 双保险）。`tools` 默认 `{}` 不渲染任何内置按钮，多选表格无需传 tools。

## [eval] 失败案例与教训

- **report/apps 按调用量排序 500**（2026-09 修复）：`call_count` 是内存聚合值而非模型字段，却被列入 ORM `order_by` 白名单导致 FieldError。修复：白名单收窄，内存排序分支兜底。教训：排序白名单只放真实模型字段。
- **用自建 DB 超管用户调超管 API 全 403**：误把 is_superuser 当超管体系。见 [rule] 第 1 条——超管认 env 账号 + token payload 标志。
- **CSV 导出按 JSON 解析报错**：导出响应为 text/csv（utf-8-sig 带 BOM），smoke 脚本需按 Content-Type 分支处理。
- **PowerShell 内联 node -e 双引号转义陷阱**：Windows 下用 `String.fromCharCode(34)` 或改写临时脚本文件，避免引号地狱。
- **`options-props` 是无效 prop，下拉/复选框无声空白**（2026-09 修复）：workdesktop-ai 全库没有任何组件接受 `optionsProps`（UMD 0 匹配），模板写了会被静默忽略，组件收不到 api 从不动请求，面板空白且无报错。正确用法是直接传 `api` / `text-prop` / `value-prop` / `:data-source`。响应结构由 common.js 拦截器的 `roles/tags/departments/tenants → list` 注入兜底。教训：用库组件前先查 UMD 源码确认 prop 名，无效 prop Vue 不会报错。
- **WdDataGrid 的 `:row-actions` 无定制插槽**：行内操作由库内部渲染为平铺 link 按钮。要用 el-button-group 包裹，必须弃用 row-actions 配置，改模板内显式 `<el-table-column label="操作">` + `@click="onRowAction({command, row})"` 复用既有 JS。
- **DataGrid `height="fix"` 在 auto 高度容器中是无效的自引用死循环**（2026-11-25 实锤）：库内 `he()` 向上找容器时用 `getComputedStyle().height` 判断"有确定高度"，而 `height:auto` 元素的 computed 值也返回像素 → fix 永远命中 datagrid 直接父级（wd-panel body，自适应高度），算出的高度=自身当前内容高度的不动点（实测恒 385px），页面照常溢出、window resize 重算结果相同（重算"无效"的真相是结果恒等）、ResizeObserver 观察的也是该父级故永不触发。教训：排查 fix 类问题先确认 `he()` 实际选中的容器，不要假设它选中真正的滚动容器；修复思路是给直接父级提供与视口挂钩的定高（flex 链），而不是派发 resize。
- **401 接管三连坑**（2026-09-28 逐一实锤）：①**守卫注册时序**——Vue 3 子组件 mounted 先于父组件，守卫若写在自己 app 的 mounted 里会漏掉 WdDataGrid 首屏自动请求的 401 事件，必须在 `createApp` 之前注册；②**WdSearchPanel 搜索去重**——搜索参数未变化时点"搜索"库内去重不发请求（0 请求 0 事件，与 token 无关），验证 401 要用分页点击（分页必发请求）；③**库 reject 的 Error 无 response**——`Sn.executeRequest` 最终 reject 的是重新包装的 Error，`reason.response` 为 undefined，`unhandledrejection` 兜底判断需同时匹配 `reason.message` 中的 `status code 401`（axios 标准文案），否则 preventDefault 不生效、Playwright pageerror 照样报。
- **Playwright 验证空租户误判**（2026-11-27）：模拟租户 4（演示企业）users/roles/tags 全为空，表格 rows=0 被误判为加载失败、登录测试 `POST /api/v1/admin/login-test` 返回 404 也被误判为路由错误——实为 view 内 `User.objects.filter(tenant_id=...)` 查无此人返回 USER_NOT_FOUND 404（业务行为，[views.py L2791](file:///e:\framework\Unified account identification service\code\unified_auth\apps\admin_panel\views.py#L2791)）。教训：验证数据类功能先确认租户有数据（租户 1 乾标 34 用户/3 角色可用），或先经 API 造数再走 UI；404 响应要抓 URL+method 看是路由 404 还是 view 内业务 404。另：菜单文案断言别用 `inner_text().contains`——页面 tips 含「角色与标签管理」会子串误中「标签管理」，须按 aside 菜单行 split 后精确比对。
- **Playwright 多 drawer 页面定位坑**（2026-11-27）：一页多个 el-drawer（组编辑/成员/登录测试）时 `document.querySelector('.el-drawer')` 拿到第一个（隐藏的组编辑 drawer），行数/勾选数统计全为空——应按内容特征定位（`[...document.querySelectorAll('.el-drawer')].find(d => d.querySelector('.el-table__body'))`）。locator 的 `has=` filter 是**惰性重解析**：勾选某行后再用同一 locator（`has=.el-checkbox:not(.is-checked)`）点第二次会命中另一个新未勾选行；用户 tab 行文本含组标签也会让 `has_text` 误命中用户行（操作列无目标按钮而超时）——必须按行索引 `all_rows.nth(idx)` 固定目标行，或用 `filter(has=locator('button:has-text("成员")'))` 限定组行。另：登录按钮文本是「登 录」（带空格），`has-text("登录")` 匹配不上，用 `.login-btn` 类定位。

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
- V_1.5（2026-11-25）：修复 DataGrid `height="fix"` 全部 7 页不生效问题（根因与 flex 布局方案见 [eval]/[skill] 新增条目）；皮肤移除 fashion 回默认；全站按钮 small 化（EP 无 mini 枚举）；vault 更新 vendor 版本为 1.2.18。
- V_1.6（2026-11-26）：邀请注册页自定义全面落地——模式一（租户默认字段 + 邀请码级完全覆盖、文案、动态渲染、User/UserProfile 分流落库）与模式二（应用三地址、`InviteCode.app` 绑定、短链 302 带 `code/ts/sign`、按应用 origin 动态 CORS、注册响应 `redirect_url`、Webhook 签名+重试+`WebhookDelivery` 落库）。实测 20/20 接口冒烟 + 两轮浏览器端到端全 PASS。文档：方案 v1.3、API_05_PUBLIC v1.1、API_03_ADMIN v1.2、接入手册 v1.0、实施记录 v1.0。关键实现细节：`resolve_invite_fields`（邀请码 > 租户 > 系统默认；username/password 固定；白名单联动 phone 必填；未知键过滤）；`apps/invites/services.py` 提供签名/URL 校验/Webhook；`middlewares/dynamic_cors.py` 置于 CorsMiddleware 之前、DEBUG 全放行、60s 缓存；测试时用 `INVITE_REGISTER_IP_LIMIT_PER_MINUTE=50` 绕过 3 次/IP 分钟限制。
- V_1.7（2026-11-26）：工作区清理与打包防污染。删除历史调试残留（admin_login*.json / login_req*.json / refresh_req.json / token_req.json / check_user.py）、全部 `__pycache__`、`.pytest_cache`、`cache/*.djcache`、`db.sqlite3` 与误命名的 SQLite 库文件 `code/unified_auth/unified_auth`、`temp/wdai/node_modules`（72MB）、`output/` 截图、旧 pytest/打包日志、根级 `error.txt`/`test_admin.db`；`db_init.sql` 归档到 `document/archive/`；保留最新打包备份 `unified_auth_2026-10-17.zip`。**根因**：`scripts/package.py` 的 `EXCLUDE_FILES` 匹配用 `endswith(pattern.replace("*",""))`，不支持前缀通配，且未排除调试文件 → 被 `*.json`/`*.py` 一并打进 dist。已改用 `fnmatch.fnmatch` 并补充排除项（admin_login*.json、login_req*.json、refresh_req.json、token_req.json、check_user.py、db_init.sql、unified_auth），实测 12 项规则全部符合预期；`.gitignore` 同步补充调试文件规则。[rule] dist/ 不改，只能通过重新运行 package.py 重建。
- V_1.8（2026-11-27）：码管理合并页上线。新增模型 `WechatBindCode`（表 wechat_bind_code，迁移 invites/0005）、管理接口 `/api/v1/admin/wechat-bind-codes`（GET/POST/PATCH/DELETE，单人缺用户 400、mode 创建后禁改、使用上限不得低于已用次数、AuditLog action=admin.wechat_bind_code.*）；新页面 `/admin-panel/code-center/`（码管理）以记录卡片流合并展示注册邀请码/资料补全码/微信绑定码三类码，顶部类型切换 + 搜索/状态筛选 + 分页，卡片含类型徽标/状态/短码复制/模式/绑定用户/使用次数/有效期/备注/操作（二维码仅前两类，微信绑定码第一版仅管理端生成与启停，核销接口后续接）；菜单「邀请码管理」「资料补全码」两项合并为「码管理」，删除旧模板 invite_codes.html / completion_codes.html，全部旧 API 路由保留不变。验证：接口 CRUD 直调全过 + Playwright 浏览器 12/12 PASS。注意：runserver 用 --noreload 时改后端代码必须手动重启进程；`_wechat_serialize` 无 request 参数（不生成公开链接）。
- V_1.9（2026-11-27）：「短信配置」升级为「系统设置」页。新路由 `/admin-panel/system-settings/`（模板 system_settings.html，urls.py 与 common.js 菜单项同步改名，icon=Setting），页面采用左侧竖排分类导航（短信配置 / 升级日志）+ 右侧内容区布局；短信配置块完整迁移原表单（wd-data-form GET/PUT tenant-sms-config）与测试发送逻辑；升级日志块为前端静态 el-timeline（V_1.5~V_1.9 摘录，后续发版手动维护该数组）。删除旧模板 sms_config.html，页面旧路由 404，API `/api/v1/admin/tenant-sms-config(/test)` 不变。[eval] 修复 `AdminTenantSmsConfigSerializer` 四个 CharField 缺 `allow_blank=True`：全空配置租户 PUT 保存报 -10602 "This field may not be blank."（旧页面同样存在），补参后直调通过。验证：Playwright 13/13 PASS（登录/模拟租户/菜单高亮/两区块切换/时间线条目/API GET+PUT/旧路由 404/无 JS 错误）。
- V_1.10（2026-11-27）：菜单两级合并。①用户管理页（users.html）合并用户组管理为第二个 tab（el-tab-pane lazy + `:active` 懒加载），原 user_groups 的抽屉/成员管理 JS 合并进同一 Vue app（重名变量与方法加 group 前缀：groupDrawerVisible/groupForm/groupFormRules/openGroupCreate/saveGroupForm/onGroupDelete，grid ref 拆为 groupGridRef）；「登录测试」按钮置于用户 tab toolbar 新增按钮右侧（禁用内置 tools.add 自绘新增+登录测试按钮，因库 toolbar slot 渲染在内置新增之前），点击打开 el-drawer（560px）承载原登录测试表单与 token 结果，合并其 JS（testUsername/testPassword/testResult/onTest/onCopy）。②角色管理页（roles.html）改名「角色与标签管理」并合并标签管理为第二个 tab，标签侧加 tag 前缀（tagDrawerVisible/tagFormMode/tagFormRules/openTagCreate/onTagRowAction/onTagDelete，tagGridRef）。③config/urls.py 删 tags//user-groups//login-test/ 三条页面路由，common.js 菜单删「标签管理」「用户组管理」「登录测试」三项并将「角色管理」改名「角色与标签管理」，删除旧模板 user_groups.html / tags.html / login_test.html（旧路由 404，API 全部保留）。验证：Playwright 22/22 PASS（模拟租户 1，tab 结构/表格加载/登录测试完整链路含 API 造数与清理/drawer 冒烟/菜单断言/无 JS 错误）。
- V_1.11（2026-11-27）：用户组成员管理 drawer 由 el-select 多选搜索改为带复选框的 WdDataGrid（dataSource 本地全量 + row-key/selection-key=id 自动回显勾选 + 本地关键词筛选 + 勾选/取消勾选自动 PUT 保存（400ms debounce，失败回滚重载），删除原「保存成员」按钮与 searchUsers/mergeUserOptions/userLabel，drawer 加宽至 640px）。范式与分页模式的跨页选中误移除问题见 [skill] 新增条目；Playwright 多 drawer 定位坑见 [eval] 新增条目。验证：Playwright 15/15 PASS（回显数=成员数/勾选即 PUT 且 member_count+1/取消勾选还原/筛选后行数变化且勾选保持/清空恢复/重开回显/无 JS 错误），脚本保留 temp/pw_verify_member_grid.py。
- V_1.12（2026-11-27）：修复 tab 页 DataGrid 首屏高度不占满问题。根因：合并页改造后 `grid-panel` 位于 el-tab-pane 内隔两层，base.html 原 `.page-flex > .grid-panel` 直接子级选择器不命中 → wd-panel 高度 auto → `height="fix"` 首算取内容高度（首屏不占满，点击 tab 切换后重算才正常）；用户 tab 表格 466 vs 用户组 566 的差异为搜索面板占位（~100px），属预期非 bug。修复：base.html 将 el-tabs/el-tabs__content/el-tab-pane 中间层接入 flex 高度链，`.grid-panel` 选择器改后代形式（详见 [skill] height="fix" 条目 tab 页扩展）。验证：Playwright 13/13 PASS（users 首屏/用户组/切回用户 + roles 首屏/标签/切回角色，panel 底边=pane 底边=page-flex 底边 851 全对齐 + 表格高度符合 fix=gbody−126 公式 + applications 对照 diff=126 + 无 JS 错误），脚本保留 temp/pw_verify_tab_height.py。
