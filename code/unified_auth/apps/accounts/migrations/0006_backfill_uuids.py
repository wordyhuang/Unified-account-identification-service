import uuid

from django.db import migrations


def backfill_uuids(apps, schema_editor):
    """为已有数据生成 UUID"""
    models_to_backfill = [
        ("Tenant", "accounts"),
        ("Department", "accounts"),
        ("User", "accounts"),
    ]

    for model_name, app_name in models_to_backfill:
        model = apps.get_model(app_name, model_name)
        for obj in model.objects.filter(uuid__isnull=True):
            obj.uuid = uuid.uuid4()
            obj.save(update_fields=["uuid"])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_auto_20260526_2157"),
    ]

    operations = [
        migrations.RunPython(backfill_uuids, migrations.RunPython.noop),
    ]
