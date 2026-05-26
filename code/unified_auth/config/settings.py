import os
import pymysql
from pathlib import Path
from dotenv import load_dotenv

pymysql.version_info = (1, 4, 6)
pymysql.install_as_MySQLdb()

load_dotenv()

if os.getenv('DB_ENGINE', '').startswith('django.db.backends.mysql'):
    from django.db.backends.mysql.base import DatabaseWrapper
    DatabaseWrapper.data_types['DateTimeField'] = 'datetime'
    DatabaseWrapper.data_types['TimeField'] = 'time'
    DatabaseWrapper.data_types['JSONField'] = 'longtext'

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'dev-secret-key-change-in-production')
DEBUG = os.getenv('DJANGO_DEBUG', 'True').lower() == 'true'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '*').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'apps.accounts',
    'apps.users',
    'apps.applications',
    'apps.rbac',
    'apps.audit',
    'apps.openapi',
    'apps.admin_panel',
]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'middlewares.rate_limit.RateLimitMiddleware',
    'middlewares.app_auth.AppAuthenticationMiddleware',
    'middlewares.token_auth.TokenAuthenticationMiddleware',
    'middlewares.admin_auth.AdminAuthenticationMiddleware',
    'middlewares.permission.PermissionMiddleware',
    'middlewares.audit_log.AuditLogMiddleware',
]

ROOT_URLCONF = 'config.urls'

DATABASES = {
    'default': {
        'ENGINE': os.getenv('DB_ENGINE', 'django.db.backends.mysql'),
        'NAME': os.getenv('DB_NAME', 'unified_auth'),
        'USER': os.getenv('DB_USER', 'root'),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', '127.0.0.1'),
        'PORT': os.getenv('DB_PORT', '3306'),
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            'charset': 'utf8',
        },
    }
}

if os.getenv('DB_ENGINE', 'mysql') == 'sqlite':
    DATABASES['default'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.getenv('DB_NAME', ':memory:'),
    }

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'],
    'DEFAULT_PARSER_CLASSES': ['rest_framework.parsers.JSONParser'],
    'DEFAULT_AUTHENTICATION_CLASSES': ['common.auth.MiddlewareUserAuthentication'],
    'EXCEPTION_HANDLER': 'common.response.exception_handler',
    'UNAUTHENTICATED_USER': None,
}

CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', '').split(',') if not DEBUG else []

AUTH_USER_MODEL = 'accounts.User'

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'static'

STATICFILES_DIRS = [
    BASE_DIR / 'apps/admin_panel/static',
]

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

USE_TZ = False

JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', SECRET_KEY)
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 120
JWT_REFRESH_TOKEN_EXPIRE_DAYS = 30
