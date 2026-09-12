"""NTWFL5 — relance à mi-SLA des étapes BPM (additive, réversible).

``WorkflowStepInstance.dernier_rappel_le`` : marqueur anti-double-
notification posé par ``core.workflow.marquer_rappel_envoye`` la première
fois qu'un rappel à 50% du SLA restant est émis.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0050_ntwfl4_calendrier_ouvre'),
    ]

    operations = [
        migrations.AddField(
            model_name='workflowstepinstance',
            name='dernier_rappel_le',
            field=models.DateTimeField(
                blank=True, null=True,
                help_text='Vide = jamais relancée ; posé une seule fois '
                          '(jamais un second rappel pour la même étape).',
                verbose_name='Dernier rappel envoyé le'),
        ),
    ]
