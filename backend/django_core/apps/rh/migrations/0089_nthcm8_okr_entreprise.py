# NTHCM8 — OKR d'entreprise (cycle trimestriel), distincts de
# `ObjectifIndividuel` (FG190, objectif d'entretien annuel).
#
# Purement ADDITIF : quatre nouvelles tables, rien n'est touché sur
# l'existant. La cascade `OkrIndividuel.objectif_parent` est NULLABLE — un OKR
# sans parent reste valide.
from decimal import Decimal

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0008_customuser_avatar_key_customuser_poste'),
        ('rh', '0088_nthcm7_application_revision'),
    ]

    operations = [
        migrations.CreateModel(
            name='ObjectifEntreprise',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('titre', models.CharField(
                    max_length=200, verbose_name='Titre')),
                ('periode', models.CharField(
                    blank=True, default='', max_length=20,
                    verbose_name='Période')),
                ('description', models.TextField(
                    blank=True, default='', verbose_name='Description')),
                ('date_creation', models.DateTimeField(
                    auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='rh_objectifs_entreprise',
                    to='authentication.company', verbose_name='Société')),
                ('proprietaire', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='objectifs_entreprise',
                    to='rh.dossieremploye', verbose_name='Propriétaire')),
            ],
            options={
                'verbose_name': "Objectif d'entreprise",
                'verbose_name_plural': "Objectifs d'entreprise",
                'ordering': ['-periode', 'titre'],
            },
        ),
        migrations.CreateModel(
            name='KeyResult',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('libelle', models.CharField(
                    max_length=200, verbose_name='Libellé')),
                ('valeur_cible', models.DecimalField(
                    decimal_places=2, default=Decimal('0'), max_digits=14,
                    verbose_name='Valeur cible')),
                ('valeur_actuelle', models.DecimalField(
                    decimal_places=2, default=Decimal('0'), max_digits=14,
                    verbose_name='Valeur actuelle')),
                ('unite', models.CharField(
                    blank=True, default='', max_length=40,
                    verbose_name='Unité')),
                ('date_creation', models.DateTimeField(
                    auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='rh_key_results',
                    to='authentication.company', verbose_name='Société')),
                ('objectif', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='key_results',
                    to='rh.objectifentreprise', verbose_name='Objectif')),
            ],
            options={
                'verbose_name': 'Résultat clé',
                'verbose_name_plural': 'Résultats clés',
                'ordering': ['objectif', 'libelle'],
            },
        ),
        migrations.CreateModel(
            name='OkrIndividuel',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('periode', models.CharField(
                    blank=True, default='', max_length=20,
                    verbose_name='Période')),
                ('titre', models.CharField(
                    max_length=200, verbose_name='Titre')),
                ('date_creation', models.DateTimeField(
                    auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='rh_okr_individuels',
                    to='authentication.company', verbose_name='Société')),
                ('employe', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='okr_individuels',
                    to='rh.dossieremploye', verbose_name='Employé')),
                ('objectif_parent', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='okr_rattaches',
                    to='rh.objectifentreprise',
                    verbose_name="Objectif d'entreprise (optionnel)")),
            ],
            options={
                'verbose_name': 'OKR individuel',
                'verbose_name_plural': 'OKR individuels',
                'ordering': ['-periode', 'titre'],
            },
        ),
        migrations.CreateModel(
            name='KeyResultIndividuel',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('libelle', models.CharField(
                    max_length=200, verbose_name='Libellé')),
                ('valeur_cible', models.DecimalField(
                    decimal_places=2, default=Decimal('0'), max_digits=14,
                    verbose_name='Valeur cible')),
                ('valeur_actuelle', models.DecimalField(
                    decimal_places=2, default=Decimal('0'), max_digits=14,
                    verbose_name='Valeur actuelle')),
                ('unite', models.CharField(
                    blank=True, default='', max_length=40,
                    verbose_name='Unité')),
                ('progression_pct', models.DecimalField(
                    decimal_places=2, default=Decimal('0'), max_digits=5,
                    verbose_name='Progression (%)')),
                ('date_creation', models.DateTimeField(
                    auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='rh_key_results_individuels',
                    to='authentication.company', verbose_name='Société')),
                ('okr', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='key_results',
                    to='rh.okrindividuel', verbose_name='OKR')),
            ],
            options={
                'verbose_name': 'Résultat clé individuel',
                'verbose_name_plural': 'Résultats clés individuels',
                'ordering': ['okr', 'libelle'],
            },
        ),
        migrations.AddIndex(
            model_name='objectifentreprise',
            index=models.Index(
                fields=['company', 'periode'],
                name='rh_objent_comp_per_idx'),
        ),
        migrations.AddIndex(
            model_name='okrindividuel',
            index=models.Index(
                fields=['company', 'periode'],
                name='rh_okrind_comp_per_idx'),
        ),
    ]
