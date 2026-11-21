"""ACAL567 — zone de serrage fabricant d'un module sur ``FicheTechnique``.

Trois champs optionnels (minimum et maximum en mm, source). Additive :
aucune donnée écrite, fiches existantes vides ; réversible.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0182_fiche_onduleur_dc_max_et_mppt_15_20kw'),
    ]

    operations = [
        migrations.AddField(
            model_name='fichetechnique',
            name='serrage_min_mm',
            field=models.PositiveIntegerField(
                blank=True, null=True,
                help_text='Module — zone de serrage fabricant, minimum (mm).'),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='serrage_max_mm',
            field=models.PositiveIntegerField(
                blank=True, null=True,
                help_text='Module — zone de serrage fabricant, maximum (mm).'),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='serrage_source',
            field=models.TextField(
                blank=True, default='',
                help_text='Module — source de la zone de serrage (notice, '
                          'page).'),
        ),
    ]
