"""TAILLES (ordre fondateur, 26/08/2026) — la CONFIGURATION des trois tailles.

Additive et réversible : un seul champ JSON nullable sur ``Devis``. Aucun
backfill, aucune valeur par défaut sur les lignes existantes — un devis
antérieur porte ``NULL`` et se comporte EXACTEMENT comme avant (la dérivation
moteur fournit alors les trois tailles).

Ce champ ne stocke QUE des entrées (nombre de panneaux, modules de batterie,
produits substitués). Aucun nombre dérivé (prix, économie, payback, couverture)
n'y entre jamais : c'est ce qui rend un prix tapé à la main physiquement
impossible.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0103_l_intprev_token_interne'),
    ]

    operations = [
        migrations.AddField(
            model_name='devis',
            name='offres_tailles_config',
            field=models.JSONField(
                blank=True, null=True,
                help_text='Configuration par taille (eco/recommande/max) '
                          'ajustée par le vendeur. Les nombres dérivés ne sont '
                          'jamais stockés : le moteur les recalcule depuis '
                          'cette configuration.',
                verbose_name='Tailles explorables (configuration ajustée)',
            ),
        ),
    ]
