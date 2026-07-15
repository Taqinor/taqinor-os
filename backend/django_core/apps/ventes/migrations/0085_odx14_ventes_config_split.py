# ODX14 — modèles de configuration de vente (FG209–221) recréés DANS L'ÉTAT de
# ``apps.ventes`` sur les MÊMES tables physiques existantes
# (db_table='compta_<model>') via SeparateDatabaseAndState (state-only, aucun
# SQL). Dépend de compta 0112 qui les retire de l'état compta AVANT : ainsi
# aucun instant n'a deux modèles pour la même table. Aucune donnée déplacée.
# Même recette que ODX9/ODX11/ODX12/ODX13.

from decimal import Decimal

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0022_usersession_device_fingerprint'),
        ('ventes', '0084_odx19_repoint_achats_crossapp'),
        ('compta', '0112_odx14_ventes_config_split'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='CodePromotion',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('code', models.CharField(max_length=40, verbose_name='Code')),
                        ('libelle', models.CharField(blank=True, default='', max_length=200, verbose_name='Libellé')),
                        ('taux_remise', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=5, verbose_name='Taux de remise (%)')),
                        ('date_debut', models.DateField(verbose_name='Valable du')),
                        ('date_fin', models.DateField(verbose_name='Valable au')),
                        ('actif', models.BooleanField(default=True, verbose_name='Actif')),
                        ('nb_utilisations', models.PositiveIntegerField(default=0, verbose_name="Nombre d'utilisations")),
                        ('ca_genere', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=14, verbose_name='CA généré (TTC)')),
                        ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                        ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='codes_promotion', to='authentication.company', verbose_name='Société')),
                    ],
                    options={
                        'verbose_name': 'Code de promotion',
                        'verbose_name_plural': 'Codes de promotion',
                        'db_table': 'compta_codepromotion',
                        'ordering': ['-date_creation'],
                    },
                ),
                migrations.CreateModel(
                    name='ModeleDevis',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('nom', models.CharField(max_length=200, verbose_name='Nom du modèle')),
                        ('marche', models.CharField(choices=[('residentiel', 'Résidentiel'), ('industriel', 'Industriel/Commercial'), ('agricole', 'Agricole (pompage)')], default='residentiel', max_length=12, verbose_name='Marché')),
                        ('description', models.TextField(blank=True, default='', verbose_name='Description')),
                        ('lignes_type', models.JSONField(blank=True, default=list, verbose_name='Lignes-types (JSON)')),
                        ('actif', models.BooleanField(default=True, verbose_name='Actif')),
                        ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                        ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='modeles_devis', to='authentication.company', verbose_name='Société')),
                    ],
                    options={
                        'verbose_name': 'Modèle de devis',
                        'verbose_name_plural': 'Modèles de devis',
                        'db_table': 'compta_modeledevis',
                        'ordering': ['marche', 'nom'],
                    },
                ),
                migrations.CreateModel(
                    name='SessionGuidedSelling',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('marche', models.CharField(default='residentiel', max_length=12, verbose_name='Marché')),
                        ('reponses', models.JSONField(blank=True, default=dict, verbose_name='Réponses (JSON)')),
                        ('composition', models.JSONField(blank=True, default=dict, verbose_name='Composition proposée (JSON)')),
                        ('complet', models.BooleanField(default=False, verbose_name='Complète')),
                        ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créée le')),
                        ('auteur', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='sessions_guided_selling', to=settings.AUTH_USER_MODEL, verbose_name='Auteur')),
                        ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sessions_guided_selling', to='authentication.company', verbose_name='Société')),
                    ],
                    options={
                        'verbose_name': 'Session de configuration guidée',
                        'verbose_name_plural': 'Sessions de configuration guidée',
                        'db_table': 'compta_sessionguidedselling',
                        'ordering': ['-date_creation'],
                    },
                ),
                migrations.CreateModel(
                    name='DemandeApprobationConfig',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('devis_id', models.PositiveIntegerField(blank=True, null=True, verbose_name='Devis (id ventes)')),
                        ('devis_reference', models.CharField(blank=True, default='', max_length=50, verbose_name='Référence devis')),
                        ('motif', models.TextField(verbose_name='Motif de la non-conformité')),
                        ('statut', models.CharField(choices=[('en_attente', 'En attente'), ('approuvee', 'Approuvée'), ('refusee', 'Refusée')], default='en_attente', max_length=12, verbose_name='Statut')),
                        ('commentaire_decision', models.TextField(blank=True, default='', verbose_name='Commentaire de décision')),
                        ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créée le')),
                        ('date_decision', models.DateTimeField(blank=True, null=True, verbose_name='Décidée le')),
                        ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='approbations_config', to='authentication.company', verbose_name='Société')),
                        ('decideur', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='approbations_decidees', to=settings.AUTH_USER_MODEL, verbose_name='Décideur')),
                        ('demandeur', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='approbations_demandees', to=settings.AUTH_USER_MODEL, verbose_name='Demandeur')),
                    ],
                    options={
                        'verbose_name': "Demande d'approbation de configuration",
                        'verbose_name_plural': "Demandes d'approbation de configuration",
                        'db_table': 'compta_demandeapprobationconfig',
                        'ordering': ['-date_creation'],
                    },
                ),
                migrations.CreateModel(
                    name='ECatalogue',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('titre', models.CharField(default='Catalogue', max_length=200, verbose_name='Titre')),
                        ('token', models.CharField(db_index=True, max_length=64, unique=True, verbose_name='Token public')),
                        ('produit_ids', models.JSONField(blank=True, default=list, verbose_name='Produits exposés (ids stock)')),
                        ('actif', models.BooleanField(default=True, verbose_name='Actif')),
                        ('expire_le', models.DateTimeField(blank=True, null=True, verbose_name='Expire le')),
                        ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                        ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ecatalogues', to='authentication.company', verbose_name='Société')),
                    ],
                    options={
                        'verbose_name': 'E-catalogue public',
                        'verbose_name_plural': 'E-catalogues publics',
                        'db_table': 'compta_ecatalogue',
                        'ordering': ['-date_creation'],
                    },
                ),
                migrations.CreateModel(
                    name='DocumentProposition',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('titre', models.CharField(max_length=200, verbose_name='Titre')),
                        ('type_document', models.CharField(choices=[('lettre', 'Lettre de couverture'), ('references', 'Références / réalisations'), ('garanties', 'Garanties'), ('autre', 'Autre annexe')], default='autre', max_length=12, verbose_name='Type de document')),
                        ('contenu', models.TextField(blank=True, default='', verbose_name='Contenu (texte)')),
                        ('fichier', models.FileField(blank=True, null=True, upload_to='compta/propositions/', verbose_name='Pièce jointe')),
                        ('ordre', models.PositiveIntegerField(default=0, verbose_name="Ordre d'affichage")),
                        ('actif', models.BooleanField(default=True, verbose_name='Actif')),
                        ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                        ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='documents_proposition', to='authentication.company', verbose_name='Société')),
                    ],
                    options={
                        'verbose_name': 'Document de proposition',
                        'verbose_name_plural': 'Documents de proposition',
                        'db_table': 'compta_documentproposition',
                        'ordering': ['type_document', 'ordre', 'titre'],
                    },
                ),
                migrations.CreateModel(
                    name='SimulationPublique',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('nom_prospect', models.CharField(blank=True, default='', max_length=200, verbose_name='Nom du prospect')),
                        ('telephone', models.CharField(blank=True, default='', max_length=40, verbose_name='Téléphone')),
                        ('email', models.EmailField(blank=True, default='', max_length=254, verbose_name='Email')),
                        ('puissance_kwc', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=8, verbose_name='Puissance estimée (kWc)')),
                        ('facture_mensuelle', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12, verbose_name='Facture mensuelle (MAD)')),
                        ('economie_annuelle', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12, verbose_name='Économie annuelle estimée (MAD)')),
                        ('parametres', models.JSONField(blank=True, default=dict, verbose_name='Paramètres de simulation')),
                        ('lead_cree', models.BooleanField(default=False, verbose_name='Lead créé')),
                        ('lead_id', models.PositiveIntegerField(blank=True, null=True, verbose_name='Id du lead créé')),
                        ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                        ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='simulations_publiques', to='authentication.company', verbose_name='Société')),
                    ],
                    options={
                        'verbose_name': 'Simulation publique',
                        'verbose_name_plural': 'Simulations publiques',
                        'db_table': 'compta_simulationpublique',
                        'ordering': ['-date_creation'],
                    },
                ),
                migrations.CreateModel(
                    name='SimulationFinancement',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('devis_id', models.PositiveIntegerField(blank=True, null=True, verbose_name='Id du devis')),
                        ('devis_reference', models.CharField(blank=True, default='', max_length=60, verbose_name='Référence devis')),
                        ('type_financement', models.CharField(choices=[('credit', 'Crédit amortissable'), ('leasing', 'Leasing / LOA')], default='credit', max_length=10, verbose_name='Type de financement')),
                        ('montant_finance', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=14, verbose_name='Montant financé (MAD)')),
                        ('duree_mois', models.PositiveIntegerField(default=12, verbose_name='Durée (mois)')),
                        ('taux_annuel', models.DecimalField(decimal_places=3, default=Decimal('0.000'), max_digits=6, verbose_name='Taux annuel (%)')),
                        ('mensualite', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=14, verbose_name='Mensualité estimée (MAD)')),
                        ('cout_total_credit', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=14, verbose_name='Coût total du crédit (MAD)')),
                        ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                        ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='simulations_financement', to='authentication.company', verbose_name='Société')),
                    ],
                    options={
                        'verbose_name': 'Simulation de financement',
                        'verbose_name_plural': 'Simulations de financement',
                        'db_table': 'compta_simulationfinancement',
                        'ordering': ['-date_creation'],
                    },
                ),
                migrations.CreateModel(
                    name='OffreFinancement',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('partenaire', models.CharField(max_length=200, verbose_name='Banque / partenaire')),
                        ('libelle', models.CharField(blank=True, default='', max_length=200, verbose_name="Libellé de l'offre")),
                        ('taux_annuel', models.DecimalField(decimal_places=3, default=Decimal('0.000'), max_digits=6, verbose_name='Taux annuel (%)')),
                        ('duree_min_mois', models.PositiveIntegerField(default=12, verbose_name='Durée minimale (mois)')),
                        ('duree_max_mois', models.PositiveIntegerField(default=84, verbose_name='Durée maximale (mois)')),
                        ('montant_min', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=14, verbose_name='Montant minimal (MAD)')),
                        ('montant_max', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=14, verbose_name='Montant maximal (MAD)')),
                        ('apport_min_pct', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=5, verbose_name='Apport minimal (%)')),
                        ('actif', models.BooleanField(default=True, verbose_name='Active')),
                        ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                        ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='offres_financement', to='authentication.company', verbose_name='Société')),
                    ],
                    options={
                        'verbose_name': 'Offre de financement',
                        'verbose_name_plural': 'Offres de financement',
                        'db_table': 'compta_offrefinancement',
                        'ordering': ['partenaire', 'taux_annuel'],
                    },
                ),
                migrations.CreateModel(
                    name='LigneIncitation',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('devis_id', models.PositiveIntegerField(blank=True, null=True, verbose_name='Id du devis')),
                        ('devis_reference', models.CharField(blank=True, default='', max_length=60, verbose_name='Référence devis')),
                        ('programme', models.CharField(choices=[('tatwir', 'Tatwir'), ('masen', 'MASEN'), ('iresen', 'IRESEN'), ('autre', 'Autre dispositif')], default='autre', max_length=10, verbose_name='Programme')),
                        ('libelle', models.CharField(blank=True, default='', max_length=200, verbose_name='Libellé')),
                        ('montant_aide', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=14, verbose_name="Montant de l'aide (MAD)")),
                        ('cout_brut', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=14, verbose_name='Coût brut (MAD)')),
                        ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                        ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lignes_incitation', to='authentication.company', verbose_name='Société')),
                    ],
                    options={
                        'verbose_name': "Ligne d'incitation",
                        'verbose_name_plural': "Lignes d'incitation",
                        'db_table': 'compta_ligneincitation',
                        'ordering': ['-date_creation'],
                    },
                ),
                migrations.CreateModel(
                    name='EcheancierPaiement',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('facture_id', models.PositiveIntegerField(blank=True, null=True, verbose_name='Id de la facture')),
                        ('facture_reference', models.CharField(blank=True, default='', max_length=60, verbose_name='Référence facture')),
                        ('montant_total', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=14, verbose_name='Montant total (MAD)')),
                        ('actif', models.BooleanField(default=True, verbose_name='Actif')),
                        ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                        ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='echeanciers_paiement', to='authentication.company', verbose_name='Société')),
                    ],
                    options={
                        'verbose_name': 'Échéancier de paiement',
                        'verbose_name_plural': 'Échéanciers de paiement',
                        'db_table': 'compta_echeancierpaiement',
                        'ordering': ['-date_creation'],
                    },
                ),
                migrations.CreateModel(
                    name='TranchePaiement',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('numero', models.PositiveIntegerField(default=1, verbose_name='N° tranche')),
                        ('montant', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=14, verbose_name='Montant (MAD)')),
                        ('date_echeance', models.DateField(verbose_name="Date d'échéance")),
                        ('montant_regle', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=14, verbose_name='Montant réglé (MAD)')),
                        ('date_reglement', models.DateField(blank=True, null=True, verbose_name='Date de règlement')),
                        ('paye', models.BooleanField(default=False, verbose_name='Payée')),
                        ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tranches_paiement', to='authentication.company', verbose_name='Société')),
                        ('echeancier', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tranches', to='ventes.echeancierpaiement', verbose_name='Échéancier')),
                    ],
                    options={
                        'verbose_name': 'Tranche de paiement',
                        'verbose_name_plural': 'Tranches de paiement',
                        'db_table': 'compta_tranchepaiement',
                        'ordering': ['echeancier', 'numero'],
                    },
                ),
                migrations.AddConstraint(
                    model_name='codepromotion',
                    constraint=models.UniqueConstraint(fields=('company', 'code'), name='uniq_code_promotion'),
                ),
                migrations.AddConstraint(
                    model_name='tranchepaiement',
                    constraint=models.UniqueConstraint(fields=('echeancier', 'numero'), name='uniq_tranche_numero'),
                ),
            ],
            database_operations=[],
        ),
    ]
