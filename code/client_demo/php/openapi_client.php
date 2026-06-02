<?php
/**
 * 统一账户认证服务 - OpenAPI PHP SDK
 *
 * 基于 API 对接文档 v2.1
 * 文档: document/gateway_openapi_documentation_v2.md
 *
 * 使用方式:
 *   composer require guzzlehttp/guzzle  (推荐)
 *   或直接用 file_get_contents + stream_context_create
 *
 *    require_once 'openapi_client.php';
 *    $client = new OpenAPIClient('APP_KEY', 'APP_SECRET', 'http://localhost:8000');
 *    $result = $client->verifyToken('user_jwt_token');
 */

class OpenAPIClient
{
    private $appKey;
    private $appSecretHash;
    private $baseUrl;

    /**
     * 构造函数
     *
     * @param string $appKey    应用唯一标识（管理后台获取）
     * @param string $appSecret 应用密钥（创建时显示一次）
     * @param string $baseUrl   服务地址，默认 http://localhost:8000
     */
    public function __construct($appKey, $appSecret, $baseUrl = 'http://localhost:8000')
    {
        $this->appKey = $appKey;
        // 签名使用 app_secret 的 SHA256 哈希值
        $this->appSecretHash = hash('sha256', $appSecret);
        $this->baseUrl = rtrim($baseUrl, '/');
    }

    /**
     * 生成 HMAC-SHA256 签名
     *
     * 签名公式: HMAC-SHA256(app_secret_hash, "{}" + timestamp)
     *
     * @param string $timestamp Unix 时间戳字符串（秒）
     * @return string 十六进制签名字符串
     */
    private function generateSignature($timestamp)
    {
        // 签名固定使用 "{}" + timestamp，不包含请求体
        $message = '{}' . $timestamp;
        return hash_hmac('sha256', $message, $this->appSecretHash);
    }

    /**
     * 构建 OpenAPI 请求头
     *
     * @return array 请求头关联数组
     */
    private function buildHeaders()
    {
        $timestamp = (string) time();
        $signature = $this->generateSignature($timestamp);

        return [
            'Content-Type: application/json',
            'X-App-Key: ' . $this->appKey,
            'X-Timestamp: ' . $timestamp,
            'X-Signature: ' . $signature,
        ];
    }

    /**
     * 发送 HTTP 请求
     *
     * @param string $method HTTP 方法（GET/POST/PUT/PATCH/DELETE）
     * @param string $path   API 路径，如 /api/v1/open/users
     * @param array|null $body 请求体（关联数组）
     * @return array 解析后的 JSON 响应
     * @throws Exception
     */
    private function request($method, $path, $body = null)
    {
        $url = $this->baseUrl . $path;
        $headers = $this->buildHeaders();

        $http = [
            'http' => [
                'method'  => $method,
                'header'  => implode("\r\n", $headers),
                'timeout' => 30,
                'ignore_errors' => true,
            ],
        ];

        if ($body !== null) {
            $jsonBody = json_encode($body, JSON_UNESCAPED_UNICODE);
            $http['http']['content'] = $jsonBody;
        }

        $context = stream_context_create($http);
        $response = file_get_contents($url, false, $context);

        if ($response === false) {
            throw new Exception('网络请求失败: ' . $url);
        }

        return json_decode($response, true);
    }

    // ==================== 开放 API（OpenAPI） ====================

    /**
     * 验证用户 Token 的有效性
     */
    public function verifyToken($token)
    {
        return $this->request('POST', '/api/v1/open/verify_token', ['token' => $token]);
    }

    /**
     * 查询当前租户下的用户列表
     */
    public function listUsers()
    {
        return $this->request('GET', '/api/v1/open/users');
    }

    /**
     * 创建新用户
     *
     * @param string $username 用户名（必填）
     * @param string $password 密码（必填，8-256字符）
     * @param string $userType 用户类型，internal/external，默认 internal
     * @param array $options 可选字段:
     *   - email: 邮箱
     *   - phone: 手机号
     *   - nickname: 昵称
     *   - department: 部门名称
     *   - dept_code: 部门编码
     *   - role_codes: 角色编码列表
     */
    public function createUser($username, $password, $userType = 'internal', $options = [])
    {
        $body = array_merge([
            'username' => $username,
            'password' => $password,
            'user_type' => $userType,
        ], $options);
        return $this->request('POST', '/api/v1/open/users', $body);
    }

    /**
     * 获取单个用户详情
     */
    public function getUser($userId)
    {
        return $this->request('GET', "/api/v1/open/users/{$userId}");
    }

    /**
     * 更新用户信息
     *
     * @param int $userId 用户 ID
     * @param array $data 可更新字段:
     *   - nickname: 昵称
     *   - email: 邮箱
     *   - phone: 手机号
     *   - avatar: 头像 URL
     *   - department: 部门名称
     *   - dept_code: 部门编码
     *   - role_codes: 角色编码列表
     */
    public function updateUser($userId, $data = [])
    {
        return $this->request('PUT', "/api/v1/open/users/{$userId}", $data);
    }

    /**
     * 启用/禁用用户
     *
     * @param int $userId 用户 ID
     * @param int $status 0=禁用，1=启用
     */
    public function toggleUserStatus($userId, $status)
    {
        return $this->request('PATCH', "/api/v1/open/users/{$userId}/status", ['status' => $status]);
    }

    /**
     * 检查用户是否具有指定权限
     */
    public function checkPermission($userId, $permissionCode)
    {
        return $this->request('POST', '/api/v1/open/check_permission', [
            'user_id' => $userId,
            'permission_code' => $permissionCode,
        ]);
    }

    // ==================== 用户认证 API（Auth） ====================

    /**
     * 用户名密码登录
     */
    public function login($username, $password)
    {
        return $this->request('POST', '/api/v1/auth/login', [
            'username' => $username,
            'password' => $password,
        ]);
    }

    /**
     * 发送短信验证码
     */
    public function smsSend($phone)
    {
        return $this->request('POST', '/api/v1/auth/sms/send', ['phone' => $phone]);
    }

    /**
     * 短信验证码登录
     */
    public function smsLogin($phone, $code)
    {
        return $this->request('POST', '/api/v1/auth/sms/login', [
            'phone' => $phone,
            'code' => $code,
        ]);
    }

    /**
     * 社交登录
     *
     * @param string $provider 第三方平台（wechat_mp/wechat_web/dingtalk/feishu）
     * @param string $code 第三方授权码
     * @param string|null $appKey 应用 AppKey，用于查找对应的微信配置（微信登录时必填）
     */
    public function socialLogin($provider, $code, $appKey = null)
    {
        $body = [
            'provider' => $provider,
            'code' => $code,
        ];
        if ($appKey !== null) {
            $body['app_key'] = $appKey;
        }
        return $this->request('POST', '/api/v1/auth/social/login', $body);
    }

    /**
     * 刷新 Token
     */
    public function refreshToken($refreshToken)
    {
        return $this->request('POST', '/api/v1/auth/refresh', [
            'refresh_token' => $refreshToken,
        ]);
    }

    /**
     * 获取当前登录用户信息（需要 access_token）
     */
    public function getUserinfo($accessToken)
    {
        $headers = $this->buildHeaders();
        $headers[] = 'Authorization: Bearer ' . $accessToken;

        $http = [
            'http' => [
                'method'  => 'GET',
                'header'  => implode("\r\n", $headers),
                'timeout' => 30,
                'ignore_errors' => true,
            ],
        ];

        $context = stream_context_create($http);
        $url = $this->baseUrl . '/api/v1/auth/userinfo';
        $response = file_get_contents($url, false, $context);

        if ($response === false) {
            throw new Exception('网络请求失败');
        }

        return json_decode($response, true);
    }

    /**
     * 更新当前登录用户个人信息
     */
    public function updateUserinfo($accessToken, $data = [])
    {
        $headers = $this->buildHeaders();
        $headers[] = 'Authorization: Bearer ' . $accessToken;

        $http = [
            'http' => [
                'method'  => 'PUT',
                'header'  => implode("\r\n", $headers),
                'content' => json_encode($data, JSON_UNESCAPED_UNICODE),
                'timeout' => 30,
                'ignore_errors' => true,
            ],
        ];

        $context = stream_context_create($http);
        $url = $this->baseUrl . '/api/v1/auth/userinfo';
        $response = file_get_contents($url, false, $context);

        if ($response === false) {
            throw new Exception('网络请求失败');
        }

        return json_decode($response, true);
    }

    /**
     * 修改密码
     */
    public function changePassword($accessToken, $oldPassword, $newPassword)
    {
        $body = ['old_password' => $oldPassword, 'new_password' => $newPassword];
        $headers = $this->buildHeaders();
        $headers[] = 'Authorization: Bearer ' . $accessToken;

        $http = [
            'http' => [
                'method'  => 'PATCH',
                'header'  => implode("\r\n", $headers),
                'content' => json_encode($body, JSON_UNESCAPED_UNICODE),
                'timeout' => 30,
                'ignore_errors' => true,
            ],
        ];

        $context = stream_context_create($http);
        $url = $this->baseUrl . '/api/v1/auth/userinfo/password';
        $response = file_get_contents($url, false, $context);

        if ($response === false) {
            throw new Exception('网络请求失败');
        }

        return json_decode($response, true);
    }

    /**
     * 用户登出
     */
    public function logout($accessToken)
    {
        $headers = $this->buildHeaders();
        $headers[] = 'Authorization: Bearer ' . $accessToken;

        $http = [
            'http' => [
                'method'  => 'POST',
                'header'  => implode("\r\n", $headers),
                'timeout' => 30,
                'ignore_errors' => true,
            ],
        ];

        $context = stream_context_create($http);
        $url = $this->baseUrl . '/api/v1/auth/logout';
        $response = file_get_contents($url, false, $context);

        if ($response === false) {
            throw new Exception('网络请求失败');
        }

        return json_decode($response, true);
    }
}

// ==================== 使用示例 ====================

// 使用 Composer 的 Guzzle（推荐）:
//   composer require guzzlehttp/guzzle
//   然后使用 GuzzleHttp\Client 替换 file_get_contents

// 命令行示例:
//   php openapi_client.php

// 仅在直接执行本文件时运行 demo 代码，被其他文件 require 时不执行
$isDirectExecution = (php_sapi_name() === 'cli' && (!isset($_SERVER['SCRIPT_FILENAME']) || realpath($_SERVER['SCRIPT_FILENAME']) === realpath(__FILE__)))
    || (php_sapi_name() !== 'cli' && basename($_SERVER['SCRIPT_FILENAME'] ?? '') === basename(__FILE__));

if (!$isDirectExecution) {
    return;
}

$appKey    = 'efc44f100f59fa0e08c1986715f587df';
$appSecret = 'ef276bb188138dcf6eaa3e958d82cbb91bd15f494df4b9ef3a5dffcc590c97c4';
$baseUrl   = 'http://localhost:8000';

$client = new OpenAPIClient($appKey, $appSecret, $baseUrl);

echo "==================================================\n";
echo "  统一账户认证服务 - OpenAPI PHP 调用示例\n";
echo "==================================================\n";

// 1. 验证 Token（使用无效 Token 演示）
echo "\n[1/5] 验证 Token ...\n";
$result = $client->verifyToken('invalid_jwt_token');
$valid = $result['data']['valid'] ?? null;
echo "      结果: valid=" . var_export($valid, true) . "\n";
echo "      message: " . ($result['message'] ?? '') . "\n";

// 2. 查询用户列表
echo "\n[2/5] 查询用户列表 ...\n";
$result = $client->listUsers();
$users = $result['data']['users'] ?? [];
echo "      共 " . count($users) . " 个用户\n";
foreach (array_slice($users, 0, 3) as $u) {
    echo "      - ID={$u['id']}, username={$u['username']}, email=" . ($u['email'] ?? '-') . "\n";
}

// 3. 创建新用户
echo "\n[3/5] 创建新用户 ...\n";
$suffix = rand(1000, 9999);
$result = $client->createUser(
    "php_demo_{$suffix}",
    'Demo@123456',
    'internal',
    [
        'email'    => "php_demo_{$suffix}@example.com",
        'phone'    => "139{$suffix}0001",
        'nickname' => "PHP演示用户{$suffix}",
    ]
);

if (($result['code'] ?? -1) === 0) {
    $newUserId = $result['data']['id'];
    echo "      创建成功: ID={$newUserId}, username=php_demo_{$suffix}\n";

    // 4. 更新用户
    echo "\n[4/5] 更新用户信息 ...\n";
    $result = $client->updateUser($newUserId, ['nickname' => "已更新-PHP演示用户{$suffix}"]);
    echo "      更新结果: " . ($result['message'] ?? '') . "\n";

    // 5. 检查权限
    echo "\n[5/5] 检查权限 (user:read) ...\n";
    $result = $client->checkPermission($newUserId, 'user:read');
    $data = $result['data'] ?? [];
    echo "      用户 ID={$data['user_id']}\n";
    echo "      权限编码={$data['permission_code']}\n";
    echo "      是否有权限=" . var_export($data['has_permission'] ?? null, true) . "\n";
} else {
    echo "      创建失败: " . ($result['message'] ?? '未知错误') . "\n";
}

echo "\n==================================================\n";
echo "  示例执行完毕\n";
echo "==================================================\n";
