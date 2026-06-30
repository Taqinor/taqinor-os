# Generated for QHSE38 — ConformiteEnvironnementale + relances.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0012_customuser_must_change_password_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("qhse", "0024_recyclagemodule"),
    ]

    operations = [
        migrations.CreateModel(
            name="ConformiteEnvironnementale",
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
                    "intitule",
                    models.CharField(max_length=255, verbose_name="Intitulé"),
                ),
                (
                    "type_conformite",
                    models.CharField(
                        choices=[
                            ("autorisation", "Autorisation environnementale"),
                            ("etude_impact", "Étude d'impact (EIE)"),
                            (
                                "enregistrement_dechets",
                                "Enregistrement déchets (loi 28-00)",
                            ),
                            ("rejets", "Conformité rejets (eau / air)"),
                            ("autre", "Autre"),
                        ],
                        default="autorisation",
                        max_length=25,
                        verbose_name="Type",
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("conforme", "Conforme"),
                            ("a_renouveler", "À renouveler"),
                            ("non_conforme", "Non conforme"),
                            ("expire", "Expiré"),
                        ],
                        default="conforme",
                        max_length=15,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "autorite",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=255,
                        verbose_name="Autorité de tutelle",
                    ),
                ),
                (
                    "reference_dossier",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=120,
                        verbose_name="Référence du dossier",
                    ),
                ),
                (
                    "chantier_id",
                    models.PositiveIntegerField(
                        blank=True, null=True, verbose_name="ID du chantier"
                    ),
                ),
                (
                    "date_obtention",
                    models.DateField(
                        blank=True, null=True, verbose_name="Date d'obtention"
                    ),
                ),
                (
                    "date_expiration",
                    models.DateField(
                        blank=True, null=True, verbose_name="Date d'expiration"
                    ),
                ),
                (
                    "prealerte_jours",
                    models.PositiveIntegerField(
                        default=60, verbose_name="Préalerte (jours)"
                    ),
                ),
                (
                    "notes",
                    models.TextField(
                        blank=True, default="", verbose_name="Notes"
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
                        related_name="qhse_conformites_env",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "responsable",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="qhse_conformites_env",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Responsable",
                    ),
                ),
            ],
            options={
                "verbose_name": "Conformité environnementale",
                "verbose_name_plural": "Conformités environnementales",
                "ordering": ["-id"],
            },
        ),
        migrations.AddIndex(
            model_name="conformiteenvironnementale",
            index=models.Index(
                fields=["company", "statut"], name="qhse_confenv_co_statut"
            ),
        ),
        migrations.AddIndex(
            model_name="conformiteenvironnementale",
            index=models.Index(
                fields=["company", "date_expiration"],
                name="qhse_confenv_co_exp",
            ),
        ),
    ]
