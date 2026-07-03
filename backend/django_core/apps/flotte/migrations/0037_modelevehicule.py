# Generated for XFLT12 — Catalogue de modèles véhicule. Crée ``ModeleVehicule``
# et le lien optionnel ``Vehicule.modele_ref``. Additif, multi-société.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("flotte", "0036_infraction_imputation_auto"),
    ]

    operations = [
        migrations.CreateModel(
            name="ModeleVehicule",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID")),
                ("marque", models.CharField(max_length=80, verbose_name="Marque")),
                ("modele", models.CharField(max_length=80, verbose_name="Modèle")),
                ("categorie", models.CharField(
                    choices=[
                        ("voiture", "Voiture"), ("fourgon", "Fourgon"),
                        ("camion", "Camion"), ("remorque", "Remorque"),
                        ("chariot", "Chariot"),
                    ], default="voiture", max_length=10,
                    verbose_name="Catégorie")),
                ("energie", models.CharField(
                    choices=[
                        ("diesel", "Diesel"), ("essence", "Essence"),
                        ("electrique", "Électrique"), ("hybride", "Hybride"),
                    ], default="diesel", max_length=20,
                    verbose_name="Énergie")),
                ("co2_g_km", models.PositiveIntegerField(
                    blank=True, null=True, verbose_name="CO₂ (g/km)")),
                ("places", models.PositiveSmallIntegerField(
                    blank=True, null=True, verbose_name="Places")),
                ("puissance_fiscale", models.PositiveSmallIntegerField(
                    blank=True, null=True,
                    verbose_name="Puissance fiscale (CV)")),
                ("puissance_kw", models.PositiveSmallIntegerField(
                    blank=True, null=True, verbose_name="Puissance (kW)")),
                ("valeur_catalogue", models.DecimalField(
                    blank=True, decimal_places=2, max_digits=12, null=True,
                    verbose_name="Valeur catalogue (MAD)")),
                ("capacite_reservoir_l", models.PositiveSmallIntegerField(
                    blank=True, null=True,
                    help_text="Sert au détecteur de fraude FLOTTE14 : un "
                    "plein dépassant cette capacité est une anomalie.",
                    verbose_name="Capacité réservoir (L)")),
                ("date_creation", models.DateTimeField(
                    auto_now_add=True, verbose_name="Créé le")),
                ("company", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="flotte_modeles_vehicule",
                    to="authentication.company", verbose_name="Société")),
            ],
            options={
                "verbose_name": "Modèle véhicule (catalogue)",
                "verbose_name_plural": "Modèles véhicule (catalogue)",
                "ordering": ["marque", "modele"],
            },
        ),
        migrations.AddField(
            model_name="vehicule",
            name="modele_ref",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="vehicules", to="flotte.modelevehicule",
                verbose_name="Modèle de référence"),
        ),
        migrations.AddIndex(
            model_name="modelevehicule",
            index=models.Index(
                fields=["company", "marque", "modele"],
                name="flotte_modveh_co_mm_idx"),
        ),
    ]
