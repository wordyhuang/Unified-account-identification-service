-- ==============================================================
-- 统一账号识别服务 · 数据库初始化脚本 (MySQL 5.5+)
-- 使用方法: 在 MySQL 中执行本文件
--   mysql -u root -p < db_init.sql
-- ==============================================================

CREATE DATABASE IF NOT EXISTS `unified_auth`
    CHARACTER SET utf8
    COLLATE utf8_general_ci;

USE `unified_auth`;

-- -----------------------------------------------------------
-- 1. Django 系统表
-- -----------------------------------------------------------

CREATE TABLE `django_migrations` (
    `id`        INTEGER AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `app`       VARCHAR(255) NOT NULL,
    `name`      VARCHAR(255) NOT NULL,
    `applied`   DATETIME NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE `django_content_type` (
    `id`            INTEGER AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `app_label`     VARCHAR(100) NOT NULL,
    `model`         VARCHAR(100) NOT NULL,
    UNIQUE KEY `django_content_type_app_label_model_uniq` (`app_label`, `model`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE `auth_permission` (
    `id`                INTEGER AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `content_type_id`   INTEGER NOT NULL,
    `codename`          VARCHAR(100) NOT NULL,
    `name`              VARCHAR(255) NOT NULL,
    UNIQUE KEY `auth_permission_content_type_id_codename_uniq` (`content_type_id`, `codename`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE `auth_group` (
    `id`    INTEGER AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `name`  VARCHAR(150) NOT NULL UNIQUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE `auth_group_permissions` (
    `id`                INTEGER AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `group_id`          INTEGER NOT NULL,
    `permission_id`     INTEGER NOT NULL,
    UNIQUE KEY `auth_group_permissions_group_id_permission_id_uniq` (`group_id`, `permission_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE `django_admin_log` (
    `id`                INTEGER AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `action_time`       DATETIME NOT NULL,
    `object_id`         TEXT,
    `object_repr`       VARCHAR(200) NOT NULL,
    `change_message`    TEXT NOT NULL,
    `content_type_id`   INTEGER,
    `user_id`           INTEGER NOT NULL,
    `action_flag`       SMALLINT NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE `django_session` (
    `session_key`   VARCHAR(40) NOT NULL PRIMARY KEY,
    `session_data`  TEXT NOT NULL,
    `expire_date`   DATETIME NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- -----------------------------------------------------------
-- 2. 业务表
-- -----------------------------------------------------------

-- 2.1 企业租户
CREATE TABLE `tenant` (
    `id`            BIGINT AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `name`          VARCHAR(128) NOT NULL,
    `slug`          VARCHAR(64) NOT NULL UNIQUE,
    `status`        TINYINT(1) NOT NULL DEFAULT 1,
    `created_at`    DATETIME NOT NULL,
    `updated_at`    DATETIME NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- 2.2 用户 (替换 Django auth_user)
CREATE TABLE `user` (
    `id`                BIGINT AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `password`          VARCHAR(128) NOT NULL,
    `last_login`        DATETIME NULL,
    `is_superuser`      TINYINT(1) NOT NULL DEFAULT 0,
    `tenant_id`         BIGINT NOT NULL,
    `user_type`         VARCHAR(20) NOT NULL DEFAULT 'internal',
    `username`          VARCHAR(64) NOT NULL UNIQUE,
    `email`             VARCHAR(128) NULL,
    `phone`             VARCHAR(20) NULL,
    `nickname`          VARCHAR(128) NULL,
    `avatar`            VARCHAR(512) NULL,
    `department`        VARCHAR(128) NULL,
    `status`            SMALLINT NOT NULL DEFAULT 1,
    `last_login_at`     DATETIME NULL,
    `is_staff`          TINYINT(1) NOT NULL DEFAULT 0,
    `created_at`        DATETIME NOT NULL,
    `updated_at`        DATETIME NOT NULL,
    UNIQUE KEY `user_tenant_username_uniq` (`tenant_id`, `username`),
    UNIQUE KEY `user_tenant_email_uniq` (`tenant_id`, `email`),
    UNIQUE KEY `user_tenant_phone_uniq` (`tenant_id`, `phone`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- 用户-组 关联 (Django PermissionsMixin)
CREATE TABLE `user_groups` (
    `id`        INTEGER AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `user_id`   BIGINT NOT NULL,
    `group_id`  INTEGER NOT NULL,
    UNIQUE KEY `user_groups_user_id_group_id_uniq` (`user_id`, `group_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- 用户-权限 关联 (Django PermissionsMixin)
CREATE TABLE `user_user_permissions` (
    `id`                INTEGER AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `user_id`           BIGINT NOT NULL,
    `permission_id`     INTEGER NOT NULL,
    UNIQUE KEY `user_user_permissions_user_id_permission_id_uniq` (`user_id`, `permission_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- 2.3 社交账号绑定
CREATE TABLE `social_account` (
    `id`            BIGINT AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `user_id`       BIGINT NOT NULL,
    `provider`      VARCHAR(32) NOT NULL,
    `open_id`       VARCHAR(128) NOT NULL,
    `union_id`      VARCHAR(128) NULL,
    `extra_data`    TEXT NULL,
    `created_at`    DATETIME NOT NULL,
    UNIQUE KEY `social_account_provider_openid_uniq` (`provider`, `open_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- 2.4 接入应用
CREATE TABLE `application` (
    `id`                        BIGINT AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `tenant_id`                 BIGINT NOT NULL,
    `name`                      VARCHAR(128) NOT NULL,
    `app_key`                   VARCHAR(64) NOT NULL UNIQUE,
    `app_secret_hash`           VARCHAR(256) NOT NULL,
    `callback_urls`             TEXT NULL,
    `default_access_user_types` TEXT NULL,
    `status`                    TINYINT(1) NOT NULL DEFAULT 1,
    `created_at`                DATETIME NOT NULL,
    `updated_at`                DATETIME NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- 2.5 用户-应用访问授权
CREATE TABLE `user_app_access` (
    `id`            BIGINT AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `user_id`       BIGINT NOT NULL,
    `app_id`        BIGINT NOT NULL,
    `status`        VARCHAR(20) NOT NULL DEFAULT 'active',
    `granted_at`    DATETIME NOT NULL,
    `granted_by`    BIGINT NULL,
    UNIQUE KEY `user_app_access_user_app_uniq` (`user_id`, `app_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- 2.6 API 权限定义
CREATE TABLE `api_permission` (
    `id`            BIGINT AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `code`          VARCHAR(64) NOT NULL UNIQUE,
    `name`          VARCHAR(128) NOT NULL,
    `method`        VARCHAR(10) NOT NULL,
    `path`          VARCHAR(256) NOT NULL,
    `category`      VARCHAR(32) NOT NULL,
    `description`   VARCHAR(512) NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- 2.7 角色
CREATE TABLE `role` (
    `id`            BIGINT AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `tenant_id`     BIGINT NOT NULL,
    `name`          VARCHAR(64) NOT NULL,
    `code`          VARCHAR(64) NOT NULL,
    `created_at`    DATETIME NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- 2.8 角色-权限关联
CREATE TABLE `role_permission` (
    `id`                BIGINT AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `role_id`           BIGINT NOT NULL,
    `permission_id`     BIGINT NOT NULL,
    UNIQUE KEY `role_permission_role_perm_uniq` (`role_id`, `permission_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- 2.9 用户-角色关联
CREATE TABLE `user_role` (
    `id`        BIGINT AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `user_id`   BIGINT NOT NULL,
    `role_id`   BIGINT NOT NULL,
    UNIQUE KEY `user_role_user_role_uniq` (`user_id`, `role_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- 2.10 应用-权限绑定（应用被授权可调用的 API）
CREATE TABLE `app_role_binding` (
    `id`                BIGINT AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `app_id`            BIGINT NOT NULL,
    `permission_id`     BIGINT NOT NULL,
    `created_at`        DATETIME NOT NULL,
    UNIQUE KEY `app_role_binding_app_perm_uniq` (`app_id`, `permission_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- 2.11 审计日志
CREATE TABLE `audit_log` (
    `id`                BIGINT AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `tenant_id`         BIGINT NOT NULL,
    `actor_id`          BIGINT NULL,
    `actor_name`        VARCHAR(64) NULL,
    `action`            VARCHAR(64) NOT NULL,
    `resource_type`     VARCHAR(32) NULL,
    `resource_id`       BIGINT NULL,
    `detail`            TEXT NULL,
    `ip_address`        VARCHAR(45) NULL,
    `user_agent`        VARCHAR(512) NULL,
    `created_at`        DATETIME NOT NULL,
    INDEX `audit_log_tenant_time_idx` (`tenant_id`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- -----------------------------------------------------------
-- 3. 外键约束
-- -----------------------------------------------------------
ALTER TABLE `auth_permission`
    ADD CONSTRAINT `auth_permission_content_type_fk`
    FOREIGN KEY (`content_type_id`) REFERENCES `django_content_type` (`id`);

ALTER TABLE `auth_group_permissions`
    ADD CONSTRAINT `auth_group_permissions_group_fk`
    FOREIGN KEY (`group_id`) REFERENCES `auth_group` (`id`),
    ADD CONSTRAINT `auth_group_permissions_permission_fk`
    FOREIGN KEY (`permission_id`) REFERENCES `auth_permission` (`id`);

ALTER TABLE `django_admin_log`
    ADD CONSTRAINT `django_admin_log_content_type_fk`
    FOREIGN KEY (`content_type_id`) REFERENCES `django_content_type` (`id`);

ALTER TABLE `user`
    ADD CONSTRAINT `user_tenant_fk`
    FOREIGN KEY (`tenant_id`) REFERENCES `tenant` (`id`);

ALTER TABLE `user_groups`
    ADD CONSTRAINT `user_groups_user_fk`
    FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
    ADD CONSTRAINT `user_groups_group_fk`
    FOREIGN KEY (`group_id`) REFERENCES `auth_group` (`id`);

ALTER TABLE `user_user_permissions`
    ADD CONSTRAINT `user_user_permissions_user_fk`
    FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
    ADD CONSTRAINT `user_user_permissions_permission_fk`
    FOREIGN KEY (`permission_id`) REFERENCES `auth_permission` (`id`);

ALTER TABLE `social_account`
    ADD CONSTRAINT `social_account_user_fk`
    FOREIGN KEY (`user_id`) REFERENCES `user` (`id`);

ALTER TABLE `application`
    ADD CONSTRAINT `application_tenant_fk`
    FOREIGN KEY (`tenant_id`) REFERENCES `tenant` (`id`);

ALTER TABLE `user_app_access`
    ADD CONSTRAINT `user_app_access_user_fk`
    FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
    ADD CONSTRAINT `user_app_access_app_fk`
    FOREIGN KEY (`app_id`) REFERENCES `application` (`id`),
    ADD CONSTRAINT `user_app_access_granted_by_fk`
    FOREIGN KEY (`granted_by`) REFERENCES `user` (`id`);

ALTER TABLE `role`
    ADD CONSTRAINT `role_tenant_fk`
    FOREIGN KEY (`tenant_id`) REFERENCES `tenant` (`id`);

ALTER TABLE `role_permission`
    ADD CONSTRAINT `role_permission_role_fk`
    FOREIGN KEY (`role_id`) REFERENCES `role` (`id`),
    ADD CONSTRAINT `role_permission_permission_fk`
    FOREIGN KEY (`permission_id`) REFERENCES `api_permission` (`id`);

ALTER TABLE `user_role`
    ADD CONSTRAINT `user_role_user_fk`
    FOREIGN KEY (`user_id`) REFERENCES `user` (`id`),
    ADD CONSTRAINT `user_role_role_fk`
    FOREIGN KEY (`role_id`) REFERENCES `role` (`id`);

ALTER TABLE `app_role_binding`
    ADD CONSTRAINT `app_role_binding_app_fk`
    FOREIGN KEY (`app_id`) REFERENCES `application` (`id`),
    ADD CONSTRAINT `app_role_binding_permission_fk`
    FOREIGN KEY (`permission_id`) REFERENCES `api_permission` (`id`);

ALTER TABLE `audit_log`
    ADD CONSTRAINT `audit_log_tenant_fk`
    FOREIGN KEY (`tenant_id`) REFERENCES `tenant` (`id`);

-- -----------------------------------------------------------
-- 4. 初始数据
-- -----------------------------------------------------------

-- 4.1 Django Content Types
INSERT INTO `django_content_type` (`app_label`, `model`) VALUES
    ('admin', 'logentry'),
    ('auth', 'group'),
    ('auth', 'permission'),
    ('contenttypes', 'contenttype'),
    ('sessions', 'session'),
    ('accounts', 'tenant'),
    ('accounts', 'socialaccount'),
    ('accounts', 'user'),
    ('applications', 'application'),
    ('audit', 'auditlog'),
    ('rbac', 'apipermission'),
    ('rbac', 'approlebinding'),
    ('rbac', 'role'),
    ('rbac', 'rolepermission'),
    ('rbac', 'userrole'),
    ('users', 'userappaccess');

-- 4.2 默认租户
INSERT INTO `tenant` (`id`, `name`, `slug`, `status`, `created_at`, `updated_at`)
VALUES (1, '默认企业', 'default', 1, NOW(), NOW());

-- 4.3 预置 API 权限
INSERT INTO `api_permission` (`code`, `name`, `method`, `path`, `category`) VALUES
    ('token:verify',      '验证Token',       'POST',  '/api/v1/open/verify_token',         'auth'),
    ('user:read',         '读取用户列表',    'GET',   '/api/v1/open/users',                'user'),
    ('user:read_detail',  '读取用户详情',    'GET',   '/api/v1/open/users/:id',            'user'),
    ('user:create',       '创建用户',        'POST',  '/api/v1/open/users',                'user'),
    ('user:update',       '修改用户',        'PUT',   '/api/v1/open/users/:id',            'user'),
    ('user:status',       '修改用户状态',    'PATCH', '/api/v1/open/users/:id/status',     'user'),
    ('permission:check',  '校验权限',        'POST',  '/api/v1/open/check_permission',     'permission');

-- 4.4 管理员角色
INSERT INTO `role` (`id`, `tenant_id`, `name`, `code`, `created_at`)
VALUES (1, 1, '管理员', 'admin', NOW());

-- 4.5 管理员角色关联全部权限
INSERT INTO `role_permission` (`role_id`, `permission_id`)
SELECT 1, `id` FROM `api_permission`;

-- 4.6 创建管理员用户 (默认密码: admin123456)
-- 密码哈希使用 Django PBKDF2 + SHA256
INSERT INTO `user` (
    `id`, `password`, `last_login`, `is_superuser`,
    `tenant_id`, `user_type`, `username`,
    `email`, `phone`, `nickname`, `avatar`, `department`,
    `status`, `last_login_at`, `is_staff`,
    `created_at`, `updated_at`
) VALUES (
    1,
    'pbkdf2_sha256$260000$re9gOvUXFIs6iG3Q5juzol$J6Yl/zxATS22jH9jZy9VBVbmOvK5AVT1oMrtZKR/rLA=',
    NULL, 1,
    1, 'internal', 'admin',
    NULL, NULL, '管理员', NULL, NULL,
    1, NULL, 1,
    NOW(), NOW()
);

-- -----------------------------------------------------------
-- 5. Django 迁移记录（标记已应用的迁移）
-- -----------------------------------------------------------
INSERT INTO `django_migrations` (`app`, `name`, `applied`) VALUES
    ('contenttypes', '0001_initial', NOW()),
    ('contenttypes', '0002_remove_content_type_name', NOW()),
    ('auth', '0001_initial', NOW()),
    ('auth', '0002_alter_permission_name_max_length', NOW()),
    ('auth', '0003_alter_user_email_max_length', NOW()),
    ('auth', '0004_alter_user_username_opts', NOW()),
    ('auth', '0005_alter_user_last_login_null', NOW()),
    ('auth', '0006_require_contenttypes_0002', NOW()),
    ('auth', '0007_alter_validators_add_error_messages', NOW()),
    ('auth', '0008_alter_user_username_max_length', NOW()),
    ('auth', '0009_alter_user_last_name_max_length', NOW()),
    ('auth', '0010_alter_group_name_max_length', NOW()),
    ('auth', '0011_update_proxy_permissions', NOW()),
    ('auth', '0012_alter_user_first_name_max_length', NOW()),
    ('accounts', '0001_initial', NOW()),
    ('admin', '0001_initial', NOW()),
    ('admin', '0002_logentry_remove_auto_add', NOW()),
    ('admin', '0003_logentry_add_action_flag_choices', NOW()),
    ('applications', '0001_initial', NOW()),
    ('audit', '0001_initial', NOW()),
    ('rbac', '0001_initial', NOW()),
    ('sessions', '0001_initial', NOW()),
    ('users', '0001_initial', NOW());
