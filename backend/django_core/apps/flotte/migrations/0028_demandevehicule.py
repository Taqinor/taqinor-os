# Generated for FLOTTE32 — pool de véhicules & demandes. Ajoute le modèle
# ``DemandeVehicule`` : un collaborateur (``authentication.User``) demande un
# véhicule du pool pour une période ; le responsable approuve/refuse et attribue
# un ``Vehicule`` (même app). company ET demandeur posés côté serveur. Additif,
# multi-société.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("authentication", "0013_customuser_poste_ref"),
        ("flotte", "0027_vehicule_immobilisation"),
    ]

    operations = [
        migrations.CreateModel(
            name="DemandeVehicule",
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
                    "besoin",
                    models.CharField(
                        max_length=255,
                        verbose_name="Besoin / objet de la demande",
                    ),
                ),
                (
                    "date_debut_souhaitee",
                    models.DateField(verbose_name="Début souhaité"),
                ),
                (
                    "date_fin_souhaitee",
                    models.DateField(verbose_name="Fin souhaitée"),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("demandee", "Demandée"),
                            ("approuvee", "Approuvée"),
                            ("refusee", "Refusée"),
                            ("annulee", "Annulée"),
                        ],
                        default="demandee",
                        max_length=9,
                        verbose_name="Statut",
                    ),
                ),
                (
                    "date_decision",
                    models.DateTimeField(
                        blank=True,
                        null=True,
                        verbose_name="Date de décision",
                    ),
                ),
                (
                    "motif_decision",
                    models.TextField(
                        blank=True, verbose_name="Motif de la décision"
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
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="flotte_demandes_vehicule",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "demandeur",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="flotte_demandes_vehicule",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Demandeur",
                    ),
                ),
                (
                    "decide_par",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="flotte_demandes_vehicule_decidees",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Décidée par",
                    ),
                ),
                (
                    "vehicule_attribue",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="demandes_attribuees",
                        to="flotte.vehicule",
                        verbose_name="Véhicule attribué",
                    ),
                ),
            ],
            options={
                "verbose_name": "Demande de véhicule (pool)",
                "verbose_name_plural": "Demandes de véhicule (pool)",
                "ordering": ["-date_creation", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="demandevehicule",
            index=models.Index(
                fields=["company", "statut"],
                name="flotte_dem_co_stat_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="demandevehicule",
            index=models.Index(
                fields=["company", "demandeur"],
                name="flotte_dem_co_dem_idx",
            ),
        ),
    ]
