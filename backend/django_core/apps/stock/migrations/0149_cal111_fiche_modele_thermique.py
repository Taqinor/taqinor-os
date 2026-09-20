"""CAL111 — le modèle thermique du module (NOCT / coefficients Uc-Uv).

La fiche portait déjà les coefficients de température Voc/Pmax
(``temp_coeff_voc_pct_c``/``temp_coeff_pmax_pct_c``) mais AUCUN paramètre de
température de cellule — ``apps/ventes/solar_design.py`` fixe la température
cellule en dur (``DEFAULT_COLD_TEMP_C=-5``, ``DEFAULT_HOT_TEMP_C=70``).
PVsyst rend le modèle thermique sélectionnable et paramétré par NOCT/Uc/Uv.

ADDITIF PUR (``null=True``/``blank=True`` sur les trois champs) : aucune
fiche existante n'est modifiée, aucune valeur n'est écrite, aucun calcul ne
lit encore ces champs (``specs_for_produit`` n'est étendu qu'à CAL114). Vide
= « non publié », jamais 0 — règle fondateur « zéro chiffre inventé ».

RÉVERSIBLE : oui — trois ``AddField`` de colonnes NULL se défont par un
``RemoveField`` automatique, sans perte.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0148_stkcat27_recherche_unaccent_trgm'),
    ]

    operations = [
        migrations.AddField(
            model_name='fichetechnique',
            name='noct_c',
            field=models.DecimalField(
                blank=True, decimal_places=1,
                help_text='NOCT — température nominale de fonctionnement '
                          'en cellule (°C, condition 800 W/m², 20 °C, '
                          '1 m/s). Vide = non publié.',
                max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='uc_w_m2k',
            field=models.DecimalField(
                blank=True, decimal_places=2,
                help_text='Coefficient thermique constant Uc du modèle '
                          'Uc-Uv (W/m²K). Vide = non publié.',
                max_digits=6, null=True),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='uv_w_m3sk',
            field=models.DecimalField(
                blank=True, decimal_places=2,
                help_text='Coefficient thermique proportionnel au vent Uv '
                          'du modèle Uc-Uv (W/m³sK — « /(m/s)/m²/K »). '
                          'Vide = non publié.',
                max_digits=6, null=True),
        ),
    ]
