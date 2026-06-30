# Generated for FLOTTE23 — carte grise & autorisation de circulation. Ajoute le
# modèle ``CarteGriseVehicule`` (documents d'immatriculation d'un actif de
# flotte : numéro de carte grise, dates d'immatriculation / de mise en
# circulation, autorisation de circulation [numéro + date de validité,
# facultatifs] et les deux documents scannés). 100 % flotte (aucun couplage à
# apps.ged). Additif, multi-société.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0013_customuser_poste_ref"),
        ("flotte", "0020_visitetechnique"),
    ]

    operations = [
        migrations.CreateModel(
            name="CarteGriseVehicule",
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
                    "numero_carte_grise",
                    models.CharField(
                        max_length=80, verbose_name="Numéro de carte grise"
                    ),
                ),
                (
                    "date_immatriculation",
                    models.DateField(
                        blank=True, null=True,
                        verbose_name="Date d'immatriculation",
                    ),
                ),
                (
                    "date_mise_circulation",
                    models.DateField(
                        blank=True, null=True,
                        verbose_name="Date de mise en circulation",
                    ),
                ),
                (
                    "autorisation_circulation_numero",
                    models.CharField(
                        blank=True, max_length=80,
                        verbose_name="Numéro d'autorisation de circulation",
                    ),
                ),
                (
                    "autorisation_date_validite",
                    models.DateField(
                        blank=True, null=True,
                        verbose_name="Validité de l'autorisation de "
                        "circulation",
                    ),
                ),
                (
                    "carte_grise_fichier",
                    models.FileField(
                        blank=True,
                        null=True,
                        upload_to="flotte/cartes_grises/%Y/%m/",
                        verbose_name="Carte grise (scan)",
                    ),
                ),
                (
                    "autorisation_fichier",
                    models.FileField(
                        blank=True,
                        null=True,
                        upload_to="flotte/autorisations_circulation/%Y/%m/",
                        verbose_name="Autorisation de circulation (scan)",
                    ),
                ),
                (
                    "alerte_jours",
                    models.PositiveIntegerField(
                        default=30, verbose_name="Marge d'alerte (jours)"
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("valide", "Valide"),
                            ("a_renouveler", "À renouveler"),
                            ("expiree", "Expirée"),
                        ],
                        default="valide",
                        max_length=12,
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
                    "actif_flotte",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="flotte_cartes_grises",
                        to="flotte.actifflotte",
                        verbose_name="Actif (véhicule ou engin)",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="flotte_cartes_grises",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
            ],
            options={
                "verbose_name": "Carte grise / autorisation de circulation",
                "verbose_name_plural":
                    "Cartes grises / autorisations de circulation",
                "ordering": ["actif_flotte", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="cartegrisevehicule",
            index=models.Index(
                fields=["company", "statut"],
                name="flotte_cg_co_stat_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="cartegrisevehicule",
            index=models.Index(
                fields=["company", "actif_flotte"],
                name="flotte_cg_co_actif_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="cartegrisevehicule",
            index=models.Index(
                fields=["company", "autorisation_date_validite"],
                name="flotte_cg_co_autval_idx",
            ),
        ),
    ]
