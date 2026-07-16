"""NTAPI10 — clé d'idempotence (`Idempotency-Key`) sur toutes les livraisons
webhook, une par ÉVÈNEMENT SOURCE (réutilise `event_id`), partagée par toutes
les tentatives (envoi original + reprises NTAPI8/YAPIC8).

Additif : nouveau champ `CharField` indexé, défaut vide — aucune conséquence
sur les lignes existantes (vide, comme `event_id` l'était avant YAPIC8)."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('publicapi', '0009_ntapi8_webhookdeliveryattempt'),
    ]

    operations = [
        migrations.AddField(
            model_name='webhookdelivery',
            name='idempotency_key',
            field=models.CharField(
                blank=True, db_index=True, default='', max_length=36),
        ),
    ]
