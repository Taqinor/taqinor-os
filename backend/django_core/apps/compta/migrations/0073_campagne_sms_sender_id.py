"""XMKT15 — Conformité SMS Maroc : sender-ID alphanumérique déclaré.

Additif : ``Campagne.sms_sender_id`` (champ informatif société — les routes
IAM/Orange/inwi exigent un expéditeur enregistré). Ne touche à aucun autre
champ existant.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('compta', '0072_rebondsoft'),
    ]

    operations = [
        migrations.AddField(
            model_name='campagne',
            name='sms_sender_id',
            field=models.CharField(blank=True, default='', max_length=11, verbose_name='Sender-ID SMS déclaré (XMKT15)'),
        ),
    ]
