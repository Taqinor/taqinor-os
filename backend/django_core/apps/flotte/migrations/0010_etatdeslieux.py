# Generated for FLOTTE11 — EtatDesLieux (check-list départ/retour + photos).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0013_customuser_poste_ref"),
        ("flotte", "0009_reservationvehicule"),
    ]

    operations = [
        migrations.CreateModel(
            name="EtatDesLieux",
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
                    "moment",
                    models.CharField(
                        choices=[("depart", "Départ"), ("retour", "Retour")],
                        default="depart",
                        max_length=10,
                        verbose_name="Moment",
                    ),
                ),
                (
                    "date_constat",
                    models.DateTimeField(verbose_name="Date du constat"),
                ),
                (
                    "kilometrage",
                    models.PositiveIntegerField(
                        default=0, verbose_name="Kilométrage relevé"
                    ),
                ),
                (
                    "niveau_carburant",
                    models.PositiveSmallIntegerField(
                        default=0, verbose_name="Niveau de carburant (%)"
                    ),
                ),
                (
                    "etat_general",
                    models.CharField(
                        choices=[
                            ("bon", "Bon"),
                            ("moyen", "Moyen"),
                            ("mauvais", "Mauvais"),
                        ],
                        default="bon",
                        max_length=10,
                        verbose_name="État général",
                    ),
                ),
                (
                    "points",
                    models.JSONField(
                        blank=True,
                        default=list,
                        verbose_name="Points contrôlés",
                    ),
                ),
                (
                    "photos",
                    models.JSONField(
                        blank=True,
                        default=list,
                        verbose_name="Photos (clés)",
                    ),
                ),
                (
                    "commentaire",
                    models.TextField(blank=True, verbose_name="Commentaire"),
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
                        related_name="etats_des_lieux_flotte",
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
                        related_name="etats_des_lieux_flotte",
                        to="flotte.conducteur",
                        verbose_name="Conducteur",
                    ),
                ),
                (
                    "reservation",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="etats_des_lieux_flotte",
                        to="flotte.reservationvehicule",
                        verbose_name="Réservation liée",
                    ),
                ),
                (
                    "vehicule",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="etats_des_lieux_flotte",
                        to="flotte.vehicule",
                        verbose_name="Véhicule",
                    ),
                ),
            ],
            options={
                "verbose_name": "État des lieux",
                "verbose_name_plural": "États des lieux",
                "ordering": ["-date_constat"],
            },
        ),
        migrations.AddIndex(
            model_name="etatdeslieux",
            index=models.Index(
                fields=["company", "vehicule"],
                name="flotte_edl_co_veh_idx",
            ),
        ),
    ]
