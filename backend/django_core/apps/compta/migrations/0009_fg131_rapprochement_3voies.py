# Generated migration — FG131 Rapprochement 3 voies (BC ↔ réception ↔ facture fournisseur)
# Additive, reversible. No destructive operations.

import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compta", "0008_bordereauremise_effet_ligneprevisionneltresorerie_and_more"),
        ("authentication", "0012_customuser_must_change_password_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── BonCommandeFournisseur ──────────────────────────────────────────
        migrations.CreateModel(
            name="BonCommandeFournisseur",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "reference",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=80,
                        verbose_name="Référence BC",
                    ),
                ),
                (
                    "date_commande",
                    models.DateField(verbose_name="Date de commande"),
                ),
                (
                    "fournisseur_type",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=30,
                        verbose_name="Type de fournisseur",
                    ),
                ),
                (
                    "fournisseur_id",
                    models.PositiveIntegerField(
                        blank=True,
                        null=True,
                        verbose_name="ID fournisseur",
                    ),
                ),
                (
                    "fournisseur_nom",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=200,
                        verbose_name="Nom fournisseur",
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("brouillon", "Brouillon"),
                            ("envoye", "Envoyé"),
                            ("partiellement_recu", "Partiellement reçu"),
                            ("recu", "Reçu"),
                            ("annule", "Annulé"),
                        ],
                        default="brouillon",
                        max_length=20,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "montant_ht",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="Montant HT",
                    ),
                ),
                (
                    "taux_tva",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("20.00"),
                        max_digits=5,
                        verbose_name="Taux TVA (%)",
                    ),
                ),
                (
                    "notes",
                    models.TextField(blank=True, default="", verbose_name="Notes"),
                ),
                (
                    "date_creation",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Créé le"
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="bons_commande_fournisseur",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="bons_commande_fournisseur_crees",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Créé par",
                    ),
                ),
            ],
            options={
                "verbose_name": "Bon de commande fournisseur",
                "verbose_name_plural": "Bons de commande fournisseur",
                "ordering": ["-date_commande", "-id"],
            },
        ),
        # ── LigneBonCommandeFournisseur ─────────────────────────────────────
        migrations.CreateModel(
            name="LigneBonCommandeFournisseur",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "designation",
                    models.CharField(max_length=255, verbose_name="Désignation"),
                ),
                (
                    "produit_id",
                    models.PositiveIntegerField(
                        blank=True,
                        null=True,
                        verbose_name="ID produit (catalogue)",
                    ),
                ),
                (
                    "quantite",
                    models.DecimalField(
                        decimal_places=4,
                        default=Decimal("1"),
                        max_digits=12,
                        verbose_name="Quantité commandée",
                    ),
                ),
                (
                    "prix_unitaire_ht",
                    models.DecimalField(
                        decimal_places=4,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="Prix unitaire HT",
                    ),
                ),
                (
                    "unite",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=20,
                        verbose_name="Unité",
                    ),
                ),
                (
                    "bon_commande",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lignes_bc",
                        to="compta.boncommandefournisseur",
                        verbose_name="Bon de commande",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lignes_bc_fournisseur",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
            ],
            options={
                "verbose_name": "Ligne de bon de commande fournisseur",
                "verbose_name_plural": "Lignes de bon de commande fournisseur",
                "ordering": ["id"],
            },
        ),
        # ── ReceptionMarchandise ────────────────────────────────────────────
        migrations.CreateModel(
            name="ReceptionMarchandise",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "reference",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=80,
                        verbose_name="Référence réception",
                    ),
                ),
                (
                    "date_reception",
                    models.DateField(verbose_name="Date de réception"),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("partielle", "Partielle"),
                            ("complete", "Complète"),
                            ("avec_reserves", "Complète avec réserves"),
                        ],
                        default="complete",
                        max_length=15,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "numero_bl_fournisseur",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=80,
                        verbose_name="N° BL fournisseur",
                    ),
                ),
                (
                    "notes",
                    models.TextField(
                        blank=True,
                        default="",
                        verbose_name="Notes / réserves",
                    ),
                ),
                (
                    "date_creation",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Créé le"
                    ),
                ),
                (
                    "bon_commande",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="receptions",
                        to="compta.boncommandefournisseur",
                        verbose_name="Bon de commande",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="receptions_marchandise",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="receptions_marchandise_creees",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Créé par",
                    ),
                ),
            ],
            options={
                "verbose_name": "Réception de marchandise",
                "verbose_name_plural": "Réceptions de marchandise",
                "ordering": ["-date_reception", "-id"],
            },
        ),
        # ── LigneReceptionMarchandise ───────────────────────────────────────
        migrations.CreateModel(
            name="LigneReceptionMarchandise",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "quantite_recue",
                    models.DecimalField(
                        decimal_places=4,
                        default=Decimal("0"),
                        max_digits=12,
                        verbose_name="Quantité reçue",
                    ),
                ),
                (
                    "notes",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=255,
                        verbose_name="Notes / réserves",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lignes_reception_marchandise",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "ligne_bc",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="lignes_reception",
                        to="compta.ligneboncommandefournisseur",
                        verbose_name="Ligne du BC",
                    ),
                ),

                (
                    "reception",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lignes_reception",
                        to="compta.receptionmarchandise",
                        verbose_name="Réception",
                    ),
                ),
            ],
            options={
                "verbose_name": "Ligne de réception de marchandise",
                "verbose_name_plural": "Lignes de réception de marchandise",
                "ordering": ["id"],
            },
        ),
        # ── FactureFournisseur ──────────────────────────────────────────────
        migrations.CreateModel(
            name="FactureFournisseur",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "reference",
                    models.CharField(
                        max_length=80, verbose_name="N° facture fournisseur"
                    ),
                ),
                (
                    "date_facture",
                    models.DateField(verbose_name="Date de facture"),
                ),
                (
                    "date_echeance",
                    models.DateField(
                        blank=True,
                        null=True,
                        verbose_name="Date d'échéance",
                    ),
                ),
                (
                    "fournisseur_type",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=30,
                        verbose_name="Type de fournisseur",
                    ),
                ),
                (
                    "fournisseur_id",
                    models.PositiveIntegerField(
                        blank=True,
                        null=True,
                        verbose_name="ID fournisseur",
                    ),
                ),
                (
                    "fournisseur_nom",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=200,
                        verbose_name="Nom fournisseur",
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("brouillon", "Brouillon"),
                            ("a_valider", "À valider"),
                            ("validee", "Validée"),
                            ("en_litige", "En litige"),
                            ("payee", "Payée"),
                        ],
                        default="brouillon",
                        max_length=15,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "montant_ht",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="Montant HT facturé",
                    ),
                ),
                (
                    "taux_tva",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("20.00"),
                        max_digits=5,
                        verbose_name="Taux TVA (%)",
                    ),
                ),
                (
                    "montant_tva",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="Montant TVA facturé",
                    ),
                ),
                (
                    "montant_ttc",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="Montant TTC facturé",
                    ),
                ),
                (
                    "notes",
                    models.TextField(blank=True, default="", verbose_name="Notes"),
                ),
                (
                    "date_creation",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Créée le"
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="factures_fournisseur",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="factures_fournisseur_creees",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Créée par",
                    ),
                ),
            ],
            options={
                "verbose_name": "Facture fournisseur",
                "verbose_name_plural": "Factures fournisseur",
                "ordering": ["-date_facture", "-id"],
            },
        ),
        migrations.AddConstraint(
            model_name="facturefournisseur",
            constraint=models.UniqueConstraint(
                fields=["company", "reference"],
                name="uniq_facture_fournisseur_ref",
            ),
        ),
        # ── LigneFactureFournisseur ─────────────────────────────────────────
        migrations.CreateModel(
            name="LigneFactureFournisseur",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "designation",
                    models.CharField(max_length=255, verbose_name="Désignation"),
                ),
                (
                    "quantite_facturee",
                    models.DecimalField(
                        decimal_places=4,
                        default=Decimal("0"),
                        max_digits=12,
                        verbose_name="Quantité facturée",
                    ),
                ),
                (
                    "prix_unitaire_ht",
                    models.DecimalField(
                        decimal_places=4,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="Prix unitaire HT facturé",
                    ),
                ),
                (
                    "unite",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=20,
                        verbose_name="Unité",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lignes_facture_fournisseur",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "facture",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lignes_facture",
                        to="compta.facturefournisseur",
                        verbose_name="Facture fournisseur",
                    ),
                ),
                (
                    "ligne_bc",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="lignes_facturees",
                        to="compta.ligneboncommandefournisseur",
                        verbose_name="Ligne du BC correspondante",
                    ),
                ),
            ],
            options={
                "verbose_name": "Ligne de facture fournisseur",
                "verbose_name_plural": "Lignes de facture fournisseur",
                "ordering": ["id"],
            },
        ),
        # ── Rapprochement3Voies ─────────────────────────────────────────────
        migrations.CreateModel(
            name="Rapprochement3Voies",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "libelle",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=255,
                        verbose_name="Libellé",
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("en_cours", "En cours de contrôle"),
                            ("approuve", "Approuvé — paiement autorisé"),
                            ("rejete", "Rejeté — écart non toléré"),
                        ],
                        default="en_cours",
                        max_length=12,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "montant_commande_ht",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="Montant commandé HT (BC)",
                    ),
                ),
                (
                    "montant_recu_ht",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="Montant reçu HT (réception × PU BC)",
                    ),
                ),
                (
                    "montant_facture_ht",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="Montant facturé HT (facture fournisseur)",
                    ),
                ),
                (
                    "ecart_commande_facture_ht",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="Écart facturé − commandé HT",
                    ),
                ),
                (
                    "ecart_recu_facture_ht",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="Écart facturé − reçu HT",
                    ),
                ),
                (
                    "tolerance_ht",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=12,
                        verbose_name="Tolérance (MAD HT)",
                    ),
                ),
                (
                    "notes",
                    models.TextField(
                        blank=True,
                        default="",
                        verbose_name="Notes du contrôleur",
                    ),
                ),
                (
                    "date_validation",
                    models.DateTimeField(
                        blank=True,
                        null=True,
                        verbose_name="Validé le",
                    ),
                ),
                (
                    "date_creation",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Créé le"
                    ),
                ),
                (
                    "bon_commande",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="rapprochements_3voies",
                        to="compta.boncommandefournisseur",
                        verbose_name="Bon de commande",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="rapprochements_3voies",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="rapprochements_3voies_crees",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Créé par",
                    ),
                ),
                (
                    "facture",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="rapprochements_3voies",
                        to="compta.facturefournisseur",
                        verbose_name="Facture fournisseur",
                    ),
                ),
                (
                    "reception",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="rapprochements_3voies",
                        to="compta.receptionmarchandise",
                        verbose_name="Réception",
                    ),
                ),
                (
                    "valide_par",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="rapprochements_3voies_valides",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Validé par",
                    ),
                ),
            ],
            options={
                "verbose_name": "Rapprochement 3 voies",
                "verbose_name_plural": "Rapprochements 3 voies",
                "ordering": ["-date_creation", "-id"],
            },
        ),
    ]
