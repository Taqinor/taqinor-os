# NTHOT3 — Réservations (walk-in/téléphone/email).
# Hand-authored (see 0001_initial.py note on the host Django version mismatch).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0062_lead_web_questionnaire_estimate"),
        ("hospitality", "0002_plantarifaire"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Reservation",
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
                            ("walk_in", "Walk-in"),
                            ("telephone", "Téléphone"),
                            ("email", "Email"),
                            ("ota_gated", "OTA (saisie manuelle)"),
                        ],
                        default="walk_in",
                        max_length=12,
                    ),
                ),
                ("date_arrivee", models.DateField(verbose_name="Date d'arrivée")),
                ("date_depart", models.DateField(verbose_name="Date de départ")),
                ("nb_adultes", models.PositiveIntegerField(default=1)),
                ("nb_enfants", models.PositiveIntegerField(default=0)),
                (
                    "client_nom",
                    models.CharField(blank=True, default="", max_length=200),
                ),
                (
                    "client_telephone",
                    models.CharField(blank=True, default="", max_length=30),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("confirmee", "Confirmée"),
                            ("en_attente", "En attente"),
                            ("annulee", "Annulée"),
                            ("no_show", "No-show"),
                            ("en_cours", "En cours (check-in fait)"),
                            ("terminee", "Terminée"),
                        ],
                        default="confirmee",
                        max_length=12,
                    ),
                ),
                (
                    "prix_nuit_snapshot",
                    models.DecimalField(
                        blank=True, decimal_places=2, max_digits=10, null=True
                    ),
                ),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                (
                    "chambre",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="reservations",
                        to="hospitality.chambre",
                        verbose_name="Chambre",
                    ),
                ),
                (
                    "client",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="hospitality_reservations",
                        to="crm.client",
                        verbose_name="Client CRM",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="hospitality_reservations",
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
                        related_name="hospitality_reservations_creees",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "type_chambre",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="reservations",
                        to="hospitality.typechambre",
                        verbose_name="Type de chambre (si chambre non assignée)",
                    ),
                ),
            ],
            options={
                "verbose_name": "Réservation",
                "verbose_name_plural": "Réservations",
                "ordering": ["-date_arrivee"],
            },
        ),
    ]
