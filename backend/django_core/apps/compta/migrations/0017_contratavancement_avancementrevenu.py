# Generated for FG146 — reconnaissance du revenu par avancement.

import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compta", "0016_retenuegarantie_cautionbancaire"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ContratAvancement",
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
                    "libelle",
                    models.CharField(
                        blank=True, default="", max_length=200,
                        verbose_name="Libellé",
                    ),
                ),
                (
                    "chantier_ref",
                    models.CharField(
                        blank=True, default="", max_length=120,
                        verbose_name="Chantier",
                    ),
                ),
                (
                    "marche_ref",
                    models.CharField(
                        blank=True, default="", max_length=120,
                        verbose_name="Marché",
                    ),
                ),
                (
                    "client_id",
                    models.PositiveIntegerField(
                        blank=True, null=True, verbose_name="ID du client",
                    ),
                ),
                (
                    "client_nom",
                    models.CharField(
                        blank=True, default="", max_length=200,
                        verbose_name="Client",
                    ),
                ),
                (
                    "methode",
                    models.CharField(
                        choices=[
                            (
                                "couts",
                                "Cost-to-cost (coûts engagés / coûts "
                                "estimés)",
                            ),
                            ("saisie", "Avancement physique saisi (%)"),
                        ],
                        default="couts",
                        max_length=10,
                        verbose_name="Méthode d'avancement",
                    ),
                ),
                (
                    "revenu_total",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="Revenu total contractuel (HT)",
                    ),
                ),
                (
                    "cout_total_estime",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="Coût total estimé",
                    ),
                ),
                (
                    "date_debut",
                    models.DateField(
                        blank=True, null=True, verbose_name="Date de début",
                    ),
                ),
                (
                    "date_fin_prevue",
                    models.DateField(
                        blank=True, null=True,
                        verbose_name="Date de fin prévue",
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("en_cours", "En cours"),
                            ("termine", "Terminé"),
                        ],
                        default="en_cours",
                        max_length=10,
                        verbose_name="Statut",
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
                        related_name="contrats_avancement",
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
                        related_name="contrats_avancement_crees",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Créé par",
                    ),
                ),
            ],
            options={
                "verbose_name": "Contrat à l'avancement",
                "verbose_name_plural": "Contrats à l'avancement",
                "ordering": ["-date_creation", "-id"],
            },
        ),
        migrations.CreateModel(
            name="AvancementRevenu",
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
                    "date_arrete",
                    models.DateField(verbose_name="Date d'arrêté"),
                ),
                (
                    "pourcentage",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=5,
                        verbose_name="Avancement cumulé (%)",
                    ),
                ),
                (
                    "cout_engage_cumule",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="Coût engagé cumulé",
                    ),
                ),
                (
                    "revenu_cumule",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="Revenu cumulé reconnu",
                    ),
                ),
                (
                    "revenu_periode",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="Revenu reconnu sur la période",
                    ),
                ),
                (
                    "ecriture_id",
                    models.PositiveIntegerField(
                        blank=True, null=True,
                        verbose_name="ID de l'écriture OD",
                    ),
                ),
                (
                    "libelle",
                    models.CharField(
                        blank=True, default="", max_length=200,
                        verbose_name="Libellé",
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
                        related_name="avancements_revenu",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "contrat",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="avancements",
                        to="compta.contratavancement",
                        verbose_name="Contrat",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="avancements_revenu_crees",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Créé par",
                    ),
                ),
            ],
            options={
                "verbose_name": "Constat d'avancement",
                "verbose_name_plural": "Constats d'avancement",
                "ordering": ["contrat", "date_arrete", "id"],
            },
        ),
        migrations.AddConstraint(
            model_name="contratavancement",
            constraint=models.UniqueConstraint(
                condition=models.Q(("reference__gt", "")),
                fields=("company", "reference"),
                name="uniq_contrat_av_ref",
            ),
        ),
    ]
