const API = {
    auth: "/api/v1/auth",
    admin: "/api/v1/admin",
    superadmin: "/api/v1/superadmin",
};

const TOKEN_KEY = "admin_token";
const USER_KEY = "admin_user";

function getToken() { return localStorage.getItem(TOKEN_KEY); }
function getUser() {
    try { return JSON.parse(localStorage.getItem(USER_KEY)) || {}; }
    catch { return {}; }
}

async function apiCall(url, options = {}) {
    const token = getToken();
    const headers = { "Content-Type": "application/json", ...options.headers };
    if (token) headers["Authorization"] = "Bearer " + token;
    const res = await fetch(url, { ...options, headers });
    const data = await res.json();
    if (data.code < 0 && (url.startsWith(API.admin) || url.startsWith(API.superadmin))) {
        if (data.code === -10001 || data.code === -10002) {
            localStorage.removeItem(TOKEN_KEY);
            localStorage.removeItem(USER_KEY);
            showLogin();
            return null;
        }
        throw new Error(data.message || "请求失败");
    }
    return data;
}

// ================== Login / Logout ==================

async function handleLogin() {
    const username = document.getElementById("login-username").value.trim();
    const password = document.getElementById("login-password").value.trim();
    const errEl = document.getElementById("login-error");
    if (!username || !password) { errEl.textContent = "请输入用户名和密码"; return; }
    errEl.textContent = "";

    try {
        const res = await apiCall(API.auth + "/login", {
            method: "POST",
            body: JSON.stringify({ username, password, app_id: null }),
            headers: {},
        });
        if (res.code < 0) { errEl.textContent = res.message; return; }
        const d = res.data;
        const isAdmin = d.is_superuser || d.is_superadmin || d.is_staff;
        if (!isAdmin) { errEl.textContent = "仅管理员可登录管理后台"; return; }
        localStorage.setItem(TOKEN_KEY, d.access_token);
        localStorage.setItem(USER_KEY, JSON.stringify(d));
        showApp();
    } catch (e) {
        errEl.textContent = e.message || "登录失败，请检查网络";
    }
}

function handleLogout() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    showLogin();
}

function showLogin() {
    document.getElementById("app-login").style.display = "flex";
    document.getElementById("app-main").style.display = "none";
    document.getElementById("login-username").value = "";
    document.getElementById("login-password").value = "";
}

function showApp() {
    document.getElementById("app-login").style.display = "none";
    document.getElementById("app-main").style.display = "flex";
    const user = getUser();
    const label = user.is_superadmin ? "超级管理员" : "管理员";
    document.getElementById("topbar-user").textContent = (user.nickname || user.username) + " " + label;

    const superadminMenus = document.querySelectorAll('[data-superadmin]');
    superadminMenus.forEach(el => {
        el.style.display = user.is_superadmin ? "" : "none";
    });

    const adminMenus = document.querySelectorAll('[data-admin]');
    const isPureSuperadmin = user.is_superadmin && !user.impersonated;
    adminMenus.forEach(el => {
        el.style.display = isPureSuperadmin ? "none" : "";
    });

    switchPage(isPureSuperadmin ? "superadmin_dashboard" : "dashboard");
}

// ================== Page Router ==================

const PAGES = {
    dashboard: renderDashboard,
    users: renderUsers,
    tags: renderTags,
    applications: renderApplications,
    roles: renderRoles,
    departments: renderDepartments,
    audit: renderAudit,
    sms_config: renderSmsConfig,
    superadmin_dashboard: renderSuperadminDashboard,
    superadmin_tenants: renderSuperadminTenants,
    superadmin_audit: renderSuperadminAudit,
    superadmin_report: renderSuperadminReport,
    superadmin_apistats: renderSuperadminApiStats,
    superadmin_config: renderSuperadminConfig,
};

function switchPage(name) {
    document.querySelectorAll(".nav-item").forEach(el => el.classList.remove("active"));
    const navEl = document.querySelector(`.nav-item[data-page="${name}"]`);
    if (navEl) navEl.classList.add("active");
    const content = document.getElementById("page-content");
    content.innerHTML = '<div class="loading"></div>';
    if (PAGES[name]) PAGES[name](content);
}

// ================== Toast ==================

function showToast(msg, type) {
    const el = document.createElement("div");
    el.className = "toast " + type;
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 2500);
}

// ================== Modal ==================

function openModal(html) {
    document.getElementById("modal-container").innerHTML = html;
    document.getElementById("modal-overlay").style.display = "flex";
}

function closeModal() {
    document.getElementById("modal-overlay").style.display = "none";
}

let __chartInstances = {};
let batchUserIds = [];

function destroyChart(id) {
    if (__chartInstances[id]) {
        __chartInstances[id].destroy();
        delete __chartInstances[id];
    }
}

function renderMiniLineChart(canvasId, labels, data, label, color) {
    destroyChart(canvasId);
    const canvas = document.getElementById(canvasId);
    if (!canvas || !window.Chart) return;
    const ctx = canvas.getContext("2d");
    __chartInstances[canvasId] = new Chart(ctx, {
        type: "line",
        data: { labels, datasets: [{ label, data, borderColor: color, backgroundColor: color + "20", fill: true, tension: 0.3, pointRadius: 2, borderWidth: 2 }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { display: false }, y: { display: false, beginAtZero: true } } },
    });
}

function renderPieChart(canvasId, labels, data, colors) {
    destroyChart(canvasId);
    const canvas = document.getElementById(canvasId);
    if (!canvas || !window.Chart) return;
    const ctx = canvas.getContext("2d");
    __chartInstances[canvasId] = new Chart(ctx, {
        type: "doughnut",
        data: { labels, datasets: [{ data, backgroundColor: colors, borderWidth: 0 }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom", labels: { boxWidth: 10, padding: 8, font: { size: 11 } } } } },
    });
}

// ================== DASHBOARD ==================

async function renderDashboard(container) {
    container.innerHTML = '<div class="loading"></div>';
    try {
        const [statRes, actRes, trendRes, distRes] = await Promise.all([
            apiCall(API.admin + "/stats"),
            apiCall(API.admin + "/recent-activities"),
            apiCall(API.admin + "/stats/login-trend?days=7"),
            apiCall(API.admin + "/stats/user-type-distribution"),
        ]);
        if (!statRes) return;
        const s = statRes.data;
        const a = actRes ? actRes.data : { activities: [] };
        const trend = trendRes ? trendRes.data : null;
        const dist = distRes ? distRes.data : null;
        const appStats = s.app_stats || [];

        container.innerHTML = `
            <div class="stats-grid">
                <div class="stat-card"><span class="stat-label">用户总数</span><span class="stat-value primary">${s.total_users}</span></div>
                <div class="stat-card"><span class="stat-label">活跃用户</span><span class="stat-value success">${s.active_users}</span></div>
                <div class="stat-card"><span class="stat-label">今日新增</span><span class="stat-value warning">${s.today_new_users}</span></div>
                <div class="stat-card"><span class="stat-label">应用总数</span><span class="stat-value">${s.total_apps}</span></div>
                <div class="stat-card"><span class="stat-label">活跃应用</span><span class="stat-value primary">${s.active_apps}</span></div>
                <div class="stat-card"><span class="stat-label">角色数</span><span class="stat-value">${s.total_roles}</span></div>
            </div>
            <div class="row" style="display:flex;gap:16px;flex-wrap:wrap">
                <div class="card" style="flex:1;min-width:300px">
                    <div class="card-title">登录趋势（近7天）</div>
                    <div style="height:140px"><canvas id="loginTrendChart"></canvas></div>
                </div>
                <div class="card" style="flex:1;min-width:260px">
                    <div class="card-title">用户类型分布</div>
                    <div style="height:140px"><canvas id="userTypeChart"></canvas></div>
                </div>
            </div>
            <div class="card">
                <div class="card-title">应用统计（近7天调用）</div>
                ${appStats.length
                    ? `<div class="table-wrap"><table><thead><tr><th>应用名称</th><th>AppKey</th><th>状态</th><th>调用次数</th><th>创建时间</th></tr></thead><tbody>
                    ${appStats.map(app => `
                        <tr>
                            <td><strong>${app.name}</strong></td>
                            <td><code style="background:#f1f5f9;padding:2px 6px;border-radius:3px;font-size:12px">${app.app_key}</code></td>
                            <td><span class="badge ${app.status ? 'badge-active' : 'badge-disabled'}">${app.status ? "启用" : "禁用"}</span></td>
                            <td>${app.call_count_7d}</td>
                            <td>${formatTime(app.created_at)}</td>
                        </tr>`).join("")}
                    </tbody></table></div>`
                    : '<div class="empty-state">暂无应用</div>'}
            </div>
            <div class="card">
                <div class="card-title">最近操作动态</div>
                ${a.activities.length
                    ? `<ul class="activity-list">${a.activities.map(log => `
                        <li class="activity-item">
                            <span><strong>${log.actor_name || "系统"}</strong> ${formatAction(log.action)}</span>
                            <span class="activity-time">${formatTime(log.created_at)}</span>
                        </li>`).join("")}</ul>`
                    : '<div class="empty-state">暂无操作记录</div>'}
            </div>`;

        if (trend && trend.trend && trend.trend.length) {
            renderMiniLineChart("loginTrendChart",
                trend.trend.map(d => d.date.slice(5)),
                trend.trend.map(d => d.total),
                "登录次数", "#1a73e8");
        }
        if (dist && dist.items) {
            const entries = Object.entries(dist.items);
            renderPieChart("userTypeChart",
                entries.map(e => e[0]),
                entries.map(e => e[1].count),
                ["#1a73e8", "#e8710a", "#0a9e5e", "#8b5cf6"]);
        }
    } catch (e) {
        container.innerHTML = `<div class="empty-state">加载失败: ${e.message}</div>`;
    }
}

function formatAction(action) {
    const map = {
        "admin.user.delete": "删除了用户",
        "admin.user.update": "修改了用户信息",
        "admin.user.status": "修改了用户状态",
        "admin.user.reset_password": "重置了用户密码",
        "admin.app.create": "注册了新应用",
        "admin.app.update": "修改了应用配置",
        "admin.app.status": "修改了应用状态",
        "admin.app.regenerate_secret": "重新生成应用密钥",
        "admin.role.create": "创建了新角色",
        "admin.role.update": "修改了角色配置",
        "superadmin.login": "超级管理员登录",
        "superadmin.tenant.create": "创建了租户",
        "superadmin.tenant.update": "修改了租户",
        "superadmin.tenant.delete": "删除了租户",
    };
    return map[action] || action;
}

// ================== USERS ==================

let page = 1, search = "", status = "", isStaff = "";

async function renderUsers(container) {
    const pageSize = 20;

    async function load() {
        const params = new URLSearchParams({ page, page_size: pageSize });
        if (search) params.set("search", search);
        if (status) params.set("status", status);
        if (isStaff) params.set("is_staff", isStaff);
        container.innerHTML = '<div class="loading"></div>';
        try {
            const res = await apiCall(API.admin + "/users?" + params);
            if (!res) return;
            const d = res.data;
            container.innerHTML = `
                <div class="toolbar">
                    <div class="search-bar">
                        <input type="text" id="user-search" placeholder="搜索用户名/手机号/邮箱" value="${search}" onkeydown="if(event.key==='Enter'){search=this.value;renderUsers(document.getElementById('page-content'))}">
                        <select id="user-status-filter" onchange="status=this.value;renderUsers(document.getElementById('page-content'))">
                            <option value="">全部状态</option>
                            <option value="1" ${status==='1'?'selected':''}>正常</option>
                            <option value="0" ${status==='0'?'selected':''}>禁用</option>
                        </select>
                        <select id="user-staff-filter" onchange="isStaff=this.value;renderUsers(document.getElementById('page-content'))" style="min-width:100px">
                            <option value="">全部用户</option>
                            <option value="1" ${isStaff==='1'?'selected':''}>租户管理员</option>
                            <option value="0" ${isStaff==='0'?'selected':''}>普通用户</option>
                        </select>
                        <button class="btn btn-primary" onclick="document.getElementById('user-search').value='';search='';status='';isStaff='';renderUsers(document.getElementById('page-content'))">重置</button>
                    </div>
                    <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
                        <button class="btn btn-sm btn-primary" onclick="batchAction('enable')">批量启用</button>
                        <button class="btn btn-sm btn-warning" onclick="batchAction('disable')" style="background:var(--warning);color:#fff">批量禁用</button>
                        <button class="btn btn-sm btn-danger" onclick="batchAction('delete')" style="background:var(--danger);color:#fff">批量删除</button>
                        <button class="btn btn-sm btn-text" onclick="showImportUsers()">导入用户</button>
                        <button class="btn btn-sm btn-text" onclick="exportUsers()">导出用户</button>
                    </div>
                    <button class="btn btn-primary" onclick="showCreateUserModal()">+ 新增用户</button>
                </div>
                <div class="card"><div class="table-wrap">
                <table><thead><tr>
                    <th style="width:40px"><input type="checkbox" onchange="toggleAllUsers(this.checked)"></th>
                    <th>ID</th><th>用户名</th><th>昵称</th><th>手机号</th><th>类型</th><th>部门</th><th>角色</th><th>标签</th><th>状态</th><th>创建时间</th><th>操作</th>
                </tr></thead><tbody>
                ${d.users.length ? d.users.map(u => `
                    <tr>
                        <td><input type="checkbox" class="user-checkbox" value="${u.id}" onchange="toggleUser(${u.id}, this.checked)"></td>
                        <td>${u.id}</td>
                        <td><strong>${u.username}</strong></td>
                        <td>${u.nickname || "-"}</td>
                        <td>${u.phone || "-"}</td>
                        <td><span class="badge badge-info">${u.user_type === "internal" ? "内部" : "外部"}</span></td>
                        <td>${u.department || "-"}</td>
                        <td>${u.is_staff ? '<span class="badge badge-active" style="margin-right:4px">租户管理员</span> ' : ''}${(u.role_names || []).length ? u.role_names.map(r => `<span class="perm-tag">${r}</span>`).join("") : u.is_staff ? '' : '<span style="color:var(--text-light)">-</span>'}</td>
                        <td>${(u.tags || []).length ? u.tags.map(t => `<span class="badge" style="background:${t.color}20;color:${t.color};border-color:${t.color}">${t.name}</span>`).join(" ") : '<span style="color:var(--text-light)">-</span>'}</td>
                        <td><span class="badge ${u.status ? 'badge-active' : 'badge-disabled'}">${u.status ? "正常" : "禁用"}</span></td>
                        <td>${formatTime(u.created_at)}</td>
                        <td style="white-space:nowrap">
                            <button class="btn btn-sm btn-text" onclick="showEditUserModal(${u.id})">编辑</button>
                            <button class="btn btn-sm btn-text" onclick="showUserProfileModal(${u.id})">资料</button>
                            <button class="btn btn-sm btn-text" onclick="showUserTagsModal(${u.id})">标签</button>
                            <button class="btn btn-sm btn-text" onclick="toggleUserStatus(${u.id},${u.status})">${u.status ? "禁用" : "启用"}</button>
                            <button class="btn btn-sm btn-text" onclick="showResetPasswordModal(${u.id},'${u.username}')">重置密码</button>
                            ${u.status ? `<button class="btn btn-sm btn-text" onclick="deleteUser(${u.id})" style="color:var(--danger)">删除</button>` : ''}
                        </td>
                    </tr>`).join("") : '<tr><td colspan="11"><div class="empty-state">暂无数据</div></td></tr>'}
                </tbody></table></div>
                ${renderPagination(d.total, page, pageSize, p => { page = p; load(); })}
                </div>`;
        } catch (e) { container.innerHTML = `<div class="empty-state">加载失败: ${e.message}</div>`; }
    }
    load();
}

async function showCreateUserModal() {
    const res = await apiCall(API.admin + "/departments");
    const depts = res ? res.data.departments || [] : [];
    
    const buildDeptOptions = (items, parentId = null, prefix = "") => {
        return items
            .filter(d => d.parent_id === parentId)
            .map(d => `<option value="${d.id}">${prefix}${d.name}</option>` + buildDeptOptions(items, d.id, prefix + "├─ "))
            .join("");
    };

    openModal(`
        <div class="modal-header"><h2>新增用户</h2><button class="modal-close" onclick="closeModal()">&times;</button></div>
        <form id="create-user-form" onsubmit="return false">
            <div class="form-group"><label>用户名</label><input id="cu-username" placeholder="留空将自动生成（优先使用手机号）"></div>
            <div class="form-group"><label>密码</label><input type="password" id="cu-password" placeholder="留空将自动生成随机密码"></div>
            <div class="form-group"><label>用户类型</label>
                <select id="cu-type"><option value="internal">内部用户</option><option value="external">外部用户</option></select></div>
            <div class="form-group"><label>昵称</label><input id="cu-nickname"></div>
            <div class="form-group"><label>邮箱</label><input type="email" id="cu-email"></div>
            <div class="form-group"><label>手机号</label><input id="cu-phone"></div>
            <div class="form-group"><label>部门</label>
                <select id="cu-dept">
                    <option value="">请选择部门</option>
                    ${buildDeptOptions(depts)}
                </select>
            </div>
            <div class="form-group" style="flex-direction:row;align-items:center;gap:10px;padding-top:4px">
                <label style="margin-bottom:0;cursor:pointer">
                    <input type="checkbox" id="cu-is-staff" style="width:auto;margin-right:6px">
                    租户管理员
                </label>
                <span style="font-size:12px;color:var(--text-light)">勾选后该用户可以登录管理后台</span>
            </div>
            <div class="modal-footer">
                <button class="btn btn-text" onclick="closeModal()">取消</button>
                <button class="btn btn-primary" onclick="createUser()">确认创建</button>
            </div>
        </form>`);
}

async function createUser() {
    const deptId = document.getElementById("cu-dept").value;
    const data = {
        username: document.getElementById("cu-username").value.trim(),
        password: document.getElementById("cu-password").value.trim(),
        user_type: document.getElementById("cu-type").value,
        nickname: document.getElementById("cu-nickname").value.trim() || null,
        email: document.getElementById("cu-email").value.trim() || null,
        phone: document.getElementById("cu-phone").value.trim() || null,
        dept_id: deptId ? parseInt(deptId) : null,
        is_staff: document.getElementById("cu-is-staff").checked,
    };
    try {
        const res = await apiCall(API.admin + "/users", { method: "POST", body: JSON.stringify(data) });
        if (!res) return;
        if (res.code < 0) { showToast(res.message, "error"); return; }
        const msg = res.data._generated_username
            ? `创建成功！用户名: ${res.data._generated_username}，密码: ${res.data._generated_password}`
            : "用户创建成功";
        showToast(msg, "success");
        closeModal();
        switchPage("users");
    } catch (e) { showToast(e.message, "error"); }
}

async function showEditUserModal(id) {
    try {
        const [userRes, rolesRes, deptRes] = await Promise.all([
            apiCall(API.admin + "/users/" + id),
            apiCall(API.admin + "/roles"),
            apiCall(API.admin + "/departments"),
        ]);
        if (!userRes) return;
        const u = userRes.data;
        const roles = rolesRes ? rolesRes.data.roles : [];
        const assignedRoles = u.role_ids || [];
        const depts = deptRes ? deptRes.data.departments || [] : [];

        const buildDeptOptions = (items, parentId = null, prefix = "") => {
            return items
                .filter(d => d.parent_id === parentId)
                .map(d => `<option value="${d.id}" ${u.dept_id === d.id ? 'selected' : ''}>${prefix}${d.name}</option>` + buildDeptOptions(items, d.id, prefix + "├─ "))
                .join("");
        };

        openModal(`
            <div class="modal-header"><h2>编辑用户 #${id}</h2><button class="modal-close" onclick="closeModal()">&times;</button></div>
            <form id="edit-user-form" onsubmit="return false">
                <div class="form-group"><label>用户名</label><input value="${u.username}" disabled style="background:#f1f5f9"></div>
                <div class="form-group"><label>昵称</label><input id="eu-nickname" value="${u.nickname || ""}"></div>
                <div class="form-group"><label>邮箱</label><input id="eu-email" value="${u.email || ""}"></div>
                <div class="form-group"><label>手机号</label><input id="eu-phone" value="${u.phone || ""}"></div>
                <div class="form-group"><label>部门</label>
                    <select id="eu-dept">
                        <option value="">请选择部门</option>
                        ${buildDeptOptions(depts)}
                    </select>
                </div>
                <div class="form-group"><label>角色分配</label>
                    <div class="perm-grid" id="eu-roles-container">
                        ${roles.length ? roles.map(r => `
                            <label class="perm-item ${assignedRoles.includes(r.id) ? 'selected' : ''}" onclick="event.preventDefault();this.classList.toggle('selected');var cb=this.querySelector('input');cb.checked=!cb.checked">
                                <input type="checkbox" value="${r.id}" ${assignedRoles.includes(r.id) ? 'checked' : ''} style="display:none">
                                <span class="perm-tag">${r.code}</span> ${r.name}
                            </label>`).join("") : '<span style="color:var(--text-light)">暂无角色</span>'}
                    </div>
                </div>
                <div class="form-group" style="flex-direction:row;align-items:center;gap:10px;padding-top:4px">
                    <label style="margin-bottom:0;cursor:pointer">
                        <input type="checkbox" id="eu-is-staff" style="width:auto;margin-right:6px" ${u.is_staff ? 'checked' : ''}>
                        租户管理员
                    </label>
                    <span style="font-size:12px;color:var(--text-light)">勾选后该用户可以登录管理后台</span>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-text" onclick="closeModal()">取消</button>
                    <button class="btn btn-primary" onclick="editUser(${id})">保存</button>
                </div>
            </form>`);
    } catch (e) { showToast(e.message, "error"); }
}

async function editUser(id) {
    const deptId = document.getElementById("eu-dept").value;
    const data = {
        nickname: document.getElementById("eu-nickname").value.trim() || null,
        email: document.getElementById("eu-email").value.trim() || null,
        phone: document.getElementById("eu-phone").value.trim() || null,
        dept_id: deptId ? parseInt(deptId) : null,
        is_staff: document.getElementById("eu-is-staff").checked,
    };
    try {
        const res = await apiCall(API.admin + "/users/" + id, { method: "PUT", body: JSON.stringify(data) });
        if (!res) return;
        if (res.code < 0) { showToast(res.message, "error"); return; }

        const roleIds = Array.from(document.querySelectorAll("#eu-roles-container input:checked")).map(el => parseInt(el.value));
        const roleRes = await apiCall(API.admin + "/users/" + id + "/roles", {
            method: "PUT", body: JSON.stringify({ role_ids: roleIds }),
        });
        if (roleRes && roleRes.code < 0) {
            showToast("角色更新失败: " + roleRes.message, "error");
        }

        showToast("用户信息已更新", "success");
        closeModal();
        switchPage("users");
    } catch (e) { showToast("保存失败: " + e.message, "error"); }
}

async function showUserProfileModal(userId) {
    try {
        const res = await apiCall(API.admin + "/users/" + userId + "/profile");
        if (!res) return;
        const p = res.data;
        
        openModal(`
            <div class="modal-header"><h2>用户资料 #${userId}</h2><button class="modal-close" onclick="closeModal()">&times;</button></div>
            <form id="edit-profile-form" onsubmit="return false" style="max-height:60vh;overflow-y:auto">
                <div class="form-group"><label>头像 URL</label><input id="up-avatar" value="${p.avatar || ""}" placeholder="头像图片URL"></div>
                <div class="form-group"><label>真实姓名</label><input id="up-real-name" value="${p.real_name || ""}"></div>
                <div class="form-group"><label>性别</label>
                    <select id="up-gender">
                        <option value="">请选择</option>
                        <option value="male" ${p.gender === 'male' ? 'selected' : ''}>男</option>
                        <option value="female" ${p.gender === 'female' ? 'selected' : ''}>女</option>
                        <option value="other" ${p.gender === 'other' ? 'selected' : ''}>其他</option>
                    </select>
                </div>
                <div class="form-group"><label>出生日期</label><input type="date" id="up-birthday" value="${p.birthday || ""}"></div>
                <div class="form-group"><label>身份证号</label><input id="up-id-card" value="${p.id_card || ""}"></div>
                <div class="form-group"><label>国籍</label><input id="up-nationality" value="${p.nationality || ""}"></div>
                <div class="form-group"><label>联系地址</label><input id="up-address" value="${p.address || ""}"></div>
                <div class="form-group"><label>邮政编码</label><input id="up-zip-code" value="${p.zip_code || ""}"></div>
                <div class="form-group"><label>紧急联系人</label><input id="up-emergency-contact" value="${p.emergency_contact || ""}"></div>
                <div class="form-group"><label>紧急联系电话</label><input id="up-emergency-phone" value="${p.emergency_phone || ""}"></div>
                <div class="form-group"><label>职位</label><input id="up-job-title" value="${p.job_title || ""}"></div>
                <div class="form-group"><label>员工编号</label><input id="up-employee-id" value="${p.employee_id || ""}"></div>
                <div class="form-group"><label>入职日期</label><input type="date" id="up-hire-date" value="${p.hire_date || ""}"></div>
                <div class="form-group"><label>工作邮箱</label><input type="email" id="up-work-email" value="${p.work_email || ""}"></div>
                <div class="form-group"><label>工作电话</label><input id="up-work-phone" value="${p.work_phone || ""}"></div>
                <div class="form-group"><label>微信号</label><input id="up-wechat" value="${p.wechat || ""}"></div>
                <div class="form-group"><label>QQ号</label><input id="up-qq" value="${p.qq || ""}"></div>
                <div class="form-group"><label>微博账号</label><input id="up-weibo" value="${p.weibo || ""}"></div>
                <div class="form-group"><label>个人简介</label><textarea id="up-bio" rows="3" placeholder="个人简介">${p.bio || ""}</textarea></div>
                <div class="form-group"><label>兴趣爱好</label><input id="up-interests" value="${p.interests || ""}"></div>
                <div class="form-group"><label>标签 (JSON)</label><input id="up-tags" value="${typeof p.tags === 'string' ? p.tags : JSON.stringify(p.tags || {})}" placeholder='["标签1", "标签2"]'></div>
                <div class="form-group"><label>扩展数据 (JSON)</label><textarea id="up-extra-data" rows="3" placeholder='{"key": "value"}'>${typeof p.extra_data === 'string' ? p.extra_data : JSON.stringify(p.extra_data || {})}</textarea></div>
                <div class="modal-footer">
                    <button class="btn btn-text" onclick="closeModal()">取消</button>
                    <button class="btn btn-primary" onclick="saveUserProfile(${userId})">保存</button>
                </div>
            </form>`);
    } catch (e) { showToast(e.message, "error"); }
}

async function saveUserProfile(userId) {
    try {
        const parseJson = (val) => {
            if (!val) return null;
            try { return JSON.parse(val); }
            catch { return val; }
        };
        
        const data = {
            avatar: document.getElementById("up-avatar").value.trim() || null,
            real_name: document.getElementById("up-real-name").value.trim() || null,
            gender: document.getElementById("up-gender").value || null,
            birthday: document.getElementById("up-birthday").value || null,
            id_card: document.getElementById("up-id-card").value.trim() || null,
            nationality: document.getElementById("up-nationality").value.trim() || null,
            address: document.getElementById("up-address").value.trim() || null,
            zip_code: document.getElementById("up-zip-code").value.trim() || null,
            emergency_contact: document.getElementById("up-emergency-contact").value.trim() || null,
            emergency_phone: document.getElementById("up-emergency-phone").value.trim() || null,
            job_title: document.getElementById("up-job-title").value.trim() || null,
            employee_id: document.getElementById("up-employee-id").value.trim() || null,
            hire_date: document.getElementById("up-hire-date").value || null,
            work_email: document.getElementById("up-work-email").value.trim() || null,
            work_phone: document.getElementById("up-work-phone").value.trim() || null,
            wechat: document.getElementById("up-wechat").value.trim() || null,
            qq: document.getElementById("up-qq").value.trim() || null,
            weibo: document.getElementById("up-weibo").value.trim() || null,
            bio: document.getElementById("up-bio").value.trim() || null,
            interests: document.getElementById("up-interests").value.trim() || null,
            tags: parseJson(document.getElementById("up-tags").value),
            extra_data: parseJson(document.getElementById("up-extra-data").value),
        };
        
        const res = await apiCall(API.admin + "/users/" + userId + "/profile", {
            method: "PUT", body: JSON.stringify(data),
        });
        if (!res) return;
        if (res.code < 0) { showToast(res.message, "error"); return; }
        
        showToast("资料已更新", "success");
        closeModal();
        switchPage("users");
    } catch (e) { showToast("保存失败: " + e.message, "error"); }
}

async function toggleUserStatus(id, current) {
    if (!confirm(`确定${current ? "禁用" : "启用"}该用户吗？`)) return;
    try {
        const res = await apiCall(API.admin + "/users/" + id + "/status", {
            method: "PATCH", body: JSON.stringify({ status: current ? 0 : 1 }),
        });
        if (!res) return;
        if (res.code < 0) { showToast(res.message, "error"); return; }
        showToast("状态已更新", "success");
        switchPage("users");
    } catch (e) { showToast(e.message, "error"); }
}

async function deleteUser(id) {
    if (!confirm("确定删除该用户吗？此操作不可恢复。")) return;
    try {
        const res = await apiCall(API.admin + "/users/" + id, { method: "DELETE" });
        if (!res) return;
        if (res.code < 0) { showToast(res.message, "error"); return; }
        showToast("用户已删除", "success");
        switchPage("users");
    } catch (e) { showToast(e.message, "error"); }
}

function showResetPasswordModal(id, username) {
    openModal(`
        <div class="modal-header"><h2>重置密码</h2><button class="modal-close" onclick="closeModal()">&times;</button></div>
        <p style="margin-bottom:16px;color:var(--text-secondary)">用户: <strong>${username}</strong></p>
        <form onsubmit="return false">
            <div class="form-group"><label>新密码 *</label><input type="password" id="rp-password" required minlength="8"></div>
            <div class="modal-footer">
                <button class="btn btn-text" onclick="closeModal()">取消</button>
                <button class="btn btn-primary" onclick="resetPassword(${id})">确认重置</button>
            </div>
        </form>`);
}

async function resetPassword(id) {
    const pw = document.getElementById("rp-password").value.trim();
    if (!pw || pw.length < 8) { showToast("密码至少8位", "error"); return; }
    try {
        const res = await apiCall(API.admin + "/users/" + id + "/reset-password", {
            method: "POST", body: JSON.stringify({ new_password: pw }),
        });
        if (!res) return;
        if (res.code < 0) { showToast(res.message, "error"); return; }
        showToast("密码已重置", "success");
        closeModal();
    } catch (e) { showToast(e.message, "error"); }
}

function toggleAllUsers(checked) {
    document.querySelectorAll(".user-checkbox").forEach(cb => {
        cb.checked = checked;
        const id = parseInt(cb.value);
        if (checked) {
            if (!batchUserIds.includes(id)) batchUserIds.push(id);
        } else {
            batchUserIds = batchUserIds.filter(i => i !== id);
        }
    });
}

function toggleUser(id, checked) {
    if (checked) {
        if (!batchUserIds.includes(id)) batchUserIds.push(id);
    } else {
        batchUserIds = batchUserIds.filter(i => i !== id);
    }
}

async function batchAction(action) {
    if (!batchUserIds.length) { showToast("请先选择用户", "error"); return; }
    const actionMap = {
        enable: { label: "启用", method: "PATCH", url: id => API.admin + "/users/" + id + "/status", body: () => JSON.stringify({ status: 1 }) },
        disable: { label: "禁用", method: "PATCH", url: id => API.admin + "/users/" + id + "/status", body: () => JSON.stringify({ status: 0 }) },
        delete: { label: "删除", method: "DELETE", url: id => API.admin + "/users/" + id, body: () => null },
    };
    const act = actionMap[action];
    if (!act) return;
    if (!confirm(`确定${act.label}选中的 ${batchUserIds.length} 个用户吗？${action === 'delete' ? '此操作不可恢复。' : ''}`)) return;
    try {
        for (const id of batchUserIds) {
            const opts = { method: act.method };
            const body = act.body();
            if (body) opts.body = body;
            await apiCall(act.url(id), opts);
        }
        showToast("批量" + act.label + "成功", "success");
        batchUserIds = [];
        switchPage("users");
    } catch (e) {
        showToast("批量操作失败: " + e.message, "error");
    }
}

function showImportUsers() {
    openModal(`
        <div class="modal-header"><h2>导入用户</h2><button class="modal-close" onclick="closeModal()">&times;</button></div>
        <form onsubmit="return false">
            <div class="form-group">
                <label>选择CSV文件</label>
                <input type="file" id="import-csv-file" accept=".csv" style="padding:8px 0">
            </div>
            <div style="background:#f8f9fa;padding:12px;border-radius:var(--radius-sm);margin-bottom:16px;font-size:13px;color:var(--text-secondary);line-height:1.8">
                <strong>CSV格式要求：</strong><br>
                第一行为列标题，支持以下列：<br>
                username（必填）, password（必填）, nickname, email, phone, department, user_type<br>
                文件编码请使用 UTF-8。
            </div>
            <div class="modal-footer">
                <button class="btn btn-text" onclick="closeModal()">取消</button>
                <button class="btn btn-primary" onclick="importUsersFromCSV()">开始导入</button>
            </div>
        </form>`);
}

async function importUsersFromCSV() {
    const fileInput = document.getElementById("import-csv-file");
    if (!fileInput.files || !fileInput.files[0]) { showToast("请选择文件", "error"); return; }
    const file = fileInput.files[0];
    const text = await file.text();
    const lines = text.trim().split("\n");
    if (lines.length < 2) { showToast("CSV文件至少需要包含标题行和一条数据", "error"); return; }
    const headers = lines[0].split(",").map(h => h.trim().toLowerCase());
    const results = { success: 0, fail: 0, errors: [] };
    for (let i = 1; i < lines.length; i++) {
        const vals = lines[i].split(",").map(v => v.trim());
        const row = {};
        headers.forEach((h, idx) => { row[h] = vals[idx] || ""; });
        if (!row.username || !row.password) {
            results.fail++;
            results.errors.push(`第${i + 1}行: 缺少username或password`);
            continue;
        }
        try {
            const res = await apiCall(API.admin + "/users", {
                method: "POST",
                body: JSON.stringify({
                    username: row.username,
                    password: row.password,
                    nickname: row.nickname || null,
                    email: row.email || null,
                    phone: row.phone || null,
                    department: row.department || null,
                    user_type: row.user_type || "internal",
                }),
            });
            if (!res) { results.fail++; results.errors.push(`第${i + 1}行: 请求失败`); continue; }
            if (res.code < 0) { results.fail++; results.errors.push(`第${i + 1}行: ${res.message}`); continue; }
            results.success++;
        } catch (e) {
            results.fail++;
            results.errors.push(`第${i + 1}行: ${e.message}`);
        }
    }
    closeModal();
    let msg = `导入完成: 成功 ${results.success} 条, 失败 ${results.fail} 条`;
    if (results.errors.length) {
        msg += "<br><br>" + results.errors.slice(0, 10).map(e => "• " + e).join("<br>");
        if (results.errors.length > 10) msg += `<br>...以及另外 ${results.errors.length - 10} 条错误`;
    }
    openModal(`
        <div class="modal-header"><h2>导入结果</h2><button class="modal-close" onclick="closeModal()">&times;</button></div>
        <div style="line-height:2">${msg}</div>
        <div class="modal-footer"><button class="btn btn-primary" onclick="closeModal();switchPage('users')">确定</button></div>`);
}

async function exportUsers() {
    try {
        const params = new URLSearchParams({ page: 1, page_size: 99999 });
        const res = await apiCall(API.admin + "/users?" + params);
        if (!res) return;
        const users = res.data.users;
        const csv = "\uFEFFID,用户名,昵称,手机号,邮箱,类型,部门,状态,创建时间\n" +
            users.map(u =>
                `"${u.id}","${u.username}","${u.nickname || ""}","${u.phone || ""}","${u.email || ""}","${u.user_type}","${u.department || ""}","${u.status ? '正常' : '禁用'}","${formatTime(u.created_at)}"`
            ).join("\n");
        const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "用户数据_" + new Date().toISOString().slice(0, 10) + ".csv";
        a.click();
        URL.revokeObjectURL(url);
        showToast("导出成功", "success");
    } catch (e) {
        showToast("导出失败: " + e.message, "error");
    }
}

// ================== APPLICATIONS ==================

async function renderApplications(container) {
    let page = 1, search = "", status = "";
    const pageSize = 20;

    async function load() {
        const params = new URLSearchParams({ page, page_size: pageSize });
        if (search) params.set("search", search);
        if (status) params.set("status", status);
        container.innerHTML = '<div class="loading"></div>';
        try {
            const res = await apiCall(API.admin + "/applications?" + params);
            if (!res) return;
            const d = res.data;
            container.innerHTML = `
                <div class="toolbar">
                    <div class="search-bar">
                        <input type="text" id="app-search" placeholder="搜索应用名称" value="${search}" onkeydown="if(event.key==='Enter'){search=this.value;renderApplications(document.getElementById('page-content'))}">
                        <select id="app-status-filter" onchange="status=this.value;renderApplications(document.getElementById('page-content'))">
                            <option value="">全部状态</option>
                            <option value="true" ${status==='true'?'selected':''}>启用</option>
                            <option value="false" ${status==='false'?'selected':''}>禁用</option>
                        </select>
                        <button class="btn btn-primary" onclick="document.getElementById('app-search').value='';search='';status='';renderApplications(document.getElementById('page-content'))">重置</button>
                    </div>
                    <button class="btn btn-primary" onclick="showCreateAppModal()">+ 注册应用</button>
                </div>
                <div class="card"><div class="table-wrap">
                <table><thead><tr>
                    <th>ID</th><th>名称</th><th>AppKey</th><th>回调地址</th><th>默认访问</th><th>状态</th><th>创建时间</th><th>操作</th>
                </tr></thead><tbody>
                ${d.apps.length ? d.apps.map(a => `
                    <tr>
                        <td>${a.id}</td>
                        <td><strong>${a.name}</strong></td>
                        <td style="font-family:monospace;font-size:12px">${a.app_key}</td>
                        <td style="max-width:150px;overflow:hidden;text-overflow:ellipsis">${(a.callback_urls||[]).join(", ") || "-"}</td>
                        <td>${(a.default_access_user_types||[]).join(", ") || "-"}</td>
                        <td><span class="badge ${a.status ? 'badge-active' : 'badge-disabled'}">${a.status ? "启用" : "禁用"}</span></td>
                        <td>${formatTime(a.created_at)}</td>
                        <td style="white-space:nowrap">
                            <button class="btn btn-sm btn-text" onclick="showEditAppModal(${a.id})">编辑</button>
                            <button class="btn btn-sm btn-text" onclick="toggleAppStatus(${a.id},${a.status})">${a.status ? "禁用" : "启用"}</button>
                            <button class="btn btn-sm btn-text" onclick="showAppSecret(${a.id})">查看密钥</button>
                            <button class="btn btn-sm btn-text" onclick="showAppApiStats(${a.id})">API统计</button>
                        </td>
                    </tr>`).join("") : '<tr><td colspan="8"><div class="empty-state">暂无数据</div></td></tr>'}
                </tbody></table></div>
                ${renderPagination(d.total, page, pageSize, p => { page = p; load(); })}
                </div>`;
        } catch (e) { container.innerHTML = `<div class="empty-state">加载失败: ${e.message}</div>`; }
    }
    load();
}

function showCreateAppModal() {
    openModal(`
        <div class="modal-header"><h2>注册应用</h2><button class="modal-close" onclick="closeModal()">&times;</button></div>
        <form id="create-app-form" onsubmit="return false">
            <div class="form-group"><label>应用名称 *</label><input id="ca-name" required></div>
            <div class="form-group"><label>默认访问用户类型</label>
                <div style="display:flex;gap:16px;padding:4px 0">
                    <label style="display:flex;align-items:center;gap:4px"><input type="checkbox" value="internal" id="ca-type-internal"> 内部用户</label>
                    <label style="display:flex;align-items:center;gap:4px"><input type="checkbox" value="external" id="ca-type-external"> 外部用户</label>
                </div></div>
            <div class="form-group"><label>回调地址（每行一个）</label>
                <textarea id="ca-urls" rows="3" placeholder="https://example.com/callback" style="width:100%;padding:8px 12px;border:1px solid var(--border);border-radius:var(--radius-sm);font-size:14px"></textarea></div>
            <div class="modal-footer">
                <button class="btn btn-text" onclick="closeModal()">取消</button>
                <button class="btn btn-primary" onclick="createApp()">确认注册</button>
            </div>
        </form>`);
}

async function createApp() {
    const urls = document.getElementById("ca-urls").value.trim().split("\n").filter(Boolean);
    const types = [];
    if (document.getElementById("ca-type-internal").checked) types.push("internal");
    if (document.getElementById("ca-type-external").checked) types.push("external");
    const data = {
        name: document.getElementById("ca-name").value.trim(),
        callback_urls: urls.length ? urls : null,
        default_access_user_types: types.length ? types : null,
    };
    if (!data.name) { showToast("应用名称不能为空", "error"); return; }
    try {
        const res = await apiCall(API.admin + "/applications", { method: "POST", body: JSON.stringify(data) });
        if (!res) return;
        if (res.code < 0) { showToast(res.message, "error"); return; }
        const secret = res.data.app_secret_raw;
        closeModal();
        showToast("应用注册成功", "success");
        if (secret) {
            openModal(`
                <div class="modal-header"><h2>应用注册成功</h2><button class="modal-close" onclick="closeModal()">&times;</button></div>
                <p style="margin-bottom:12px;color:var(--text-secondary)">请保存以下密钥，关闭后不再显示：</p>
                <div style="background:#f1f5f9;padding:12px;border-radius:var(--radius-sm);margin-bottom:16px">
                    <div style="margin-bottom:8px"><label style="font-size:12px;color:var(--text-secondary)">AppKey</label><div style="font-family:monospace;font-size:13px">${res.data.app_key}</div></div>
                    <div><label style="font-size:12px;color:var(--text-secondary)">AppSecret</label><div style="font-family:monospace;font-size:13px">${secret}</div></div>
                </div>
                <button class="btn btn-primary btn-block" onclick="closeModal();switchPage('applications')">我已保存，返回列表</button>`);
        } else {
            switchPage("applications");
        }
    } catch (e) { showToast(e.message, "error"); }
}

async function showEditAppModal(id) {
    try {
        const res = await apiCall(API.admin + "/applications/" + id);
        if (!res) return;
        const a = res.data;
        const types = a.default_access_user_types || [];
        const assignedPerms = a.permission_ids || [];
        openModal(`
            <div class="modal-header"><h2>编辑应用 #${id}</h2><button class="modal-close" onclick="closeModal()">&times;</button></div>
            <form onsubmit="return false">
                <div class="form-group"><label>应用名称</label><input id="ea-name" value="${a.name}"></div>
                <div class="form-group"><label>默认访问用户类型</label>
                    <div style="display:flex;gap:16px;padding:4px 0">
                        <label style="display:flex;align-items:center;gap:4px"><input type="checkbox" value="internal" id="ea-type-internal" ${types.includes("internal")?"checked":""}> 内部用户</label>
                        <label style="display:flex;align-items:center;gap:4px"><input type="checkbox" value="external" id="ea-type-external" ${types.includes("external")?"checked":""}> 外部用户</label>
                    </div></div>
                <div class="form-group"><label>回调地址（每行一个）</label>
                    <textarea id="ea-urls" rows="3" style="width:100%;padding:8px 12px;border:1px solid var(--border);border-radius:var(--radius-sm)">${(a.callback_urls||[]).join("\\n")}</textarea></div>
                <div class="form-group"><label>权限配置</label>
                    <div id="ea-permissions-section" style="padding:4px 0;min-height:40px"><span style="color:var(--text-light)">加载中...</span></div></div>
                <div class="panel-section-title">微信登录配置（选填）</div>
                <div class="form-group"><label>微信小程序 AppID</label><input id="ea-wx-mp-id" value="${a.wechat_mp_app_id||''}" placeholder="微信小程序 AppID"></div>
                <div class="form-group"><label>微信小程序 AppSecret</label><input type="password" id="ea-wx-mp-secret" value="${a.wechat_mp_app_secret||''}" placeholder="输入新值将更新，留空保持不变"></div>
                <div class="form-group"><label>微信网页 AppID</label><input id="ea-wx-web-id" value="${a.wechat_web_app_id||''}" placeholder="微信网页 AppID"></div>
                <div class="form-group"><label>微信网页 AppSecret</label><input type="password" id="ea-wx-web-secret" value="${a.wechat_web_app_secret||''}" placeholder="输入新值将更新，留空保持不变"></div>
                <div class="modal-footer">
                    <button class="btn btn-text" onclick="closeModal()">取消</button>
                    <button class="btn btn-primary" onclick="editApp(${id})">保存</button>
                </div>
            </form>`);
        loadAppPermissions(id, assignedPerms);
    } catch (e) { showToast(e.message, "error"); }
}

async function editApp(id) {
    const urls = document.getElementById("ea-urls").value.trim().split("\n").filter(Boolean);
    const types = [];
    if (document.getElementById("ea-type-internal").checked) types.push("internal");
    if (document.getElementById("ea-type-external").checked) types.push("external");
    const permIds = Array.from(document.querySelectorAll("#ea-permissions-section input[type=checkbox]:checked")).map(el => parseInt(el.value));
    const data = {
        name: document.getElementById("ea-name").value.trim(),
        callback_urls: urls.length ? urls : null,
        default_access_user_types: types.length ? types : null,
        permission_ids: permIds.length ? permIds : null,
        wechat_mp_app_id: document.getElementById("ea-wx-mp-id").value.trim() || null,
        wechat_mp_app_secret: document.getElementById("ea-wx-mp-secret").value.trim() || null,
        wechat_web_app_id: document.getElementById("ea-wx-web-id").value.trim() || null,
        wechat_web_app_secret: document.getElementById("ea-wx-web-secret").value.trim() || null,
    };
    if (!data.name) { showToast("应用名称不能为空", "error"); return; }
    try {
        const res = await apiCall(API.admin + "/applications/" + id, { method: "PUT", body: JSON.stringify(data) });
        if (!res) return;
        if (res.code < 0) { showToast(res.message, "error"); return; }
        showToast("应用已更新", "success");
        closeModal();
        switchPage("applications");
    } catch (e) { showToast(e.message, "error"); }
}

async function toggleAppStatus(id, current) {
    if (!confirm(`确定${current ? "禁用" : "启用"}该应用吗？`)) return;
    try {
        const res = await apiCall(API.admin + "/applications/" + id + "/status", {
            method: "PATCH", body: JSON.stringify({ status: !current }),
        });
        if (!res) return;
        if (res.code < 0) { showToast(res.message, "error"); return; }
        showToast("状态已更新", "success");
        switchPage("applications");
    } catch (e) { showToast(e.message, "error"); }
}

async function showAppSecret(id) {
    try {
        const res = await apiCall(API.admin + "/applications/" + id + "/regenerate-secret", {
            method: "POST",
        });
        if (!res) return;
        if (res.code < 0) { showToast(res.message, "error"); return; }
        openModal(`
            <div class="modal-header"><h2>应用密钥</h2><button class="modal-close" onclick="closeModal()">&times;</button></div>
            <p style="margin-bottom:12px;color:var(--text-secondary)">已重新生成密钥，请立即保存：</p>
            <div style="background:#f1f5f9;padding:12px;border-radius:var(--radius-sm);margin-bottom:16px">
                <div><label style="font-size:12px;color:var(--text-secondary)">AppSecret</label>
                <div style="font-family:monospace;font-size:13px;word-break:break-all">${res.data.app_secret_raw}</div></div>
            </div>
            <button class="btn btn-primary btn-block" onclick="closeModal()">我已保存</button>`);
    } catch (e) { showToast(e.message, "error"); }
}

async function showAppApiStats(id) {
    const days = prompt("统计天数（1-365，默认7天）", "7") || "7";
    try {
        const res = await apiCall(API.admin + "/applications/" + id + "/api-stats?days=" + days);
        if (!res) return;
        const d = res.data;
        let html = `
            <div class="modal-header"><h2>API调用统计 — ${d.app_name}</h2><button class="modal-close" onclick="closeModal()">&times;</button></div>
            <div style="padding:16px 0">最近 ${d.period_days} 天的调用情况：</div>`;
        if (d.daily_totals && d.daily_totals.length) {
            html += `<div class="card"><div class="card-title">每日调用趋势</div><div class="table-wrap"><table><thead><tr><th>日期</th><th>调用次数</th></tr></thead><tbody>`;
            d.daily_totals.forEach(s => {
                html += `<tr><td>${s.date}</td><td><strong>${s.count}</strong></td></tr>`;
            });
            html += `</tbody></table></div></div>`;
        }
        if (d.path_totals && d.path_totals.length) {
            html += `<div class="card" style="margin-top:16px"><div class="card-title">接口调用排行</div><div class="table-wrap"><table><thead><tr><th>API路径</th><th>调用次数</th></tr></thead><tbody>`;
            d.path_totals.forEach(s => {
                const path = s.api_path.replace("/api/v1/open/", "");
                html += `<tr><td style="font-family:monospace;font-size:12px">${path}</td><td><strong>${s.count}</strong></td></tr>`;
            });
            html += `</tbody></table></div></div>`;
        }
        if (!d.daily_totals || !d.daily_totals.length) {
            html += `<div class="empty-state">暂无调用记录</div>`;
        }
        html += `<div style="margin-top:16px"><button class="btn btn-text btn-block" onclick="showAppApiStats(${id})">刷新</button></div>`;
        openModal(html);
    } catch (e) { showToast(e.message, "error"); }
}

async function loadAppPermissions(appId, assignedPermIds) {
    try {
        const res = await apiCall(API.admin + "/permissions");
        if (!res) return;
        const allPerms = res.data.permissions || [];
        const cats = [...new Set(allPerms.map(p => p.category))];
        const section = document.getElementById("ea-permissions-section");
        if (!section) return;
        if (!allPerms.length) {
            section.innerHTML = '<span style="color:var(--text-light)">无可用权限</span>';
            return;
        }
        section.innerHTML = `<div class="perm-grid">
            ${cats.map(cat => `<div style="margin:8px 0 4px;font-weight:600;font-size:13px;color:var(--primary)">${cat}</div>`
                + allPerms.filter(p => p.category === cat).map(p => `
                <label class="perm-item ${assignedPermIds.includes(p.id) ? 'selected' : ''}" onclick="event.preventDefault();this.classList.toggle('selected');var cb=this.querySelector('input');cb.checked=!cb.checked" title="${p.description}">
                    <input type="checkbox" value="${p.id}" ${assignedPermIds.includes(p.id) ? 'checked' : ''} style="display:none">
                    <span style="display:flex;flex-direction:column;gap:2px;padding:2px 0;cursor:pointer">
                        <strong style="font-size:13px">${p.name}</strong>
                        <small style="font-size:11px;color:var(--text-light)">${p.description || p.code}</small>
                    </span>
                </label>`).join("")).join("")}
        </div>`;
    } catch (e) {
        const section = document.getElementById("ea-permissions-section");
        if (section) section.innerHTML = '<span style="color:var(--danger)">加载失败</span>';
    }
}

// ================== ROLES ==================

async function renderRoles(container) {
    container.innerHTML = '<div class="loading"></div>';
    try {
        const [roleRes, permRes] = await Promise.all([
            apiCall(API.admin + "/roles"),
            apiCall(API.admin + "/permissions"),
        ]);
        if (!roleRes) return;
        const roles = roleRes.data.roles;
        const allPerms = permRes ? permRes.data.permissions : [];

        container.innerHTML = `
            <div class="toolbar">
                <div></div>
                <button class="btn btn-primary" onclick="showCreateRoleModal(${JSON.stringify(allPerms).replace(/"/g, "'")})">+ 新增角色</button>
            </div>
            <div class="card"><div class="table-wrap">
            <table><thead><tr>
                <th>ID</th><th>角色名称</th><th>角色编码</th><th>权限</th><th>创建时间</th><th>操作</th>
            </tr></thead><tbody>
            ${roles.length ? roles.map(r => {
                const rPerms = r.permissions || [];
                const shown = rPerms.slice(0, 8);
                return `<tr>
                    <td>${r.id}</td>
                    <td><strong>${r.name}</strong></td>
                    <td><code style="background:#f1f5f9;padding:2px 6px;border-radius:3px;font-size:12px">${r.code}</code></td>
                    <td>
                        ${shown.map(p => `<span class="perm-tag" title="${p.description || p.name}">${p.name}</span>`).join("")}
                        ${rPerms.length > 8 ? `<span class="perm-tag">+${rPerms.length - 8}</span>` : ''}
                        ${!rPerms.length ? '<span style="color:var(--text-light)">无权限</span>' : ''}
                    </td>
                    <td>${formatTime(r.created_at)}</td>
                    <td><button class="btn btn-sm btn-text" onclick="showEditRoleModal(${r.id},${JSON.stringify(allPerms).replace(/"/g, "'")})">编辑</button></td>
                </tr>`;
            }).join("") : '<tr><td colspan="6"><div class="empty-state">暂无数据</div></td></tr>'}
            </tbody></table></div></div>`;
    } catch (e) { container.innerHTML = `<div class="empty-state">加载失败: ${e.message}</div>`; }
}

function showCreateRoleModal(allPerms) {
    const cats = [...new Set(allPerms.map(p => p.category))];
    openModal(`
        <div class="modal-header"><h2>新增角色</h2><button class="modal-close" onclick="closeModal()">&times;</button></div>
        <form onsubmit="return false">
            <div class="form-group"><label>角色名称 *</label><input id="cr-name" required></div>
            <div class="form-group"><label>角色编码 *</label><input id="cr-code" required placeholder="如：admin, operator"></div>
            <div class="form-group"><label>权限分配</label>
                <div class="perm-grid">
                    ${cats.map(cat => `<div style="margin:8px 0 4px;font-weight:600;font-size:13px;color:var(--primary)">${cat}</div>`
                        + allPerms.filter(p => p.category === cat).map(p => `
                        <label class="perm-item" onclick="event.preventDefault();this.classList.toggle('selected');var cb=this.querySelector('input');cb.checked=!cb.checked" title="${p.description}">
                            <input type="checkbox" value="${p.id}" style="display:none">
                            <span style="display:flex;flex-direction:column;gap:2px;padding:2px 0;cursor:pointer">
                                <strong style="font-size:13px">${p.name}</strong>
                                <small style="font-size:11px;color:var(--text-light)">${p.description || p.code}</small>
                            </span>
                        </label>`).join("")).join("")}
                </div></div>
            <div class="modal-footer">
                <button class="btn btn-text" onclick="closeModal()">取消</button>
                <button class="btn btn-primary" onclick="createRole()">确认创建</button>
            </div>
        </form>`);
}

async function createRole() {
    const name = document.getElementById("cr-name").value.trim();
    const code = document.getElementById("cr-code").value.trim();
    const permIds = Array.from(document.querySelectorAll(".perm-item input:checked")).map(el => parseInt(el.value));
    if (!name || !code) { showToast("名称和编码不能为空", "error"); return; }
    try {
        const res = await apiCall(API.admin + "/roles", {
            method: "POST", body: JSON.stringify({ name, code, permission_ids: permIds }),
        });
        if (!res) return;
        if (res.code < 0) { showToast(res.message, "error"); return; }
        showToast("角色创建成功", "success");
        closeModal();
        switchPage("roles");
    } catch (e) { showToast(e.message, "error"); }
}

async function showEditRoleModal(id, allPerms) {
    try {
        const res = await apiCall(API.admin + "/roles/" + id);
        if (!res) return;
        const r = res.data;
        const cats = [...new Set(allPerms.map(p => p.category))];
        const assigned = r.permission_ids || [];
        openModal(`
            <div class="modal-header"><h2>编辑角色 #${id}</h2><button class="modal-close" onclick="closeModal()">&times;</button></div>
            <form onsubmit="return false">
                <div class="form-group"><label>角色名称</label><input id="er-name" value="${r.name}"></div>
                <div class="form-group"><label>角色编码</label><input value="${r.code}" disabled style="background:#f1f5f9"></div>
                <div class="form-group"><label>权限分配</label>
                    <div class="perm-grid">
                        ${cats.map(cat => `<div style="margin:8px 0 4px;font-weight:600;font-size:13px;color:var(--primary)">${cat}</div>`
                            + allPerms.filter(p => p.category === cat).map(p => `
                            <label class="perm-item ${assigned.includes(p.id) ? 'selected' : ''}" onclick="event.preventDefault();this.classList.toggle('selected');var cb=this.querySelector('input');cb.checked=!cb.checked" title="${p.description}">
                                <input type="checkbox" value="${p.id}" ${assigned.includes(p.id) ? 'checked' : ''} style="display:none">
                                <span style="display:flex;flex-direction:column;gap:2px;padding:2px 0;cursor:pointer">
                                    <strong style="font-size:13px">${p.name}</strong>
                                    <small style="font-size:11px;color:var(--text-light)">${p.description || p.code}</small>
                                </span>
                            </label>`).join("")).join("")}
                    </div></div>
                <div class="modal-footer">
                    <button class="btn btn-text" onclick="closeModal()">取消</button>
                    <button class="btn btn-primary" onclick="copyRole(${id})" style="background:var(--warning)">复制角色</button>
                    <button class="btn btn-primary" onclick="editRole(${id})">保存</button>
                </div>
            </form>`);
    } catch (e) { showToast(e.message, "error"); }
}

async function editRole(id) {
    const name = document.getElementById("er-name").value.trim();
    const permIds = Array.from(document.querySelectorAll(".perm-item input:checked")).map(el => parseInt(el.value));
    if (!name) { showToast("名称不能为空", "error"); return; }
    try {
        const res = await apiCall(API.admin + "/roles/" + id, {
            method: "PUT", body: JSON.stringify({ name, permission_ids: permIds }),
        });
        if (!res) return;
        if (res.code < 0) { showToast(res.message, "error"); return; }
        showToast("角色已更新", "success");
        closeModal();
        switchPage("roles");
    } catch (e) { showToast(e.message, "error"); }
}

async function copyRole(id) {
    try {
        const res = await apiCall(API.admin + "/roles/" + id);
        if (!res) return;
        const r = res.data;
        const newName = prompt("请输入新角色名称（复制自: " + r.name + "）", r.name + "_副本");
        if (!newName) return;
        const newCode = prompt("请输入新角色编码", r.code + "_copy");
        if (!newCode) return;
        const createRes = await apiCall(API.admin + "/roles", {
            method: "POST", body: JSON.stringify({
                name: newName,
                code: newCode,
                permission_ids: r.permission_ids || [],
            }),
        });
        if (!createRes) return;
        if (createRes.code < 0) { showToast(createRes.message, "error"); return; }
        showToast("角色复制成功", "success");
        closeModal();
        switchPage("roles");
    } catch (e) { showToast(e.message, "error"); }
}

// ================== DEPARTMENTS ==================

async function renderDepartments(container) {
    container.innerHTML = '<div class="loading"></div>';
    try {
        const res = await apiCall(API.admin + "/departments");
        if (!res) return;
        const depts = res.data.departments || [];
        const buildTree = (parentId) => {
            return depts.filter(d => d.parent_id === parentId).map(d => ({
                ...d,
                children: buildTree(d.id),
            }));
        };
        const tree = buildTree(null);
        const renderTree = (nodes, depth = 0) => {
            return nodes.map(d => `
                <div style="padding-left:${depth * 24}px;display:flex;align-items:center;gap:8px;padding-top:6px;padding-bottom:6px;border-bottom:1px solid var(--border-light)">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="flex-shrink:0;color:var(--text-light)"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
                    <span style="flex:1"><strong>${d.name}</strong></span>
                    <span style="background:rgba(26,115,232,0.08);color:var(--primary);padding:0 8px;border-radius:4px;font-size:12px;font-family:monospace">${d.code || "无编码"}</span>
                    <span style="color:var(--text-secondary);font-size:13px;min-width:40px;text-align:right">${d.user_count !== undefined ? d.user_count + "人" : ""}</span>
                    <button class="btn btn-sm btn-text" onclick="showDepartmentDialog(${d.id},'${d.name.replace(/'/g, "\\'")}','',\`${(d.code || '').replace(/`/g, '\\`')}\`)">编辑</button>
                    <button class="btn btn-sm btn-text" onclick="showDepartmentDialog(null,'','${d.id}')">+ 子部门</button>
                    <button class="btn btn-sm btn-text" onclick="deleteDepartment(${d.id},'${d.name.replace(/'/g, "\\'")}')" style="color:var(--danger)">删除</button>
                </div>
                ${d.children && d.children.length ? renderTree(d.children, depth + 1) : ''}
            `).join("");
        };
        container.innerHTML = `
            <div class="toolbar">
                <div></div>
                <button class="btn btn-primary" onclick="showDepartmentDialog(null,'')">+ 新增部门</button>
            </div>
            <div class="card">
                <div class="card-title">部门结构</div>
                ${tree.length ? renderTree(tree) : '<div class="empty-state">暂无部门，请先创建</div>'}
            </div>`;
    } catch (e) { container.innerHTML = `<div class="empty-state">加载失败: ${e.message}</div>`; }
}

function showDepartmentDialog(id, name, parentId, code) {
    const isEdit = id !== null;
    const title = parentId ? "新增子部门" : (isEdit ? "编辑部门" : "新增部门");
    openModal(`
        <div class="modal-header"><h2>${title}</h2><button class="modal-close" onclick="closeModal()">&times;</button></div>
        <form onsubmit="return false">
            ${parentId ? `<div class="form-group"><label>父部门ID</label><input value="${parentId}" disabled style="background:#f1f5f9"></div>` : ''}
            <div class="form-group"><label>部门名称 *</label><input id="dept-name" value="${isEdit ? name : ''}" placeholder="如：技术部"></div>
            <div class="form-group"><label>部门编码</label><input id="dept-code" value="${isEdit ? (code || '') : ''}" placeholder="如：tech（可选）"></div>
            <div class="modal-footer">
                <button class="btn btn-text" onclick="closeModal()">取消</button>
                <button class="btn btn-primary" onclick="saveDepartment(${isEdit ? id : 'null'}, ${parentId || 'null'})">${isEdit ? "保存" : "创建"}</button>
            </div>
        </form>`);
}

async function saveDepartment(id, parentId) {
    const name = document.getElementById("dept-name").value.trim();
    const code = document.getElementById("dept-code").value.trim() || null;
    if (!name) { showToast("部门名称不能为空", "error"); return; }
    try {
        const body = { name, code };
        if (parentId) body.parent_id = parentId;
        const url = id ? API.admin + "/departments/" + id : API.admin + "/departments";
        const method = id ? "PUT" : "POST";
        const res = await apiCall(url, { method, body: JSON.stringify(body) });
        if (!res) return;
        if (res.code < 0) { showToast(res.message, "error"); return; }
        showToast(id ? "部门已更新" : "部门创建成功", "success");
        closeModal();
        switchPage("departments");
    } catch (e) { showToast(e.message, "error"); }
}

async function deleteDepartment(id, name) {
    if (!confirm(`确定删除部门"${name}"吗？子部门将一并删除。`)) return;
    try {
        const res = await apiCall(API.admin + "/departments/" + id, { method: "DELETE" });
        if (!res) return;
        if (res.code < 0) { showToast(res.message, "error"); return; }
        showToast("部门已删除", "success");
        switchPage("departments");
    } catch (e) { showToast(e.message, "error"); }
}

// ================== AUDIT LOGS ==================

async function renderAudit(container) {
    let page = 1, action = "", actor = "", dateFrom = "", dateTo = "";
    const pageSize = 20;

    async function load() {
        const params = new URLSearchParams({ page, page_size: pageSize });
        if (action) params.set("action", action);
        if (actor) params.set("actor", actor);
        if (dateFrom) params.set("date_from", dateFrom);
        if (dateTo) params.set("date_to", dateTo);
        container.innerHTML = '<div class="loading"></div>';
        try {
            const res = await apiCall(API.admin + "/audit-logs?" + params);
            if (!res) return;
            const d = res.data;
            container.innerHTML = `
                <div class="search-bar" id="audit-search-bar">
                    <input type="text" data-audit-filter="action" placeholder="操作类型" value="${action}">
                    <input type="text" data-audit-filter="actor" placeholder="操作人" value="${actor}">
                    <input type="date" data-audit-filter="dateFrom" value="${dateFrom}" style="flex:0 0 auto">
                    <span style="color:var(--text-secondary)">~</span>
                    <input type="date" data-audit-filter="dateTo" value="${dateTo}" style="flex:0 0 auto">
                    <button class="btn btn-primary" data-audit-reset>重置</button>
                    <button class="btn btn-primary" onclick="exportAuditLogs()">导出</button>
                </div>
                <div class="card"><div class="table-wrap">
                <table><thead><tr>
                    <th>时间</th><th>操作人</th><th>操作类型</th><th>资源类型</th><th>资源ID</th><th>IP</th><th>详情</th>
                </tr></thead><tbody>
                ${d.logs.length ? d.logs.map(log => `
                    <tr data-audit-detail='${JSON.stringify(log).replace(/'/g, "&#39;")}' style="cursor:pointer">
                        <td style="white-space:nowrap">${formatTime(log.created_at)}</td>
                        <td>${log.actor_name || "-"}</td>
                        <td><code style="background:#f1f5f9;padding:2px 6px;border-radius:3px;font-size:12px">${log.action}</code></td>
                        <td>${log.resource_type || "-"}</td>
                        <td>${log.resource_id || "-"}</td>
                        <td style="font-family:monospace;font-size:12px">${log.ip_address || "-"}</td>
                        <td><button class="btn btn-sm btn-text" data-audit-detail='${JSON.stringify(log).replace(/'/g, "&#39;")}'>查看</button></td>
                    </tr>`).join("") : '<tr><td colspan="7"><div class="empty-state">暂无日志</div></td></tr>'}
                </tbody></table></div>
                ${renderPagination(d.total, page, pageSize, p => { page = p; load(); })}
                </div>`;

            // 绑定搜索事件
            const bar = container.querySelector('#audit-search-bar');
            if (bar) {
                bar.querySelectorAll('[data-audit-filter]').forEach(el => {
                    el.addEventListener('change', () => {
                        const key = el.dataset.auditFilter;
                        if (key === 'action') action = el.value;
                        else if (key === 'actor') actor = el.value;
                        else if (key === 'dateFrom') dateFrom = el.value;
                        else if (key === 'dateTo') dateTo = el.value;
                        load();
                    });
                });
                bar.querySelector('[data-audit-reset]').addEventListener('click', () => {
                    action = ''; actor = ''; dateFrom = ''; dateTo = '';
                    load();
                });
            }
            // 使用事件委托监听表格中的查看按钮
            container.addEventListener('click', function __auditClick(e) {
                const btn = e.target.closest('[data-audit-detail]');
                if (btn) {
                    e.stopPropagation();
                    try {
                        const log = JSON.parse(btn.dataset.auditDetail.replace(/&#39;/g, "'"));
                        showAuditDetail(log);
                    } catch(ex) { /* ignore parse errors */ }
                }
            });
        } catch (e) { container.innerHTML = `<div class="empty-state">加载失败: ${e.message}</div>`; }
    }
    load();
}

async function exportAuditLogs() {
    try {
        const params = new URLSearchParams({ page: 1, page_size: 99999 });
        const res = await apiCall(API.admin + "/audit-logs?" + params);
        if (!res) return;
        const logs = res.data.logs;
        const csv = "\uFEFF时间,操作人,操作类型,资源类型,资源ID,IP,详情\n" +
            logs.map(log =>
                `"${formatTime(log.created_at)}","${log.actor_name || ""}","${log.action}","${log.resource_type || ""}","${log.resource_id || ""}","${log.ip_address || ""}","${(log.detail ? JSON.stringify(log.detail).replace(/"/g, '""') : "")}"`
            ).join("\n");
        const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "审计日志_" + new Date().toISOString().slice(0, 10) + ".csv";
        a.click();
        URL.revokeObjectURL(url);
        showToast("导出成功", "success");
    } catch (e) {
        showToast("导出失败: " + e.message, "error");
    }
}

function showAuditDetail(log) {
    openModal(`
        <div class="modal-header"><h2>操作详情</h2><button class="modal-close" onclick="closeModal()">&times;</button></div>
        <div style="line-height:2">
            <div><strong>时间：</strong>${formatTime(log.created_at)}</div>
            <div><strong>操作人：</strong>${log.actor_name || "-"}</div>
            <div><strong>操作类型：</strong><code style="background:#f1f5f9;padding:2px 6px;border-radius:3px">${log.action}</code></div>
            <div><strong>资源类型：</strong>${log.resource_type || "-"}</div>
            <div><strong>资源ID：</strong>${log.resource_id || "-"}</div>
            <div><strong>IP地址：</strong>${log.ip_address || "-"}</div>
            <div><strong>UserAgent：</strong><span style="font-size:12px;word-break:break-all">${log.user_agent || "-"}</span></div>
            ${log.detail ? `<div><strong>变更详情：</strong><pre style="background:#f1f5f9;padding:12px;border-radius:var(--radius-sm);margin-top:4px;font-size:12px;overflow-x:auto">${JSON.stringify(log.detail, null, 2)}</pre></div>` : ''}
        </div>
        <div class="modal-footer"><button class="btn btn-primary" onclick="closeModal()">关闭</button></div>`);
}

// ================== SMS CONFIG ==================

async function renderSmsConfig(container) {
    container.innerHTML = '<div class="loading"></div>';
    try {
        const res = await apiCall(API.admin + "/tenant-sms-config");
        const cfg = res.data || {};

        container.innerHTML = `
            <div class="page-header"><h1>短信配置</h1></div>
            <div class="card">
                <div class="card-title">自定义短信渠道</div>
                <p style="color:var(--text-secondary);margin-bottom:16px;font-size:14px">配置后，发送短信验证码将优先使用您自定义的短信服务商。留空则使用平台全局配置。</p>
                <div class="form-group">
                    <label>短信服务商</label>
                    <select id="sms-provider" class="form-control">
                        <option value="">使用平台全局配置</option>
                        <option value="mock">模拟（开发调试）</option>
                        <option value="aliyun">阿里云短信</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>AccessKey ID</label>
                    <input type="text" id="sms-access-key-id" class="form-control" placeholder="阿里云 AccessKey ID">
                </div>
                <div class="form-group">
                    <label>AccessKey Secret</label>
                    <input type="password" id="sms-access-key-secret" class="form-control" placeholder="输入新值将更新，留空保持不变">
                </div>
                <div class="form-group">
                    <label>短信签名</label>
                    <input type="text" id="sms-sign-name" class="form-control" placeholder="短信签名（如：XX科技）">
                </div>
                <div class="form-group">
                    <label>短信模板编码</label>
                    <input type="text" id="sms-template-code" class="form-control" placeholder="模板编码（如：SMS_123456）">
                </div>
                <div class="form-actions" style="display:flex;gap:12px;flex-wrap:wrap">
                    <button class="btn btn-primary" onclick="saveSmsConfig()">保存配置</button>
                    <button class="btn btn-success" onclick="showSmsTestModal()" style="background:var(--success);color:#fff">发送测试</button>
                </div>
            </div>
            <div class="card">
                <div class="card-title">使用说明</div>
                <ul style="line-height:2;font-size:14px;color:var(--text-secondary);padding-left:20px">
                    <li>仅支持 <strong>阿里云短信</strong> 服务商</li>
                    <li>配置后，调用 <code>POST /api/v1/auth/sms/send</code> 并传入 <code>app_key</code> 参数时，将使用该应用所属租户的短信配置</li>
                    <li>未传入 <code>app_key</code> 时，使用平台全局配置</li>
                    <li>AccessKey Secret 显示为 <code>***</code>，输入新值才会更新</li>
                    <li>点击 <strong>"发送测试"</strong> 将使用当前填写的配置向指定手机号发送测试短信</li>
                </ul>
            </div>`;

        if (cfg.sms_provider) document.getElementById("sms-provider").value = cfg.sms_provider;
        if (cfg.sms_access_key_id) document.getElementById("sms-access-key-id").value = cfg.sms_access_key_id;
        if (cfg.sms_sign_name) document.getElementById("sms-sign-name").value = cfg.sms_sign_name;
        if (cfg.sms_template_code) document.getElementById("sms-template-code").value = cfg.sms_template_code;

    } catch (e) {
        container.innerHTML = `<div class="error-state">加载失败: ${e.message}</div>`;
    }
}

async function saveSmsConfig() {
    const data = {
        sms_provider: document.getElementById("sms-provider").value || "",
        sms_access_key_id: document.getElementById("sms-access-key-id").value || "",
        sms_access_key_secret: document.getElementById("sms-access-key-secret").value || "",
        sms_sign_name: document.getElementById("sms-sign-name").value || "",
        sms_template_code: document.getElementById("sms-template-code").value || "",
    };
    try {
        const res = await apiCall(API.admin + "/tenant-sms-config", {
            method: "PUT",
            body: JSON.stringify(data),
        });
        if (!res || res.code < 0) {
            showToast(res ? res.message : "保存失败", "error");
            return;
        }
        showToast("短信配置保存成功", "success");
        renderSmsConfig(document.getElementById("page-content"));
    } catch (e) {
        showToast("保存失败: " + e.message, "error");
    }
}

function showSmsTestModal() {
    openModal(`
        <div class="modal-header"><h2>发送测试短信</h2><button class="modal-close" onclick="closeModal()">&times;</button></div>
        <form onsubmit="return false">
            <div class="form-group">
                <label>手机号码 *</label>
                <input type="tel" id="test-sms-phone" placeholder="请输入接收测试短信的手机号" required>
            </div>
            <div id="test-sms-result" style="display:none;padding:12px;border-radius:var(--radius-sm);margin-bottom:16px;font-size:14px;line-height:1.6"></div>
            <div class="modal-footer">
                <button class="btn btn-text" onclick="closeModal()">取消</button>
                <button class="btn btn-primary" onclick="sendTestSms()" id="test-sms-btn">发送测试</button>
            </div>
        </form>`);
    document.getElementById("test-sms-phone").focus();
}

async function sendTestSms() {
    const phone = document.getElementById("test-sms-phone").value.trim();
    if (!phone) { showToast("请输入手机号码", "error"); return; }

    const btn = document.getElementById("test-sms-btn");
    btn.disabled = true;
    btn.textContent = "发送中...";

    const resultEl = document.getElementById("test-sms-result");
    resultEl.style.display = "none";

    try {
        const res = await apiCall(API.admin + "/tenant-sms-config/test", {
            method: "POST",
            body: JSON.stringify({ phone }),
        });
        if (!res) { showToast("请求失败", "error"); return; }
        if (res.code < 0) {
            resultEl.style.display = "block";
            resultEl.style.background = "#fef2f2";
            resultEl.style.color = "#991b1b";
            resultEl.innerHTML = `<strong>发送失败</strong><br>${res.message}`;
            return;
        }
        resultEl.style.display = "block";
        resultEl.style.background = "#f0fdf4";
        resultEl.style.color = "#065f46";
        resultEl.innerHTML = `<strong>发送成功</strong><br>测试验证码已发送至 <strong>${res.data.phone}</strong><br>${res.data.message || ""}`;
        showToast("测试短信发送成功", "success");
    } catch (e) {
        resultEl.style.display = "block";
        resultEl.style.background = "#fef2f2";
        resultEl.style.color = "#991b1b";
        resultEl.innerHTML = `发送异常: ${e.message}`;
        showToast("发送失败: " + e.message, "error");
    } finally {
        btn.disabled = false;
        btn.textContent = "发送测试";
    }
}

// ================== SUPERADMIN DASHBOARD ==================

async function renderSuperadminDashboard(container) {
    container.innerHTML = '<div class="loading"></div>';
    try {
        const [statsRes, tenantGrowthRes, activityRankRes, appCallRes] = await Promise.all([
            apiCall(API.superadmin + "/global-stats"),
            apiCall(API.superadmin + "/stats/tenant-growth?days=7"),
            apiCall(API.superadmin + "/stats/tenant-activity-ranking"),
            apiCall(API.superadmin + "/stats/app-call-ranking?days=30"),
        ]);
        if (!statsRes) return;
        const s = statsRes.data;
        const tg = tenantGrowthRes ? tenantGrowthRes.data : null;
        const ar = activityRankRes ? activityRankRes.data : null;
        const ac = appCallRes ? appCallRes.data : null;

        container.innerHTML = `
            <div class="stats-grid">
                <div class="stat-card"><span class="stat-label">租户总数</span><span class="stat-value primary">${s.total_tenants}</span></div>
                <div class="stat-card"><span class="stat-label">活跃租户</span><span class="stat-value success">${s.active_tenants}</span></div>
                <div class="stat-card"><span class="stat-label">总用户数</span><span class="stat-value">${s.total_users}</span></div>
                <div class="stat-card"><span class="stat-label">活跃用户</span><span class="stat-value success">${s.active_users}</span></div>
                <div class="stat-card"><span class="stat-label">应用总数</span><span class="stat-value">${s.total_apps}</span></div>
                <div class="stat-card"><span class="stat-label">活跃应用</span><span class="stat-value primary">${s.active_apps}</span></div>
                <div class="stat-card"><span class="stat-label">角色数</span><span class="stat-value">${s.total_roles}</span></div>
            </div>
            <div class="card">
                <div class="card-title">租户增长趋势（近7天）</div>
                <div style="height:120px"><canvas id="saTenantGrowthChart"></canvas></div>
            </div>
            <div class="row" style="display:flex;gap:16px;flex-wrap:wrap">
                <div class="card" style="flex:1;min-width:320px">
                    <div class="card-title">活跃租户排行 Top 5</div>
                    ${ar && ar.rankings && ar.rankings.length
                        ? `<div class="table-wrap"><table><thead><tr><th>#</th><th>租户</th><th>活跃用户</th><th>总用户</th><th>应用数</th></tr></thead><tbody>
                        ${ar.rankings.slice(0, 5).map((t, i) => `
                            <tr><td>${i + 1}</td><td><strong>${t.tenant_name}</strong></td><td>${t.active_users}</td><td>${t.total_users}</td><td>${t.app_count}</td></tr>
                        `).join("")}</tbody></table></div>`
                        : '<div class="empty-state">暂无数据</div>'}
                </div>
                <div class="card" style="flex:1;min-width:320px">
                    <div class="card-title">应用调用排行 Top 5</div>
                    ${ac && ac.rankings && ac.rankings.length
                        ? `<div class="table-wrap"><table><thead><tr><th>#</th><th>应用</th><th>接口</th><th>调用次数</th></tr></thead><tbody>
                        ${ac.rankings.slice(0, 5).map((a, i) => {
                            const path = a.api_path ? a.api_path.replace("/api/v1/open/", "") : "-";
                            return `<tr><td>${i + 1}</td><td><strong>${a.app_name}</strong></td><td style="font-family:monospace;font-size:11px">${path}</td><td>${a.total_calls}</td></tr>`;
                        }).join("")}</tbody></table></div>`
                        : '<div class="empty-state">暂无数据</div>'}
                </div>
            </div>
            <div class="card">
                <div class="card-title">租户概览</div>
                ${s.tenant_stats && s.tenant_stats.length
                    ? `<div class="table-wrap"><table><thead><tr>
                        <th>ID</th><th>名称</th><th>标识</th><th>状态</th><th>用户数</th><th>应用数</th><th>创建时间</th>
                    </tr></thead><tbody>
                    ${s.tenant_stats.map(t => `
                        <tr>
                            <td>${t.id}</td>
                            <td><strong>${t.name}</strong></td>
                            <td><code style="background:#f1f5f9;padding:2px 6px;border-radius:3px;font-size:12px">${t.slug}</code></td>
                            <td><span class="badge ${t.status ? 'badge-active' : 'badge-disabled'}">${t.status ? "启用" : "禁用"}</span></td>
                            <td>${t.user_count}</td>
                            <td>${t.app_count}</td>
                            <td>${formatTime(t.created_at)}</td>
                        </tr>`).join("")}
                    </tbody></table></div>`
                    : '<div class="empty-state">暂无租户数据</div>'}
            </div>`;

        if (tg && tg.trend && tg.trend.length) {
            renderMiniLineChart("saTenantGrowthChart",
                tg.trend.map(d => d.date.slice(5)),
                tg.trend.map(d => d.new_tenants),
                "新增租户", "#0a9e5e");
        }
    } catch (e) {
        container.innerHTML = `<div class="empty-state">加载失败: ${e.message}</div>`;
    }
}

// ================== SUPERADMIN TENANTS ==================

async function renderSuperadminTenants(container) {
    let page = 1, search = "", status = "";
    const pageSize = 20;

    async function load() {
        const params = new URLSearchParams({ page, page_size: pageSize });
        if (search) params.set("search", search);
        if (status) params.set("status", status);
        container.innerHTML = '<div class="loading"></div>';
        try {
            const res = await apiCall(API.superadmin + "/tenants?" + params);
            if (!res) return;
            const d = res.data;
            container.innerHTML = `
                <div class="toolbar">
                    <div class="search-bar">
                        <input type="text" id="t-search" placeholder="搜索名称/标识" value="${search}" onkeydown="if(event.key==='Enter'){search=this.value;renderSuperadminTenants(document.getElementById('page-content'))}">
                        <select id="t-status-filter" onchange="status=this.value;renderSuperadminTenants(document.getElementById('page-content'))">
                            <option value="">全部状态</option>
                            <option value="true" ${status==='true'?'selected':''}>启用</option>
                            <option value="false" ${status==='false'?'selected':''}>禁用</option>
                        </select>
                        <button class="btn btn-primary" onclick="document.getElementById('t-search').value='';search='';status='';renderSuperadminTenants(document.getElementById('page-content'))">重置</button>
                    </div>
                    <button class="btn btn-primary" onclick="showCreateTenantModal()">+ 新建租户</button>
                </div>
                <div class="card"><div class="table-wrap">
                <table><thead><tr>
                    <th>ID</th><th>名称</th><th>标识</th><th>状态</th><th>创建时间</th><th>更新时间</th><th>操作</th>
                </tr></thead><tbody>
                ${d.tenants.length ? d.tenants.map(t => `
                    <tr>
                        <td>${t.id}</td>
                        <td><strong>${t.name}</strong></td>
                        <td><code style="background:#f1f5f9;padding:2px 6px;border-radius:3px;font-size:12px">${t.slug}</code></td>
                        <td><span class="badge ${t.status ? 'badge-active' : 'badge-disabled'}">${t.status ? "启用" : "禁用"}</span></td>
                        <td>${formatTime(t.created_at)}</td>
                        <td>${formatTime(t.updated_at)}</td>
                        <td style="white-space:nowrap">
                            <button class="btn btn-sm btn-text" onclick="impersonateTenant(${t.id})" style="color:var(--primary)">模拟</button>
                            <button class="btn btn-sm btn-text" onclick="showEditTenantModal(${t.id})">编辑</button>
                            <button class="btn btn-sm btn-text" onclick="toggleTenantStatus(${t.id},${t.status})">${t.status ? "禁用" : "启用"}</button>
                            <button class="btn btn-sm btn-text" onclick="deleteTenant(${t.id},'${t.name}')" style="color:var(--danger)">删除</button>
                        </td>
                    </tr>`).join("") : '<tr><td colspan="7"><div class="empty-state">暂无租户</div></td></tr>'}
                </tbody></table></div>
                ${renderPagination(d.total, page, pageSize, p => { page = p; load(); })}
                </div>`;
        } catch (e) { container.innerHTML = `<div class="empty-state">加载失败: ${e.message}</div>`; }
    }
    load();
}

function showCreateTenantModal() {
    openModal(`
        <div class="modal-header"><h2>新建租户</h2><button class="modal-close" onclick="closeModal()">&times;</button></div>
        <form id="create-tenant-form" onsubmit="return false">
            <div class="form-group"><label>企业名称 *</label><input id="ct-name" required placeholder="如：XX科技有限公司"></div>
            <div class="form-group"><label>唯一标识 *</label><input id="ct-slug" required placeholder="如：company_xxx（字母/数字/下划线）"></div>
            <div class="modal-footer">
                <button class="btn btn-text" onclick="closeModal()">取消</button>
                <button class="btn btn-primary" onclick="createTenant()">确认创建</button>
            </div>
        </form>`);
}

async function createTenant() {
    const name = document.getElementById("ct-name").value.trim();
    const slug = document.getElementById("ct-slug").value.trim();
    if (!name || !slug) { showToast("名称和标识不能为空", "error"); return; }
    try {
        const res = await apiCall(API.superadmin + "/tenants", {
            method: "POST", body: JSON.stringify({ name, slug }),
        });
        if (!res) return;
        if (res.code < 0) { showToast(res.message, "error"); return; }
        showToast("租户创建成功", "success");
        closeModal();
        switchPage("superadmin_tenants");
    } catch (e) { showToast(e.message, "error"); }
}

async function showEditTenantModal(id) {
    try {
        const res = await apiCall(API.superadmin + "/tenants/" + id);
        if (!res) return;
        const t = res.data;
        openModal(`
            <div class="modal-header"><h2>编辑租户 #${id}</h2><button class="modal-close" onclick="closeModal()">&times;</button></div>
            <form onsubmit="return false">
                <div class="form-group"><label>企业名称</label><input id="et-name" value="${t.name}"></div>
                <div class="form-group"><label>唯一标识</label><input id="et-slug" value="${t.slug}"></div>
                <div class="form-group"><label>状态</label>
                    <select id="et-status">
                        <option value="true" ${t.status ? "selected" : ""}>启用</option>
                        <option value="false" ${!t.status ? "selected" : ""}>禁用</option>
                    </select></div>
                <div class="modal-footer">
                    <button class="btn btn-text" onclick="closeModal()">取消</button>
                    <button class="btn btn-primary" onclick="editTenant(${id})">保存</button>
                </div>
            </form>`);
    } catch (e) { showToast(e.message, "error"); }
}

async function editTenant(id) {
    const data = {
        name: document.getElementById("et-name").value.trim(),
        slug: document.getElementById("et-slug").value.trim(),
        status: document.getElementById("et-status").value === "true",
    };
    if (!data.name || !data.slug) { showToast("名称和标识不能为空", "error"); return; }
    try {
        const res = await apiCall(API.superadmin + "/tenants/" + id, {
            method: "PUT", body: JSON.stringify(data),
        });
        if (!res) return;
        if (res.code < 0) { showToast(res.message, "error"); return; }
        showToast("租户已更新", "success");
        closeModal();
        switchPage("superadmin_tenants");
    } catch (e) { showToast(e.message, "error"); }
}

async function toggleTenantStatus(id, current) {
    if (!confirm(`确定${current ? "禁用" : "启用"}该租户吗？`)) return;
    try {
        const res = await apiCall(API.superadmin + "/tenants/" + id, {
            method: "PUT", body: JSON.stringify({ status: !current }),
        });
        if (!res) return;
        if (res.code < 0) { showToast(res.message, "error"); return; }
        showToast("状态已更新", "success");
        switchPage("superadmin_tenants");
    } catch (e) { showToast(e.message, "error"); }
}

async function deleteTenant(id, name) {
    if (!confirm(`确定删除租户"${name}"吗？此操作不可恢复，将同时删除该租户下的所有关联数据。`)) return;
    try {
        const res = await apiCall(API.superadmin + "/tenants/" + id, {
            method: "DELETE",
        });
        if (!res) return;
        if (res.code < 0) { showToast(res.message, "error"); return; }
        showToast("租户已删除", "success");
        switchPage("superadmin_tenants");
    } catch (e) { showToast(e.message, "error"); }
}

async function impersonateTenant(id) {
    if (!confirm("确定以超级管理员身份模拟进入该租户吗？")) return;
    try {
        const res = await apiCall(API.superadmin + "/impersonate/" + id, { method: "POST" });
        if (!res) return;
        if (res.code < 0) { showToast(res.message, "error"); return; }
        localStorage.setItem(TOKEN_KEY, res.data.access_token);
        localStorage.setItem(USER_KEY, JSON.stringify(res.data));
        showToast("已模拟进入租户", "success");
        showApp();
    } catch (e) { showToast(e.message, "error"); }
}

async function exitImpersonation() {
    if (!confirm("确定退出模拟模式吗？")) return;
    try {
        const res = await apiCall(API.superadmin + "/impersonate/exit", { method: "POST" });
        if (!res) return;
        if (res.code < 0) { showToast(res.message, "error"); return; }
        localStorage.setItem(TOKEN_KEY, res.data.access_token);
        localStorage.setItem(USER_KEY, JSON.stringify(res.data));
        showToast("已退出模拟模式", "success");
        showApp();
    } catch (e) { showToast(e.message, "error"); }
}

// ================== SUPERADMIN AUDIT LOGS ==================

async function renderSuperadminAudit(container) {
    let page = 1, action = "", actor = "", tenantId = "", dateFrom = "", dateTo = "";
    const pageSize = 20;

    async function load() {
        const params = new URLSearchParams({ page, page_size: pageSize });
        if (action) params.set("action", action);
        if (actor) params.set("actor", actor);
        if (tenantId) params.set("tenant_id", tenantId);
        if (dateFrom) params.set("date_from", dateFrom);
        if (dateTo) params.set("date_to", dateTo);
        container.innerHTML = '<div class="loading"></div>';
        try {
            const res = await apiCall(API.superadmin + "/audit-logs?" + params);
            if (!res) return;
            const d = res.data;
            container.innerHTML = `
                <div class="search-bar" id="sa-search-bar">
                    <input type="text" data-sa-filter="action" placeholder="操作类型" value="${action}">
                    <input type="text" data-sa-filter="actor" placeholder="操作人" value="${actor}">
                    <input type="text" data-sa-filter="tenantId" placeholder="租户ID" value="${tenantId}" style="flex:0 1 100px">
                    <input type="date" data-sa-filter="dateFrom" value="${dateFrom}" style="flex:0 0 auto">
                    <span style="color:var(--text-secondary)">~</span>
                    <input type="date" data-sa-filter="dateTo" value="${dateTo}" style="flex:0 0 auto">
                    <button class="btn btn-primary" data-sa-reset>重置</button>
                    <button class="btn btn-primary" onclick="exportSuperadminAuditLogs()">导出</button>
                </div>
                <div class="card"><div class="table-wrap">
                <table><thead><tr>
                    <th>时间</th><th>操作人</th><th>租户</th><th>操作类型</th><th>资源类型</th><th>资源ID</th><th>IP</th><th>详情</th>
                </tr></thead><tbody>
                ${d.logs.length ? d.logs.map(log => `
                    <tr style="cursor:pointer">
                        <td style="white-space:nowrap">${formatTime(log.created_at)}</td>
                        <td>${log.actor_name || "-"}</td>
                        <td>${log.tenant_name || log.tenant_id || "平台"}</td>
                        <td><code style="background:#f1f5f9;padding:2px 6px;border-radius:3px;font-size:12px">${log.action}</code></td>
                        <td>${log.resource_type || "-"}</td>
                        <td>${log.resource_id || "-"}</td>
                        <td style="font-family:monospace;font-size:12px">${log.ip_address || "-"}</td>
                        <td><button class="btn btn-sm btn-text" data-sa-detail='${JSON.stringify(log).replace(/'/g, "&#39;")}'>查看</button></td>
                    </tr>`).join("") : '<tr><td colspan="8"><div class="empty-state">暂无日志</div></td></tr>'}
                </tbody></table></div>
                ${renderPagination(d.total, page, pageSize, p => { page = p; load(); })}
                </div>`;

            const bar = container.querySelector('#sa-search-bar');
            if (bar) {
                bar.querySelectorAll('[data-sa-filter]').forEach(el => {
                    el.addEventListener('change', () => {
                        const key = el.dataset.saFilter;
                        if (key === 'action') action = el.value;
                        else if (key === 'actor') actor = el.value;
                        else if (key === 'tenantId') tenantId = el.value;
                        else if (key === 'dateFrom') dateFrom = el.value;
                        else if (key === 'dateTo') dateTo = el.value;
                        load();
                    });
                });
                bar.querySelector('[data-sa-reset]').addEventListener('click', () => {
                    action = ''; actor = ''; tenantId = ''; dateFrom = ''; dateTo = '';
                    load();
                });
            }
            container.addEventListener('click', function __saClick(e) {
                const btn = e.target.closest('[data-sa-detail]');
                if (btn) {
                    e.stopPropagation();
                    try {
                        const log = JSON.parse(btn.dataset.saDetail.replace(/&#39;/g, "'"));
                        showAuditDetail(log);
                    } catch(ex) { /* ignore parse errors */ }
                }
            });
        } catch (e) { container.innerHTML = `<div class="empty-state">加载失败: ${e.message}</div>`; }
    }
    load();
}

async function exportSuperadminAuditLogs() {
    try {
        const params = new URLSearchParams({ page: 1, page_size: 99999 });
        const res = await apiCall(API.superadmin + "/audit-logs?" + params);
        if (!res) return;
        const logs = res.data.logs;
        const csv = "\uFEFF时间,操作人,租户,操作类型,资源类型,资源ID,IP,详情\n" +
            logs.map(log =>
                `"${formatTime(log.created_at)}","${log.actor_name || ""}","${log.tenant_name || log.tenant_id || "平台"}","${log.action}","${log.resource_type || ""}","${log.resource_id || ""}","${log.ip_address || ""}","${(log.detail ? JSON.stringify(log.detail).replace(/"/g, '""') : "")}"`
            ).join("\n");
        const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "全局审计日志_" + new Date().toISOString().slice(0, 10) + ".csv";
        a.click();
        URL.revokeObjectURL(url);
        showToast("导出成功", "success");
    } catch (e) {
        showToast("导出失败: " + e.message, "error");
    }
}

// ================== SUPERADMIN REPORT ==================

async function renderSuperadminReport(container) {
    container.innerHTML = `
        <div class="page-header"><h1>统计报表</h1></div>
        <div class="tabs" style="display:flex;gap:0;margin-bottom:16px;border-bottom:2px solid var(--border)">
            <button id="report-tab-tenants" class="tab-btn active" onclick="switchReportTab('tenants')" style="padding:10px 24px;border:none;background:none;cursor:pointer;font-size:14px;border-bottom:2px solid var(--primary);margin-bottom:-2px;color:var(--primary);font-weight:600">租户报表</button>
            <button id="report-tab-apps" class="tab-btn" onclick="switchReportTab('apps')" style="padding:10px 24px;border:none;background:none;cursor:pointer;font-size:14px;color:var(--text-light)">应用报表</button>
            <button id="report-tab-endpoints" class="tab-btn" onclick="switchReportTab('endpoints')" style="padding:10px 24px;border:none;background:none;cursor:pointer;font-size:14px;color:var(--text-light)">接口统计</button>
        </div>
        <div id="report-content"></div>`;
    __reportTenantReset();
    __reportTenantLoad();
}

let __reportTab = "tenants";

function switchReportTab(tab) {
    __reportTab = tab;
    document.querySelectorAll(".tab-btn").forEach(b => {
        b.style.borderBottomColor = "transparent";
        b.style.color = "var(--text-light)";
        b.style.fontWeight = "400";
    });
    const activeBtn = document.getElementById("report-tab-" + tab);
    if (activeBtn) {
        activeBtn.style.borderBottomColor = "var(--primary)";
        activeBtn.style.color = "var(--primary)";
        activeBtn.style.fontWeight = "600";
    }
    if (tab === "tenants") {
        __reportTenantReset();
        __reportTenantLoad();
    } else if (tab === "endpoints") {
        __reportEndpointReset();
        __reportEndpointLoad();
    } else {
        __reportAppReset();
        __reportAppLoad();
    }
}

// 租户报表全局状态
let __rtPage = 1, __rtSearch = "", __rtDateFrom = "", __rtDateTo = "";
let __rtSortBy = "created_at", __rtSortOrder = "desc";

function __reportTenantReset() {
    __rtPage = 1; __rtSearch = ""; __rtDateFrom = ""; __rtDateTo = "";
    __rtSortBy = "created_at"; __rtSortOrder = "desc";
}

async function __reportTenantLoad() {
    const container = document.getElementById("report-content");
    if (!container) return;
    container.innerHTML = '<div class="loading"></div>';
    const data = { search: __rtSearch, page: __rtPage, page_size: 20, sort_by: __rtSortBy, sort_order: __rtSortOrder };
    if (__rtDateFrom) data.date_from = __rtDateFrom;
    if (__rtDateTo) data.date_to = __rtDateTo;
    try {
        const res = await apiCall(API.superadmin + "/report/tenants", {
            method: "POST", body: JSON.stringify(data)
        });
        if (!res) return;
        const d = res.data;
        const pageSize = 20;
        let html = `
            <div class="toolbar" style="flex-wrap:wrap;gap:8px;align-items:center">
                <input type="text" id="rt-search" placeholder="搜索租户名称/标识" value="${__rtSearch}" onkeydown="if(event.key==='Enter'){__rtSearch=this.value;__reportTenantLoad()}" style="padding:8px 12px;border:1px solid var(--border);border-radius:6px;font-size:13px;flex:1;min-width:200px">
                <input type="date" id="rt-date-from" value="${__rtDateFrom}" onchange="__rtDateFrom=this.value" style="padding:8px 12px;border:1px solid var(--border);border-radius:6px;font-size:13px;height:38px">
                <input type="date" id="rt-date-to" value="${__rtDateTo}" onchange="__rtDateTo=this.value" style="padding:8px 12px;border:1px solid var(--border);border-radius:6px;font-size:13px;height:38px">
                <button class="btn btn-primary" onclick="__rtSearch=document.getElementById('rt-search').value;__rtDateFrom=document.getElementById('rt-date-from').value;__rtDateTo=document.getElementById('rt-date-to').value;__rtPage=1;__reportTenantLoad()" style="height:38px">查询</button>
            </div>`;

        if (d.items && d.items.length) {
            const totalPages = Math.ceil(d.total / pageSize);
            function sortLink(field) {
                const nextOrder = __rtSortBy === field && __rtSortOrder === "asc" ? "desc" : "asc";
                const arrow = __rtSortBy === field ? (__rtSortOrder === "asc" ? "▲" : "▼") : "";
                const labels = { name: "名称", slug: "标识", status: "状态", user_count: "用户数", active_users_30d: "活跃用户", app_count: "应用数", total_api_calls: "API调用", created_at: "创建时间" };
                return `<a href="javascript:void(0)" onclick="__rtSortBy='${field}';__rtSortOrder='${nextOrder}';__rtPage=1;__reportTenantLoad()" style="color:var(--text-primary);text-decoration:none">${labels[field] || field} ${arrow}</a>`;
            }
            html += `<div class="table-wrap"><table><thead><tr>
                <th>${sortLink("name")}</th>
                <th>${sortLink("slug")}</th>
                <th>${sortLink("status")}</th>
                <th>${sortLink("user_count")}</th>
                <th>${sortLink("active_users_30d")}</th>
                <th>${sortLink("app_count")}</th>
                <th>${sortLink("total_api_calls")}</th>
                <th>${sortLink("created_at")}</th>
                <th>操作</th>
            </tr></thead><tbody>`;
            d.items.forEach(t => {
                const statusText = t.status ? "启用" : "禁用";
                const badgeClass = t.status ? "badge badge-active" : "badge badge-disabled";
                html += `<tr>
                    <td><strong>${t.name}</strong></td>
                    <td><code style="background:#f1f5f9;padding:2px 6px;border-radius:3px;font-size:12px">${t.slug}</code></td>
                    <td><span class="${badgeClass}">${statusText}</span></td>
                    <td>${t.user_count}</td>
                    <td>${t.active_users_30d}</td>
                    <td>${t.app_count}</td>
                    <td><strong>${t.total_api_calls || 0}</strong></td>
                    <td>${formatTime(t.created_at)}</td>
                    <td><button class="btn btn-sm" onclick="showTenantEndpoints(${t.id},'${t.name.replace(/'/g, "\\'")}')" style="font-size:12px">查看接口</button></td>
                </tr>`;
            });
            html += `</tbody></table></div>`;
            html += `<div class="pagination" style="display:flex;justify-content:space-between;align-items:center;padding:12px 0">
                <span style="color:var(--text-light);font-size:13px">共 ${d.total} 条，第 ${__rtPage}/${totalPages} 页</span>
                <div>${__rtPage > 1 ? `<button class="btn" onclick="__rtPage--;__reportTenantLoad()" style="margin-right:4px">上一页</button>` : ""}
                ${__rtPage < totalPages ? `<button class="btn btn-primary" onclick="__rtPage++;__reportTenantLoad()">下一页</button>` : ""}</div>
            </div>`;
        } else {
            html += '<div class="empty-state">暂无租户数据</div>';
        }
        container.innerHTML = html;
    } catch (e) {
        container.innerHTML = `<div class="empty-state">加载失败: ${e.message}</div>`;
    }
}

// 应用报表全局状态
let __raPage = 1, __raSearch = "", __raTenantId = "", __raDateFrom = "", __raDateTo = "";
let __raSortBy = "created_at", __raSortOrder = "desc";

function __reportAppReset() {
    __raPage = 1; __raSearch = ""; __raTenantId = ""; __raDateFrom = ""; __raDateTo = "";
    __raSortBy = "created_at"; __raSortOrder = "desc";
}

async function __reportAppLoad() {
    const container = document.getElementById("report-content");
    if (!container) return;
    container.innerHTML = '<div class="loading"></div>';
    const data = { search: __raSearch, page: __raPage, page_size: 20, sort_by: __raSortBy, sort_order: __raSortOrder };
    if (__raTenantId) data.tenant_id = __raTenantId;
    if (__raDateFrom) data.date_from = __raDateFrom;
    if (__raDateTo) data.date_to = __raDateTo;
    try {
        const res = await apiCall(API.superadmin + "/report/apps", {
            method: "POST", body: JSON.stringify(data)
        });
        if (!res) return;
        const d = res.data;
        const pageSize = 20;
        let html = `
            <div class="toolbar" style="flex-wrap:wrap;gap:8px;align-items:center">
                <input type="text" id="ra-search" placeholder="搜索应用名称/AppKey" value="${__raSearch}" onkeydown="if(event.key==='Enter'){__raSearch=this.value;__reportAppLoad()}" style="padding:8px 12px;border:1px solid var(--border);border-radius:6px;font-size:13px;flex:1;min-width:200px">
                <input type="number" id="ra-tenant-id" placeholder="租户ID（可选）" value="${__raTenantId}" style="padding:8px 12px;border:1px solid var(--border);border-radius:6px;font-size:13px;width:120px;height:38px">
                <input type="date" id="ra-date-from" value="${__raDateFrom}" onchange="__raDateFrom=this.value" style="padding:8px 12px;border:1px solid var(--border);border-radius:6px;font-size:13px;height:38px">
                <input type="date" id="ra-date-to" value="${__raDateTo}" onchange="__raDateTo=this.value" style="padding:8px 12px;border:1px solid var(--border);border-radius:6px;font-size:13px;height:38px">
                <button class="btn btn-primary" onclick="__raSearch=document.getElementById('ra-search').value;__raTenantId=document.getElementById('ra-tenant-id').value;__raDateFrom=document.getElementById('ra-date-from').value;__raDateTo=document.getElementById('ra-date-to').value;__raPage=1;__reportAppLoad()" style="height:38px">查询</button>
            </div>`;

        if (d.items && d.items.length) {
            const totalPages = Math.ceil(d.total / pageSize);
            function sortLink(field, label) {
                const nextOrder = __raSortBy === field && __raSortOrder === "asc" ? "desc" : "asc";
                const arrow = __raSortBy === field ? (__raSortOrder === "asc" ? "▲" : "▼") : "";
                return `<a href="javascript:void(0)" onclick="__raSortBy='${field}';__raSortOrder='${nextOrder}';__raPage=1;__reportAppLoad()" style="color:var(--text-primary);text-decoration:none">${label} ${arrow}</a>`;
            }
            html += `<div class="table-wrap"><table><thead><tr>
                <th>${sortLink("name", "应用名称")}</th>
                <th>AppKey</th>
                <th>${sortLink("tenant_id", "所属租户")}</th>
                <th>${sortLink("status", "状态")}</th>
                <th>${sortLink("call_count", "调用次数")}</th>
                <th>${sortLink("created_at", "创建时间")}</th>
                <th>操作</th>
            </tr></thead><tbody>`;
            d.items.forEach(a => {
                const statusText = a.status ? "启用" : "禁用";
                const badgeClass = a.status ? "badge badge-active" : "badge badge-disabled";
                html += `<tr>
                    <td><strong>${a.name}</strong></td>
                    <td><code style="background:#f1f5f9;padding:2px 6px;border-radius:3px;font-size:12px">${a.app_key}</code></td>
                    <td>${a.tenant_name}</td>
                    <td><span class="${badgeClass}">${statusText}</span></td>
                    <td><strong>${a.call_count}</strong></td>
                    <td>${formatTime(a.created_at)}</td>
                    <td><button class="btn btn-sm" onclick="showAppEndpoints(${a.id},'${a.name.replace(/'/g, "\\'")}')" style="font-size:12px">查看接口</button></td>
                </tr>`;
            });
            html += `</tbody></table></div>`;
            html += `<div class="pagination" style="display:flex;justify-content:space-between;align-items:center;padding:12px 0">
                <span style="color:var(--text-light);font-size:13px">共 ${d.total} 条，第 ${__raPage}/${totalPages} 页</span>
                <div>${__raPage > 1 ? `<button class="btn" onclick="__raPage--;__reportAppLoad()" style="margin-right:4px">上一页</button>` : ""}
                ${__raPage < totalPages ? `<button class="btn btn-primary" onclick="__raPage++;__reportAppLoad()">下一页</button>` : ""}</div>
            </div>`;
        } else {
            html += '<div class="empty-state">暂无应用数据</div>';
        }
        container.innerHTML = html;
    } catch (e) {
        container.innerHTML = `<div class="empty-state">加载失败: ${e.message}</div>`;
    }
}

// 接口统计全局状态
let __rePage = 1, __reStatType = "all", __reTenantId = "", __reAppId = "";
let __reDateFrom = "", __reDateTo = "";

function __reportEndpointReset() {
    __rePage = 1; __reStatType = "all"; __reTenantId = ""; __reAppId = "";
    __reDateFrom = ""; __reDateTo = "";
}

async function __reportEndpointLoad() {
    const container = document.getElementById("report-content");
    if (!container) return;
    container.innerHTML = '<div class="loading"></div>';
    const data = { stat_type: __reStatType, page: __rePage, page_size: 50 };
    if (__reTenantId) data.tenant_id = __reTenantId;
    if (__reAppId) data.app_id = __reAppId;
    if (__reDateFrom) data.date_from = __reDateFrom;
    if (__reDateTo) data.date_to = __reDateTo;
    try {
        const res = await apiCall(API.superadmin + "/report/endpoint-stats", {
            method: "POST", body: JSON.stringify(data)
        });
        if (!res) return;
        const d = res.data;
        const pageSize = 50;
        let html = `
            <div class="toolbar" style="flex-wrap:wrap;gap:8px;align-items:center">
                <select id="re-stat-type" onchange="__reStatType=this.value" style="padding:8px 12px;border:1px solid var(--border);border-radius:6px;font-size:13px;height:38px">
                    <option value="all" ${__reStatType === "all" ? "selected" : ""}>全部接口</option>
                    <option value="app" ${__reStatType === "app" ? "selected" : ""}>应用接口(OpenAPI)</option>
                    <option value="tenant" ${__reStatType === "tenant" ? "selected" : ""}>租户接口(管理端)</option>
                </select>
                <input type="number" id="re-tenant-id" placeholder="租户ID筛选" value="${__reTenantId}" style="padding:8px 12px;border:1px solid var(--border);border-radius:6px;font-size:13px;width:120px;height:38px">
                <input type="number" id="re-app-id" placeholder="应用ID筛选" value="${__reAppId}" style="padding:8px 12px;border:1px solid var(--border);border-radius:6px;font-size:13px;width:120px;height:38px">
                <input type="date" id="re-date-from" value="${__reDateFrom}" style="padding:8px 12px;border:1px solid var(--border);border-radius:6px;font-size:13px;height:38px">
                <input type="date" id="re-date-to" value="${__reDateTo}" style="padding:8px 12px;border:1px solid var(--border);border-radius:6px;font-size:13px;height:38px">
                <button class="btn btn-primary" onclick="__reStatType=document.getElementById('re-stat-type').value;__reTenantId=document.getElementById('re-tenant-id').value;__reAppId=document.getElementById('re-app-id').value;__reDateFrom=document.getElementById('re-date-from').value;__reDateTo=document.getElementById('re-date-to').value;__rePage=1;__reportEndpointLoad()" style="height:38px">查询</button>
            </div>`;
        if (d.items && d.items.length) {
            const totalPages = Math.ceil(d.total / pageSize);
            html += `<div style="margin-bottom:12px;color:var(--text-light);font-size:13px">共 <strong>${d.total}</strong> 个接口路径</div>`;
            html += `<div class="table-wrap"><table><thead><tr>
                <th>API路径</th>
                <th>调用次数</th>
                <th>来源</th>
                <th>所属租户/应用</th>
            </tr></thead><tbody>`;
            d.items.forEach(s => {
                const sourceLabel = s.source === "app" ? "应用接口" : "管理接口";
                const detail = s.source === "app" ? `${s.app_name || "应用#" + s.app_id}` : `${s.tenant_name || "租户#" + s.tenant_id}`;
                html += `<tr>
                    <td><code style="background:#f1f5f9;padding:2px 6px;border-radius:3px;font-size:12px">${s.api_path}</code></td>
                    <td><strong>${s.call_count}</strong></td>
                    <td><span class="badge ${s.source === 'app' ? 'badge-active' : 'badge'}">${sourceLabel}</span></td>
                    <td style="font-size:13px;color:var(--text-light)">${detail}</td>
                </tr>`;
            });
            html += `</tbody></table></div>`;
            html += `<div class="pagination" style="display:flex;justify-content:space-between;align-items:center;padding:12px 0">
                <span style="color:var(--text-light);font-size:13px">共 ${d.total} 条，第 ${__rePage}/${totalPages} 页</span>
                <div>${__rePage > 1 ? `<button class="btn" onclick="__rePage--;__reportEndpointLoad()" style="margin-right:4px">上一页</button>` : ""}
                ${__rePage < totalPages ? `<button class="btn btn-primary" onclick="__rePage++;__reportEndpointLoad()">下一页</button>` : ""}</div>
            </div>`;
        } else {
            html += '<div class="empty-state">暂无接口统计数据</div>';
        }
        container.innerHTML = html;
    } catch (e) {
        container.innerHTML = `<div class="empty-state">加载失败: ${e.message}</div>`;
    }
}

// 从租户报表查看具体租户的接口详情弹窗
async function showTenantEndpoints(tenantId, tenantName) {
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    overlay.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,0.4);z-index:999;display:flex;align-items:center;justify-content:center;padding:20px";
    overlay.innerHTML = `
        <div class="modal" style="background:#fff;border-radius:12px;width:90%;max-width:800px;max-height:80vh;overflow-y:auto;padding:24px;box-shadow:0 20px 60px rgba(0,0,0,0.2)">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
                <h3 style="margin:0">接口调用详情 - ${tenantName}</h3>
                <button onclick="this.closest('.modal-overlay').remove()" style="background:none;border:none;font-size:24px;cursor:pointer;color:var(--text-light)">&times;</button>
            </div>
            <div id="endpoint-detail-content"><div class="loading"></div></div>
        </div>`;
    document.body.appendChild(overlay);
    try {
        const res = await apiCall(API.superadmin + "/report/endpoint-stats", {
            method: "POST", body: JSON.stringify({ tenant_id: tenantId, stat_type: "all", page: 1, page_size: 200 })
        });
        if (!res) return;
        const d = res.data;
        const detailContainer = document.getElementById("endpoint-detail-content");
        if (!d.items || !d.items.length) {
            detailContainer.innerHTML = '<div class="empty-state">暂无接口调用记录</div>';
            return;
        }
        let html = `<div class="table-wrap"><table><thead><tr>
            <th>API路径</th><th>调用次数</th><th>来源</th>
        </tr></thead><tbody>`;
        d.items.forEach(s => {
            const sourceLabel = s.source === "app" ? "应用接口" : "管理接口";
            html += `<tr>
                <td><code style="background:#f1f5f9;padding:2px 6px;border-radius:3px;font-size:12px">${s.api_path}</code></td>
                <td><strong>${s.call_count}</strong></td>
                <td><span class="badge ${s.source === 'app' ? 'badge-active' : 'badge'}">${sourceLabel}</span></td>
            </tr>`;
        });
        html += `</tbody></table></div>`;
        detailContainer.innerHTML = html;
    } catch (e) {
        document.getElementById("endpoint-detail-content").innerHTML = `<div class="empty-state">加载失败: ${e.message}</div>`;
    }
}

// 从应用报表查看具体应用的接口详情弹窗
async function showAppEndpoints(appId, appName) {
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    overlay.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,0.4);z-index:999;display:flex;align-items:center;justify-content:center;padding:20px";
    overlay.innerHTML = `
        <div class="modal" style="background:#fff;border-radius:12px;width:90%;max-width:800px;max-height:80vh;overflow-y:auto;padding:24px;box-shadow:0 20px 60px rgba(0,0,0,0.2)">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
                <h3 style="margin:0">接口调用详情 - ${appName}</h3>
                <button onclick="this.closest('.modal-overlay').remove()" style="background:none;border:none;font-size:24px;cursor:pointer;color:var(--text-light)">&times;</button>
            </div>
            <div id="endpoint-detail-content"><div class="loading"></div></div>
        </div>`;
    document.body.appendChild(overlay);
    try {
        const res = await apiCall(API.superadmin + "/report/endpoint-stats", {
            method: "POST", body: JSON.stringify({ app_id: appId, stat_type: "app", page: 1, page_size: 200 })
        });
        if (!res) return;
        const d = res.data;
        const detailContainer = document.getElementById("endpoint-detail-content");
        if (!d.items || !d.items.length) {
            detailContainer.innerHTML = '<div class="empty-state">暂无接口调用记录</div>';
            return;
        }
        let html = `<div class="table-wrap"><table><thead><tr>
            <th>API路径</th><th>调用次数</th>
        </tr></thead><tbody>`;
        d.items.forEach(s => {
            html += `<tr>
                <td><code style="background:#f1f5f9;padding:2px 6px;border-radius:3px;font-size:12px">${s.api_path}</code></td>
                <td><strong>${s.call_count}</strong></td>
            </tr>`;
        });
        html += `</tbody></table></div>`;
        detailContainer.innerHTML = html;
    } catch (e) {
        document.getElementById("endpoint-detail-content").innerHTML = `<div class="empty-state">加载失败: ${e.message}</div>`;
    }
}

// ================== SUPERADMIN API STATS ==================

async function renderSuperadminApiStats(container) {
    container.innerHTML = '<div class="loading"></div>';
    try {
        const res = await apiCall(API.superadmin + "/api-stats?days=30");
        if (!res) return;
        const d = res.data;
        let html = `<div class="toolbar"><div></div>
            <button class="btn btn-primary" onclick="renderSuperadminApiStats(document.getElementById('page-content'))">刷新</button>
        </div>`;

        if (d.daily_totals && d.daily_totals.length) {
            html += `<div class="card"><div class="card-title">最近 ${d.period_days} 天平台API调用趋势</div><div class="table-wrap"><table><thead><tr><th>日期</th><th>总调用次数</th></tr></thead><tbody>`;
            d.daily_totals.forEach(s => {
                html += `<tr><td>${s.date}</td><td><strong>${s.count}</strong></td></tr>`;
            });
            html += `</tbody></table></div></div>`;
        }

        if (d.app_rankings && d.app_rankings.length) {
            html += `<div class="card" style="margin-top:16px"><div class="card-title">应用API调用排行</div><div class="table-wrap"><table><thead><tr><th>排名</th><th>应用</th><th>API路径</th><th>调用次数</th></tr></thead><tbody>`;
            d.app_rankings.forEach((s, i) => {
                const path = s.api_path.replace("/api/v1/open/", "");
                html += `<tr><td>${i + 1}</td><td><strong>${s.app_name}</strong></td><td style="font-family:monospace;font-size:12px">${path}</td><td><strong>${s.total_calls}</strong></td></tr>`;
            });
            html += `</tbody></table></div></div>`;
        }

        if (!d.daily_totals || !d.daily_totals.length) {
            html += `<div class="empty-state">暂无API调用数据（需要应用通过开放API发起请求后自动累积）</div>`;
        }
        container.innerHTML = html;
    } catch (e) { container.innerHTML = `<div class="empty-state">加载失败: ${e.message}</div>`; }
}

async function renderSuperadminConfig(container) {
    container.innerHTML = '<div class="loading"></div>';
    try {
        const res = await apiCall(API.superadmin + "/platform-config");
        if (!res) return;
        const d = res.data;
        let html = `<div class="toolbar"><div></div>
            <button class="btn btn-primary" onclick="renderSuperadminConfig(document.getElementById('page-content'))">刷新</button>
        </div>`;
        if (d.configs && d.configs.length) {
            d.configs.forEach(group => {
                html += `<div class="card" style="margin-top:${d.configs.indexOf(group) > 0 ? '16px' : '0'}">
                    <div class="card-title">${group.group}</div>
                    <div class="table-wrap"><table><thead><tr><th style="width:260px">配置项</th><th>当前值</th></tr></thead><tbody>`;
                group.items.forEach(item => {
                    const displayVal = item.sensitive ? "***" : (item.value || "未配置");
                    const valTag = item.sensitive
                        ? `<code style="background:#f1f5f9;padding:2px 8px;border-radius:3px;color:#94a3b8">***</code>`
                        : `<code style="background:#f1f5f9;padding:2px 8px;border-radius:3px">${displayVal}</code>`;
                    html += `<tr><td><strong>${item.key}</strong></td><td>${valTag}</td></tr>`;
                });
                html += `</tbody></table></div></div>`;
            });
        } else {
            html += `<div class="empty-state">暂无配置数据</div>`;
        }
        container.innerHTML = html;
    } catch (e) { container.innerHTML = `<div class="empty-state">加载失败: ${e.message}</div>`; }
}

// ================== Common ==================

let __pgHandler = null;

document.addEventListener('click', function(e) {
    const btn = e.target.closest('.pagination [data-page]');
    if (btn && !btn.disabled && __pgHandler) {
        __pgHandler(parseInt(btn.dataset.page, 10));
    }
});

function renderPagination(total, page, pageSize, onChange) {
    __pgHandler = onChange;
    const totalPages = Math.ceil(total / pageSize) || 1;
    if (totalPages <= 1) return "";
    const start = Math.max(1, page - 2);
    const end = Math.min(totalPages, page + 2);
    let html = '<div class="pagination">';
    html += `<button class="btn btn-sm btn-text" data-page="${page - 1}" ${page <= 1 ? 'disabled style="opacity:0.4"' : ''}>上一页</button>`;
    for (let i = start; i <= end; i++) {
        const active = i === page;
        html += `<button class="btn btn-sm ${active ? 'btn-primary active' : 'btn-text'}" data-page="${i}">${i}</button>`;
    }
    html += `<button class="btn btn-sm btn-text" data-page="${page + 1}" ${page >= totalPages ? 'disabled style="opacity:0.4"' : ''}>下一页</button>`;
    html += `<span class="page-info">共 ${total} 条</span>`;
    html += "</div>";
    return html;
}

function formatTime(ts) {
    if (!ts) return "-";
    const d = new Date(ts);
    const pad = n => n.toString().padStart(2, "0");
    return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate())
        + " " + pad(d.getHours()) + ":" + pad(d.getMinutes());
}

// ================== TAGS ==================

async function renderTags(container) {
    container.innerHTML = '<div class="loading"></div>';
    try {
        const res = await apiCall(API.admin + "/tags");
        if (!res) return;
        const tags = res.data.tags || [];
        
        container.innerHTML = `
            <div class="toolbar">
                <div></div>
                <button class="btn btn-primary" onclick="showCreateTagModal()">+ 新增标签</button>
            </div>
            <div class="card"><div class="table-wrap">
            <table><thead><tr>
                <th>ID</th><th>标签名称</th><th>颜色</th><th>描述</th><th>排序</th><th>创建时间</th><th>操作</th>
            </tr></thead><tbody>
            ${tags.length ? tags.map(t => `
                <tr>
                    <td>${t.id}</td>
                    <td><strong>${t.name}</strong></td>
                    <td><span class="tag-color" style="background:${t.color};width:24px;height:24px;border-radius:4px;display:inline-block"></span></td>
                    <td>${t.description || "-"}</td>
                    <td>${t.sort_order}</td>
                    <td>${formatTime(t.created_at)}</td>
                    <td style="white-space:nowrap">
                        <button class="btn btn-sm btn-text" onclick="showEditTagModal(${t.id}, '${t.name}', '${t.color}', '${t.description || ''}')">编辑</button>
                        <button class="btn btn-sm btn-text" onclick="deleteTag(${t.id}, '${t.name}')" style="color:var(--danger)">删除</button>
                    </td>
                </tr>`).join("") : '<tr><td colspan="7"><div class="empty-state">暂无标签</div></td></tr>'}
            </tbody></table></div></div>`;
    } catch (e) { container.innerHTML = `<div class="empty-state">加载失败: ${e.message}</div>`; }
}

function showCreateTagModal() {
    openModal(`
        <div class="modal-header"><h2>新增标签</h2><button class="modal-close" onclick="closeModal()">&times;</button></div>
        <form onsubmit="return false">
            <div class="form-group"><label>标签名称 *</label><input id="ct-name" required placeholder="请输入标签名称"></div>
            <div class="form-group"><label>颜色</label>
                <div style="display:flex;gap:8px;flex-wrap:wrap">
                    ${['#1a73e8', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16'].map(c => 
                        `<label style="cursor:pointer"><input type="radio" name="tag-color" value="${c}" ${c === '#1a73e8' ? 'checked' : ''} style="display:none"><span style="width:28px;height:28px;border-radius:4px;display:block;background:${c};border:2px solid ${c === '#1a73e8' ? '#1a73e8' : 'transparent'}" onclick="document.querySelectorAll('input[name=tag-color]').forEach(i => i.parentElement.querySelector('span').style.borderColor = 'transparent');this.style.borderColor='${c}';this.parentElement.querySelector('input').checked=true"></span></label>`
                    ).join("")}
                </div>
                <input type="text" id="ct-color" value="#1a73e8" style="margin-top:8px;width:120px">
            </div>
            <div class="form-group"><label>描述</label><input id="ct-desc" placeholder="标签描述（可选）"></div>
            <div class="modal-footer">
                <button class="btn btn-text" onclick="closeModal()">取消</button>
                <button class="btn btn-primary" onclick="createTag()">确认创建</button>
            </div>
        </form>`);
}

async function createTag() {
    const name = document.getElementById("ct-name").value.trim();
    const color = document.getElementById("ct-color").value.trim() || '#1a73e8';
    const desc = document.getElementById("ct-desc").value.trim();
    
    if (!name) { showToast("标签名称不能为空", "error"); return; }
    
    try {
        const res = await apiCall(API.admin + "/tags/create", {
            method: "POST",
            body: JSON.stringify({ name, color, description: desc || null }),
        });
        if (!res) return;
        if (res.code < 0) { showToast(res.message, "error"); return; }
        showToast("标签创建成功", "success");
        closeModal();
        switchPage("tags");
    } catch (e) { showToast(e.message, "error"); }
}

function showEditTagModal(id, name, color, description) {
    openModal(`
        <div class="modal-header"><h2>编辑标签 #${id}</h2><button class="modal-close" onclick="closeModal()">&times;</button></div>
        <form onsubmit="return false">
            <div class="form-group"><label>标签名称</label><input id="et-name" value="${name}"></div>
            <div class="form-group"><label>颜色</label>
                <div style="display:flex;gap:8px;flex-wrap:wrap">
                    ${['#1a73e8', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16'].map(c => 
                        `<label style="cursor:pointer"><input type="radio" name="tag-color" value="${c}" ${c === color ? 'checked' : ''} style="display:none"><span style="width:28px;height:28px;border-radius:4px;display:block;background:${c};border:2px solid ${c === color ? c : 'transparent'}" onclick="document.querySelectorAll('input[name=tag-color]').forEach(i => i.parentElement.querySelector('span').style.borderColor = 'transparent');this.style.borderColor='${c}';this.parentElement.querySelector('input').checked=true"></span></label>`
                    ).join("")}
                </div>
                <input type="text" id="et-color" value="${color}" style="margin-top:8px;width:120px">
            </div>
            <div class="form-group"><label>描述</label><input id="et-desc" value="${description}"></div>
            <div class="modal-footer">
                <button class="btn btn-text" onclick="closeModal()">取消</button>
                <button class="btn btn-primary" onclick="editTag(${id})">保存</button>
            </div>
        </form>`);
}

async function editTag(id) {
    const name = document.getElementById("et-name").value.trim();
    const color = document.getElementById("et-color").value.trim() || '#1a73e8';
    const desc = document.getElementById("et-desc").value.trim();
    
    if (!name) { showToast("标签名称不能为空", "error"); return; }
    
    try {
        const res = await apiCall(API.admin + "/tags/" + id, {
            method: "PUT",
            body: JSON.stringify({ name, color, description: desc || null }),
        });
        if (!res) return;
        if (res.code < 0) { showToast(res.message, "error"); return; }
        showToast("标签已更新", "success");
        closeModal();
        switchPage("tags");
    } catch (e) { showToast(e.message, "error"); }
}

async function deleteTag(id, name) {
    if (!confirm(`确定删除标签 "${name}" 吗？`)) return;
    try {
        const res = await apiCall(API.admin + "/tags/" + id, { method: "DELETE" });
        if (!res) return;
        if (res.code < 0) { showToast(res.message, "error"); return; }
        showToast("标签已删除", "success");
        switchPage("tags");
    } catch (e) { showToast(e.message, "error"); }
}

async function showUserTagsModal(userId) {
    try {
        const [tagsRes, userTagsRes] = await Promise.all([
            apiCall(API.admin + "/tags"),
            apiCall(API.admin + "/users/" + userId + "/tags"),
        ]);
        if (!tagsRes) return;
        
        const allTags = tagsRes.data.tags || [];
        const userTagIds = (userTagsRes && userTagsRes.data.tags ? userTagsRes.data.tags.map(t => t.id) : []);
        
        openModal(`
            <div class="modal-header"><h2>设置用户标签</h2><button class="modal-close" onclick="closeModal()">&times;</button></div>
            <div class="form-group"><label>选择标签</label>
                <div class="tag-grid">
                    ${allTags.length ? allTags.map(t => `
                        <label class="tag-item ${userTagIds.includes(t.id) ? 'selected' : ''}" onclick="event.preventDefault();this.classList.toggle('selected');var cb=this.querySelector('input');cb.checked=!cb.checked">
                            <input type="checkbox" value="${t.id}" ${userTagIds.includes(t.id) ? 'checked' : ''} style="display:none">
                            <span class="tag-label" style="background:${t.color}20;color:${t.color};border-color:${t.color}">${t.name}</span>
                        </label>`).join("") : '<span style="color:var(--text-light)">暂无标签，请先创建</span>'}
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn btn-text" onclick="closeModal()">取消</button>
                <button class="btn btn-primary" onclick="saveUserTags(${userId})">保存</button>
            </div>`);
    } catch (e) { showToast(e.message, "error"); }
}

async function saveUserTags(userId) {
    const selectedIds = Array.from(document.querySelectorAll(".tag-grid input:checked")).map(el => parseInt(el.value));
    
    try {
        // 使用 PUT 请求一次性设置用户标签（替换模式）
        const res = await apiCall(API.admin + "/users/" + userId + "/tags", {
            method: "PUT",
            body: JSON.stringify({ tag_ids: selectedIds }),
        });
        if (!res) return;
        if (res.code < 0) { showToast(res.message, "error"); return; }
        
        showToast("标签已更新", "success");
        closeModal();
        switchPage("users");
    } catch (e) { showToast(e.message, "error"); }
}

// ================== Init ==================

(function init() {
    if (getToken()) showApp();
    else showLogin();
})();
