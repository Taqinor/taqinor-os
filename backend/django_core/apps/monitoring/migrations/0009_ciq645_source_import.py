# CIQ645 (Groupe CIQ, D-CIQ-18) — source « import » des relevés de production
# (import CSV). AlterField de choix uniquement (max_length inchangé) : additif
# et réversible, aucune donnée existante modifiée.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('monitoring', '0008_ciq644_sla_sans_defaut'),
    ]

    operations = [
        migrations.AlterField(
            model_name='productionreading',
            name='source',
            field=models.CharField(
                choices=[('manual', 'Saisie manuelle'),
                         ('auto', 'Automatique'),
                         ('import', 'Import CSV')],
                default='manual', max_length=10),
        ),
    ]
