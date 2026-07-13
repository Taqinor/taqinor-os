"""YAPIC8 — champ ``event_id`` (uuid4 stable) sur WebhookDelivery.

Additif et sûr sur données existantes : CharField avec ``default=''`` (les
livraisons historiques restent sans event_id), ``db_index=True`` pour retrouver
toutes les tentatives d'un même évènement.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('publicapi', '0004_serviceaccount'),
    ]

    operations = [
        migrations.AddField(
            model_name='webhookdelivery',
            name='event_id',
            field=models.CharField(
                blank=True, db_index=True, default='', max_length=36),
        ),
    ]
