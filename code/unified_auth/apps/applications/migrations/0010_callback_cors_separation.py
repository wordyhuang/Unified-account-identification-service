from django.db import migrations, models

import common.fields


def split_callback_urls(apps, schema_editor):
    """存量数据迁移：把 callback_urls 的 origin 复制到 cors_origins，保持原行为。"""
    from urllib.parse import urlparse

    def origin_of(url):
        parsed = urlparse(str(url or ""))
        if parsed.scheme in ("http", "https") and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
        return ""

    Application = apps.get_model("applications", "Application")
    for app in Application.objects.exclude(callback_urls__isnull=True):
        origins = []
        for url in (app.callback_urls or []):
            o = origin_of(url)
            if o and o not in origins:
                origins.append(o)
        app.cors_origins = origins
        app.save(update_fields=["cors_origins"])


class Migration(migrations.Migration):

    dependencies = [
        ("applications", "0009_auto_20261125_2318"),
    ]

    operations = [
        migrations.AddField(
            model_name="application",
            name="cors_origins",
            field=common.fields.CompatibleJSONField(blank=True, null=True, verbose_name="跨域/页面对接域列表"),
        ),
        migrations.AlterField(
            model_name="application",
            name="callback_urls",
            field=common.fields.CompatibleJSONField(blank=True, null=True, verbose_name="授权回调地址列表"),
        ),
        migrations.RunPython(split_callback_urls, migrations.RunPython.noop),
    ]
