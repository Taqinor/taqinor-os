"""NTAPI5 — épingle la version d'API servie à une clé (`ApiKey.api_version`).

Additif : nouveau champ `CharField`, défaut `'v1'` — aucune conséquence sur
les clés existantes (toutes migrent vers 'v1', valeur déjà servie de facto
aujourd'hui, il n'existe qu'une seule version)."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('publicapi', '0007_yhard1_encrypt_webhook_secret'),
    ]

    operations = [
        migrations.AddField(
            model_name='apikey',
            name='api_version',
            field=models.CharField(blank=True, default='v1', max_length=10),
        ),
    ]
