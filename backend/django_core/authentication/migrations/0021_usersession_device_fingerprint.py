from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0020_company_benchmarking_opt_in"),
    ]

    operations = [
        migrations.AddField(
            model_name="usersession",
            name="device_fingerprint",
            field=models.CharField(
                blank=True, db_index=True, default="", max_length=64),
        ),
    ]
