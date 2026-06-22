import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0008_customuser_avatar_key_customuser_poste"),
        ("contrats", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PartieContrat",
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
                    "type_partie",
                    models.CharField(
                        choices=[
                            ("client", "Client"),
                            ("prestataire", "Prestataire"),
                            ("temoin", "Témoin"),
                            ("garant", "Garant"),
                            ("autre", "Autre"),
                        ],
                        default="client",
                        max_length=20,
                        verbose_name="Rôle de la partie",
                    ),
                ),
                ("nom", models.CharField(max_length=255, verbose_name="Nom")),
                (
                    "fonction",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=120,
                        verbose_name="Fonction",
                    ),
                ),
                (
                    "email",
                    models.EmailField(
                        blank=True,
                        default="",
                        max_length=254,
                        verbose_name="Email",
                    ),
                ),
                (
                    "telephone",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=30,
                        verbose_name="Téléphone",
                    ),
                ),
                (
                    "ordre",
                    models.PositiveIntegerField(default=0, verbose_name="Ordre"),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="parties_contrat",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "contrat",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="parties",
                        to="contrats.contrat",
                        verbose_name="Contrat",
                    ),
                ),
            ],
            options={
                "verbose_name": "Partie au contrat",
                "verbose_name_plural": "Parties au contrat",
                "ordering": ["contrat_id", "ordre", "id"],
            },
        ),
    ]
