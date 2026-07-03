# Generated for XPRJ2 -- Billable classification + activity type on timesheets.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_projet', '0023_timesheet_workflow_periode_verrouillee'),
    ]

    operations = [
        migrations.AddField(
            model_name='timesheet',
            name='facturable',
            field=models.BooleanField(default=True, verbose_name='Facturable'),
        ),
        migrations.AddField(
            model_name='timesheet',
            name='type_activite',
            field=models.CharField(
                choices=[
                    ('etude', 'Étude'),
                    ('pose', 'Pose'),
                    ('raccordement', 'Raccordement'),
                    ('mes', 'Mise en service'),
                    ('deplacement', 'Déplacement'),
                    ('sav', 'SAV'),
                    ('admin', 'Administratif'),
                ],
                default='pose', max_length=15, verbose_name="Type d'activité"),
        ),
        migrations.AddField(
            model_name='timesheet',
            name='taux_facturation',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=10, null=True,
                verbose_name='Taux de facturation (MAD/h)'),
        ),
    ]
