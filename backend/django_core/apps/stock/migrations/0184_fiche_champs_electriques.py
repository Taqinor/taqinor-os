"""ACAL659 — six champs optionnels de ``FicheTechnique`` lus par les modèles
électriques (cellules en série, coefficient de Isc, réduction de puissance de
l'onduleur, MPPT indépendants, onduleurs compatibles d'un optimiseur).

Additive : six ``AddField`` nullables, aucune donnée écrite ; réversible.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0183_acal567_fiche_serrage_module'),
    ]

    operations = [
        migrations.AddField(
            model_name='fichetechnique',
            name='cellules_serie',
            field=models.PositiveIntegerField(
                blank=True, null=True,
                help_text='Module — nombre de cellules en série. Vide = non '
                          'publié.'),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='temp_coeff_isc_pct_c',
            field=models.DecimalField(
                blank=True, decimal_places=3, max_digits=5, null=True,
                help_text='Module — coefficient de température de Isc '
                          '(%/°C). Vide = non publié.'),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='ond_pnom_reduite_debut_c',
            field=models.DecimalField(
                blank=True, decimal_places=1, max_digits=5, null=True,
                help_text='Onduleur — température de début de réduction de '
                          'puissance (°C). Vide = non publié.'),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='ond_pnom_pente_pct_c',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=5, null=True,
                help_text='Onduleur — pente de réduction de puissance '
                          '(%/°C). Vide = non publié.'),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='ond_mppt_independants',
            field=models.BooleanField(
                blank=True, null=True,
                help_text='Onduleur — entrées MPPT indépendantes. Vide = non '
                          'publié.'),
        ),
        migrations.AddField(
            model_name='fichetechnique',
            name='opt_onduleurs_compatibles',
            field=models.JSONField(
                blank=True, null=True,
                help_text='Optimiseur — SKU des onduleurs compatibles '
                          '(liste). Vide = non publié.'),
        ),
    ]
