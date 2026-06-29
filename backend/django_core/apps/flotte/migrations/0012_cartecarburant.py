# Generated for FLOTTE14 — CarteCarburant (cartes carburant & alertes anomalie).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0013_customuser_poste_ref"),
        ("flotte", "0011_pleincarburant"),
    ]

    operations = [
        migrations.CreateModel(
            name="CarteCarburant",
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
                    "numero",
                    models.CharField(
                        max_length=60, verbose_name="Numéro de carte"
                    ),
                ),
                (
                    "plafond",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        help_text=(
                            "Montant maximum toléré sur un plein avant alerte ; "
                            "laisser vide pour aucun plafond."
                        ),
                        max_digits=12,
                        null=True,
                        verbose_name="Plafond par plein (MAD)",
                    ),
                ),
                (
                    "actif",
                    models.BooleanField(
                        default=True, verbose_name="Active"
                    ),
                ),
                ("notes", models.TextField(blank=True, verbose_name="Notes")),
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
                        related_name="cartes_carburant_flotte",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "conducteur",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="cartes_carburant_flotte",
                        to="flotte.conducteur",
                        verbose_name="Conducteur attribué",
                    ),
                ),
                (
                    "vehicule",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="cartes_carburant_flotte",
                        to="flotte.vehicule",
                        verbose_name="Véhicule attribué",
                    ),
                ),
            ],
            options={
                "verbose_name": "Carte carburant",
                "verbose_name_plural": "Cartes carburant",
                "ordering": ["numero"],
            },
        ),
        migrations.AddIndex(
            model_name="cartecarburant",
            index=models.Index(
                fields=["company", "actif"],
                name="flotte_carte_co_act_idx",
            ),
        ),
    ]
