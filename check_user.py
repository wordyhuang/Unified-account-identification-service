import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from apps.accounts.models import User

u = User.objects.get(username='openapi_test_user')
print(f'id={u.id}, username={u.username}, tenant_id={u.tenant_id}')
for pw in ['test1234', '123456', 'admin123', 'password']:
    print(f'  check_password({pw}): {u.check_password(pw)}')
