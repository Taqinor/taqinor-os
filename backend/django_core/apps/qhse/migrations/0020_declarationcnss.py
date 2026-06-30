# Generated for QHSE30 — Déclaration CNSS de l'accident du travail (échéance légale).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0012_customuser_must_change_password_and_more"),
        # FK-chaîne cross-app vers rh.AccidentTravail (FG181) — jamais un import
        # du modèle rh.
        ("rh", "0021_accident_travail"),
        ("qhse", "0019_incident"),
    ]

    operations = [
        migrations.CreateModel(
            name="DeclarationCnss",
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
                    "date_accident",
                    models.DateField(verbose_name="Date de l'accident"),
                ),
                (
                    "delai_jours",
                    models.PositiveSmallIntegerField(
                        default=2, verbose_name="Délai légal (jours)"
                    ),
                ),
                (
                    "date_limite",
                    models.DateField(
                        blank=True,
                        null=True,
                        verbose_name="Date limite de déclaration",
                    ),
                ),
                (
                    "date_declaration",
                    models.DateField(
                        blank=True,
                        null=True,
                        verbose_name="Date de déclaration",
                    ),
                ),
                (
                    "numero_declaration",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=80,
                        verbose_name="N° / référence de déclaration",
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("a_declarer", "À déclarer"),
                            ("declare", "Déclaré"),
                            ("hors_delai", "Hors délai"),
                        ],
                        default="a_declarer",
                        max_length=20,
                        verbose_name="Statut",
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
                    "date_modification",
                    models.DateTimeField(
                        auto_now=True, verbose_name="Modifié le"
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="qhse_declarations_cnss",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "accident_travail",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="qhse_declarations_cnss",
                        to="rh.accidenttravail",
                        verbose_name="Accident du travail",
                    ),
                ),
            ],
            options={
                "verbose_name": "Déclaration CNSS d'accident du travail",
                "verbose_name_plural": "Déclarations CNSS d'accident du travail",
                "ordering": ["-id"],
            },
        ),
        migrations.AddIndex(
            model_name="declarationcnss",
            index=models.Index(
                fields=["company", "statut"], name="qhse_declcnss_co_statut"
            ),
        ),
        migrations.AddIndex(
            model_name="declarationcnss",
            index=models.Index(
                fields=["company", "date_limite"],
                name="qhse_declcnss_co_limite",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="declarationcnss",
            unique_together={("company", "accident_travail")},
        ),
    ]
