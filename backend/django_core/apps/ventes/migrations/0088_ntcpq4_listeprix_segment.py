from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ventes", "0087_qx43_mode_commercial"),
    ]

    operations = [
        migrations.AddField(
            model_name="listeprix",
            name="segment_client",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
    ]
