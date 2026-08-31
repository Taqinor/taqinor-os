"""NTDATA39 — canal WhatsApp (lien tokenisé) pour les rapports planifiés.

Deux champs ADDITIFS inertes par défaut : ``canal='email'`` reproduit
EXACTEMENT le comportement historique (pièce jointe .xlsx par email), et
``destinataires_whatsapp`` est vide. Le canal WhatsApp reste par ailleurs un
NO-OP TOTAL tant que le fondateur n'a pas provisionné les credentials Meta
(``WHATSAPP_BSP_ENABLED`` + les trois variables ``WHATSAPP_BSP_*``).

CHAÎNE : enchaîne explicitement sur la migration NTDATA38.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reporting', '0014_ntdata38_cadence_mensuelle'),
    ]

    operations = [
        migrations.AddField(
            model_name='savedreport',
            name='canal',
            field=models.CharField(
                choices=[('email', 'Email'), ('whatsapp', 'WhatsApp')],
                default='email', max_length=10, verbose_name='Canal'),
        ),
        migrations.AddField(
            model_name='savedreport',
            name='destinataires_whatsapp',
            field=models.TextField(blank=True, default='',
                                   verbose_name='Numéros WhatsApp'),
        ),
    ]
