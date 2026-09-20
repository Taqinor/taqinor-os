"""CAL115 — chaînes par MPPT, entrées par MPPT, puissance apparente max.

``ond_n_mppt``, les plages MPPT, ``ond_v_max_abs``, ``ond_i_max_mppt_a``,
``ond_isc_max_mppt_a`` existent déjà — mais rien ne dit COMBIEN de chaînes
une entrée accepte, ni la puissance apparente (kVA), ni la puissance DC
maximale recommandée. PVsyst modélise 8-12 entrées MPPT avec limitation de
courant PAR entrée.

ADDITIF PUR (``null=True``/``blank=True`` sur les quatre champs) : aucune
fiche existante n'est modifiée. Vide = non publié ; ``fenetre_onduleur_pour_
produit`` (apps/ventes/solar_design.py:406) ne change pas un seul verdict
pour une fiche qui ne les porte pas.

RÉVERSIBLE : oui — quatre ``AddField`` de colonnes NULL se défont par un
``RemoveField`` automatique, sans perte.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0151_cal113_fiche_degradation_garantie'),
    ]

    operations = [
        migrations.AddField(
            model_name='fichetechnique',
            name='ond_entrees_par_mppt',
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text="Nombre d'entrées (chaînes physiques) par "
                          'tracker MPPT. Vide = non publié.',
                null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='ond_chaines_max_par_mppt',
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text='Nombre maximal de chaînes acceptées par '
                          'tracker MPPT. Vide = non publié.',
                null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='ond_s_max_kva',
            field=models.DecimalField(
                blank=True, decimal_places=2,
                help_text='Puissance apparente AC maximale (kVA). Vide = '
                          'non publié.',
                max_digits=6, null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='ond_dc_max_kwc',
            field=models.DecimalField(
                blank=True, decimal_places=2,
                help_text='Puissance DC maximale recommandée (kWc). Vide '
                          '= non publié.',
                max_digits=6, null=True),
        ),
    ]
