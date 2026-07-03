# Generated for XFLT5 — signalement d'anomalie véhicule par le conducteur.
# Ajoute le modèle ``SignalementVehicule`` : description, photo (MinIO),
# gravité, statut, lien optionnel vers un ``OrdreReparation`` (FLOTTE17) créé
# via l'action ``convertir-en-or``. Tout rôle peut créer (comme
# DemandeVehicule) ; company posée côté serveur. Additif, multi-société.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("flotte", "0032_vehicule_cycle_de_vie"),
    ]

    operations = [
        migrations.CreateModel(
            name="SignalementVehicule",
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
                    "description",
                    models.TextField(verbose_name="Description"),
                ),
                (
                    "photo",
                    models.FileField(
                        blank=True, null=True,
                        upload_to="flotte/signalements/photos/%Y/%m/",
                        verbose_name="Photo",
                    ),
                ),
                (
                    "gravite",
                    models.CharField(
                        choices=[
                            ("faible", "Faible"),
                            ("moyenne", "Moyenne"),
                            ("critique", "Critique"),
                        ],
                        default="moyenne",
                        max_length=8,
                        verbose_name="Gravité",
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("ouvert", "Ouvert"),
                            ("en_cours", "En cours"),
                            ("resolu", "Résolu"),
                            ("clos", "Clos"),
                        ],
                        default="ouvert",
                        max_length=8,
                        verbose_name="Statut",
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
                        related_name="flotte_signalements_vehicule",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "actif_flotte",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="flotte_signalements_vehicule",
                        to="flotte.actifflotte",
                        verbose_name="Actif (véhicule ou engin)",
                    ),
                ),
                (
                    "conducteur",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="flotte_signalements_vehicule",
                        to="flotte.conducteur",
                        verbose_name="Conducteur",
                    ),
                ),
                (
                    "auteur",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="flotte_signalements_vehicule",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Auteur",
                    ),
                ),
                (
                    "ordre_reparation",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="signalements",
                        to="flotte.ordrereparation",
                        verbose_name="Ordre de réparation lié",
                    ),
                ),
            ],
            options={
                "verbose_name": "Signalement d'anomalie véhicule",
                "verbose_name_plural": "Signalements d'anomalie véhicule",
                "ordering": ["-date_creation", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="signalementvehicule",
            index=models.Index(
                fields=["company", "statut"],
                name="flotte_sig_co_stat_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="signalementvehicule",
            index=models.Index(
                fields=["company", "actif_flotte"],
                name="flotte_sig_co_actif_idx",
            ),
        ),
    ]
