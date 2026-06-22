import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0008_customuser_avatar_key_customuser_poste"),
        ("contrats", "0002_partiecontrat"),
    ]

    operations = [
        migrations.CreateModel(
            name="ContratLien",
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
                    "type_cible",
                    models.CharField(
                        choices=[
                            ("devis", "Devis"),
                            ("lead", "Lead"),
                            ("installation", "Installation"),
                            ("maintenance", "Maintenance"),
                        ],
                        max_length=20,
                        verbose_name="Type de cible",
                    ),
                ),
                (
                    "cible_id",
                    models.PositiveIntegerField(verbose_name="ID de la cible"),
                ),
                (
                    "libelle",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=200,
                        verbose_name="Libellé",
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
                        related_name="contrat_liens",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "contrat",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="liens",
                        to="contrats.contrat",
                        verbose_name="Contrat",
                    ),
                ),
            ],
            options={
                "verbose_name": "Lien du contrat",
                "verbose_name_plural": "Liens du contrat",
                "ordering": ["id"],
            },
        ),
        migrations.AlterUniqueTogether(
            name="contratlien",
            unique_together={("contrat", "type_cible", "cible_id")},
        ),
    ]
