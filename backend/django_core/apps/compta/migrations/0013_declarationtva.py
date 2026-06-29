# Generated for FG137 — préparation de la déclaration de TVA.

import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compta", "0012_baremeindemnite_indemnitechantier"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DeclarationTVA",
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
                    "regime",
                    models.CharField(
                        choices=[
                            ("mensuel", "Mensuel"),
                            ("trimestriel", "Trimestriel"),
                        ],
                        default="mensuel",
                        max_length=12,
                        verbose_name="Régime",
                    ),
                ),
                (
                    "methode",
                    models.CharField(
                        choices=[
                            ("debit", "Débit"),
                            ("encaissement", "Encaissement"),
                        ],
                        default="debit",
                        max_length=12,
                        verbose_name="Méthode",
                    ),
                ),
                (
                    "date_debut",
                    models.DateField(verbose_name="Début de période"),
                ),
                (
                    "date_fin",
                    models.DateField(verbose_name="Fin de période"),
                ),
                (
                    "tva_collectee",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="TVA collectée",
                    ),
                ),
                (
                    "tva_deductible",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="TVA déductible",
                    ),
                ),
                (
                    "credit_anterieur",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="Crédit de TVA antérieur",
                    ),
                ),
                (
                    "tva_a_declarer",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="TVA à déclarer",
                    ),
                ),
                (
                    "credit_reportable",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=14,
                        verbose_name="Crédit de TVA reportable",
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("brouillon", "Brouillon"),
                            ("preparee", "Préparée"),
                            ("deposee", "Déposée"),
                        ],
                        default="brouillon",
                        max_length=12,
                        verbose_name="Statut",
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
                        related_name="declarations_tva",
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
                        related_name="declarations_tva_creees",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Préparée par",
                    ),
                ),
            ],
            options={
                "verbose_name": "Déclaration de TVA",
                "verbose_name_plural": "Déclarations de TVA",
                "ordering": ["-date_fin", "-id"],
            },
        ),
        migrations.AddConstraint(
            model_name="declarationtva",
            constraint=models.UniqueConstraint(
                condition=models.Q(("reference__gt", "")),
                fields=("company", "reference"),
                name="uniq_decl_tva_reference",
            ),
        ),
    ]
