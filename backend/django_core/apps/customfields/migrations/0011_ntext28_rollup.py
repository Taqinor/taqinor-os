"""NTEXT28 — champ ROLLUP (agrégat d'objets liés).

Purement ADDITIF et RÉVERSIBLE : un ``JSONField`` nullable, ignoré pour tout
type autre que ``rollup`` — aucun changement de comportement sur l'existant.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customfields', '0010_ntext9_field_role_permission'),
    ]

    operations = [
        migrations.AddField(
            model_name='customfielddef',
            name='rollup_config',
            field=models.JSONField(
                blank=True, null=True, verbose_name='Configuration rollup'),
        ),
    ]
