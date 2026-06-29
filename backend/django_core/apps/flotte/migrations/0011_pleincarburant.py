# Generated for FLOTTE12 — PleinCarburant (carnet de carburant).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0013_customuser_poste_ref"),
        ("flotte", "0010_etatdeslieux"),
    ]

    operations = [
        migrations.CreateModel(
            name="PleinCarburant",
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
                    "date_plein",
                    models.DateField(verbose_name="Date du plein"),
                ),
                (
                    "kilometrage",
                    models.PositiveIntegerField(
                        verbose_name="Kilométrage au compteur"
                    ),
                ),
                (
                    "quantite",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        max_digits=10,
                        verbose_name="Quantité",
                    ),
                ),
                (
                    "unite",
                    models.CharField(
                        choices=[("litre", "Litre"), ("kwh", "kWh")],
                        default="litre",
                        max_length=10,
                        verbose_name="Unité",
                    ),
                ),
                (
                    "prix_total",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        max_digits=12,
                        verbose_name="Prix total (MAD)",
                    ),
                ),
                (
                    "plein_complet",
                    models.BooleanField(
                        default=True, verbose_name="Plein complet"
                    ),
                ),
                (
                    "station",
                    models.CharField(
                        blank=True, max_length=120, verbose_name="Station"
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
                        related_name="pleins_carburant_flotte",
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
                        related_name="pleins_carburant_flotte",
                        to="flotte.conducteur",
                        verbose_name="Conducteur",
                    ),
                ),
                (
                    "vehicule",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="pleins_carburant_flotte",
                        to="flotte.vehicule",
                        verbose_name="Véhicule",
                    ),
                ),
            ],
            options={
                "verbose_name": "Plein de carburant",
                "verbose_name_plural": "Pleins de carburant",
                "ordering": ["-date_plein", "-kilometrage"],
            },
        ),
        migrations.AddIndex(
            model_name="pleincarburant",
            index=models.Index(
                fields=["company", "vehicule"],
                name="flotte_plein_co_veh_idx",
            ),
        ),
    ]
