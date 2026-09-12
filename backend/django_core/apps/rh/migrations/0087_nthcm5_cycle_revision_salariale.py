# NTHCM5 — cycles de révision salariale avec enveloppe par manager.
#
# Purement ADDITIF : trois nouvelles tables, aucun champ touché sur
# l'existant. `PropositionRevision` s'appuie sur `DossierEmploye.manager`
# (NTHCM1) pour borner le périmètre de chaque manager.
from decimal import Decimal

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0008_customuser_avatar_key_customuser_poste'),
        ('rh', '0086_nthcm4_poste_effectif_budgete'),
    ]

    operations = [
        migrations.CreateModel(
            name='CycleRevisionSalariale',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('libelle', models.CharField(
                    max_length=200, verbose_name='Libellé')),
                ('periode', models.CharField(
                    blank=True, default='', max_length=20,
                    verbose_name='Période')),
                ('enveloppe_totale_pct', models.DecimalField(
                    blank=True, decimal_places=2, max_digits=6, null=True,
                    verbose_name='Enveloppe totale (%)')),
                ('statut', models.CharField(
                    choices=[('brouillon', 'Brouillon'), ('ouvert', 'Ouvert'),
                             ('calibration', 'Calibration'), ('clos', 'Clos')],
                    default='brouillon', max_length=12,
                    verbose_name='Statut')),
                ('date_debut', models.DateField(
                    blank=True, null=True, verbose_name='Date de début')),
                ('date_fin', models.DateField(
                    blank=True, null=True, verbose_name='Date de fin')),
                # SCA4 — socle core.models.TenantModel (created_at/updated_at
                # au lieu de date_creation à la main).
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Cycle de révision salariale',
                'verbose_name_plural': 'Cycles de révision salariale',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='EnveloppeManager',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('enveloppe_pct', models.DecimalField(
                    decimal_places=2, default=Decimal('0'), max_digits=6,
                    verbose_name='Enveloppe allouée (%)')),
                # SCA4 — socle core.models.TenantModel.
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
                ('cycle', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='enveloppes',
                    to='rh.cyclerevisionsalariale', verbose_name='Cycle')),
                ('manager', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='enveloppes_revision',
                    to='rh.dossieremploye', verbose_name='Manager')),
            ],
            options={
                'verbose_name': 'Enveloppe manager',
                'verbose_name_plural': 'Enveloppes manager',
                'ordering': ['manager__nom'],
            },
        ),
        migrations.CreateModel(
            name='PropositionRevision',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('salaire_actuel', models.DecimalField(
                    decimal_places=2, default=Decimal('0'), max_digits=14,
                    verbose_name='Salaire actuel (snapshot)')),
                ('augmentation_pct_proposee', models.DecimalField(
                    decimal_places=2, default=Decimal('0'), max_digits=6,
                    verbose_name='Augmentation proposée (%)')),
                ('augmentation_montant_proposee', models.DecimalField(
                    decimal_places=2, default=Decimal('0'), max_digits=14,
                    verbose_name='Augmentation proposée (montant)')),
                ('justification', models.TextField(
                    blank=True, default='', verbose_name='Justification')),
                ('statut', models.CharField(
                    choices=[('proposee', 'Proposée'),
                             ('approuvee', 'Approuvée'),
                             ('rejetee', 'Rejetée')],
                    default='proposee', max_length=10,
                    verbose_name='Statut')),
                # SCA4 — socle core.models.TenantModel.
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company', verbose_name='Société')),
                ('cycle', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='propositions',
                    to='rh.cyclerevisionsalariale', verbose_name='Cycle')),
                ('employe', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='propositions_revision',
                    to='rh.dossieremploye', verbose_name='Employé')),
                ('propose_par', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='propositions_revision_proposees',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Proposé par')),
            ],
            options={
                'verbose_name': 'Proposition de révision',
                'verbose_name_plural': 'Propositions de révision',
                'ordering': ['employe__nom', 'employe__prenom'],
            },
        ),
        migrations.AddIndex(
            model_name='cyclerevisionsalariale',
            index=models.Index(
                fields=['company', 'statut'],
                name='rh_cyclerev_comp_stat_idx'),
        ),
        migrations.AddConstraint(
            model_name='enveloppemanager',
            constraint=models.UniqueConstraint(
                fields=('cycle', 'manager'),
                name='rh_envmgr_cycle_manager_uniq'),
        ),
        migrations.AddIndex(
            model_name='propositionrevision',
            index=models.Index(
                fields=['company', 'cycle'],
                name='rh_proprev_comp_cycle_idx'),
        ),
        migrations.AddConstraint(
            model_name='propositionrevision',
            constraint=models.UniqueConstraint(
                fields=('cycle', 'employe'),
                name='rh_proprev_cycle_employe_uniq'),
        ),
    ]
