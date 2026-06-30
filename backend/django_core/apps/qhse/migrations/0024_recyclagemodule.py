# Generated for QHSE37 — RecyclageModule (fin de vie des modules PV).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0012_customuser_must_change_password_and_more"),
        ("qhse", "0023_dechet_bordereausuividechet"),
    ]

    operations = [
        migrations.CreateModel(
            name="RecyclageModule",
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
                        max_length=50,
                        verbose_name="Référence",
                    ),
                ),
                (
                    "marque",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=120,
                        verbose_name="Marque",
                    ),
                ),
                (
                    "modele",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=120,
                        verbose_name="Modèle",
                    ),
                ),
                (
                    "nombre_modules",
                    models.PositiveIntegerField(
                        default=0, verbose_name="Nombre de modules"
                    ),
                ),
                (
                    "masse_kg",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=10,
                        null=True,
                        verbose_name="Masse estimée (kg)",
                    ),
                ),
                (
                    "motif",
                    models.CharField(
                        choices=[
                            ("casse", "Casse / bris"),
                            ("declassement", "Déclassement (performance)"),
                            ("renovation", "Rénovation / remplacement"),
                            ("fin_de_vie", "Fin de vie"),
                            ("autre", "Autre"),
                        ],
                        default="fin_de_vie",
                        max_length=15,
                        verbose_name="Motif",
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("collecte", "Collecté"),
                            ("transporte", "Transporté"),
                            ("recycle", "Recyclé"),
                            ("annule", "Annulé"),
                        ],
                        default="collecte",
                        max_length=12,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "filiere",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=255,
                        verbose_name="Filière / repreneur",
                    ),
                ),
                (
                    "chantier_id",
                    models.PositiveIntegerField(
                        blank=True,
                        null=True,
                        verbose_name="ID du chantier d'origine",
                    ),
                ),
                (
                    "date_collecte",
                    models.DateField(
                        blank=True, null=True, verbose_name="Date de collecte"
                    ),
                ),
                (
                    "date_recyclage",
                    models.DateField(
                        blank=True, null=True, verbose_name="Date de recyclage"
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
                        related_name="qhse_recyclage_modules",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "bordereau",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="recyclages_modules",
                        to="qhse.bordereausuividechet",
                        verbose_name="Bordereau de suivi",
                    ),
                ),
            ],
            options={
                "verbose_name": "Recyclage de modules PV",
                "verbose_name_plural": "Recyclages de modules PV",
                "ordering": ["-id"],
            },
        ),
        migrations.AddConstraint(
            model_name="recyclagemodule",
            constraint=models.UniqueConstraint(
                fields=("company", "reference"), name="qhse_recyc_co_ref_uniq"
            ),
        ),
        migrations.AddIndex(
            model_name="recyclagemodule",
            index=models.Index(
                fields=["company", "statut"], name="qhse_recyc_co_statut"
            ),
        ),
        migrations.AddIndex(
            model_name="recyclagemodule",
            index=models.Index(
                fields=["company", "chantier_id"], name="qhse_recyc_co_chant"
            ),
        ),
    ]
