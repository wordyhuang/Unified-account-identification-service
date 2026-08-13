from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rbac", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL("DELETE FROM app_role_binding", reverse_sql=migrations.RunSQL.noop),
        migrations.AlterUniqueTogether(
            name="approlebinding",
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name="approlebinding",
            name="permission",
        ),
        migrations.AddField(
            model_name="approlebinding",
            name="role",
            field=models.ForeignKey(on_delete=models.deletion.CASCADE, to="rbac.role"),
        ),
        migrations.AlterUniqueTogether(
            name="approlebinding",
            unique_together={("app", "role")},
        ),
    ]
