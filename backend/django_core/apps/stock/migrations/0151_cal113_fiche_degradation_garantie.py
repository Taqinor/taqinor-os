"""CAL113 — dégradation annuelle et paliers de garantie du module.

``grep degradation apps/stock/models.py`` = 0 : ces valeurs vivaient en
constantes de code (``apps/ventes/solar_design.py`` :
``DEFAULT_WARRANTY_FLOORS = {10: 0.90, 25: 0.80}``,
``DEFAULT_YEAR1_DEGRADATION = 0.02``) alors que la datasheet les publie.

ADDITIF PUR (``null=True``/``blank=True`` sur les quatre champs) : aucune
fiche existante n'est modifiée. Vide = « non publié » — le moteur ventes
retombe alors sur son hypothèse de référence et le dit (discipline déjà
appliquée au rendement aller-retour batterie, QJR137).

RÉVERSIBLE : oui — quatre ``AddField`` de colonnes NULL se défont par un
``RemoveField`` automatique, sans perte.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0150_cal112_fiche_bifacialite_pct'),
    ]

    operations = [
        migrations.AddField(
            model_name='fichetechnique',
            name='degradation_annuelle_pct',
            field=models.DecimalField(
                blank=True, decimal_places=2,
                help_text='Dégradation annuelle linéaire publiée (%/an), '
                          'années 2+. Vide = non publié.',
                max_digits=4, null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='degradation_annee1_pct',
            field=models.DecimalField(
                blank=True, decimal_places=2,
                help_text='Dégradation de la première année publiée (%). '
                          'Vide = non publié.',
                max_digits=4, null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='garantie_pct_a_10_ans',
            field=models.DecimalField(
                blank=True, decimal_places=1,
                help_text='Palier de garantie de production à 10 ans '
                          'publié (% de Pmax nominal). Vide = non publié.',
                max_digits=4, null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='garantie_pct_a_25_ans',
            field=models.DecimalField(
                blank=True, decimal_places=1,
                help_text='Palier de garantie de production à 25 ans '
                          'publié (% de Pmax nominal). Vide = non publié.',
                max_digits=4, null=True),
        ),
    ]
