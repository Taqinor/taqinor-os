# Generated 2026-06-30 — FG195 Avances sur salaire
#
# Entièrement additive : ``CreateModel`` (``AvanceSalaire``) + index nommés —
# réversible. Demande d'avance d'un employé (montant, date, motif), mois/année
# de déduction (par défaut mois suivant, posé côté serveur), valideur,
# statut (demandée → approuvée → déduite, ou refusée). Les avances approuvées
# alimentent l'export paie (FG192) via le sélecteur ``avances_a_deduire``.
# Société posée côté serveur. RUNTIME-SAFETY : statut borné ≤ 20 ; montant en
# DecimalField ; motif en TextField ; index nommés (≤ 30 chars).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0013_customuser_poste_ref'),
        ('rh', '0032_ordre_mission'),
    ]

    operations = [
        migrations.CreateModel(
            name='AvanceSalaire',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('montant', models.DecimalField(decimal_places=2, default=0, max_digits=12, verbose_name='Montant')),
                ('date_demande', models.DateField(blank=True, null=True, verbose_name='Date de demande')),
                ('motif', models.TextField(blank=True, default='', verbose_name='Motif')),
                ('annee_deduction', models.PositiveIntegerField(blank=True, null=True, verbose_name='Année de déduction')),
                ('mois_deduction', models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='Mois de déduction')),
                ('statut', models.CharField(choices=[('demandee', 'Demandée'), ('approuvee', 'Approuvée'), ('deduite', 'Déduite'), ('refusee', 'Refusée')], default='demandee', max_length=20, verbose_name='Statut')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('date_modification', models.DateTimeField(auto_now=True, verbose_name='Modifié le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rh_avances_salaire', to='authentication.company', verbose_name='Société')),
                ('employe', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='avances_salaire', to='rh.dossieremploye', verbose_name='Employé')),
                ('valideur', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='avances_validees', to='rh.dossieremploye', verbose_name='Valideur')),
            ],
            options={
                'verbose_name': 'Avance sur salaire',
                'verbose_name_plural': 'Avances sur salaire',
                'ordering': ['-date_demande', '-date_creation'],
            },
        ),
        migrations.AddIndex(
            model_name='avancesalaire',
            index=models.Index(fields=['company', 'employe'], name='rh_avance_comp_emp_idx'),
        ),
        migrations.AddIndex(
            model_name='avancesalaire',
            index=models.Index(fields=['company', 'statut'], name='rh_avance_comp_stat_idx'),
        ),
        migrations.AddIndex(
            model_name='avancesalaire',
            index=models.Index(fields=['company', 'annee_deduction', 'mois_deduction'], name='rh_avance_comp_ded_idx'),
        ),
    ]
