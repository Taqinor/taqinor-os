# NTHOT7 — Folio client unifié (nuitées + extras + restaurant → une facture).
# Hand-authored (see 0001_initial.py note on the host Django version mismatch).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hospitality", "0004_ficheclient"),
    ]

    operations = [
        migrations.CreateModel(
            name="Folio",
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
                    "statut",
                    models.CharField(
                        choices=[("ouvert", "Ouvert"), ("solde", "Soldé")],
                        default="ouvert",
                        max_length=10,
                    ),
                ),
                ("facture_id", models.PositiveIntegerField(blank=True, null=True)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("date_cloture", models.DateTimeField(blank=True, null=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="hospitality_folios",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "reservation",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="folio",
                        to="hospitality.reservation",
                        verbose_name="Réservation",
                    ),
                ),
            ],
            options={
                "verbose_name": "Folio",
                "verbose_name_plural": "Folios",
                "ordering": ["-date_creation"],
            },
        ),
        migrations.CreateModel(
            name="LigneFolio",
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
                    "origine",
                    models.CharField(
                        choices=[
                            ("nuitee", "Nuitée"),
                            ("extra", "Extra"),
                            ("restaurant", "Restaurant"),
                            ("taxe_sejour", "Taxe de séjour"),
                        ],
                        max_length=15,
                    ),
                ),
                (
                    "description",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                (
                    "montant_ht",
                    models.DecimalField(decimal_places=2, max_digits=10),
                ),
                (
                    "tva",
                    models.DecimalField(
                        decimal_places=2, default=20, max_digits=5
                    ),
                ),
                (
                    "source_type",
                    models.CharField(blank=True, default="", max_length=30),
                ),
                ("source_id", models.PositiveIntegerField(blank=True, null=True)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                (
                    "folio",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lignes",
                        to="hospitality.folio",
                    ),
                ),
            ],
            options={
                "verbose_name": "Ligne de folio",
                "verbose_name_plural": "Lignes de folio",
                "ordering": ["id"],
            },
        ),
    ]
