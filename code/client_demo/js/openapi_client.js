#!/usr/bin/env node
/**
 * 统一账户认证服务 - OpenAPI Node.js SDK
 *
 * 基于 API 对接文档 v2.1
 * 文档: document/gateway_openapi_documentation_v2.md
 *
 * Node.js 使用:
 *   const { OpenAPIClient } = require('./openapi_client');
 *   const client = new OpenAPIClient('APP_KEY', 'APP_SECRET', 'http://localhost:8000');
 *
 * 浏览器使用:
 *   <script src="openapi_client.js"></script>
 *   <script>
 *     const client = new OpenAPIClient('APP_KEY', 'APP_SECRET');
 *     client.listUsers().then(console.log);
 *   </script>
 */
(function (root, factory) {
    if (typeof define === 'function' && define.amd) {
        define([], factory);
    } else if (typeof module === 'object' && module.exports) {
        module.exports = factory(require('crypto'), require('http'), require('https'));
    } else {
        root.OpenAPIClient = factory(null, null, null);
    }
}(typeof self !== 'undefined' ? self : this, function (crypto, http, https) {

    /**
     * SHA256 哈希
     */
    function sha256(str) {
        if (crypto) {
            return crypto.createHash('sha256').update(str).digest('hex');
        }
        throw new Error('浏览器环境请使用 async 版本的 sha256Browser()');
    }

    /**
     * 浏览器 SHA256（异步）
     */
    async function sha256Browser(str) {
        var encoder = new TextEncoder();
        var data = encoder.encode(str);
        var hashBuffer = await crypto.subtle.digest('SHA-256', data);
        var hashArray = Array.from(new Uint8Array(hashBuffer));
        return hashArray.map(function (b) { return b.toString(16).padStart(2, '0'); }).join('');
    }

    /**
     * 生成 HMAC-SHA256 签名
     *
     * 签名公式: HMAC-SHA256(app_secret, "{}" + timestamp)
     * 签名固定使用 "{}" + timestamp，不包含请求体
     */
    function generateSignature(appSecret, timestamp) {
        if (crypto) {
            var message = '{}' + timestamp;
            return crypto.createHmac('sha256', appSecret).update(message).digest('hex');
        }
        throw new Error('crypto 模块不可用');
    }

    /**
     * 构建认证请求头
     */
    function buildHeaders(appKey, appSecret) {
        var timestamp = String(Math.floor(Date.now() / 1000));
        var signature = generateSignature(appSecret, timestamp);
        return {
            'Content-Type': 'application/json',
            'X-App-Key': appKey,
            'X-Timestamp': timestamp,
            'X-Signature': signature,
        };
    }

    /**
     * 发送 HTTP 请求（Node.js）
     */
    function request(method, path, body, headers, baseUrl) {
        return new Promise(function (resolve, reject) {
            var url = new URL(baseUrl + path);
            var isHttps = url.protocol === 'https:';
            var transport = isHttps ? https : http;

            var options = {
                hostname: url.hostname,
                port: url.port || (isHttps ? 443 : 80),
                path: url.pathname + url.search,
                method: method,
                headers: headers,
                timeout: 30000,
            };

            var bodyStr = null;
            if (body !== undefined && body !== null) {
                bodyStr = JSON.stringify(body);
                options.headers['Content-Length'] = Buffer.byteLength(bodyStr);
            }

            var req = transport.request(options, function (res) {
                var data = '';
                res.on('data', function (chunk) { data += chunk; });
                res.on('end', function () {
                    try { resolve(JSON.parse(data)); }
                    catch (e) { reject(new Error('响应解析失败: ' + data.slice(0, 200))); }
                });
            });

            req.on('error', function (e) { reject(new Error('请求失败: ' + e.message)); });
            req.on('timeout', function () { req.destroy(); reject(new Error('请求超时')); });
            if (bodyStr) req.write(bodyStr);
            req.end();
        });
    }

    /**
     * OpenAPI 客户端
     */
    class OpenAPIClient {
        /**
         * @param {string} appKey    应用唯一标识
         * @param {string} appSecret 应用密钥
         * @param {string} [baseUrl] 服务地址，默认 http://localhost:8000
         */
        constructor(appKey, appSecret, baseUrl) {
            this.appKey = appKey;
            this.appSecret = appSecret;
            this.baseUrl = (baseUrl || 'http://localhost:8000').replace(/\/+$/, '');
        }

        _headers() {
            return buildHeaders(this.appKey, this.appSecret);
        }

        _req(method, path, body) {
            return request(method, path, body, this._headers(), this.baseUrl);
        }

        _reqWithAuth(method, path, body, accessToken) {
            var h = this._headers();
            h['Authorization'] = 'Bearer ' + accessToken;
            return request(method, path, body, h, this.baseUrl);
        }

        // ==================== 开放 API（OpenAPI） ====================

        /** 验证用户 Token */
        verifyToken(token) {
            return this._req('POST', '/api/v1/open/verify_token', { token: token });
        }

        /** 查询用户列表 */
        listUsers() {
            return this._req('GET', '/api/v1/open/users');
        }

        /**
         * 创建用户
         * @param {string} username
         * @param {string} password
         * @param {string} [userType] - internal/external
         * @param {object} [options] - 可选字段
         */
        createUser(username, password, userType, options) {
            var body = { username: username, password: password, user_type: userType || 'internal' };
            if (options) Object.assign(body, options);
            return this._req('POST', '/api/v1/open/users', body);
        }

        /** 获取用户详情 */
        getUser(userId) {
            return this._req('GET', '/api/v1/open/users/' + userId);
        }

        /** 更新用户 */
        updateUser(userId, data) {
            return this._req('PUT', '/api/v1/open/users/' + userId, data || {});
        }

        /** 启用/禁用用户 */
        toggleUserStatus(userId, status) {
            return this._req('PATCH', '/api/v1/open/users/' + userId + '/status', { status: status });
        }

        /** 检查用户权限 */
        checkPermission(userId, permissionCode) {
            return this._req('POST', '/api/v1/open/check_permission', {
                user_id: userId,
                permission_code: permissionCode,
            });
        }

        // ==================== 用户认证 API（Auth） ====================

        /** 用户名密码登录 */
        login(username, password) {
            return this._req('POST', '/api/v1/auth/login', { username: username, password: password });
        }

        /** 发送短信验证码 */
        smsSend(phone) {
            return this._req('POST', '/api/v1/auth/sms/send', { phone: phone });
        }

        /** 短信登录 */
        smsLogin(phone, code) {
            return this._req('POST', '/api/v1/auth/sms/login', { phone: phone, code: code });
        }

        /** 社交登录 */
        socialLogin(provider, code) {
            return this._req('POST', '/api/v1/auth/social/login', { provider: provider, code: code });
        }

        /** 刷新 Token */
        refreshToken(refreshToken) {
            return this._req('POST', '/api/v1/auth/refresh', { refresh_token: refreshToken });
        }

        /** 获取用户信息 */
        getUserinfo(accessToken) {
            return this._reqWithAuth('GET', '/api/v1/auth/userinfo', null, accessToken);
        }

        /** 更新个人信息 */
        updateUserinfo(accessToken, data) {
            return this._reqWithAuth('PUT', '/api/v1/auth/userinfo', data || {}, accessToken);
        }

        /** 修改密码 */
        changePassword(accessToken, oldPassword, newPassword) {
            return this._reqWithAuth('PATCH', '/api/v1/auth/userinfo/password', {
                old_password: oldPassword,
                new_password: newPassword,
            }, accessToken);
        }

        /** 登出 */
        logout(accessToken) {
            return this._reqWithAuth('POST', '/api/v1/auth/logout', null, accessToken);
        }
    }

    return { OpenAPIClient: OpenAPIClient };
}));
