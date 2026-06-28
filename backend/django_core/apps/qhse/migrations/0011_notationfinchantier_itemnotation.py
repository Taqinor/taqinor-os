# Generated for QHSE17 — Grille de notation fin de chantier (gate clôture)

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0012_customuser_must_change_password_and_more"),
        ("qhse", "0010_audit_reponsecritere"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="NotationFinChantier",
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
                    "chantier_id",
                    models.PositiveIntegerField(verbose_name="ID du chantier"),
                ),
                (
                    "date_notation",
                    models.DateField(
                        blank=True, null=True, verbose_name="Date de notation"
                    ),
                ),
                (
                    "score",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=5,
                        null=True,
                        verbose_name="Score (%)",
                    ),
                ),
                (
                    "seuil_passage",
                    models.PositiveIntegerField(
                        default=70, verbose_name="Seuil de passage (%)"
                    ),
                ),
                (
                    "verdict",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("passe", "Passé"),
                            ("echec", "Échec"),
                        ],
                        max_length=6,
                        null=True,
                        verbose_name="Verdict",
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
                    "auteur",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="qhse_notations_fin_chantier",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Auteur",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="qhse_notations_fin_chantier",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
            ],
            options={
                "verbose_name": "Notation fin de chantier",
                "verbose_name_plural": "Notations fin de chantier",
                "ordering": ["-id"],
            },
        ),
        migrations.AddIndex(
            model_name="notationfinchantier",
            index=models.Index(
                fields=["company", "chantier_id"],
                name="qhse_notation_co_chantier",
            ),
        ),
        migrations.CreateModel(
            name="ItemNotation",
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
                    "categorie",
                    models.CharField(
                        blank=True, default="", max_length=120,
                        verbose_name="Catégorie"
                    ),
                ),
                (
                    "poids",
                    models.PositiveIntegerField(default=1, verbose_name="Poids"),
                ),
                (
                    "conforme",
                    models.BooleanField(
                        blank=True, null=True, verbose_name="Conforme"
                    ),
                ),
                (
                    "commentaire",
                    models.TextField(
                        blank=True, default="", verbose_name="Commentaire"
                    ),
                ),
                (
                    "ordre",
                    models.PositiveIntegerField(default=0, verbose_name="Ordre"),
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
                        related_name="qhse_items_notation",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "notation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="qhse.notationfinchantier",
                        verbose_name="Notation fin de chantier",
                    ),
                ),
            ],
            options={
                "verbose_name": "Item de notation fin de chantier",
                "verbose_name_plural": "Items de notation fin de chantier",
                "ordering": ["notation", "ordre", "id"],
            },
        ),
    ]
