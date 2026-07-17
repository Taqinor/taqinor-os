"""NTAPI23 — rotation de clé API SANS COUPURE (grace period).

Additif : nouveau champ `ApiKey.expire_le` (`DateTimeField`, `null=True`) —
`None` sur toute clé existante (comportement historique inchangé, aucune
clé n'est en grace period tant que `rotate()` n'a pas été appelé)."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('publicapi', '0011_ntapi26_27_environnement_sandboxtenant'),
    ]

    operations = [
        migrations.AddField(
            model_name='apikey',
            name='expire_le',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
