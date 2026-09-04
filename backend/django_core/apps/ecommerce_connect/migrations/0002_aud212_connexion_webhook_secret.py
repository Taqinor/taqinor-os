# AUD212 — secret HMAC PAR CONNEXION (remplace le secret `.env` global, qui
# rendait les webhooks forgeables d'une société vers une autre). Additive :
# défaut '' = aucune connexion existante n'accepte de webhook tant que le
# fondateur n'a pas posé son secret (fail-closed, jamais une acceptation
# héritée du secret partagé).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ecommerce_connect', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='connexionecommerce',
            name='webhook_secret',
            field=models.CharField(
                blank=True,
                default='',
                help_text=(
                    'Secret HMAC-SHA256 propre à cette boutique (AUD212). '
                    "Vide = aucun webhook accepté. N'est exposé par aucune "
                    'API.'),
                max_length=128,
            ),
        ),
    ]
