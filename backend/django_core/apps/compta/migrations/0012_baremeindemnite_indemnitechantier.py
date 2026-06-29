# Generated for FG136 — indemnités kilométriques & per-diem chantier.

import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0012_customuser_must_change_password_and_more"),
        ("compta", "0011_notefrais"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="BaremeIndemnite",
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
                        max_length=120, verbose_name="Libellé du barème"
                    ),
                ),
                (
                    "taux_km",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=8,
                        verbose_name="Indemnité kilométrique (MAD/km)",
                    ),
                ),
                (
                    "per_diem",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=10,
                        verbose_name="Per-diem chantier (MAD/jour)",
                    ),
                ),
                (
                    "defaut",
                    models.BooleanField(
                        default=False, verbose_name="Barème par défaut"
                    ),
                ),
                (
                    "actif",
                    models.BooleanField(default=True, verbose_name="Actif"),
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
                        related_name="baremes_indemnite",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
            ],
            options={
                "verbose_name": "Barème d'indemnité",
                "verbose_name_plural": "Barèmes d'indemnité",
                "ordering": ["-defaut", "libelle", "-id"],
            },
        ),
        migrations.CreateModel(
            name="IndemniteChantier",
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
                        blank=True, default="", max_length=50,
                        verbose_name="Référence",
                    ),
                ),
                (
                    "date_deplacement",
                    models.DateField(verbose_name="Date du déplacement"),
                ),
                (
                    "libelle_chantier",
                    models.CharField(
                        blank=True, default="", max_length=255,
                        verbose_name="Chantier",
                    ),
                ),
                (
                    "depart_lat",
                    models.FloatField(
                        blank=True, null=True, verbose_name="Latitude départ"
                    ),
                ),
                (
                    "depart_lng",
                    models.FloatField(
                        blank=True, null=True, verbose_name="Longitude départ"
                    ),
                ),
                (
                    "site_lat",
                    models.FloatField(
                        blank=True, null=True, verbose_name="Latitude chantier"
                    ),
                ),
                (
                    "site_lng",
                    models.FloatField(
                        blank=True, null=True,
                        verbose_name="Longitude chantier",
                    ),
                ),
                (
                    "aller_retour",
                    models.BooleanField(
                        default=True, verbose_name="Aller-retour"
                    ),
                ),
                (
                    "nombre_jours",
                    models.PositiveIntegerField(
                        default=1, verbose_name="Nombre de jours de chantier"
                    ),
                ),
                (
                    "distance_km",
                    models.DecimalField(
                        decimal_places=3,
                        default=Decimal("0"),
                        max_digits=10,
                        verbose_name="Distance (km)",
                    ),
                ),
                (
                    "montant_km",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="Indemnité kilométrique",
                    ),
                ),
                (
                    "montant_per_diem",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="Per-diem",
                    ),
                ),
                (
                    "montant_total",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="Montant total",
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("brouillon", "Brouillon"),
                            ("soumise", "Soumise"),
                            ("validee", "Validée"),
                            ("rejetee", "Rejetée"),
                            ("remboursee", "Remboursée"),
                        ],
                        default="brouillon",
                        max_length=12,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "date_validation",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="Validée le"
                    ),
                ),
                (
                    "motif_rejet",
                    models.CharField(
                        blank=True, default="", max_length=255,
                        verbose_name="Motif de rejet",
                    ),
                ),
                (
                    "date_remboursement",
                    models.DateField(
                        blank=True, null=True,
                        verbose_name="Date de remboursement",
                    ),
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
                        related_name="indemnites_chantier",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "employe",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="indemnites_chantier",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Employé",
                    ),
                ),
                (
                    "bareme",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="indemnites",
                        to="compta.baremeindemnite",
                        verbose_name="Barème appliqué",
                    ),
                ),
                (
                    "compte_charge",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="indemnites_chantier_charge",
                        to="compta.comptecomptable",
                        verbose_name="Compte de charge",
                    ),
                ),
                (
                    "valide_par",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="indemnites_chantier_validees",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Validée par",
                    ),
                ),
                (
                    "ecriture_charge",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="indemnites_chantier_charge",
                        to="compta.ecriturecomptable",
                        verbose_name="Écriture de charge",
                    ),
                ),
                (
                    "compte_tresorerie",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="indemnites_chantier",
                        to="compta.comptetresorerie",
                        verbose_name="Compte de trésorerie (payeur)",
                    ),
                ),
                (
                    "rembourse_par",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="indemnites_chantier_remboursees",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Remboursée par",
                    ),
                ),
                (
                    "ecriture_remboursement",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="indemnites_chantier_remboursement",
                        to="compta.ecriturecomptable",
                        verbose_name="Écriture de remboursement",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="indemnites_chantier_creees",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Saisie par",
                    ),
                ),
            ],
            options={
                "verbose_name": "Indemnité chantier",
                "verbose_name_plural": "Indemnités chantier",
                "ordering": ["-date_deplacement", "-id"],
            },
        ),
        migrations.AddConstraint(
            model_name="baremeindemnite",
            constraint=models.UniqueConstraint(
                condition=models.Q(("defaut", True), ("actif", True)),
                fields=("company",),
                name="uniq_bareme_indem_defaut",
            ),
        ),
        migrations.AddConstraint(
            model_name="indemnitechantier",
            constraint=models.UniqueConstraint(
                condition=models.Q(("reference__gt", "")),
                fields=("company", "reference"),
                name="uniq_indem_chantier_reference",
            ),
        ),
    ]
