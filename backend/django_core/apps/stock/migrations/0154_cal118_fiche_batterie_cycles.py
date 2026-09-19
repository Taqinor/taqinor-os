"""CAL118 — fiche batterie : nombre de cycles publié et vieillissement.

Le bloc batterie porte capacité/DoD/tension/puissances/rendement
aller-retour (``bat_rendement_ar_pct``) mais AUCUN nombre de cycles ni
courbe de vieillissement ; SAM (NREL) modélise explicitement la dégradation
calendaire ET cyclique.

ADDITIF PUR (``null=True``/``blank=True`` sur les trois champs) : aucune
fiche existante n'est modifiée. Vide = « non publié » — toute sortie citant
une durée de vie batterie doit afficher « fiche produit » ou « hypothèse de
référence », jamais un chiffre nu.

RÉVERSIBLE : oui — trois ``AddField`` de colonnes NULL se défont par un
``RemoveField`` automatique, sans perte.
"""
from decimal import Decimal

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0153_cal116_fiche_optimiseur'),
    ]

    operations = [
        migrations.AddField(
            model_name='fichetechnique',
            name='bat_cycles_publies',
            field=models.PositiveIntegerField(
                blank=True,
                help_text='Nombre de cycles publié par le fabricant (à '
                          'la rétention de fin de vie ci-dessous). Vide '
                          '= non publié.',
                null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='bat_retention_fin_de_vie_pct',
            field=models.DecimalField(
                blank=True, decimal_places=1,
                help_text='Rétention de capacité publiée en fin de vie '
                          'garantie (% de la capacité nominale, ex. '
                          '80 %). Vide = non publié.',
                max_digits=4, null=True,
                validators=[
                    django.core.validators.MinValueValidator(Decimal('1')),
                    django.core.validators.MaxValueValidator(Decimal('100')),
                ]),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='bat_garantie_annees',
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text='Durée de garantie publiée (années). Vide = '
                          'non publié.',
                null=True),
        ),
    ]
