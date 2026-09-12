"""NTWFL4 — SLA en heures OUVRÉES (additive, réversible).

``WorkflowStepDefinition.calendrier_ouvre`` (défaut FAUX = comportement
inchangé) : activé, ``core.workflow._sla_echeance`` consomme le calendrier
d'heures ouvrées de la société (``apps.notifications.calendar_utils``) au
lieu de compter en heures brutes.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0049_ntwfl1_matriceapprobation'),
    ]

    operations = [
        migrations.AddField(
            model_name='workflowstepdefinition',
            name='calendrier_ouvre',
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Active, l'échéance SLA saute les jours non ouvrés/"
                    'fériés de la société au lieu de compter en heures '
                    'brutes.'),
                verbose_name='Échéance en jours ouvrés'),
        ),
    ]
