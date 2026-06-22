import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0008_customuser_avatar_key_customuser_poste"),
        ("gestion_projet", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProjetLien",
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
                            ("facture", "Facture"),
                            ("ticket", "Ticket SAV"),
                            ("achat", "Achat"),
                        ],
                        max_length=10,
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
                        related_name="projet_liens",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "projet",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="liens",
                        to="gestion_projet.projet",
                        verbose_name="Projet",
                    ),
                ),
            ],
            options={
                "verbose_name": "Lien du projet",
                "verbose_name_plural": "Liens du projet",
                "ordering": ["id"],
            },
        ),
        migrations.AlterUniqueTogether(
            name="projetlien",
            unique_together={("projet", "type_cible", "cible_id")},
        ),
    ]
