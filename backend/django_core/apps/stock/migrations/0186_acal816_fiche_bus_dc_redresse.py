"""ACAL816 — tension redressée du bus DC d'un variateur de pompage sur
``FicheTechnique``.

Additive : un ``AddField`` nullable, aucune donnée écrite ; réversible.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0185_fiche_sous_chaines_module'),
    ]

    operations = [
        migrations.AddField(
            model_name='fichetechnique',
            name='var_bus_dc_redresse_v',
            field=models.DecimalField(
                blank=True, decimal_places=1, max_digits=6, null=True,
                help_text='Variateur — tension DC redressée admise du bus '
                          '(V). Vide = non publié.'),
        ),
    ]
