import uuid

from django.db import migrations


def backfill_uuids(apps, schema_editor):
    """为已有数据生成 UUID"""
    model = apps.get_model("applications", "Application")
    for obj in model.objects.filter(uuid__isnull=True):
        obj.uuid = uuid.uuid4()
        obj.save(update_fields=["uuid"])


class Migration(migrations.Migration):

    dependencies = [
        ("applications", "0004_application_uuid"),
    ]

    operations = [
        migrations.RunPython(backfill_uuids, migrations.RunPython.noop),
    ]
