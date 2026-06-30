# Generated 2026-06-30 — FG193 Primes & indemnités
#
# Entièrement additive : ``CreateModel`` (``TypePrime`` référentiel +
# ``PrimeAttribuee``) + contrainte d'unicité + index nommés — réversible.
# TypePrime = catalogue (rendement/chantier/panier/transport) avec code,
# libellé, nature, montant par défaut, drapeaux imposable/actif ;
# (company, code) unique. PrimeAttribuee = attribution à un employé pour une
# période (annee/mois) avec montant/motif/statut (proposée → validée → payée).
# Société posée côté serveur. RUNTIME-SAFETY : codes bornés ; montants en
# DecimalField ; contrainte + index nommés (≤ 30 chars).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0013_customuser_poste_ref'),
        ('rh', '0030_elements_variables_paie'),
    ]

    operations = [
        migrations.CreateModel(
            name='TypePrime',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=30, verbose_name='Code')),
                ('libelle', models.CharField(max_length=120, verbose_name='Libellé')),
                ('nature', models.CharField(choices=[('prime', 'Prime'), ('indemnite', 'Indemnité')], default='prime', max_length=20, verbose_name='Nature')),
                ('montant_defaut', models.DecimalField(decimal_places=2, default=0, max_digits=12, verbose_name='Montant par défaut')),
                ('imposable', models.BooleanField(default=True, verbose_name='Imposable (indicatif)')),
                ('actif', models.BooleanField(default=True, verbose_name='Actif')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rh_types_prime', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Type de prime/indemnité',
                'verbose_name_plural': 'Types de primes/indemnités',
                'ordering': ['libelle'],
            },
        ),
        migrations.CreateModel(
            name='PrimeAttribuee',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('annee', models.PositiveIntegerField(verbose_name='Année')),
                ('mois', models.PositiveSmallIntegerField(verbose_name='Mois')),
                ('montant', models.DecimalField(decimal_places=2, default=0, max_digits=12, verbose_name='Montant')),
                ('motif', models.CharField(blank=True, default='', max_length=255, verbose_name='Motif')),
                ('statut', models.CharField(choices=[('proposee', 'Proposée'), ('validee', 'Validée'), ('payee', 'Payée')], default='proposee', max_length=20, verbose_name='Statut')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                ('date_modification', models.DateTimeField(auto_now=True, verbose_name='Modifié le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rh_primes_attribuees', to='authentication.company', verbose_name='Société')),
                ('employe', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='primes_attribuees', to='rh.dossieremploye', verbose_name='Employé')),
                ('type_prime', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='attributions', to='rh.typeprime', verbose_name='Type de prime')),
            ],
            options={
                'verbose_name': 'Prime/indemnité attribuée',
                'verbose_name_plural': 'Primes/indemnités attribuées',
                'ordering': ['-annee', '-mois', 'employe'],
            },
        ),
        migrations.AddConstraint(
            model_name='typeprime',
            constraint=models.UniqueConstraint(fields=('company', 'code'), name='rh_typeprime_comp_code_uniq'),
        ),
        migrations.AddIndex(
            model_name='primeattribuee',
            index=models.Index(fields=['company', 'annee', 'mois'], name='rh_prime_comp_an_mois_idx'),
        ),
        migrations.AddIndex(
            model_name='primeattribuee',
            index=models.Index(fields=['company', 'employe'], name='rh_prime_comp_emp_idx'),
        ),
        migrations.AddIndex(
            model_name='primeattribuee',
            index=models.Index(fields=['company', 'statut'], name='rh_prime_comp_stat_idx'),
        ),
    ]
