# Generated for XFLT3 — grand livre des coûts par véhicule. Ajoute le modèle
# ``CoutVehicule`` : saisie manuelle des coûts divers (péage Jawaz, parking,
# lavage…) non capturés par les modèles existants, catégorisée, rattachée à un
# ``ActifFlotte`` et un ``Conducteur`` optionnel. company posée côté serveur.
# Additif, multi-société. Alimente le grand livre unifié
# ``selectors.ledger_vehicule`` (PleinCarburant, OrdreReparation, AssuranceVehicule,
# TSAV, Infraction, CoutVehicule) sans dupliquer ces sources.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("flotte", "0030_echeancecontrat"),
    ]

    operations = [
        migrations.CreateModel(
            name="CoutVehicule",
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
                    "categorie",
                    models.CharField(
                        choices=[
                            ("carburant", "Carburant"),
                            ("entretien", "Entretien"),
                            ("assurance", "Assurance"),
                            ("vignette", "Vignette"),
                            ("amende", "Amende"),
                            ("peage", "Péage"),
                            ("parking", "Parking"),
                            ("lavage", "Lavage"),
                            ("contrat", "Contrat"),
                            ("autre", "Autre"),
                        ],
                        default="autre",
                        max_length=10,
                        verbose_name="Catégorie",
                    ),
                ),
                (
                    "date",
                    models.DateField(verbose_name="Date"),
                ),
                (
                    "montant",
                    models.DecimalField(
                        decimal_places=2, default=0, max_digits=12,
                        verbose_name="Montant (MAD)",
                    ),
                ),
                (
                    "fournisseur",
                    models.CharField(
                        blank=True, max_length=150,
                        verbose_name="Fournisseur",
                    ),
                ),
                (
                    "reference_piece",
                    models.CharField(
                        blank=True, max_length=80,
                        verbose_name="Référence pièce",
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
                        related_name="flotte_couts_vehicule",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "actif_flotte",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="flotte_couts_vehicule",
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
                        related_name="flotte_couts_vehicule",
                        to="flotte.conducteur",
                        verbose_name="Conducteur",
                    ),
                ),
            ],
            options={
                "verbose_name": "Coût véhicule",
                "verbose_name_plural": "Coûts véhicule",
                "ordering": ["-date", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="coutvehicule",
            index=models.Index(
                fields=["company", "actif_flotte"],
                name="flotte_cv_co_actif_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="coutvehicule",
            index=models.Index(
                fields=["company", "categorie"],
                name="flotte_cv_co_cat_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="coutvehicule",
            index=models.Index(
                fields=["company", "date"],
                name="flotte_cv_co_date_idx",
            ),
        ),
    ]
