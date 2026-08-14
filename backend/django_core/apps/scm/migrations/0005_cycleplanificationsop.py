# NTSCM12 — CyclePlanificationSOP (cycle S&OP mensuel, machine a etats sequentielle).
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scm', '0004_politiquestock'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CyclePlanificationSOP',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('periode', models.CharField(max_length=7, verbose_name='Période (YYYY-MM)')),
                ('statut', models.CharField(choices=[('brouillon', 'Brouillon'), ('revue_demande', 'Revue de la demande'), ('revue_offre', "Revue de l'offre"), ('revue_finance', 'Revue financière'), ('reunion_reconciliation', 'Réunion de réconciliation'), ('approuve', 'Approuvé'), ('clos', 'Clos')], default='brouillon', max_length=24, verbose_name='Statut')),
                ('date_reunion', models.DateField(blank=True, null=True, verbose_name='Date de la réunion')),
                ('notes_reunion', models.TextField(blank=True, default='', verbose_name='Notes de réunion')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('anime_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='scm_cycles_sop_animes', to=settings.AUTH_USER_MODEL, verbose_name='Animé par')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='scm_cycles_sop', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Cycle de planification S&OP',
                'verbose_name_plural': 'Cycles de planification S&OP',
                'ordering': ['-periode'],
            },
        ),
        migrations.AddConstraint(
            model_name='cycleplanificationsop',
            constraint=models.UniqueConstraint(fields=('company', 'periode'), name='uniq_scm_cycle_sop_periode'),
        ),
    ]
