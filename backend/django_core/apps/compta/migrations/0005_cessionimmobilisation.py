# Generated for FG120 — cession / mise au rebut d'immobilisation.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0012_customuser_must_change_password_and_more"),
        ("compta", "0004_planamortissement_dotationamortissement"),
    ]

    operations = [
        migrations.CreateModel(
            name="CessionImmobilisation",
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
                    "type_cession",
                    models.CharField(
                        choices=[
                            ("vente", "Vente"),
                            ("rebut", "Mise au rebut"),
                        ],
                        default="vente",
                        max_length=10,
                        verbose_name="Type de cession",
                    ),
                ),
                (
                    "date_cession",
                    models.DateField(verbose_name="Date de cession"),
                ),
                (
                    "prix_cession",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        max_digits=14,
                        verbose_name="Prix de cession (HT)",
                    ),
                ),
                (
                    "valeur_nette_comptable",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        max_digits=14,
                        verbose_name="Valeur nette comptable",
                    ),
                ),
                (
                    "amortissements_cumules",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        max_digits=14,
                        verbose_name="Amortissements cumulés",
                    ),
                ),
                (
                    "resultat_cession",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        max_digits=14,
                        verbose_name="Résultat de cession",
                    ),
                ),
                (
                    "posted",
                    models.BooleanField(
                        default=False, verbose_name="Postée au grand livre"
                    ),
                ),
                (
                    "date_creation",
                    models.DateTimeField(auto_now_add=True, verbose_name="Créé le"),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cessions_immobilisation",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "ecriture",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="cessions_immobilisation",
                        to="compta.ecriturecomptable",
                        verbose_name="Écriture comptable",
                    ),
                ),
                (
                    "immobilisation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="cessions",
                        to="compta.immobilisation",
                        verbose_name="Immobilisation",
                    ),
                ),
            ],
            options={
                "verbose_name": "Cession d'immobilisation",
                "verbose_name_plural": "Cessions d'immobilisation",
                "ordering": ["-date_cession", "-id"],
            },
        ),
    ]
