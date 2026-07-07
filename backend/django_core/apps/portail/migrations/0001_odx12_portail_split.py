# ODX12 — modèles portail (FG228–233) recréés DANS L'ÉTAT de ``apps.portail``
# sur les MÊMES tables physiques existantes (db_table='compta_<model>') via
# SeparateDatabaseAndState (state-only, aucun SQL). Dépend de compta 0107 qui les
# retire de l'état compta AVANT : ainsi aucun instant n'a deux modèles pour la
# même table. Aucune donnée déplacée ; surface AUTH conservée à l'identique.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('authentication', '0014_customuser_account_lockout'),
        ('crm', '0001_initial'),
        ('compta', '0107_odx12_portail_split'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='ComptePortailClient',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('token_acces', models.CharField(db_index=True, max_length=64, unique=True, verbose_name="Token d'accès")),
                        ('actif', models.BooleanField(default=True, verbose_name='Actif')),
                        ('derniere_connexion', models.DateTimeField(blank=True, null=True, verbose_name='Dernière connexion')),
                        ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                        ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comptes_portail', to='authentication.company', verbose_name='Société')),
                        ('client', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comptes_portail', to='crm.client', verbose_name='Client')),
                    ],
                    options={
                        'verbose_name': 'Compte portail client',
                        'verbose_name_plural': 'Comptes portail client',
                        'db_table': 'compta_compteportailclient',
                        'ordering': ['-date_creation'],
                    },
                ),
                migrations.CreateModel(
                    name='AcceptationDevisPortail',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('devis_id', models.PositiveIntegerField(verbose_name='Id du devis')),
                        ('option_choisie', models.CharField(blank=True, default='', max_length=120, verbose_name='Option choisie')),
                        ('nom_signataire', models.CharField(max_length=200, verbose_name='Nom du signataire')),
                        ('signature_ip', models.GenericIPAddressField(blank=True, null=True, verbose_name='IP de signature')),
                        ('accepte', models.BooleanField(default=False, verbose_name='Accepté')),
                        ('signe_le', models.DateTimeField(blank=True, null=True, verbose_name='Signé le')),
                        ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créée le')),
                        ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='acceptations_devis_portail', to='authentication.company', verbose_name='Société')),
                    ],
                    options={
                        'verbose_name': 'Acceptation de devis (portail)',
                        'verbose_name_plural': 'Acceptations de devis (portail)',
                        'db_table': 'compta_acceptationdevisportail',
                        'ordering': ['-date_creation'],
                    },
                ),
                migrations.CreateModel(
                    name='PaiementFacturePortail',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('facture_id', models.PositiveIntegerField(verbose_name='Id de la facture')),
                        ('montant', models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Montant (MAD)')),
                        ('methode', models.CharField(choices=[('carte', 'Carte (CMI)'), ('virement', 'Virement')], default='carte', max_length=8, verbose_name='Méthode')),
                        ('statut', models.CharField(choices=[('initie', 'Initié'), ('paye', 'Payé'), ('echoue', 'Échoué')], default='initie', max_length=8, verbose_name='Statut')),
                        ('reference', models.CharField(blank=True, default='', max_length=64, verbose_name='Référence de transaction')),
                        ('paye_le', models.DateTimeField(blank=True, null=True, verbose_name='Payé le')),
                        ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                        ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='paiements_facture_portail', to='authentication.company', verbose_name='Société')),
                    ],
                    options={
                        'verbose_name': 'Paiement de facture (portail)',
                        'verbose_name_plural': 'Paiements de facture (portail)',
                        'db_table': 'compta_paiementfactureportail',
                        'ordering': ['-date_creation'],
                    },
                ),
                migrations.CreateModel(
                    name='DocumentClientPortail',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('client_id', models.PositiveIntegerField(verbose_name='Id du client')),
                        ('lead_id', models.PositiveIntegerField(blank=True, null=True, verbose_name='Id du lead')),
                        ('type_document', models.CharField(choices=[('facture_onee', 'Facture ONEE'), ('plan', 'Plan / schéma'), ('autre', 'Autre')], default='facture_onee', max_length=14, verbose_name='Type de document')),
                        ('libelle', models.CharField(blank=True, default='', max_length=200, verbose_name='Libellé')),
                        ('fichier', models.FileField(blank=True, null=True, upload_to='compta/portail_docs/', verbose_name='Fichier')),
                        ('traite', models.BooleanField(default=False, verbose_name="Traité (intégré à l'étude)")),
                        ('date_depot', models.DateTimeField(auto_now_add=True, verbose_name='Déposé le')),
                        ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='documents_client_portail', to='authentication.company', verbose_name='Société')),
                    ],
                    options={
                        'verbose_name': 'Document client (portail)',
                        'verbose_name_plural': 'Documents client (portail)',
                        'db_table': 'compta_documentclientportail',
                        'ordering': ['-date_depot'],
                    },
                ),
                migrations.CreateModel(
                    name='JalonChantierPortail',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('chantier_id', models.PositiveIntegerField(verbose_name='Id du chantier')),
                        ('libelle', models.CharField(max_length=120, verbose_name='Jalon')),
                        ('ordre', models.PositiveIntegerField(default=0, verbose_name='Ordre')),
                        ('atteint', models.BooleanField(default=False, verbose_name='Atteint')),
                        ('date_jalon', models.DateField(blank=True, null=True, verbose_name='Date du jalon')),
                        ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                        ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='jalons_chantier_portail', to='authentication.company', verbose_name='Société')),
                    ],
                    options={
                        'verbose_name': 'Jalon de chantier (portail)',
                        'verbose_name_plural': 'Jalons de chantier (portail)',
                        'db_table': 'compta_jalonchantierportail',
                        'ordering': ['chantier_id', 'ordre', 'id'],
                    },
                ),
                migrations.CreateModel(
                    name='DemandeTicketPortail',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('client_id', models.PositiveIntegerField(verbose_name='Id du client')),
                        ('chantier_id', models.PositiveIntegerField(blank=True, null=True, verbose_name='Id du chantier')),
                        ('sujet', models.CharField(max_length=200, verbose_name='Sujet')),
                        ('description', models.TextField(blank=True, default='', verbose_name='Description')),
                        ('statut', models.CharField(choices=[('soumise', 'Soumise'), ('prise_en_charge', 'Prise en charge'), ('resolue', 'Résolue'), ('refusee', 'Refusée')], default='soumise', max_length=16, verbose_name='Statut')),
                        ('ticket_id', models.PositiveIntegerField(blank=True, null=True, verbose_name='Id du ticket SAV créé')),
                        ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créée le')),
                        ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='demandes_ticket_portail', to='authentication.company', verbose_name='Société')),
                    ],
                    options={
                        'verbose_name': 'Demande de ticket SAV (portail)',
                        'verbose_name_plural': 'Demandes de ticket SAV (portail)',
                        'db_table': 'compta_demandeticketportail',
                        'ordering': ['-date_creation'],
                    },
                ),
                migrations.AddConstraint(
                    model_name='compteportailclient',
                    constraint=models.UniqueConstraint(fields=('company', 'client'), name='uniq_compte_portail_client'),
                ),
            ],
            database_operations=[],
        ),
    ]
