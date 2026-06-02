<?php
/**
 * 统一账户认证服务 - 微信网页扫码登录 (wechat_web) 示例
 *
 * 功能：演示完整的微信 OAuth2 扫码登录流程
 *   1. 用户点击"微信登录"按钮，重定向到微信授权页面
 *   2. 用户扫码授权后，微信回调携带 code 返回本页面
 *   3. 回调处理：调用统一认证服务 API 完成登录，展示结果
 *
 * 前置条件：
 *   - 已在微信开放平台 (https://open.weixin.qq.com) 注册网页应用并获得 AppID
 *   - 微信开放平台中配置了授权回调域名（指向本文件所在服务器）
 *   - 统一认证服务后台已为该应用配置了 wechat_web_app_id / wechat_web_app_secret
 *   - 本文件所在目录的 openapi_client.php 可用
 *
 * 运行方式：
 *   php -S localhost:8080 -t ./
 *   然后访问 http://localhost:8080/php/wechat_login.php
 */

require_once __DIR__ . '/openapi_client.php';

// ======================== 配置区（请根据实际情况修改） ========================

/** 统一认证服务的应用 AppKey（管理后台获取） */
define('APP_KEY', 'efc44f100f59fa0e08c1986715f587df');

/** 统一认证服务的应用 AppSecret */
define('APP_SECRET', 'ef276bb188138dcf6eaa3e958d82cbb91bd15f494df4b9ef3a5dffcc590c97c4');

/** 统一认证服务地址 */
define('BASE_URL', 'http://uais.qianbiaodashuju.cn');

/** 微信开放平台网页应用的 AppID */
define('WECHAT_APP_ID', 'wx65b293290648f3e3');

/** 微信授权回调地址（必须与微信开放平台配置的授权回调域名一致） */
define('CALLBACK_URL', 'https://uaistest.qianbiaodashuju.cn/wechat_login.php');

// ======================== 主流程 ========================

session_start();

$action = $_GET['action'] ?? '';
$code   = $_GET['code'] ?? '';
$state  = $_GET['state'] ?? '';

// 状态1：用户发起登录，重定向到微信授权页面
if ($action === 'login') {
    $stateToken = bin2hex(random_bytes(16));
    $_SESSION['wechat_state'] = $stateToken;

    $wechatAuthUrl = 'https://open.weixin.qq.com/connect/qrconnect'
        . '?appid=' . urlencode(WECHAT_APP_ID)
        . '&redirect_uri=' . urlencode(CALLBACK_URL)
        . '&response_type=code'
        . '&scope=snsapi_login'
        . '&state=' . urlencode($stateToken)
        . '#wechat_redirect';

    header('Location: ' . $wechatAuthUrl);
    exit;
}

// 状态2：微信回调，携带 code 回到本页面
if ($code !== '') {
    handleWeChatCallback($code, $state);
    exit;
}

// 状态3：默认展示微信登录入口页面
renderLoginPage();

// ======================== 函数实现 ========================

/**
 * 处理微信登录回调
 */
function handleWeChatCallback($code, $state)
{
    $expectedState = $_SESSION['wechat_state'] ?? '';
    unset($_SESSION['wechat_state']);

    if ($expectedState === '' || $state !== $expectedState) {
        renderResultPage('error', '安全校验失败', 'state 参数不匹配，可能遭受 CSRF 攻击，请重新扫码登录。');
        return;
    }

    $client = new OpenAPIClient(APP_KEY, APP_SECRET, BASE_URL);
    $result = $client->socialLogin('wechat_web', $code, APP_KEY);

    if (($result['code'] ?? -1) !== 0) {
        $msg = $result['message'] ?? '未知错误';
        renderResultPage('error', '微信登录失败', htmlspecialchars($msg));
        return;
    }

    $data = $result['data'];
    $accessToken  = $data['access_token'] ?? '';
    $refreshToken = $data['refresh_token'] ?? '';

    $userInfo = [];
    try {
        $userInfoResult = $client->getUserinfo($accessToken);
        if (($userInfoResult['code'] ?? -1) === 0) {
            $userInfo = $userInfoResult['data'] ?? [];
        }
    } catch (Exception $e) {
    }

    renderResultPage('success', '微信登录成功', '', [
        'access_token'  => $accessToken,
        'refresh_token' => $refreshToken,
        'user_id'       => $data['user_id'] ?? '',
        'is_new'        => !empty($data['is_new']),
        'user_info'     => $userInfo,
    ]);
}

/**
 * 渲染微信登录入口页面
 */
function renderLoginPage()
{
    $configured = WECHAT_APP_ID !== '' && strpos(WECHAT_APP_ID, '填写你的') !== 0;
    $notice = '';
    if (!$configured) {
        $notice = '<div class="notice-warn"><strong>配置提醒：</strong>请先编辑本文件，将 <code>WECHAT_APP_ID</code> 替换为你的微信开放平台网页应用 AppID。</div>';
    }

    echo '<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>微信扫码登录 | 统一账号认证服务</title>
<style>
    *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
    body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;background:linear-gradient(135deg,#667eea,#764ba2);min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}
    .card{background:#fff;border-radius:16px;box-shadow:0 20px 60px rgba(0,0,0,.15);padding:48px 40px 40px;max-width:440px;width:100%;text-align:center}
    .logo{width:80px;height:80px;margin:0 auto 16px;background:#07c160;border-radius:20px;display:flex;align-items:center;justify-content:center;font-size:40px;color:#fff}
    h1{font-size:24px;font-weight:600;color:#1a1a1a;margin-bottom:8px}
    .desc{font-size:14px;color:#666;margin-bottom:32px;line-height:1.6}
    .wechat-btn{display:inline-flex;align-items:center;gap:10px;background:#07c160;color:#fff;border:none;border-radius:8px;padding:14px 40px;font-size:17px;font-weight:500;cursor:pointer;text-decoration:none;transition:background .2s}
    .wechat-btn:hover{background:#06ad56}
    .wechat-btn svg{width:24px;height:24px;fill:currentColor}
    .notice-warn{background:#fff8e1;border:1px solid #ffe082;border-radius:8px;padding:12px 16px;font-size:13px;color:#795548;text-align:left;margin-bottom:24px;line-height:1.6}
    .notice-warn code{background:rgba(0,0,0,.06);padding:2px 6px;border-radius:3px;font-size:12px}
    .notice-warn strong{display:block;margin-bottom:4px}
    .footer{margin-top:28px;font-size:12px;color:#aaa}
</style>
</head>
<body>
    <div class="card">
        <div class="logo">&#x1F4F1;</div>
        <h1>微信扫码登录</h1>
        <p class="desc">使用微信扫描二维码即可安全登录<br>统一账号认证服务演示</p>
        ' . $notice . '
        <a href="?action=login" class="wechat-btn">
            <svg viewBox="0 0 24 24"><path d="M8.5 11a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3zm7 0a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3zM12 2C6.48 2 2 6.48 2 12c0 1.82.49 3.53 1.34 5L2 22l5.34-1.34A9.97 9.97 0 0 0 12 22c5.52 0 10-4.48 10-10S17.52 2 12 2z"/></svg>
            微信扫码登录
        </a>
        <div class="footer">统一账号认证服务 v2 &middot; OpenAPI 示例</div>
    </div>
</body>
</html>';
}

/**
 * 渲染登录结果页面
 */
function renderResultPage($type, $title, $message, $data = [])
{
    $isSuccess = $type === 'success';
    $icon = $isSuccess ? '&#x2705;' : '&#x274C;';
    $pageTitle = $isSuccess ? '登录成功' : '登录失败';
    $iconColor = $isSuccess ? '#07c160' : '#e53935';

    $extra = '';

    if ($isSuccess && !empty($data)) {
        $userInfo = $data['user_info'] ?? [];
        $extra .= '<div class="section"><h3>令牌信息</h3>';
        $extra .= '<div class="field"><span class="label">access_token</span><code class="token">' . htmlspecialchars($data['access_token']) . '</code></div>';
        $extra .= '<div class="field"><span class="label">refresh_token</span><code class="token">' . htmlspecialchars($data['refresh_token']) . '</code></div>';
        $extra .= '<div class="field"><span class="label">user_id</span><code>' . htmlspecialchars((string)$data['user_id']) . '</code></div>';
        $extra .= '<div class="field"><span class="label">is_new</span><code>' . ($data['is_new'] ? 'true' : 'false') . '</code></div>';
        $extra .= '</div>';

        if (!empty($userInfo)) {
            $extra .= '<div class="section"><h3>用户信息</h3><table class="info-table">';
            $fields = ['id','uuid','username','nickname','email','phone','department','user_type','status'];
            foreach ($fields as $f) {
                if (isset($userInfo[$f]) && $userInfo[$f] !== '' && $userInfo[$f] !== null) {
                    $val = is_bool($userInfo[$f]) ? ($userInfo[$f] ? 'true' : 'false') : htmlspecialchars((string)$userInfo[$f]);
                    $extra .= "<tr><td>{$f}</td><td>{$val}</td></tr>";
                }
            }
            $extra .= '</table></div>';
        }
    } else {
        $extra .= '<p class="error-msg">' . htmlspecialchars($message) . '</p>';
    }

    echo '<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>' . $pageTitle . ' | 统一账号认证服务</title>
<style>
    *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
    body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;background:linear-gradient(135deg,#667eea,#764ba2);min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}
    .card{background:#fff;border-radius:16px;box-shadow:0 20px 60px rgba(0,0,0,.15);padding:40px;max-width:640px;width:100%}
    .icon{font-size:48px;text-align:center;margin-bottom:8px}
    h1{font-size:22px;font-weight:600;text-align:center;color:#1a1a1a;margin-bottom:8px}
    .subtitle{text-align:center;font-size:14px;color:#666;margin-bottom:20px}
    .section{margin-top:20px;padding-top:20px;border-top:1px solid #eee}
    .section h3{font-size:14px;font-weight:600;color:#333;margin-bottom:12px}
    .field{margin-bottom:10px;font-size:13px}
    .field .label{display:block;font-weight:500;color:#888;margin-bottom:2px;font-size:11px;text-transform:uppercase;letter-spacing:.5px}
    .field code{display:block;background:#f5f5f5;padding:8px 12px;border-radius:6px;font-size:12px;color:#333;word-break:break-all}
    .field .token{font-family:"SF Mono","Fira Code",monospace;font-size:11px;line-height:1.5}
    .info-table{width:100%;border-collapse:collapse;font-size:13px}
    .info-table td{padding:8px 12px;border-bottom:1px solid #f0f0f0;vertical-align:top}
    .info-table td:first-child{font-weight:500;color:#888;width:120px;white-space:nowrap}
    .info-table td:last-child{color:#333;word-break:break-all}
    .error-msg{text-align:center;color:#c62828;font-size:14px;padding:12px;background:#fff3f3;border-radius:8px}
    .btn-back{display:block;text-align:center;margin-top:24px;padding:12px;background:#f5f5f5;border-radius:8px;color:#333;text-decoration:none;font-size:14px;font-weight:500}
    .btn-back:hover{background:#e8e8e8}
</style>
</head>
<body>
    <div class="card">
        <div class="icon" style="color:' . $iconColor . '">' . $icon . '</div>
        <h1>' . $pageTitle . '</h1>
        <p class="subtitle">' . htmlspecialchars($title) . '</p>
        ' . $extra . '
        <a href="?" class="btn-back">&#x2190; 返回首页</a>
    </div>
</body>
</html>';
}