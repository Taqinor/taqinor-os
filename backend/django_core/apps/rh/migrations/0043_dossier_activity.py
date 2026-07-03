# Generated for XRH6 — Historique d'emploi (timeline auditée du dossier).
#
# Entièrement additive : un nouveau modèle ``DossierActivity`` (chatter,
# pattern ``contrats.ContratActivity``/``crm.LeadActivity``) + un index nommé.
# Réversible.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0013_customuser_poste_ref'),
        ('rh', '0042_declaration_entree_cnss'),
    ]

    operations = [
        migrations.CreateModel(
            name='DossierActivity',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(choices=[('log', 'Transition'), ('note', 'Note')], max_length=10, verbose_name='Type')),
                ('field', models.CharField(blank=True, default='', max_length=100, verbose_name='Champ')),
                ('old_value', models.TextField(blank=True, default='', verbose_name='Ancienne valeur')),
                ('new_value', models.TextField(blank=True, default='', verbose_name='Nouvelle valeur')),
                ('message', models.TextField(blank=True, default='', verbose_name='Message')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('auteur', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='rh_dossier_activites', to=settings.AUTH_USER_MODEL, verbose_name='Auteur')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rh_dossier_activites', to='authentication.company', verbose_name='Société')),
                ('employe', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='activites', to='rh.dossieremploye', verbose_name='Employé')),
            ],
            options={
                'verbose_name': 'Activité dossier employé',
                'verbose_name_plural': 'Activités dossier employé',
                'ordering': ['-date_creation', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='dossieractivity',
            index=models.Index(fields=['employe', '-date_creation'], name='rh_dossier_act_emp_date_idx'),
        ),
    ]
