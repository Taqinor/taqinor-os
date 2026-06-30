# Generated for FLOTTE21 — assurance auto. Ajoute le modèle ``AssuranceVehicule``
# (police d'assurance d'un actif de flotte : assureur, numéro de police, période
# de couverture, franchise, attestation scannée). Modèle DÉDIÉ au CONTRAT, qui
# COMPLÈTE sans la dupliquer l'``EcheanceReglementaire`` générique (FLOTTE19).
# Additif, multi-société.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0013_customuser_poste_ref"),
        ("flotte", "0018_baremevignette"),
    ]

    operations = [
        migrations.CreateModel(
            name="AssuranceVehicule",
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
                    "assureur",
                    models.CharField(
                        max_length=120, verbose_name="Assureur / Compagnie"
                    ),
                ),
                (
                    "numero_police",
                    models.CharField(
                        max_length=80, verbose_name="Numéro de police"
                    ),
                ),
                (
                    "date_debut",
                    models.DateField(
                        blank=True, null=True,
                        verbose_name="Début de couverture",
                    ),
                ),
                (
                    "date_echeance",
                    models.DateField(verbose_name="Date d'échéance"),
                ),
                (
                    "franchise",
                    models.DecimalField(
                        decimal_places=2, default=0, max_digits=12,
                        verbose_name="Franchise (MAD)",
                    ),
                ),
                (
                    "attestation",
                    models.FileField(
                        blank=True,
                        null=True,
                        upload_to="flotte/assurances/attestations/%Y/%m/",
                        verbose_name="Attestation d'assurance",
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
                        related_name="flotte_assurances_vehicule",
                        to="flotte.actifflotte",
                        verbose_name="Actif (véhicule ou engin)",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="flotte_assurances_vehicule",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
            ],
            options={
                "verbose_name": "Police d'assurance",
                "verbose_name_plural": "Polices d'assurance",
                "ordering": ["date_echeance", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="assurancevehicule",
            index=models.Index(
                fields=["company", "statut"],
                name="flotte_assur_co_stat_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="assurancevehicule",
            index=models.Index(
                fields=["company", "actif_flotte"],
                name="flotte_assur_co_actif_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="assurancevehicule",
            index=models.Index(
                fields=["company", "date_echeance"],
                name="flotte_assur_co_date_idx",
            ),
        ),
    ]
