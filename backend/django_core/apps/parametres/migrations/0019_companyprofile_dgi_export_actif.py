# Generated for N105 — Capacité DGI LOCALE (interrupteur maître, défaut OFF).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parametres", "0018_statutconfig"),
    ]

    operations = [
        migrations.AddField(
            model_name="companyprofile",
            name="dgi_export_actif",
            field=models.BooleanField(default=False),
        ),
    ]
