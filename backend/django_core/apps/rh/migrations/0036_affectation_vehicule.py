# Generated 2026-06-30 — FG198 Affectation conducteur ↔ véhicule
#
# Entièrement additive : ``CreateModel`` (``AffectationVehicule``) + index
# nommés — réversible. Lie un conducteur (DossierEmploye, même société) à un
# véhicule du parc (vehicule_id = STRING-FK flotte.Vehicule) sur une période,
# avec un statut (active → terminée). GARDE PERMIS (décision FG198) appliquée
# CÔTÉ SERVEUR à la création/màj : pas de permis valide (FG197) → refus ;
# permis_verifie matérialise le contrôle. Société posée côté serveur.
# RUNTIME-SAFETY : statut borné ≤ 20 ; note plafonnée ; index nommés (≤ 30).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0013_customuser_poste_ref'),
        ('rh', '0035_permis_conduire'),
    ]

    operations = [
        migrations.CreateModel(
            name='AffectationVehicule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('vehicule_id', models.PositiveIntegerField(verbose_name='Véhicule (ID)')),
                ('date_debut', models.DateField(blank=True, null=True, verbose_name="Début d'affectation")),
                ('date_fin', models.DateField(blank=True, null=True, verbose_name="Fin d'affectation")),
                ('statut', models.CharField(choices=[('active', 'Active'), ('terminee', 'Terminée')], default='active', max_length=20, verbose_name='Statut')),
                ('permis_verifie', models.BooleanField(default=False, verbose_name='Permis vérifié')),
                ('note', models.CharField(blank=True, default='', max_length=255, verbose_name='Note')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('date_modification', models.DateTimeField(auto_now=True, verbose_name='Modifié le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rh_affectations_vehicule', to='authentication.company', verbose_name='Société')),
                ('employe', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='affectations_vehicule', to='rh.dossieremploye', verbose_name='Conducteur')),
            ],
            options={
                'verbose_name': 'Affectation véhicule',
                'verbose_name_plural': 'Affectations véhicule',
                'ordering': ['-date_debut', '-date_creation'],
            },
        ),
        migrations.AddIndex(
            model_name='affectationvehicule',
            index=models.Index(fields=['company', 'employe'], name='rh_affveh_comp_emp_idx'),
        ),
        migrations.AddIndex(
            model_name='affectationvehicule',
            index=models.Index(fields=['company', 'vehicule_id'], name='rh_affveh_comp_veh_idx'),
        ),
        migrations.AddIndex(
            model_name='affectationvehicule',
            index=models.Index(fields=['company', 'statut'], name='rh_affveh_comp_stat_idx'),
        ),
    ]
