# ODX19 — modèles Achats (PrixFournisseur, BonCommandeFournisseur +
# LigneBonCommandeFournisseur, ReceptionFournisseur +
# LigneReceptionFournisseur, FactureFournisseur + LigneFactureFournisseur,
# PaiementFournisseur, RetourFournisseur + LigneRetourFournisseur) recréés
# DANS L'ÉTAT de ``apps.achats`` sur les MÊMES tables physiques existantes
# (db_table='stock_<model>') via SeparateDatabaseAndState (state-only, aucun
# SQL). Dépend de stock 0079 qui les retire de l'état stock AVANT : ainsi
# aucun instant n'a deux modèles pour la même table. Aucune donnée déplacée.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('authentication', '0014_customuser_account_lockout'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('installations', '0095_sca36_demandeachat_kit'),
        # ODX19 — les modèles sortent de stock en STATE-ONLY : stock 0079 les
        # retire de l'état (SeparateDatabaseAndState, zéro SQL) AVANT que
        # achats 0001 ne les recrée dans l'état sur les MÊMES tables
        # (db_table='stock_*'). L'ordre garantit qu'aucun instant n'a deux
        # modèles pour la même table.
        ('stock', '0079_odx19_achats_split'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='PrixFournisseur',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('prix_achat', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                        ('date_dernier_achat', models.DateField(blank=True, null=True)),
                        ('delai_livraison_jours', models.PositiveIntegerField(blank=True, null=True)),
                        ('ref_produit_fournisseur', models.CharField(blank=True, default='', help_text='Code article chez le fournisseur (imprimé sur le PDF BCF).', max_length=100)),
                        ('date_debut', models.DateField(blank=True, null=True)),
                        ('date_fin', models.DateField(blank=True, null=True)),
                        ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='prix_fournisseurs', to='authentication.company')),
                        ('produit', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='prix_fournisseurs', to='stock.produit')),
                        ('fournisseur', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='prix_produits', to='stock.fournisseur')),
                    ],
                    options={
                        'verbose_name': 'Prix fournisseur',
                        'verbose_name_plural': 'Prix fournisseurs',
                        'db_table': 'stock_prixfournisseur',
                        'ordering': ['prix_achat'],
                        'unique_together': {('produit', 'fournisseur')},
                    },
                ),
                migrations.CreateModel(
                    name='BonCommandeFournisseur',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('reference', models.CharField(max_length=50)),
                        ('statut', models.CharField(choices=[('brouillon', 'Brouillon'), ('envoye', 'Envoyé'), ('recu', 'Reçu'), ('annule', 'Annulé')], default='brouillon', max_length=20)),
                        ('date_commande', models.DateField(blank=True, null=True)),
                        ('devise', models.CharField(choices=[('MAD', 'Dirham marocain (MAD)'), ('EUR', 'Euro (EUR)'), ('USD', 'Dollar américain (USD)'), ('CNY', 'Yuan chinois (CNY)')], default='MAD', max_length=3)),
                        ('taux_change', models.DecimalField(decimal_places=6, default=1, help_text='Taux de change devise → MAD à la date du document (saisie manuelle, aucun appel externe).', max_digits=12)),
                        ('date_livraison_prevue', models.DateField(blank=True, null=True)),
                        ('date_confirmee_fournisseur', models.DateField(blank=True, null=True)),
                        ('numero_confirmation_fournisseur', models.CharField(blank=True, default='', max_length=100)),
                        ('revision', models.PositiveIntegerField(default=0)),
                        ('nb_relances', models.PositiveIntegerField(default=0)),
                        ('ref_fournisseur', models.CharField(blank=True, help_text='Référence de la commande côté fournisseur (texte libre).', max_length=100, null=True)),
                        ('note_bas_page', models.TextField(blank=True, help_text='Mentions imprimées en bas de page du PDF BCF.', null=True)),
                        ('incoterm', models.CharField(blank=True, max_length=10, null=True)),
                        ('conditions_paiement', models.CharField(blank=True, help_text='Conditions de paiement reportées du fournisseur (éditables au document), dérivées de delai_paiement_jours.', max_length=200, null=True)),
                        ('motif_annulation', models.TextField(blank=True, null=True)),
                        ('note', models.TextField(blank=True, null=True)),
                        ('date_creation', models.DateTimeField(auto_now_add=True)),
                        ('date_mise_a_jour', models.DateTimeField(auto_now=True)),
                        ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='bons_commande_fournisseur', to='authentication.company')),
                        ('fournisseur', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='bons_commande', to='stock.fournisseur')),
                        ('emplacement_destination', models.ForeignKey(blank=True, help_text='Emplacement crédité à la réception (vide = dépôt principal, comportement historique).', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='bons_commande_destination', to='stock.emplacementstock')),
                        ('chantier_livraison', models.ForeignKey(blank=True, help_text="Chantier de LIVRAISON DIRECTE (distinct de chantier_origine/YPROC10, qui trace la demande d'origine) : la réception est suivie d'une affectation chantier tracée (n'entre jamais en stock libre). Vide = comportement historique.", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='bons_commande_livraison_directe', to='installations.installation')),
                        ('chantier_origine', models.ForeignKey(blank=True, help_text="Chantier D'ORIGINE du besoin matériel (distinct de chantier_livraison, qui trace la LIVRAISON) : réceptionner ce BCF réserve automatiquement les quantités reçues pour ce chantier. Vide = comportement historique (stock libre).", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='bons_commande_besoin_origine', to='installations.installation')),
                        ('acheteur', models.ForeignKey(blank=True, help_text='Acheteur responsable du BCF (défaut = created_by).', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='bons_commande_fournisseur_acheteur', to=settings.AUTH_USER_MODEL)),
                        ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='bons_commande_fournisseur', to=settings.AUTH_USER_MODEL)),
                    ],
                    options={
                        'verbose_name': 'Bon de commande fournisseur',
                        'verbose_name_plural': 'Bons de commande fournisseur',
                        'db_table': 'stock_boncommandefournisseur',
                        'ordering': ['-date_creation'],
                        'unique_together': {('company', 'reference')},
                    },
                ),
                migrations.CreateModel(
                    name='LigneBonCommandeFournisseur',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('designation', models.CharField(blank=True, default='', help_text='Désignation libre (obligatoire quand produit est vide — ex. « Transport Casablanca »).', max_length=255)),
                        ('sans_stock', models.BooleanField(default=False, help_text='Ligne libre/service : jamais de mouvement de stock à la réception. Toujours vrai quand produit est vide.')),
                        ('quantite', models.IntegerField()),
                        ('prix_achat_unitaire', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                        ('prix_achat_unitaire_devise', models.DecimalField(blank=True, decimal_places=2, help_text="Prix d'achat unitaire dans la devise du document (optionnel — null = document en MAD).", max_digits=12, null=True)),
                        ('frais_annexes', models.DecimalField(decimal_places=2, default=0, help_text='Frais annexes TOTAUX de la ligne (fret/douane/TVA import/transit), répartis sur les unités. INTERNE.', max_digits=12)),
                        ('quantite_recue', models.IntegerField(default=0)),
                        ('bon_commande', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lignes', to='achats.boncommandefournisseur')),
                        ('produit', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='lignes_bon_commande_fournisseur', to='stock.produit')),
                    ],
                    options={
                        'verbose_name': 'Ligne de bon de commande fournisseur',
                        'verbose_name_plural': 'Lignes de bon de commande fournisseur',
                        'db_table': 'stock_ligneboncommandefournisseur',
                    },
                ),
                migrations.CreateModel(
                    name='ReceptionFournisseur',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('reference', models.CharField(max_length=50)),
                        ('statut', models.CharField(choices=[('brouillon', 'Brouillon'), ('confirme', 'Confirmé'), ('annule', 'Annulé')], default='brouillon', max_length=20)),
                        ('date_reception', models.DateField(blank=True, null=True)),
                        ('note', models.TextField(blank=True, null=True)),
                        ('date_creation', models.DateTimeField(auto_now_add=True)),
                        ('date_mise_a_jour', models.DateTimeField(auto_now=True)),
                        ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='receptions_fournisseur', to='authentication.company')),
                        ('bon_commande', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='receptions', to='achats.boncommandefournisseur')),
                        ('recu_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='receptions_fournisseur', to=settings.AUTH_USER_MODEL)),
                        ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='receptions_fournisseur_creees', to=settings.AUTH_USER_MODEL)),
                    ],
                    options={
                        'verbose_name': 'Réception fournisseur',
                        'verbose_name_plural': 'Réceptions fournisseur',
                        'db_table': 'stock_receptionfournisseur',
                        'ordering': ['-date_creation'],
                        'unique_together': {('company', 'reference')},
                    },
                ),
                migrations.CreateModel(
                    name='LigneReceptionFournisseur',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('quantite', models.IntegerField()),
                        ('numeros_serie', models.JSONField(blank=True, help_text='Numéros de série reçus lors de cette ligne (liste de chaînes). Optionnel ; aucune série = null.', null=True)),
                        ('numero_lot', models.CharField(blank=True, help_text='Numéro de lot ou batch (optionnel).', max_length=100, null=True)),
                        ('date_peremption', models.DateField(blank=True, help_text='Date de péremption / fin de vie (optionnel).', null=True)),
                        ('reception', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lignes', to='achats.receptionfournisseur')),
                        ('ligne_commande', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='lignes_reception', to='achats.ligneboncommandefournisseur')),
                        ('produit', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='lignes_reception_fournisseur', to='stock.produit')),
                    ],
                    options={
                        'verbose_name': 'Ligne de réception fournisseur',
                        'verbose_name_plural': 'Lignes de réception fournisseur',
                        'db_table': 'stock_lignereceptionfournisseur',
                    },
                ),
                migrations.CreateModel(
                    name='FactureFournisseur',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('reference', models.CharField(max_length=50)),
                        ('ref_fournisseur', models.CharField(blank=True, max_length=100, null=True)),
                        ('type_achat', models.CharField(choices=[('biens', 'Biens & travaux'), ('services', 'Prestations de services')], default='biens', help_text="Nature de l'achat (RAS-TVA LF 2024) : biens & travaux ou prestations de services.", max_length=10)),
                        ('date_facture', models.DateField(blank=True, null=True)),
                        ('date_echeance', models.DateField(blank=True, null=True)),
                        ('devise', models.CharField(choices=[('MAD', 'Dirham marocain (MAD)'), ('EUR', 'Euro (EUR)'), ('USD', 'Dollar américain (USD)'), ('CNY', 'Yuan chinois (CNY)')], default='MAD', max_length=3)),
                        ('taux_change', models.DecimalField(decimal_places=6, default=1, help_text='Taux de change devise → MAD à la date du document (saisie manuelle, aucun appel externe).', max_digits=12)),
                        ('montant_ttc_devise', models.DecimalField(blank=True, decimal_places=2, help_text='Montant TTC dans la devise du document (optionnel — null = document en MAD).', max_digits=14, null=True)),
                        ('montant_ht', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                        ('montant_tva', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                        ('montant_ttc', models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                        ('statut', models.CharField(choices=[('a_payer', 'À payer'), ('partiellement_payee', 'Partiellement payée'), ('payee', 'Payée')], default='a_payer', max_length=24)),
                        ('statut_controle', models.CharField(choices=[('normale', 'Normale'), ('exception', 'En exception'), ('resolue', 'Résolue')], default='normale', max_length=12)),
                        ('motif_ecart', models.TextField(blank=True, null=True)),
                        ('numero_clearance_dgi', models.CharField(blank=True, help_text="Numéro de clearance DGI (e-invoicing entrant, si fourni par le document UBL).", max_length=100, null=True)),
                        ('statut_conformite_dgi', models.CharField(choices=[('non_applicable', 'Non applicable'), ('cleared', 'Validée (clearance DGI)'), ('non_cleared', 'Non validée')], default='non_applicable', max_length=20)),
                        ('resolu_le', models.DateTimeField(blank=True, null=True)),
                        ('note', models.TextField(blank=True, null=True)),
                        ('date_creation', models.DateTimeField(auto_now_add=True)),
                        ('date_mise_a_jour', models.DateTimeField(auto_now=True)),
                        ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='factures_fournisseur', to='authentication.company')),
                        ('fournisseur', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='factures_fournisseur', to='stock.fournisseur')),
                        ('bon_commande', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='factures_fournisseur', to='achats.boncommandefournisseur')),
                        ('resolu_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='factures_fournisseur_resolues', to=settings.AUTH_USER_MODEL)),
                        ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='factures_fournisseur', to=settings.AUTH_USER_MODEL)),
                    ],
                    options={
                        'verbose_name': 'Facture fournisseur',
                        'verbose_name_plural': 'Factures fournisseur',
                        'db_table': 'stock_facturefournisseur',
                        'ordering': ['-date_creation'],
                        'unique_together': {('company', 'reference')},
                    },
                ),
                migrations.CreateModel(
                    name='LigneFactureFournisseur',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('designation', models.CharField(max_length=255)),
                        ('quantite', models.DecimalField(decimal_places=2, default=1, max_digits=12)),
                        ('prix_unitaire_ht', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                        ('taux_tva', models.DecimalField(blank=True, decimal_places=2, default=20, help_text='Taux TVA de la ligne (%). Vide = taux global de la facture (comportement historique).', max_digits=5, null=True)),
                        ('facture', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lignes', to='achats.facturefournisseur')),
                        ('produit', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='lignes_facture_fournisseur', to='stock.produit')),
                    ],
                    options={
                        'verbose_name': 'Ligne de facture fournisseur',
                        'verbose_name_plural': 'Lignes de facture fournisseur',
                        'db_table': 'stock_lignefacturefournisseur',
                    },
                ),
                migrations.CreateModel(
                    name='PaiementFournisseur',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('montant', models.DecimalField(decimal_places=2, max_digits=14)),
                        ('date_paiement', models.DateField(blank=True, null=True)),
                        ('mode', models.CharField(choices=[('virement', 'Virement'), ('cheque', 'Chèque'), ('especes', 'Espèces'), ('carte', 'Carte'), ('effet', 'Effet / traite'), ('autre', 'Autre')], default='virement', max_length=20)),
                        ('note', models.TextField(blank=True, null=True)),
                        ('montant_ras_tva', models.DecimalField(decimal_places=2, default=0, help_text='Montant de la retenue à la source sur la TVA (LF 2024).', max_digits=14)),
                        ('taux_ras', models.DecimalField(decimal_places=2, default=0, help_text='Taux de RAS-TVA appliqué (0/75/100 %).', max_digits=5)),
                        ('date_creation', models.DateTimeField(auto_now_add=True)),
                        ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='paiements_fournisseur', to='authentication.company')),
                        ('facture', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='paiements', to='achats.facturefournisseur')),
                        ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='paiements_fournisseur', to=settings.AUTH_USER_MODEL)),
                    ],
                    options={
                        'verbose_name': 'Paiement fournisseur',
                        'verbose_name_plural': 'Paiements fournisseur',
                        'db_table': 'stock_paiementfournisseur',
                        'ordering': ['-date_paiement', '-date_creation'],
                    },
                ),
                migrations.CreateModel(
                    name='RetourFournisseur',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('reference', models.CharField(max_length=50)),
                        ('statut', models.CharField(choices=[('brouillon', 'Brouillon'), ('valide', 'Validé'), ('annule', 'Annulé')], default='brouillon', max_length=20)),
                        ('motif', models.TextField(blank=True, null=True)),
                        ('date_creation', models.DateTimeField(auto_now_add=True)),
                        ('date_mise_a_jour', models.DateTimeField(auto_now=True)),
                        ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='retours_fournisseur', to='authentication.company')),
                        ('fournisseur', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='retours', to='stock.fournisseur')),
                        ('bon_commande', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='retours', to='achats.boncommandefournisseur')),
                        ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='retours_fournisseur', to=settings.AUTH_USER_MODEL)),
                    ],
                    options={
                        'verbose_name': 'Retour fournisseur',
                        'verbose_name_plural': 'Retours fournisseur',
                        'db_table': 'stock_retourfournisseur',
                        'ordering': ['-date_creation'],
                        'unique_together': {('company', 'reference')},
                    },
                ),
                migrations.CreateModel(
                    name='LigneRetourFournisseur',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('quantite', models.IntegerField()),
                        ('motif', models.CharField(blank=True, max_length=255, null=True)),
                        ('retour', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lignes', to='achats.retourfournisseur')),
                        ('produit', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='lignes_retour_fournisseur', to='stock.produit')),
                    ],
                    options={
                        'verbose_name': 'Ligne de retour fournisseur',
                        'verbose_name_plural': 'Lignes de retour fournisseur',
                        'db_table': 'stock_ligneretourfournisseur',
                    },
                ),
            ],
            database_operations=[],
        ),
    ]
