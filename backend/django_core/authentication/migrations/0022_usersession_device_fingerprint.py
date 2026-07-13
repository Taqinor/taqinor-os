from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0021_ntsec9_usersession_last_mfa_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="usersession",
            name="device_fingerprint",
            field=models.CharField(
                blank=True, db_index=True, default="", max_length=64),
        ),
    ]
