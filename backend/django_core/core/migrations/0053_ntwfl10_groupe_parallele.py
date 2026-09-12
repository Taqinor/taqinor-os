"""NTWFL10 — étapes en parallèle (fan-out/fan-in simple), additive, réversible.

``WorkflowStepDefinition.groupe_parallele`` : les étapes d'une définition
partageant le même entier démarrent ENSEMBLE. Vide (défaut) = comportement
séquentiel inchangé.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0052_ntwfl7_garde_transition'),
    ]

    operations = [
        migrations.AddField(
            model_name='workflowstepdefinition',
            name='groupe_parallele',
            field=models.PositiveIntegerField(
                blank=True, null=True,
                help_text=(
                    'Étapes partageant ce même entier démarrent ensemble '
                    '(fan-out/fan-in simple). Vide = séquentiel (défaut).'),
                verbose_name='Groupe parallèle'),
        ),
    ]
