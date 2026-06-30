# FG26 — RGPD : drapeau d'anonymisation client (droit à l'effacement).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0030_pointcontact"),
    ]

    operations = [
        migrations.AddField(
            model_name="client",
            name="is_anonymized",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="client",
            name="anonymized_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
