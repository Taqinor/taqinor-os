# Generated for FLOTTE10 — ReservationVehicule + détection de conflit.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0013_customuser_poste_ref"),
        ("flotte", "0008_vehicule_categorie_permis_requise"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReservationVehicule",
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
                ("debut", models.DateTimeField(verbose_name="Début")),
                ("fin", models.DateTimeField(verbose_name="Fin")),
                (
                    "motif",
                    models.CharField(
                        blank=True, max_length=200, verbose_name="Motif"
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("demandee", "Demandée"),
                            ("confirmee", "Confirmée"),
                            ("annulee", "Annulée"),
                        ],
                        default="demandee",
                        max_length=20,
                        verbose_name="Statut",
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
                        related_name="reservations_flotte",
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
                        related_name="reservations_flotte",
                        to="flotte.conducteur",
                        verbose_name="Conducteur prévu",
                    ),
                ),
                (
                    "vehicule",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reservations_flotte",
                        to="flotte.vehicule",
                        verbose_name="Véhicule",
                    ),
                ),
            ],
            options={
                "verbose_name": "Réservation de véhicule",
                "verbose_name_plural": "Réservations de véhicule",
                "ordering": ["-debut"],
            },
        ),
        migrations.AddIndex(
            model_name="reservationvehicule",
            index=models.Index(
                fields=["company", "vehicule"],
                name="flotte_resa_co_veh_idx",
            ),
        ),
    ]
