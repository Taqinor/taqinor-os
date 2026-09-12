"""CHT25 — RegulatoryDossier gagne une échéance EXPLICITE.

Additive only : deux colonnes nullable/blank sur une table existante, aucune
donnée existante touchée, entièrement revertable. ``prochaine_action`` note
l'action attendue (ex. « relancer l'opérateur ») et ``prochaine_action_date``
sa date ; le calendrier réglementaire (``calendrier_view.py``) les intègre à
ses alertes en plus des règles déjà déduites (dépôt en instruction, validité
d'accord).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0115_aud136_paymentlink_actif_unique'),
    ]

    operations = [
        migrations.AddField(
            model_name='regulatorydossier',
            name='prochaine_action',
            field=models.CharField(
                blank=True, default='', max_length=200,
                verbose_name='Prochaine action'),
        ),
        migrations.AddField(
            model_name='regulatorydossier',
            name='prochaine_action_date',
            field=models.DateField(
                blank=True, null=True,
                verbose_name='Date de la prochaine action'),
        ),
    ]
