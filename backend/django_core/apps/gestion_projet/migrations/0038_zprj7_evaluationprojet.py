import django.core.validators
import django.db.models.deletion
from django.db import migrations, models

import apps.gestion_projet.models


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_projet', '0037_zprj2_affectation_publication'),
    ]

    operations = [
        migrations.CreateModel(
            name='EvaluationProjet',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('token', models.CharField(
                    default=apps.gestion_projet.models._generer_token_portail,
                    max_length=64, unique=True, verbose_name='Jeton')),
                ('note', models.PositiveSmallIntegerField(
                    blank=True, null=True,
                    validators=[
                        django.core.validators.MinValueValidator(1),
                        django.core.validators.MaxValueValidator(5)],
                    verbose_name='Note (1-5)')),
                ('commentaire', models.TextField(
                    blank=True, default='', verbose_name='Commentaire')),
                ('soumis_le', models.DateTimeField(
                    blank=True, null=True, verbose_name='Soumis le')),
                ('date_creation', models.DateTimeField(
                    auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='gestion_projet_evaluations',
                    to='authentication.company', verbose_name='Société')),
                ('projet', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='evaluation', to='gestion_projet.projet',
                    verbose_name='Projet')),
            ],
            options={
                'verbose_name': 'Évaluation projet (CSAT)',
                'verbose_name_plural': 'Évaluations projet (CSAT)',
                'ordering': ['-id'],
            },
        ),
        migrations.AddIndex(
            model_name='evaluationprojet',
            index=models.Index(
                fields=['token'], name='gp_eval_token_idx'),
        ),
    ]
