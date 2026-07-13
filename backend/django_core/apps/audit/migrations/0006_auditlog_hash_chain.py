from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0005_alter_auditlog_action"),
    ]

    operations = [
        migrations.AddField(
            model_name="auditlog",
            name="prev_hash",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="auditlog",
            name="entry_hash",
            field=models.CharField(
                blank=True, db_index=True, default="", max_length=64),
        ),
    ]
