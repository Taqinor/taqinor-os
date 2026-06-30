# Generated for PROJ24 -- Suivi des temps (timesheets imputés au projet).

import django.core.validators
import django.db.models.deletion
from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0012_customuser_must_change_password_and_more'),
        ('gestion_projet', '0013_budget_projet'),
    ]

    operations = [
        migrations.CreateModel(
            name='Timesheet',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(verbose_name='Date')),
                ('heures', models.DecimalField(decimal_places=2, max_digits=6, validators=[django.core.validators.MinValueValidator(Decimal('0'))], verbose_name='Heures')),
                ('cout', models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=14, verbose_name='Coût interne (figé)')),
                ('commentaire', models.TextField(blank=True, default='', verbose_name='Commentaire')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gestion_projet_timesheets', to='authentication.company', verbose_name='Société')),
                ('phase', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='timesheets', to='gestion_projet.phaseprojet', verbose_name='Phase')),
                ('projet', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='timesheets', to='gestion_projet.projet', verbose_name='Projet')),
                ('ressource', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='timesheets', to='gestion_projet.ressourceprofil', verbose_name='Ressource (profil)')),
                ('tache', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='timesheets', to='gestion_projet.tache', verbose_name='Tâche')),
            ],
            options={
                'verbose_name': 'Feuille de temps',
                'verbose_name_plural': 'Feuilles de temps',
                'ordering': ['-date', '-id'],
                'indexes': [models.Index(fields=['projet', 'date'], name='gp_ts_proj_date_idx'), models.Index(fields=['ressource', 'date'], name='gp_ts_res_date_idx')],
            },
        ),
    ]
