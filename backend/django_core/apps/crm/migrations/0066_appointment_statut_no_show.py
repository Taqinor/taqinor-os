# PUB37 — nouvelle valeur de choix 'no_show' sur Appointment.statut (aucun
# changement de schéma, choices only) — distinct d'ANNULE (RDV annulé À
# L'AVANCE) : le prospect ne s'est jamais présenté.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0065_motifperte_est_junk'),
    ]

    operations = [
        migrations.AlterField(
            model_name='appointment',
            name='statut',
            field=models.CharField(
                choices=[
                    ('planifie', 'Planifié'),
                    ('confirme', 'Confirmé'),
                    ('effectue', 'Effectué'),
                    ('annule', 'Annulé'),
                    ('no_show', 'Absent (no-show)'),
                ],
                default='planifie',
                max_length=10,
                verbose_name='Statut',
            ),
        ),
    ]
