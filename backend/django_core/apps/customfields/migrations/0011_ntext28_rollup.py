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
        # NTEXT28 — le choix « rollup » entre dans la liste fermée de ``type``
        # (0009 n'avait ajouté que « formula ») : AlterField aligné sur l'état
        # final du modèle, sinon derive modele<->migration en CI.
        migrations.AlterField(
            model_name='customfielddef',
            name='type',
            field=models.CharField(
                choices=[
                    ('text', 'Texte'), ('number', 'Nombre'), ('date', 'Date'),
                    ('choice', 'Choix'), ('boolean', 'Oui/Non'),
                    ('relation', 'Relation'), ('fichier', 'Fichier'),
                    ('ia', 'Champ IA'),
                    ('formula', 'Champ calculé (formule)'),
                    ('rollup', 'Agrégat (rollup)'),
                ],
                default='text', max_length=12),
        ),
        migrations.AddField(
            model_name='customfielddef',
            name='rollup_config',
            field=models.JSONField(
                blank=True, null=True, verbose_name='Configuration rollup'),
        ),
    ]
