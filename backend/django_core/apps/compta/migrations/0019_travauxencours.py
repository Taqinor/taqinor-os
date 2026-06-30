# Generated for FG147 — produits constatés d'avance & travaux en cours.

import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compta", "0018_centrecout_ligneecriture_centre_cout"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="TravauxEnCours",
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
                    "nature",
                    models.CharField(
                        choices=[
                            ("pca", "Produits constatés d'avance"),
                            (
                                "wip",
                                "Travaux en cours (production stockée)",
                            ),
                        ],
                        default="wip",
                        max_length=4,
                        verbose_name="Nature",
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
                    "contrat_id",
                    models.PositiveIntegerField(
                        blank=True, null=True, verbose_name="ID du contrat",
                    ),
                ),
                (
                    "montant",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="Montant régularisé",
                    ),
                ),
                (
                    "date_arrete",
                    models.DateField(verbose_name="Date d'arrêté"),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("constate", "Constaté"),
                            ("repris", "Repris (extourné)"),
                        ],
                        default="constate",
                        max_length=10,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "ecriture_id",
                    models.PositiveIntegerField(
                        blank=True, null=True,
                        verbose_name="ID de l'écriture de constat",
                    ),
                ),
                (
                    "ecriture_reprise_id",
                    models.PositiveIntegerField(
                        blank=True, null=True,
                        verbose_name="ID de l'écriture de reprise",
                    ),
                ),
                (
                    "date_reprise",
                    models.DateField(
                        blank=True, null=True,
                        verbose_name="Date de reprise",
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
                        related_name="travaux_en_cours",
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
                        related_name="travaux_en_cours_crees",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Créé par",
                    ),
                ),
            ],
            options={
                "verbose_name": "Régularisation (PCA / WIP)",
                "verbose_name_plural": "Régularisations (PCA / WIP)",
                "ordering": ["-date_arrete", "-id"],
            },
        ),
        migrations.AddConstraint(
            model_name="travauxencours",
            constraint=models.UniqueConstraint(
                condition=models.Q(("reference__gt", "")),
                fields=("company", "reference"),
                name="uniq_tec_reference",
            ),
        ),
    ]
