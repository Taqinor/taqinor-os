# ODX13 — modèles Partenaire/SoumissionLeadPartenaire/CommissionPartenaire/
# TerritoireCommercial (FG234–237) recréés DANS L'ÉTAT de ``apps.crm`` sur les
# MÊMES tables physiques existantes (db_table='compta_<model>') via
# SeparateDatabaseAndState (state-only, aucun SQL). Dépend de compta 0109 qui
# les retire de l'état compta AVANT : ainsi aucun instant n'a deux modèles
# pour la même table. Aucune donnée déplacée. Même recette que ODX9/ODX11/
# ODX12. La FK ``tiers`` (ARC19, pont vers le répertoire unifié) est préservée
# à l'identique.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0020_company_benchmarking_opt_in'),
        ('tiers', '0001_initial'),
        ('crm', '0058_leadactivity_attachment'),
        ('compta', '0109_odx13_partenaires_split'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='Partenaire',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('nom', models.CharField(max_length=200, verbose_name='Nom / raison sociale')),
                        ('type_partenaire', models.CharField(choices=[('apporteur', "Apporteur d'affaires"), ('sous_revendeur', 'Sous-revendeur'), ('installateur', 'Installateur')], default='apporteur', max_length=16, verbose_name='Type de partenaire')),
                        ('email', models.EmailField(blank=True, default='', max_length=254, verbose_name='Email')),
                        ('telephone', models.CharField(blank=True, default='', max_length=30, verbose_name='Téléphone')),
                        ('taux_commission', models.DecimalField(decimal_places=2, default=0, max_digits=5, verbose_name='Taux de commission (%)')),
                        ('token_acces', models.CharField(db_index=True, max_length=64, unique=True, verbose_name="Token d'accès")),
                        ('actif', models.BooleanField(default=True, verbose_name='Actif')),
                        ('statut_onboarding', models.CharField(choices=[('prospect', 'Prospect'), ('en_cours', "En cours d'agrément"), ('agree', 'Agréé (activé)'), ('suspendu', 'Suspendu')], default='prospect', max_length=12, verbose_name="Statut d'onboarding")),
                        ('numero_agrement', models.CharField(blank=True, default='', max_length=60, verbose_name="Numéro d'agrément")),
                        ('zone', models.CharField(blank=True, default='', max_length=120, verbose_name='Zone géographique')),
                        ('date_activation', models.DateField(blank=True, null=True, verbose_name="Date d'activation")),
                        ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                        ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='partenaires', to='authentication.company', verbose_name='Société')),
                        ('tiers', models.ForeignKey(blank=True, help_text='Fiche du répertoire unifié des parties prenantes reflétant ce partenaire. Renseignée automatiquement (miroir).', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='partenaires', to='tiers.tiers', verbose_name='Tiers (répertoire unifié)')),
                    ],
                    options={
                        'verbose_name': 'Partenaire commercial',
                        'verbose_name_plural': 'Partenaires commerciaux',
                        'db_table': 'compta_partenaire',
                        'ordering': ['nom'],
                    },
                ),
                migrations.CreateModel(
                    name='SoumissionLeadPartenaire',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('nom_prospect', models.CharField(max_length=200, verbose_name='Nom du prospect')),
                        ('telephone_prospect', models.CharField(blank=True, default='', max_length=30, verbose_name='Téléphone du prospect')),
                        ('email_prospect', models.EmailField(blank=True, default='', max_length=254, verbose_name='Email du prospect')),
                        ('ville', models.CharField(blank=True, default='', max_length=120, verbose_name='Ville')),
                        ('note', models.TextField(blank=True, default='', verbose_name='Note')),
                        ('statut', models.CharField(choices=[('soumis', 'Soumis'), ('qualifie', 'Qualifié'), ('converti', 'Converti'), ('rejete', 'Rejeté')], default='soumis', max_length=10, verbose_name='Statut')),
                        ('lead_id', models.PositiveIntegerField(blank=True, null=True, verbose_name='Id du lead créé')),
                        ('date_soumission', models.DateTimeField(auto_now_add=True, verbose_name='Soumis le')),
                        ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='soumissions_lead_partenaire', to='authentication.company', verbose_name='Société')),
                        ('partenaire', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='soumissions', to='crm.partenaire', verbose_name='Partenaire')),
                    ],
                    options={
                        'verbose_name': 'Soumission de lead (partenaire)',
                        'verbose_name_plural': 'Soumissions de lead (partenaire)',
                        'db_table': 'compta_soumissionleadpartenaire',
                        'ordering': ['-date_soumission'],
                    },
                ),
                migrations.CreateModel(
                    name='CommissionPartenaire',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('devis_id', models.PositiveIntegerField(blank=True, null=True, verbose_name='Id du devis signé')),
                        ('lead_id', models.PositiveIntegerField(blank=True, null=True, verbose_name='Id du lead')),
                        ('base_ht', models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Base HT (MAD)')),
                        ('taux', models.DecimalField(decimal_places=2, default=0, max_digits=5, verbose_name='Taux de commission (%)')),
                        ('montant', models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Montant de commission (MAD)')),
                        ('statut', models.CharField(choices=[('due', 'Due'), ('payee', 'Payée'), ('annulee', 'Annulée')], default='due', max_length=8, verbose_name='Statut')),
                        ('paye_le', models.DateField(blank=True, null=True, verbose_name='Payée le')),
                        ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créée le')),
                        ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='commissions_partenaire', to='authentication.company', verbose_name='Société')),
                        ('partenaire', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='commissions', to='crm.partenaire', verbose_name='Partenaire')),
                    ],
                    options={
                        'verbose_name': 'Commission partenaire',
                        'verbose_name_plural': 'Commissions partenaire',
                        'db_table': 'compta_commissionpartenaire',
                        'ordering': ['-date_creation'],
                    },
                ),
                migrations.CreateModel(
                    name='TerritoireCommercial',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('nom', models.CharField(max_length=120, verbose_name='Nom du territoire')),
                        ('villes', models.JSONField(blank=True, default=list, verbose_name='Villes / régions (liste)')),
                        ('owner_user_id', models.PositiveIntegerField(blank=True, null=True, verbose_name='Commercial responsable (id)')),
                        ('priorite', models.IntegerField(default=0, verbose_name='Priorité (haute = prioritaire)')),
                        ('actif', models.BooleanField(default=True, verbose_name='Actif')),
                        ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                        ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='territoires_commerciaux', to='authentication.company', verbose_name='Société')),
                    ],
                    options={
                        'verbose_name': 'Territoire commercial',
                        'verbose_name_plural': 'Territoires commerciaux',
                        'db_table': 'compta_territoirecommercial',
                        'ordering': ['-priorite', 'nom'],
                    },
                ),
            ],
            database_operations=[],
        ),
    ]
