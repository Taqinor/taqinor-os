"""ACAL720 — sous-chaînes par module (brins protégés par une diode de
dérivation) sur ``FicheTechnique``.

Additive : un ``AddField`` nullable, aucune donnée écrite ; réversible.
"""
import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0184_fiche_champs_electriques'),
    ]

    operations = [
        migrations.AddField(
            model_name='fichetechnique',
            name='sous_chaines_par_module',
            field=models.PositiveSmallIntegerField(
                blank=True, null=True,
                validators=[django.core.validators.MinValueValidator(1)],
                help_text='Module — sous-chaînes par module (brins protégés '
                          'par une diode de dérivation), lu sur la fiche '
                          'constructeur. Vide = non publié.'),
        ),
    ]
