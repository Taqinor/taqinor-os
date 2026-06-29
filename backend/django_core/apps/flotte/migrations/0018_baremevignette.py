# Generated for FLOTTE20 — vignette / TSAV (taxe spéciale annuelle sur les
# véhicules). Ajoute ``Vehicule.puissance_fiscale`` (chevaux fiscaux / CV,
# nullable) et le barème éditable ``BaremeVignette`` (montant TSAV par énergie ×
# tranche de CV × année). Modèle additif, multi-société.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0013_customuser_poste_ref"),
        ("flotte", "0017_echeancereglementaire"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehicule",
            name="puissance_fiscale",
            field=models.PositiveSmallIntegerField(
                blank=True,
                null=True,
                help_text=(
                    "Chevaux fiscaux (carte grise). Sert au calcul de la "
                    "TSAV."
                ),
                verbose_name="Puissance fiscale (CV)",
            ),
        ),
        migrations.CreateModel(
            name="BaremeVignette",
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
                    "energie",
                    models.CharField(
                        choices=[
                            ("diesel", "Diesel"),
                            ("essence", "Essence"),
                            ("electrique", "Électrique"),
                            ("hybride", "Hybride"),
                        ],
                        default="essence",
                        max_length=20,
                        verbose_name="Énergie",
                    ),
                ),
                (
                    "cv_min",
                    models.PositiveSmallIntegerField(
                        default=0, verbose_name="CV min (inclus)"
                    ),
                ),
                (
                    "cv_max",
                    models.PositiveSmallIntegerField(
                        default=9999, verbose_name="CV max (inclus)"
                    ),
                ),
                (
                    "montant",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        max_digits=12,
                        verbose_name="Montant TSAV (MAD)",
                    ),
                ),
                (
                    "annee",
                    models.PositiveIntegerField(
                        default=0,
                        help_text=(
                            "Année du barème (0 = barème générique, toutes "
                            "années)."
                        ),
                        verbose_name="Année",
                    ),
                ),
                (
                    "actif",
                    models.BooleanField(default=True, verbose_name="Actif"),
                ),
                (
                    "notes",
                    models.CharField(
                        blank=True, max_length=200, verbose_name="Notes"
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
                        related_name="flotte_baremes_vignette",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
            ],
            options={
                "verbose_name": "Barème vignette / TSAV",
                "verbose_name_plural": "Barèmes vignette / TSAV",
                "ordering": ["annee", "energie", "cv_min"],
                "unique_together": {
                    ("company", "energie", "cv_min", "cv_max", "annee")
                },
            },
        ),
        migrations.AddIndex(
            model_name="baremevignette",
            index=models.Index(
                fields=["company", "energie", "annee"],
                name="flotte_barvig_co_en_an_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="baremevignette",
            index=models.Index(
                fields=["company", "actif"],
                name="flotte_barvig_co_act_idx",
            ),
        ),
    ]
