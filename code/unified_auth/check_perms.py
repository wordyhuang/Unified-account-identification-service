#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.applications.models import Application
from apps.rbac.models import AppRoleBinding, ApiPermission

app = Application.objects.get(app_key='efc44f100f59fa0e08c1986715f587df')
print('应用:', app.name)
print('权限绑定:')
for b in AppRoleBinding.objects.filter(app=app):
    print(f'  - {b.permission.code} ({b.permission.method} {b.permission.path})')
print('所有可用权限:')
for p in ApiPermission.objects.all():
    print(f'  - {p.code} ({p.method} {p.path})')
