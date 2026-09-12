"""NTWFL7 — garde de transition (branche simple) sur WorkflowStepDefinition
(additive, réversible).

``condition_transition`` (format core.rules.evaluate_condition_group, FG367 —
aucun nouveau moteur de conditions) + ``etape_alternative_si_echec`` (ordre de
l'étape de repli) ; ``WorkflowStepInstance`` gagne le statut ``ignoree``
(branche non empruntée), additif aux 4 statuts existants.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0051_ntwfl5_dernier_rappel_le'),
    ]

    operations = [
        migrations.AddField(
            model_name='workflowstepdefinition',
            name='condition_transition',
            field=models.JSONField(
                blank=True, default=None, null=True,
                help_text=(
                    'Garde évaluée contre la cible (format core.rules) '
                    "avant qu'une étape automatique ne s'auto-approuve. "
                    'Vide = toujours franchie.'),
                verbose_name='Condition de transition'),
        ),
        migrations.AddField(
            model_name='workflowstepdefinition',
            name='etape_alternative_si_echec',
            field=models.PositiveIntegerField(
                blank=True, null=True,
                help_text=(
                    "Ordre (dans la même définition) de l'étape vers "
                    'laquelle router si la garde ci-dessus échoue.'),
                verbose_name='Étape alternative si échec'),
        ),
        migrations.AlterField(
            model_name='workflowstepinstance',
            name='statut',
            field=models.CharField(
                choices=[
                    ('en_attente', 'En attente'),
                    ('approuve', 'Approuvé'),
                    ('rejete', 'Rejeté'),
                    ('escalade', 'Escaladé'),
                    ('ignoree', 'Ignorée (branche non empruntée)'),
                ],
                default='en_attente', max_length=16, verbose_name='Statut'),
        ),
    ]
