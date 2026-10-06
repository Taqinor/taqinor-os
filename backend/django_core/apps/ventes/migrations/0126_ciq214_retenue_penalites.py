"""CIQ214 — conditions C&I SEULEMENT à la demande du client (D-CIQ-14) :
``Devis.retenue_garantie``, ``penalites_retard_livraison`` et ``caution``.

ADDITIF : trois JSONField nullables, vides par défaut (aucune valeur posée,
aucun devis existant modifié). Réversible : ``migrate ventes 0125``.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0125_ciq213_tiers_payeur'),
    ]

    operations = [
        migrations.AddField(
            model_name='devis',
            name='retenue_garantie',
            field=models.JSONField(blank=True, default=None, null=True),
        ),
        migrations.AddField(
            model_name='devis',
            name='penalites_retard_livraison',
            field=models.JSONField(blank=True, default=None, null=True),
        ),
        migrations.AddField(
            model_name='devis',
            name='caution',
            field=models.JSONField(blank=True, default=None, null=True),
        ),
    ]
