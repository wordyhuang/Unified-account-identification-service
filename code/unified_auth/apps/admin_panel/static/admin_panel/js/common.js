/**
 * 统一账号识别服务 · 管理后台公共模块
 * 职责：认证管理 / workdesktop-ai 全局配置 / 菜单与布局 / 公共工具
 * 加载时机：必须在 workdesktop-ai UMD 之前加载（负责定义 window.workDesktopConfig）
 */
(function () {
  'use strict';

  var TOKEN_KEY = 'admin_token';
  var USER_KEY = 'admin_user';
  var LOGIN_PATH = '/admin-panel/login/';

  /* ==================== 认证 ==================== */
  var AdminAuth = {
    getToken: function () {
      return localStorage.getItem(TOKEN_KEY) || '';
    },
    getUser: function () {
      try {
        return JSON.parse(localStorage.getItem(USER_KEY) || 'null');
      } catch (e) {
        return null;
      }
    },
    /** 存储凭证；user 中的 token 字段会被清洗，避免冗余存储 */
    setAuth: function (token, user) {
      var u = Object.assign({}, user || {});
      delete u.access_token;
      delete u.refresh_token;
      localStorage.setItem(TOKEN_KEY, token);
      localStorage.setItem(USER_KEY, JSON.stringify(u));
    },
    clear: function () {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
    },
    /** 页面守卫：无凭证跳登录页；返回当前用户对象 */
    requireAuth: function () {
      var user = this.getUser();
      if (!this.getToken() || !user) {
        location.href = LOGIN_PATH;
        return null;
      }
      return user;
    },
    logout: function () {
      this.clear();
      location.href = LOGIN_PATH;
    },
    /** 后端 token 失效错误码：-10001 过期 / -10002 无效 */
    isTokenError: function (code) {
      return code === -10001 || code === -10002;
    }
  };

  /* ==================== 菜单定义 ==================== */
  var MENU_GROUPS = [
    {
      key: 'admin', title: '租户管理', icon: 'OfficeBuilding',
      menus: [
        { title: '工作台', path: '/admin-panel/dashboard/', icon: 'Odometer' },
        { title: '用户管理', path: '/admin-panel/users/', icon: 'User' },
        { title: '应用管理', path: '/admin-panel/applications/', icon: 'Grid' },
        { title: '角色管理', path: '/admin-panel/roles/', icon: 'Avatar' },
        { title: '部门管理', path: '/admin-panel/departments/', icon: 'Notebook' },
        { title: '标签管理', path: '/admin-panel/tags/', icon: 'PriceTag' },
        { title: '审计日志', path: '/admin-panel/audit/', icon: 'Document' },
        { title: '短信配置', path: '/admin-panel/sms-config/', icon: 'ChatDotSquare' },
        { title: '登录测试', path: '/admin-panel/login-test/', icon: 'Key' }
      ]
    },
    {
      key: 'superadmin', title: '平台管理', icon: 'Platform',
      menus: [
        { title: '全局概览', path: '/admin-panel/superadmin/dashboard/', icon: 'DataAnalysis' },
        { title: '租户管理', path: '/admin-panel/superadmin/tenants/', icon: 'Shop' },
        { title: '全局审计', path: '/admin-panel/superadmin/audit/', icon: 'Tickets' },
        { title: '统计报表', path: '/admin-panel/superadmin/report/', icon: 'PieChart' },
        { title: 'API统计', path: '/admin-panel/superadmin/api-stats/', icon: 'TrendCharts' },
        { title: '平台配置', path: '/admin-panel/superadmin/config/', icon: 'Setting' },
        { title: '组件版本', path: '/admin-panel/superadmin/workdesktop-version/', icon: 'Refresh' }
      ]
    }
  ];

  /** 按用户身份生成可见菜单：纯超管仅平台管理，其余（租户管理员 / 模拟中的超管）仅租户管理 */
  function buildMenus(user) {
    if (user && user.is_superadmin && !user.impersonated) return [MENU_GROUPS[1]];
    return [MENU_GROUPS[0]];
  }

  /** 由路径反查菜单 key（规则：分组key:name||path||title，无 name 时用 path） */
  function menuKey(path) {
    for (var g = 0; g < MENU_GROUPS.length; g++) {
      var grp = MENU_GROUPS[g];
      for (var i = 0; i < grp.menus.length; i++) {
        if (grp.menus[i].path === path) return grp.key + ':' + path;
      }
    }
    return '';
  }

  /* ==================== workdesktop-ai 全局配置（须早于 UMD 加载） ==================== */
  window.workDesktopConfig = {
    // 时尚皮肤（workdesktop-ai@1.1.1+ 预设皮肤系统，11 套之一）
    theme: { skin: 'fashion' },
    page: {
      // 注：库内 componentDefault 仅 WdRequester 消费，wd-data-grid 等须在模板显式传 api-method
      pager: {
        pageSize: 10,
        pageSizes: [10, 20, 50, 100],
        layout: 'total, sizes, prev, pager, next, jumper'
      }
    },
    request: {
      // 后端分页参数为 page / page_size；搜索条件经请求拦截器展开到顶层
      pageParam: { pageField: 'page', sizeField: 'page_size', searchField: 'param' },
      transform: {
        requestInterceptor: function (cfg) {
          var token = AdminAuth.getToken();
          cfg.headers = cfg.headers || {};
          if (token) cfg.headers.Authorization = 'Bearer ' + token;
          // 搜索条件 param → 顶层（GET：平铺 query；POST：平铺 body，后端报表接口从 request.data 取）
          if (cfg.params && cfg.params.param && typeof cfg.params.param === 'object') {
            var p = cfg.params.param;
            delete cfg.params.param;
            Object.keys(p).forEach(function (k) {
              if (p[k] !== '' && p[k] !== null && p[k] !== undefined) cfg.params[k] = p[k];
            });
          }
          if (cfg.data && cfg.data.param && typeof cfg.data.param === 'object') {
            var pd = cfg.data.param;
            delete cfg.data.param;
            Object.keys(pd).forEach(function (k) {
              if (pd[k] !== '' && pd[k] !== null && pd[k] !== undefined) cfg.data[k] = pd[k];
            });
          }
          return cfg;
        },
        responseInterceptor: function (res) {
          // 列表字段规范化：后端 users/apps/logs/tenants → list（DataGrid 默认识别 list/total）
          var d = res && res.data && res.data.data;
          if (d && typeof d === 'object' && !Array.isArray(d) && d.list === undefined) {
            var keys = ['users', 'apps', 'logs', 'tenants', 'records', 'items', 'activities', 'tags', 'roles', 'departments'];
            for (var i = 0; i < keys.length; i++) {
              if (Array.isArray(d[keys[i]])) {
                d.list = d[keys[i]];
                break;
              }
            }
          }
          return res;
        }
      }
    },
    response: {
      fail: { tipsMode: 'message', tipsType: 'error' },
      // 异常提示由 AdminUI 守卫统一接管：401 弹框引导重新登录，其余弹 error message
      exception: { showTips: false }
    }
  };

  /* ==================== 登录失效引导 ==================== */
  var reloginPrompting = false;
  /** 弹框要求重新登录：清凭证 → 确认后跳登录页（并发 401 去重） */
  function promptRelogin() {
    if (reloginPrompting) return;
    reloginPrompting = true;
    AdminAuth.clear();
    ElementPlus.ElMessageBox.confirm('登录状态已过期，请重新登录。', '登录失效', {
      type: 'warning',
      confirmButtonText: '重新登录',
      cancelButtonText: '取消',
      closeOnClickModal: false,
      closeOnPressEscape: false
    }).then(function () {
      location.href = LOGIN_PATH;
    }).catch(function () {
      // 凭证已清，取消同样回登录页
      location.href = LOGIN_PATH;
    });
  }

  /* ==================== UI 启动器与公共工具 ==================== */
  var AdminUI = {
    buildMenus: buildMenus,
    menuKey: menuKey,

    /**
     * 启动管理页 Vue 应用（含认证守卫、菜单高亮、token 失效守卫）
     * @param {string} activePath 当前页菜单路径，如 '/admin-panel/users/'
     * @param {object} pageOptions 页面级 Vue 选项：data/methods/computed/watch/mounted
     */
    start: function (activePath, pageOptions) {
      var user = AdminAuth.requireAuth();
      if (!user) return null;
      pageOptions = pageOptions || {};
      var pageData = typeof pageOptions.data === 'function' ? pageOptions.data() : {};
      var pageMounted = pageOptions.mounted;

      // 登录失效全局守卫（须早于 createApp 注册：子组件 mounted 先于父级，晚注册会漏掉首屏请求的 401）：
      // ① apiFail（HTTP 200 业务码 -10001/-10002）② apiException 中 HTTP 401 → 弹框要求重新登录
      WorkDesktop.request.on(function (evt) {
        if (evt.type === 'apiFail' && AdminAuth.isTokenError(evt.code)) {
          promptRelogin();
          return;
        }
        if (evt.type === 'apiException') {
          var status = evt.error && evt.error.response && evt.error.response.status;
          if (status === 401) {
            promptRelogin();
            return;
          }
          ElementPlus.ElMessage.error(evt.message || '网络异常，请稍后重试');
        }
      });

      // 401 已由上方守卫接管弹框，组件内部未 catch 的 401 rejection 在此兜底静默，避免控制台 unhandledrejection
      // 注：库最终 reject 的是重新包装的 Error（不带 response），需同时按 message 中的 status code 401 匹配
      window.addEventListener('unhandledrejection', function (e) {
        var status = e.reason && e.reason.response && e.reason.response.status;
        var msg = (e.reason && e.reason.message) || '';
        if (status === 401 || msg.indexOf('status code 401') !== -1) e.preventDefault();
      });

      var app = Vue.createApp({
        delimiters: ['[[', ']]'],
        data: function () {
          return Object.assign({
            currentUser: user,
            menuGroups: buildMenus(user),
            activeMenu: menuKey(activePath),
            stationCollapsed: false
          }, pageData);
        },
        computed: pageOptions.computed || {},
        watch: pageOptions.watch || {},
        methods: Object.assign({
          onMenuSelect: function (item) {
            if (item && item.path && item.path !== location.pathname) location.href = item.path;
          },
          onLogout: function () {
            ElementPlus.ElMessageBox.confirm('确定退出登录吗？', '退出登录', {
              type: 'warning', confirmButtonText: '退出', cancelButtonText: '取消'
            }).then(function () {
              AdminAuth.logout();
            }).catch(function () {});
          },
          onExitImpersonate: function () {
            ElementPlus.ElMessageBox.confirm('确定退出模拟模式，返回平台管理吗？', '退出模拟', {
              type: 'warning', confirmButtonText: '退出模拟', cancelButtonText: '取消'
            }).then(function () {
              return WorkDesktop.request.post('/api/v1/superadmin/impersonate/exit');
            }).then(function (res) {
              if (!res) return;
              if (res.success) {
                AdminAuth.setAuth(res.data.access_token, {
                  username: user.username, is_superadmin: true, impersonated: false
                });
                location.href = '/admin-panel/superadmin/dashboard/';
              } else if (!AdminAuth.isTokenError(res.code)) {
                ElementPlus.ElMessage.error(res.message || '退出模拟失败');
              }
            }).catch(function () {});
          }
        }, pageOptions.methods || {}),
        mounted: function () {
          if (typeof pageMounted === 'function') pageMounted.call(this);
        }
      });

      app.use(ElementPlus, { locale: ElementPlusLocaleZhCn });
      // UMD 全局变量是导出命名空间，插件本体（含 install）挂在 default/WorkDesktop 上
      app.use(WorkDesktop.default || WorkDesktop.WorkDesktop);
      Object.keys(ElementPlusIconsVue).forEach(function (name) {
        app.component(name, ElementPlusIconsVue[name]);
      });
      app.mount('#app');
      return app;
    },

    /**
     * 超管模拟进入租户：成功后切换到租户工作台
     */
    impersonate: function (tenantId) {
      var user = AdminAuth.getUser() || {};
      return WorkDesktop.request.post('/api/v1/superadmin/impersonate/' + tenantId).then(function (res) {
        if (res && res.success) {
          AdminAuth.setAuth(res.data.access_token, {
            username: user.username,
            is_superadmin: true,
            impersonated: true,
            tenant_id: res.data.tenant_id,
            tenant_name: res.data.tenant_name
          });
          location.href = '/admin-panel/dashboard/';
        }
        return res;
      });
    },

    /**
     * CSV 文件下载（导出接口返回文件流，须经 fetch 带 token 下载）
     */
    downloadCsv: function (url, params, filename) {
      var qs = [];
      Object.keys(params || {}).forEach(function (k) {
        if (params[k] !== '' && params[k] !== null && params[k] !== undefined) {
          qs.push(encodeURIComponent(k) + '=' + encodeURIComponent(params[k]));
        }
      });
      if (qs.length) url += (url.indexOf('?') >= 0 ? '&' : '?') + qs.join('&');
      return fetch(url, { headers: { Authorization: 'Bearer ' + AdminAuth.getToken() } })
        .then(function (resp) {
          if (!resp.ok) throw new Error('导出失败（HTTP ' + resp.status + '）');
          return resp.blob();
        })
        .then(function (blob) {
          var a = document.createElement('a');
          a.href = URL.createObjectURL(blob);
          a.download = filename || 'export.csv';
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          URL.revokeObjectURL(a.href);
        })
        .catch(function (err) {
          ElementPlus.ElMessage.error(err.message || '导出失败');
        });
    },

    /** 时间格式化：ISO 字符串 → YYYY-MM-DD HH:mm */
    fmtTime: function (s) {
      if (!s) return '-';
      var d = new Date(s);
      if (isNaN(d.getTime())) return s;
      var p = function (n) { return n < 10 ? '0' + n : '' + n; };
      return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()) +
        ' ' + p(d.getHours()) + ':' + p(d.getMinutes());
    },

    /** 手动请求结果的业务失败提示（token 错误由全局守卫处理）；返回是否为失败 */
    toastFail: function (res, fallback) {
      if (res && !res.success && !AdminAuth.isTokenError(res.code)) {
        ElementPlus.ElMessage.error(res.message || fallback || '操作失败');
        return true;
      }
      return false;
    }
  };

  window.AdminAuth = AdminAuth;
  window.AdminUI = AdminUI;
})();
