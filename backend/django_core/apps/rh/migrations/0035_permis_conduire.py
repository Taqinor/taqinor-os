# Generated 2026-06-30 — FG197 Suivi des permis de conduire & habilitation
#
# Entièrement additive : ``CreateModel`` (``PermisConduire``) + contrainte
# d'unicité + index nommés — réversible. Suit le droit de conduire d'un employé
# (catégorie, numéro, date de délivrance, date d'expiration/validité,
# habilitation interne à conduire). Source de vérité RH du droit de conduire,
# consultée par la garde d'affectation conducteur↔véhicule (FG198). Le couple
# (company, employe, categorie) est unique. Société posée côté serveur.
# RUNTIME-SAFETY : codes bornés ; contrainte + index nommés (≤ 30 chars).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0013_customuser_poste_ref'),
        ('rh', '0034_bulletin_paie'),
    ]

    operations = [
        migrations.CreateModel(
            name='PermisConduire',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('categorie', models.CharField(choices=[('A', 'A — Motos'), ('B', 'B — Véhicules légers'), ('C', 'C — Poids lourds'), ('D', 'D — Transport de personnes'), ('EB', 'EB — Léger + remorque'), ('EC', 'EC — Poids lourd + remorque')], default='B', max_length=10, verbose_name='Catégorie')),
                ('numero', models.CharField(blank=True, default='', max_length=40, verbose_name='Numéro de permis')),
                ('date_delivrance', models.DateField(blank=True, null=True, verbose_name='Date de délivrance')),
                ('date_expiration', models.DateField(blank=True, null=True, verbose_name="Date d'expiration")),
                ('habilitation_conduite', models.BooleanField(default=False, verbose_name='Habilitation à conduire (interne)')),
                ('note', models.CharField(blank=True, default='', max_length=255, verbose_name='Note')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('date_modification', models.DateTimeField(auto_now=True, verbose_name='Modifié le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rh_permis_conduire', to='authentication.company', verbose_name='Société')),
                ('employe', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='permis_conduire', to='rh.dossieremploye', verbose_name='Employé')),
            ],
            options={
                'verbose_name': 'Permis de conduire',
                'verbose_name_plural': 'Permis de conduire',
                'ordering': ['employe', 'categorie'],
            },
        ),
        migrations.AddConstraint(
            model_name='permisconduire',
            constraint=models.UniqueConstraint(fields=('company', 'employe', 'categorie'), name='rh_permis_comp_emp_cat_uniq'),
        ),
        migrations.AddIndex(
            model_name='permisconduire',
            index=models.Index(fields=['company', 'employe'], name='rh_permis_comp_emp_idx'),
        ),
        migrations.AddIndex(
            model_name='permisconduire',
            index=models.Index(fields=['company', 'date_expiration'], name='rh_permis_comp_exp_idx'),
        ),
    ]
