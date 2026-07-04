# Generated for XFLT2 — génération des coûts récurrents de contrat. Ajoute le
# modèle ``EcheanceContrat`` : ligne de coût datée matérialisant l'échéance
# récurrente d'un ``ContratVehicule`` (XFLT1), une ligne par (contrat, période)
# — unique_together garantit l'idempotence de la génération
# (``services.generer_couts_contrat``). company posée côté serveur. Additif,
# multi-société. Repli tant que ``CoutVehicule`` (XFLT3) n'existe pas.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("flotte", "0029_contratvehicule"),
    ]

    operations = [
        migrations.CreateModel(
            name="EcheanceContrat",
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
                    "period",
                    models.CharField(
                        max_length=7, verbose_name="Période (YYYY-MM)"
                    ),
                ),
                (
                    "date_echeance",
                    models.DateField(verbose_name="Date de l'échéance"),
                ),
                (
                    "montant",
                    models.DecimalField(
                        decimal_places=2, default=0, max_digits=12,
                        verbose_name="Montant (MAD)",
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
                        related_name="flotte_echeances_contrat",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "contrat",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="echeances",
                        to="flotte.contratvehicule",
                        verbose_name="Contrat véhicule",
                    ),
                ),
            ],
            options={
                "verbose_name": "Échéance de contrat",
                "verbose_name_plural": "Échéances de contrat",
                "ordering": ["-date_echeance", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="echeancecontrat",
            index=models.Index(
                fields=["company", "period"],
                name="flotte_ecc_co_period_idx",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="echeancecontrat",
            unique_together={("contrat", "period")},
        ),
    ]
