# Generated for U4 — WhatsApp-send a devis flips it to « envoyé ».

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ventes", "0026_paymentlink"),
    ]

    operations = [
        migrations.AddField(
            model_name="devis",
            name="date_envoi",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
