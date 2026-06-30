# Generated for FLOTTE27 — point d'intégration télématique (no-op sans
# fournisseur). Ajoute le modèle ``ReleveTelematique`` : magasin scopé société
# des relevés GPS/télématiques (odomètre, position, carburant, heures moteur),
# rattaché à un ``ActifFlotte`` (FLOTTE5, même app). La synchronisation depuis
# un fournisseur externe est un NO-OP key-gated (``settings.TELEMATIQUE_ENABLED``
# faux par défaut) ; l'ingestion manuelle marche toujours. Additif,
# multi-société.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0013_customuser_poste_ref"),
        ("flotte", "0023_infraction"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReleveTelematique",
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
                    "horodatage",
                    models.DateTimeField(verbose_name="Horodatage du relevé"),
                ),
                (
                    "odometre",
                    models.DecimalField(
                        blank=True,
                        decimal_places=1,
                        max_digits=12,
                        null=True,
                        verbose_name="Odomètre (km)",
                    ),
                ),
                (
                    "position_lat",
                    models.DecimalField(
                        blank=True,
                        decimal_places=6,
                        max_digits=9,
                        null=True,
                        verbose_name="Latitude",
                    ),
                ),
                (
                    "position_lng",
                    models.DecimalField(
                        blank=True,
                        decimal_places=6,
                        max_digits=9,
                        null=True,
                        verbose_name="Longitude",
                    ),
                ),
                (
                    "niveau_carburant",
                    models.DecimalField(
                        blank=True,
                        decimal_places=1,
                        max_digits=5,
                        null=True,
                        verbose_name="Niveau de carburant (%)",
                    ),
                ),
                (
                    "heures_moteur",
                    models.DecimalField(
                        blank=True,
                        decimal_places=1,
                        max_digits=10,
                        null=True,
                        verbose_name="Heures moteur",
                    ),
                ),
                (
                    "source",
                    models.CharField(
                        choices=[
                            ("manuel", "Saisie manuelle"),
                            ("telematique", "Fournisseur télématique"),
                        ],
                        default="manuel",
                        max_length=20,
                        verbose_name="Source",
                    ),
                ),
                (
                    "raw_payload",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        verbose_name="Charge brute (fournisseur)",
                    ),
                ),
                (
                    "date_creation",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Créé le"
                    ),
                ),
                (
                    "actif_flotte",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="flotte_releves_telematiques",
                        to="flotte.actifflotte",
                        verbose_name="Actif (véhicule ou engin)",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="flotte_releves_telematiques",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
            ],
            options={
                "verbose_name": "Relevé télématique",
                "verbose_name_plural": "Relevés télématiques",
                "ordering": ["-horodatage", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="relevetelematique",
            index=models.Index(
                fields=["company", "actif_flotte"],
                name="flotte_tel_co_actif_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="relevetelematique",
            index=models.Index(
                fields=["company", "horodatage"],
                name="flotte_tel_co_horo_idx",
            ),
        ),
    ]
