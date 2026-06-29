# Generated for QHSE19 — Retour client qualité (satisfaction)

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0012_customuser_must_change_password_and_more"),
        ("qhse", "0012_procedurequalite"),
    ]

    operations = [
        migrations.CreateModel(
            name="RetourClientQualite",
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
                    "chantier_id",
                    models.PositiveIntegerField(
                        blank=True, null=True,
                        verbose_name="ID du chantier"
                    ),
                ),
                (
                    "client_id",
                    models.PositiveIntegerField(
                        blank=True, null=True,
                        verbose_name="ID du client"
                    ),
                ),
                (
                    "note_satisfaction",
                    models.PositiveSmallIntegerField(
                        verbose_name="Note de satisfaction (1–5)"
                    ),
                ),
                (
                    "commentaire",
                    models.TextField(
                        blank=True, default="", verbose_name="Commentaire"
                    ),
                ),
                (
                    "date_retour",
                    models.DateField(verbose_name="Date du retour"),
                ),
                (
                    "canal",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("telephone", "Téléphone"),
                            ("email", "Email"),
                            ("whatsapp", "WhatsApp"),
                            ("formulaire", "Formulaire"),
                            ("visite", "Visite sur site"),
                            ("autre", "Autre"),
                        ],
                        default="",
                        max_length=12,
                        verbose_name="Canal",
                    ),
                ),
                (
                    "traite",
                    models.BooleanField(
                        default=False, verbose_name="Traité"
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
                        related_name="qhse_retours_client",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
            ],
            options={
                "verbose_name": "Retour client qualité",
                "verbose_name_plural": "Retours client qualité",
                "ordering": ["-date_retour", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="retourclientqualite",
            index=models.Index(
                fields=["company", "date_retour"],
                name="qhse_retcli_co_date",
            ),
        ),
        migrations.AddIndex(
            model_name="retourclientqualite",
            index=models.Index(
                fields=["company", "chantier_id"],
                name="qhse_retcli_co_chant",
            ),
        ),
    ]
