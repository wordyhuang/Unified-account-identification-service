#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.applications.models import Application
from apps.rbac.models import AppRoleBinding, ApiPermission

app = Application.objects.get(app_key='efc44f100f59fa0e08c1986715f587df')
print(f'为应用 {app.name} 添加所有开放API权限...')

all_perms = ApiPermission.objects.all()
added = 0
for perm in all_perms:
    if not AppRoleBinding.objects.filter(app=app, permission=perm).exists():
        AppRoleBinding.objects.create(app=app, permission=perm)
        added += 1
        print(f'  + 添加了: {perm.code} ({perm.method} {perm.path})')

print(f'完成！共添加了 {added} 个新权限。')
print('当前权限列表:')
for b in AppRoleBinding.objects.filter(app=app):
    print(f'  - {b.permission.code} ({b.permission.method} {b.permission.path})')
