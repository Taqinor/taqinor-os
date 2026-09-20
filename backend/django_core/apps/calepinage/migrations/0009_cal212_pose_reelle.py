"""CAL212 — le POSÉ RÉEL d'un pan (as-built), saisi sur le chantier.

ADDITIVE et SANS DONNÉE : la table naît VIDE, et c'est la règle même de la
tâche — sans saisie, AUCUN écart n'est affiché (jamais un zéro rassurant).
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0032_customuser_calendrier_hegirien'),
        ('calepinage', '0008_cal190_dossiers_reglementaires'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PoseReelle',
            fields=[
                ('id', models.BigAutoField(auto_created=True,
                                           primary_key=True,
                                           serialize=False,
                                           verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('pan', models.CharField(max_length=120,
                                         verbose_name='Pan')),
                ('modules_poses', models.PositiveIntegerField(
                    verbose_name='Modules réellement posés')),
                ('ecarts_position', models.TextField(
                    blank=True, default='',
                    verbose_name='Écarts de position (texte libre)')),
                ('releve_le', models.DateField(verbose_name='Relevé le')),
                ('calepinage', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='poses_reelles',
                    to='calepinage.calepinage',
                    verbose_name='Calepinage')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company',
                    verbose_name='Société')),
                ('releve_par', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='calepinage_poses_reelles',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Relevé par')),
            ],
            options={
                'verbose_name': 'Pose réelle (as-built)',
                'verbose_name_plural': 'Poses réelles (as-built)',
                'ordering': ['pan', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='posereelle',
            index=models.Index(fields=['company', 'calepinage'],
                               name='cal_pos_co_cal_idx'),
        ),
        migrations.AddConstraint(
            model_name='posereelle',
            constraint=models.UniqueConstraint(
                fields=('calepinage', 'pan'),
                name='uniq_pose_reelle_par_pan'),
        ),
    ]
