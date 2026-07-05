# ODX11 — modèles AO (FG222–227) recréés DANS L'ÉTAT de ``apps.ao`` sur les
# MÊMES tables physiques existantes (db_table='compta_<model>') via
# SeparateDatabaseAndState (state-only, aucun SQL). Dépend de compta 0106 qui les
# retire de l'état compta AVANT : ainsi aucun instant n'a deux modèles pour la
# même table. Aucune donnée déplacée.

import django.db.models.deletion
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('authentication', '0014_customuser_account_lockout'),
        ('compta', '0106_odx11_ao_split'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='AppelOffre',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('reference', models.CharField(max_length=120, verbose_name="Référence de l'AO")),
                        ('objet', models.CharField(max_length=255, verbose_name='Objet')),
                        ('acheteur', models.CharField(blank=True, default='', max_length=255, verbose_name='Acheteur')),
                        ('type_marche', models.CharField(choices=[('public', 'Public'), ('prive', 'Privé')], default='public', max_length=8, verbose_name='Type de marché')),
                        ('lot', models.CharField(blank=True, default='', max_length=120, verbose_name='Lot')),
                        ('date_limite', models.DateField(blank=True, null=True, verbose_name='Date limite de remise des plis')),
                        ('montant_estime', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=16, verbose_name='Montant estimé (MAD)')),
                        ('caution_provisoire', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=14, verbose_name='Caution provisoire (MAD)')),
                        ('statut', models.CharField(choices=[('identifie', 'Identifié'), ('en_preparation', 'En préparation'), ('depose', 'Déposé'), ('gagne', 'Gagné'), ('perdu', 'Perdu'), ('abandonne', 'Abandonné')], default='identifie', max_length=16, verbose_name='Statut')),
                        ('lead_id', models.PositiveIntegerField(blank=True, null=True, verbose_name='Id du lead lié')),
                        ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                        ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='appels_offres', to='authentication.company', verbose_name='Société')),
                    ],
                    options={
                        'verbose_name': "Appel d'offres",
                        'verbose_name_plural': "Appels d'offres",
                        'db_table': 'compta_appeloffre',
                        'ordering': ['-date_creation'],
                    },
                ),
                migrations.CreateModel(
                    name='BordereauPrix',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('intitule', models.CharField(default='Bordereau des prix', max_length=200, verbose_name='Intitulé')),
                        ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                        ('appel_offre', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bordereaux', to='ao.appeloffre', verbose_name="Appel d'offres")),
                        ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bordereaux_prix', to='authentication.company', verbose_name='Société')),
                    ],
                    options={
                        'verbose_name': 'Bordereau des prix (BOQ)',
                        'verbose_name_plural': 'Bordereaux des prix (BOQ)',
                        'db_table': 'compta_bordereauprix',
                        'ordering': ['-date_creation'],
                    },
                ),
                migrations.CreateModel(
                    name='LigneBordereau',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('numero', models.PositiveIntegerField(default=1, verbose_name='N° ligne')),
                        ('designation', models.CharField(max_length=255, verbose_name='Désignation')),
                        ('unite', models.CharField(blank=True, default='U', max_length=20, verbose_name='Unité')),
                        ('quantite', models.DecimalField(decimal_places=3, default=Decimal('0.000'), max_digits=12, verbose_name='Quantité')),
                        ('prix_unitaire', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=14, verbose_name='Prix unitaire HT (MAD)')),
                        ('bordereau', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lignes', to='ao.bordereauprix', verbose_name='Bordereau')),
                        ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lignes_bordereau', to='authentication.company', verbose_name='Société')),
                    ],
                    options={
                        'verbose_name': 'Ligne de bordereau',
                        'verbose_name_plural': 'Lignes de bordereau',
                        'db_table': 'compta_lignebordereau',
                        'ordering': ['bordereau', 'numero'],
                    },
                ),
                migrations.CreateModel(
                    name='CautionSoumission',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('type_caution', models.CharField(choices=[('provisoire', 'Provisoire'), ('definitive', 'Définitive'), ('retenue_garantie', 'Retenue de garantie')], default='provisoire', max_length=16, verbose_name='Type de caution')),
                        ('montant', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=14, verbose_name='Montant (MAD)')),
                        ('banque', models.CharField(blank=True, default='', max_length=200, verbose_name='Banque')),
                        ('date_emission', models.DateField(blank=True, null=True, verbose_name="Date d'émission")),
                        ('date_echeance', models.DateField(blank=True, null=True, verbose_name="Date d'échéance")),
                        ('date_restitution', models.DateField(blank=True, null=True, verbose_name='Date de restitution')),
                        ('statut', models.CharField(choices=[('constituee', 'Constituée'), ('restituee', 'Restituée'), ('appelee', 'Appelée')], default='constituee', max_length=16, verbose_name='Statut')),
                        ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                        ('appel_offre', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cautions', to='ao.appeloffre', verbose_name="Appel d'offres")),
                        ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cautions_soumission', to='authentication.company', verbose_name='Société')),
                    ],
                    options={
                        'verbose_name': 'Caution de soumission',
                        'verbose_name_plural': 'Cautions de soumission',
                        'db_table': 'compta_cautionsoumission',
                        'ordering': ['-date_creation'],
                    },
                ),
                migrations.CreateModel(
                    name='DossierSoumission',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                        ('appel_offre', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='dossier', to='ao.appeloffre', verbose_name="Appel d'offres")),
                        ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='dossiers_soumission', to='authentication.company', verbose_name='Société')),
                    ],
                    options={
                        'verbose_name': 'Dossier de soumission',
                        'verbose_name_plural': 'Dossiers de soumission',
                        'db_table': 'compta_dossiersoumission',
                        'ordering': ['-date_creation'],
                    },
                ),
                migrations.CreateModel(
                    name='PieceSoumission',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('libelle', models.CharField(max_length=200, verbose_name='Libellé')),
                        ('obligatoire', models.BooleanField(default=True, verbose_name='Obligatoire')),
                        ('fournie', models.BooleanField(default=False, verbose_name='Fournie')),
                        ('fichier', models.FileField(blank=True, null=True, upload_to='compta/soumissions/', verbose_name='Document')),
                        ('date_depot', models.DateField(blank=True, null=True, verbose_name='Date de dépôt')),
                        ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pieces_soumission', to='authentication.company', verbose_name='Société')),
                        ('dossier', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pieces', to='ao.dossiersoumission', verbose_name='Dossier')),
                    ],
                    options={
                        'verbose_name': 'Pièce de soumission',
                        'verbose_name_plural': 'Pièces de soumission',
                        'db_table': 'compta_piecesoumission',
                        'ordering': ['dossier', 'libelle'],
                    },
                ),
                migrations.CreateModel(
                    name='EcheanceAO',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('type_echeance', models.CharField(choices=[('remise_plis', 'Remise des plis'), ('ouverture', 'Ouverture des plis'), ('validite', "Fin de validité de l'offre"), ('autre', 'Autre date clé')], default='autre', max_length=12, verbose_name="Type d'échéance")),
                        ('libelle', models.CharField(blank=True, default='', max_length=200, verbose_name='Libellé')),
                        ('date_echeance', models.DateField(verbose_name="Date d'échéance")),
                        ('rappel_jours', models.PositiveIntegerField(default=3, verbose_name='Rappel (jours avant)')),
                        ('traitee', models.BooleanField(default=False, verbose_name='Traitée')),
                        ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                        ('appel_offre', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='echeances', to='ao.appeloffre', verbose_name="Appel d'offres")),
                        ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='echeances_ao', to='authentication.company', verbose_name='Société')),
                    ],
                    options={
                        'verbose_name': "Échéance d'AO",
                        'verbose_name_plural': "Échéances d'AO",
                        'db_table': 'compta_echeanceao',
                        'ordering': ['date_echeance'],
                    },
                ),
                migrations.CreateModel(
                    name='ResultatAO',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('issue', models.CharField(choices=[('gagne', 'Gagné'), ('perdu', 'Perdu'), ('infructueux', 'Infructueux'), ('annule', 'Annulé')], default='perdu', max_length=12, verbose_name='Issue')),
                        ('attributaire', models.CharField(blank=True, default='', max_length=255, verbose_name='Attributaire')),
                        ('notre_prix', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=16, verbose_name='Notre prix (MAD)')),
                        ('prix_gagnant', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=16, verbose_name='Prix gagnant (MAD)')),
                        ('motif', models.TextField(blank=True, default='', verbose_name='Motif / commentaire')),
                        ('date_resultat', models.DateField(blank=True, null=True, verbose_name='Date du résultat')),
                        ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                        ('appel_offre', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='resultat', to='ao.appeloffre', verbose_name="Appel d'offres")),
                        ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='resultats_ao', to='authentication.company', verbose_name='Société')),
                    ],
                    options={
                        'verbose_name': "Résultat d'AO",
                        'verbose_name_plural': "Résultats d'AO",
                        'db_table': 'compta_resultatao',
                        'ordering': ['-date_creation'],
                    },
                ),
                migrations.AddConstraint(
                    model_name='appeloffre',
                    constraint=models.UniqueConstraint(fields=('company', 'reference'), name='uniq_appel_offre_reference'),
                ),
            ],
            database_operations=[],
        ),
    ]
