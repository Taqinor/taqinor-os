# Generated for FLOTTE28 — suivi de position & trajets télématiques. Ajoute le
# modèle ``TrajetTelematique`` : magasin scopé société des trajets (déplacement
# de A à B) d'un ``ActifFlotte`` (FLOTTE5, même app), construits à partir des
# ``ReleveTelematique`` (FLOTTE27) successifs ou saisis manuellement. Additif,
# multi-société.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0013_customuser_poste_ref"),
        ("flotte", "0024_relevetelematique"),
    ]

    operations = [
        migrations.CreateModel(
            name="TrajetTelematique",
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
                    "debut",
                    models.DateTimeField(verbose_name="Début du trajet"),
                ),
                (
                    "fin",
                    models.DateTimeField(verbose_name="Fin du trajet"),
                ),
                (
                    "depart_lat",
                    models.DecimalField(
                        blank=True,
                        decimal_places=6,
                        max_digits=9,
                        null=True,
                        verbose_name="Latitude de départ",
                    ),
                ),
                (
                    "depart_lng",
                    models.DecimalField(
                        blank=True,
                        decimal_places=6,
                        max_digits=9,
                        null=True,
                        verbose_name="Longitude de départ",
                    ),
                ),
                (
                    "arrivee_lat",
                    models.DecimalField(
                        blank=True,
                        decimal_places=6,
                        max_digits=9,
                        null=True,
                        verbose_name="Latitude d'arrivée",
                    ),
                ),
                (
                    "arrivee_lng",
                    models.DecimalField(
                        blank=True,
                        decimal_places=6,
                        max_digits=9,
                        null=True,
                        verbose_name="Longitude d'arrivée",
                    ),
                ),
                (
                    "distance_km",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=10,
                        null=True,
                        verbose_name="Distance parcourue (km)",
                    ),
                ),
                (
                    "notes",
                    models.TextField(blank=True, verbose_name="Notes"),
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
                        related_name="flotte_trajets_telematiques",
                        to="flotte.actifflotte",
                        verbose_name="Actif (véhicule ou engin)",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="flotte_trajets_telematiques",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "releve_depart",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="trajets_depart",
                        to="flotte.relevetelematique",
                        verbose_name="Relevé de départ",
                    ),
                ),
                (
                    "releve_arrivee",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="trajets_arrivee",
                        to="flotte.relevetelematique",
                        verbose_name="Relevé d'arrivée",
                    ),
                ),
            ],
            options={
                "verbose_name": "Trajet télématique",
                "verbose_name_plural": "Trajets télématiques",
                "ordering": ["-debut", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="trajettelematique",
            index=models.Index(
                fields=["company", "actif_flotte"],
                name="flotte_traj_co_actif_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="trajettelematique",
            index=models.Index(
                fields=["company", "debut"],
                name="flotte_traj_co_debut_idx",
            ),
        ),
    ]
