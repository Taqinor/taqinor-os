"""ODX15 — entrée state-only des notes de frais dans ``apps.frais``.

Pendant de ``apps/compta/migrations/0122_odx15_frais_split.py`` : les 5
modèles sont recréés dans l'ÉTAT sur les MÊMES tables physiques
(``db_table='compta_*'``), avec ``database_operations=[]``. La dépendance
sur compta 0122 garantit l'ordre (retrait de l'état AVANT recréation) —
aucun instant n'a deux modèles pointant la même table.
"""

import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('authentication', '0025_company_est_demo_mode_presentation'),
        ('compta', '0122_odx15_frais_split'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='BaremeIndemnite',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('libelle', models.CharField(max_length=120, verbose_name='Libellé du barème')),
                        ('taux_km', models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=8, verbose_name='Indemnité kilométrique (MAD/km)')),
                        ('per_diem', models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=10, verbose_name='Per-diem chantier (MAD/jour)')),
                        ('defaut', models.BooleanField(default=False, verbose_name='Barème par défaut')),
                        ('actif', models.BooleanField(default=True, verbose_name='Actif')),
                        ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                        ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='baremes_indemnite', to='authentication.company', verbose_name='Société')),
                    ],
                    options={
                        'verbose_name': "Barème d'indemnité",
                        'verbose_name_plural': "Barèmes d'indemnité",
                        'db_table': 'compta_baremeindemnite',
                        'ordering': ['-defaut', 'libelle', '-id'],
                    },
                ),
                migrations.CreateModel(
                    name='IndemniteChantier',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('reference', models.CharField(blank=True, default='', max_length=50, verbose_name='Référence')),
                        ('date_deplacement', models.DateField(verbose_name='Date du déplacement')),
                        ('libelle_chantier', models.CharField(blank=True, default='', max_length=255, verbose_name='Chantier')),
                        ('depart_lat', models.FloatField(blank=True, null=True, verbose_name='Latitude départ')),
                        ('depart_lng', models.FloatField(blank=True, null=True, verbose_name='Longitude départ')),
                        ('site_lat', models.FloatField(blank=True, null=True, verbose_name='Latitude chantier')),
                        ('site_lng', models.FloatField(blank=True, null=True, verbose_name='Longitude chantier')),
                        ('aller_retour', models.BooleanField(default=True, verbose_name='Aller-retour')),
                        ('nombre_jours', models.PositiveIntegerField(default=1, verbose_name='Nombre de jours de chantier')),
                        ('distance_km', models.DecimalField(decimal_places=3, default=Decimal('0'), max_digits=10, verbose_name='Distance (km)')),
                        ('montant_km', models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=14, verbose_name='Indemnité kilométrique')),
                        ('montant_per_diem', models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=14, verbose_name='Per-diem')),
                        ('montant_total', models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=14, verbose_name='Montant total')),
                        ('statut', models.CharField(choices=[('brouillon', 'Brouillon'), ('soumise', 'Soumise'), ('validee', 'Validée'), ('rejetee', 'Rejetée'), ('remboursee', 'Remboursée')], default='brouillon', max_length=12, verbose_name='Statut')),
                        ('date_validation', models.DateTimeField(blank=True, null=True, verbose_name='Validée le')),
                        ('motif_rejet', models.CharField(blank=True, default='', max_length=255, verbose_name='Motif de rejet')),
                        ('date_remboursement', models.DateField(blank=True, null=True, verbose_name='Date de remboursement')),
                        ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                        ('bareme', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='indemnites', to='frais.baremeindemnite', verbose_name='Barème appliqué')),
                        ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='indemnites_chantier', to='authentication.company', verbose_name='Société')),
                        ('compte_charge', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='indemnites_chantier_charge', to='compta.comptecomptable', verbose_name='Compte de charge')),
                        ('compte_tresorerie', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='indemnites_chantier', to='compta.comptetresorerie', verbose_name='Compte de trésorerie (payeur)')),
                        ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='indemnites_chantier_creees', to=settings.AUTH_USER_MODEL, verbose_name='Saisie par')),
                        ('ecriture_charge', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='indemnites_chantier_charge', to='compta.ecriturecomptable', verbose_name='Écriture de charge')),
                        ('ecriture_remboursement', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='indemnites_chantier_remboursement', to='compta.ecriturecomptable', verbose_name='Écriture de remboursement')),
                        ('employe', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='indemnites_chantier', to=settings.AUTH_USER_MODEL, verbose_name='Employé')),
                        ('rembourse_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='indemnites_chantier_remboursees', to=settings.AUTH_USER_MODEL, verbose_name='Remboursée par')),
                        ('valide_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='indemnites_chantier_validees', to=settings.AUTH_USER_MODEL, verbose_name='Validée par')),
                    ],
                    options={
                        'verbose_name': 'Indemnité chantier',
                        'verbose_name_plural': 'Indemnités chantier',
                        'db_table': 'compta_indemnitechantier',
                        'ordering': ['-date_deplacement', '-id'],
                    },
                ),
                migrations.CreateModel(
                    name='PlafondNoteFrais',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('categorie', models.CharField(choices=[('deplacement', 'Déplacement / transport'), ('carburant', 'Carburant'), ('repas', 'Repas / restauration'), ('hebergement', 'Hébergement'), ('fournitures', 'Petites fournitures'), ('peage', 'Péage / stationnement'), ('autre', 'Autre')], max_length=15, verbose_name='Catégorie')),
                        ('montant_max', models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=14, verbose_name='Plafond (montant max)')),
                        ('seuil_justificatif_obligatoire', models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True, verbose_name='Seuil au-delà duquel le justificatif est obligatoire')),
                        ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                        ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='plafonds_notes_frais', to='authentication.company', verbose_name='Société')),
                    ],
                    options={
                        'verbose_name': 'Plafond de note de frais',
                        'verbose_name_plural': 'Plafonds de notes de frais',
                        'db_table': 'compta_plafondnotefrais',
                        'ordering': ['categorie'],
                    },
                ),
                migrations.CreateModel(
                    name='RapportNoteFrais',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('reference', models.CharField(blank=True, default='', max_length=50, verbose_name='Référence')),
                        ('libelle', models.CharField(blank=True, default='', max_length=200, verbose_name='Libellé')),
                        ('statut', models.CharField(choices=[('brouillon', 'Brouillon'), ('soumis', 'Soumis'), ('valide', 'Validé'), ('rembourse', 'Remboursé')], default='brouillon', max_length=10, verbose_name='Statut')),
                        ('date_validation', models.DateTimeField(blank=True, null=True, verbose_name='Validé le')),
                        ('mode_remboursement', models.CharField(choices=[('virement', 'Virement bancaire'), ('especes', 'Espèces'), ('cheque', 'Chèque')], default='virement', max_length=10, verbose_name='Mode de remboursement')),
                        ('date_remboursement', models.DateField(blank=True, null=True, verbose_name='Date de remboursement')),
                        ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                        ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rapports_notes_frais', to='authentication.company', verbose_name='Société')),
                        ('compte_tresorerie', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='rapports_notes_frais', to='compta.comptetresorerie', verbose_name='Compte de trésorerie (payeur)')),
                        ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='rapports_notes_frais_crees', to=settings.AUTH_USER_MODEL, verbose_name='Créé par')),
                        ('ecriture_charge', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='rapports_notes_frais_charge', to='compta.ecriturecomptable', verbose_name='Écriture de charge agrégée')),
                        ('ecriture_remboursement', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='rapports_notes_frais_remboursement', to='compta.ecriturecomptable', verbose_name='Écriture de remboursement')),
                        ('employe', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='rapports_notes_frais', to=settings.AUTH_USER_MODEL, verbose_name='Employé')),
                        ('rembourse_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='rapports_notes_frais_rembourses', to=settings.AUTH_USER_MODEL, verbose_name='Remboursé par')),
                        ('valide_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='rapports_notes_frais_valides', to=settings.AUTH_USER_MODEL, verbose_name='Validé par')),
                    ],
                    options={
                        'verbose_name': 'Rapport de notes de frais',
                        'verbose_name_plural': 'Rapports de notes de frais',
                        'db_table': 'compta_rapportnotefrais',
                        'ordering': ['-date_creation', '-id'],
                    },
                ),
                migrations.CreateModel(
                    name='NoteFrais',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('reference', models.CharField(blank=True, default='', max_length=50, verbose_name='Référence')),
                        ('date_frais', models.DateField(verbose_name='Date de la dépense')),
                        ('categorie', models.CharField(choices=[('deplacement', 'Déplacement / transport'), ('carburant', 'Carburant'), ('repas', 'Repas / restauration'), ('hebergement', 'Hébergement'), ('fournitures', 'Petites fournitures'), ('peage', 'Péage / stationnement'), ('autre', 'Autre')], default='autre', max_length=15, verbose_name='Catégorie')),
                        ('montant', models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=14, verbose_name='Montant (TTC)')),
                        ('motif', models.CharField(max_length=255, verbose_name='Motif')),
                        ('justificatif', models.FileField(blank=True, null=True, upload_to='notes_frais/justificatifs/%Y/%m/', verbose_name='Justificatif (photo)')),
                        ('statut', models.CharField(choices=[('brouillon', 'Brouillon'), ('soumise', 'Soumise'), ('validee', 'Validée'), ('rejetee', 'Rejetée'), ('remboursee', 'Remboursée')], default='brouillon', max_length=12, verbose_name='Statut')),
                        ('date_validation', models.DateTimeField(blank=True, null=True, verbose_name='Validée le')),
                        ('motif_rejet', models.CharField(blank=True, default='', max_length=255, verbose_name='Motif de rejet')),
                        ('mode_remboursement', models.CharField(choices=[('virement', 'Virement bancaire'), ('especes', 'Espèces'), ('cheque', 'Chèque')], default='virement', max_length=10, verbose_name='Mode de remboursement')),
                        ('date_remboursement', models.DateField(blank=True, null=True, verbose_name='Date de remboursement')),
                        ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créé le')),
                        ('hors_politique', models.BooleanField(default=False, verbose_name='Hors politique (dépasse le plafond)')),
                        ('refacturable', models.BooleanField(default=False, verbose_name='Refacturable au client')),
                        ('taux_marge', models.DecimalField(decimal_places=2, default=Decimal('0'), max_digits=5, verbose_name='Taux de marge à la refacturation (%)')),
                        ('client_refacturation_id', models.PositiveIntegerField(blank=True, null=True, verbose_name='Client à refacturer (id crm, string-ref)')),
                        ('chantier_refacturation', models.CharField(blank=True, default='', max_length=255, verbose_name='Chantier (référence libre)')),
                        ('facture_refacturation_id', models.PositiveIntegerField(blank=True, null=True, verbose_name='Facture de refacturation (id ventes, string-ref)')),
                        ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notes_frais', to='authentication.company', verbose_name='Société')),
                        ('compte_charge', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='notes_frais_charge', to='compta.comptecomptable', verbose_name='Compte de charge')),
                        ('compte_tresorerie', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='notes_frais', to='compta.comptetresorerie', verbose_name='Compte de trésorerie (payeur)')),
                        ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='notes_frais_creees', to=settings.AUTH_USER_MODEL, verbose_name='Saisie par')),
                        ('ecriture_charge', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='notes_frais_charge', to='compta.ecriturecomptable', verbose_name='Écriture de charge')),
                        ('ecriture_remboursement', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='notes_frais_remboursement', to='compta.ecriturecomptable', verbose_name='Écriture de remboursement')),
                        ('employe', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='notes_frais', to=settings.AUTH_USER_MODEL, verbose_name='Employé')),
                        ('rembourse_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='notes_frais_remboursees', to=settings.AUTH_USER_MODEL, verbose_name='Remboursée par')),
                        ('valide_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='notes_frais_validees', to=settings.AUTH_USER_MODEL, verbose_name='Validée par')),
                        ('rapport', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='notes', to='frais.rapportnotefrais', verbose_name='Rapport de frais')),
                    ],
                    options={
                        'verbose_name': 'Note de frais',
                        'verbose_name_plural': 'Notes de frais',
                        'db_table': 'compta_notefrais',
                        'ordering': ['-date_frais', '-id'],
                    },
                ),
                migrations.AddConstraint(
                    model_name='baremeindemnite',
                    constraint=models.UniqueConstraint(condition=models.Q(('actif', True), ('defaut', True)), fields=('company',), name='uniq_bareme_indem_defaut'),
                ),
                migrations.AddConstraint(
                    model_name='indemnitechantier',
                    constraint=models.UniqueConstraint(condition=models.Q(('reference__gt', '')), fields=('company', 'reference'), name='uniq_indem_chantier_reference'),
                ),
                migrations.AddConstraint(
                    model_name='plafondnotefrais',
                    constraint=models.UniqueConstraint(fields=('company', 'categorie'), name='uniq_plafond_notefrais_categorie'),
                ),
                migrations.AddConstraint(
                    model_name='rapportnotefrais',
                    constraint=models.UniqueConstraint(condition=models.Q(('reference__gt', '')), fields=('company', 'reference'), name='uniq_rapport_note_frais_reference'),
                ),
                migrations.AddConstraint(
                    model_name='notefrais',
                    constraint=models.UniqueConstraint(condition=models.Q(('reference__gt', '')), fields=('company', 'reference'), name='uniq_note_frais_reference'),
                ),
            ],
            # ODX15 — ZÉRO SQL : les tables restent celles de compta
            # (db_table 'compta_*' figé sur chaque modèle).
            database_operations=[],
        ),
    ]
