#!/usr/bin/env node
/**
 * OpenAPI Node.js SDK - 调用示例
 *
 * 运行: node demo.js
 */
const { OpenAPIClient } = require('./openapi_client');

const APP_KEY = 'efc44f100f59fa0e08c1986715f587df';
const APP_SECRET = 'ef276bb188138dcf6eaa3e958d82cbb91bd15f494df4b9ef3a5dffcc590c97c4';
const BASE_URL = 'http://localhost:8000';

const client = new OpenAPIClient(APP_KEY, APP_SECRET, BASE_URL);

async function main() {
    console.log('==================================================');
    console.log('  统一账户认证服务 - OpenAPI Node.js 调用示例');
    console.log('==================================================');

    // 1. 验证 Token
    console.log('\n[1/5] 验证 Token ...');
    let result = await client.verifyToken('invalid_jwt_token');
    console.log('      结果: valid=' + result.data?.valid);
    console.log('      message: ' + result.message);

    // 2. 查询用户列表
    console.log('\n[2/5] 查询用户列表 ...');
    result = await client.listUsers();
    const users = result.data?.users || [];
    console.log('      共 ' + users.length + ' 个用户');
    users.slice(0, 3).forEach(u => {
        console.log('      - ID=' + u.id + ', username=' + u.username + ', email=' + (u.email || '-'));
    });

    // 3. 创建新用户
    console.log('\n[3/5] 创建新用户 ...');
    const suffix = Math.floor(Math.random() * 9000) + 1000;
    result = await client.createUser(
        'js_demo_' + suffix,
        'Demo@123456',
        'internal',
        {
            email: 'js_demo_' + suffix + '@example.com',
            phone: '136' + suffix + '0001',
            nickname: 'JS演示用户' + suffix,
        }
    );

    if (result.code === 0) {
        const newUserId = result.data.id;
        console.log('      创建成功: ID=' + newUserId + ', username=js_demo_' + suffix);

        // 4. 更新用户
        console.log('\n[4/5] 更新用户信息 ...');
        result = await client.updateUser(newUserId, { nickname: '已更新-JS演示用户' + suffix });
        console.log('      更新结果: ' + result.message);

        // 5. 检查权限
        console.log('\n[5/5] 检查权限 (user:read) ...');
        result = await client.checkPermission(newUserId, 'user:read');
        const data = result.data || {};
        console.log('      用户 ID=' + data.user_id);
        console.log('      权限编码=' + data.permission_code);
        console.log('      是否有权限=' + data.has_permission);
    } else {
        console.log('      创建失败: ' + (result.message || '未知错误'));
    }

    console.log('\n==================================================');
    console.log('  示例执行完毕');
    console.log('==================================================');
}

main().catch(console.error);
