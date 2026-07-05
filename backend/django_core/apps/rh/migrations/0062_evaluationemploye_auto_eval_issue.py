# Generated for XRH26 — auto-évaluation + issues d'évaluation structurées.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rh', '0061_entretiensortie'),
    ]

    operations = [
        migrations.AddField(
            model_name='evaluationemploye',
            name='auto_evaluation',
            field=models.TextField(
                blank=True, default='', verbose_name='Auto-évaluation'),
        ),
        migrations.AddField(
            model_name='evaluationemploye',
            name='note_auto',
            field=models.DecimalField(
                blank=True, decimal_places=1, max_digits=3, null=True,
                verbose_name='Note (auto-évaluation)'),
        ),
        migrations.AddField(
            model_name='evaluationemploye',
            name='issue',
            field=models.CharField(
                blank=True, choices=[
                    ('augmentation_proposee', 'Augmentation proposée'),
                    ('promotion', 'Promotion'),
                    ('formation', 'Formation'),
                    ('pip', 'Plan de performance (PIP)'),
                    ('aucune', 'Aucune'),
                ], default='', max_length=25, verbose_name='Issue'),
        ),
        migrations.AddField(
            model_name='evaluationemploye',
            name='issue_details',
            field=models.TextField(
                blank=True, default='', verbose_name="Détails de l'issue"),
        ),
    ]
