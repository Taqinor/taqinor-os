# Generated 2026-06-30 — FG194 Ordre de mission (déplacement chantier)
#
# Entièrement additive : ``CreateModel`` (``OrdreMission``) + contrainte
# d'unicité + index nommés — réversible. Document daté autorisant un
# déplacement : référence (posée côté serveur, unique par société), employé,
# destination, motif, dates départ/retour, moyen de transport, véhicule
# (STRING-FK flotte), per-diem, statut (brouillon → émis → clôturé).
# Restituable en PDF. Société posée côté serveur. RUNTIME-SAFETY : codes
# bornés ; motif en TextField ; per_diem en DecimalField ; contrainte + index
# nommés (≤ 30 chars).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0013_customuser_poste_ref'),
        ('rh', '0031_primes_indemnites'),
    ]

    operations = [
        migrations.CreateModel(
            name='OrdreMission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reference', models.CharField(max_length=40, verbose_name='Référence')),
                ('destination', models.CharField(max_length=255, verbose_name='Destination')),
                ('motif', models.TextField(blank=True, default='', verbose_name='Motif')),
                ('date_depart', models.DateField(blank=True, null=True, verbose_name='Date de départ')),
                ('date_retour', models.DateField(blank=True, null=True, verbose_name='Date de retour')),
                ('moyen_transport', models.CharField(blank=True, default='', max_length=60, verbose_name='Moyen de transport')),
                ('vehicule_id', models.PositiveIntegerField(blank=True, null=True, verbose_name='Véhicule (ID, optionnel)')),
                ('per_diem', models.DecimalField(decimal_places=2, default=0, max_digits=12, verbose_name='Per-diem (par jour)')),
                ('statut', models.CharField(choices=[('brouillon', 'Brouillon'), ('emis', 'Émis'), ('cloture', 'Clôturé')], default='brouillon', max_length=20, verbose_name='Statut')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('date_modification', models.DateTimeField(auto_now=True, verbose_name='Modifié le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rh_ordres_mission', to='authentication.company', verbose_name='Société')),
                ('employe', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ordres_mission', to='rh.dossieremploye', verbose_name='Employé')),
            ],
            options={
                'verbose_name': 'Ordre de mission',
                'verbose_name_plural': 'Ordres de mission',
                'ordering': ['-date_depart', '-date_creation'],
            },
        ),
        migrations.AddConstraint(
            model_name='ordremission',
            constraint=models.UniqueConstraint(fields=('company', 'reference'), name='rh_ordmiss_comp_ref_uniq'),
        ),
        migrations.AddIndex(
            model_name='ordremission',
            index=models.Index(fields=['company', 'employe'], name='rh_ordmiss_comp_emp_idx'),
        ),
        migrations.AddIndex(
            model_name='ordremission',
            index=models.Index(fields=['company', 'statut'], name='rh_ordmiss_comp_stat_idx'),
        ),
    ]
