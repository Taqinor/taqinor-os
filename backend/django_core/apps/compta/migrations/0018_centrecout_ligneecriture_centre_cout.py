# Generated for FG150 — comptabilité analytique / centres de coût.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compta", "0017_contratavancement_avancementrevenu"),
    ]

    operations = [
        migrations.CreateModel(
            name="CentreCout",
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
                ("code", models.CharField(max_length=30, verbose_name="Code")),
                (
                    "libelle",
                    models.CharField(max_length=200, verbose_name="Libellé"),
                ),
                (
                    "axe",
                    models.CharField(
                        choices=[
                            ("chantier", "Chantier"),
                            ("agence", "Agence"),
                            ("marche", "Marché"),
                            ("commercial", "Commercial"),
                            ("autre", "Autre"),
                        ],
                        default="chantier",
                        max_length=12,
                        verbose_name="Axe analytique",
                    ),
                ),
                (
                    "actif",
                    models.BooleanField(default=True, verbose_name="Actif"),
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
                        related_name="centres_cout",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
            ],
            options={
                "verbose_name": "Centre de coût",
                "verbose_name_plural": "Centres de coût",
                "ordering": ["code"],
            },
        ),
        migrations.AddField(
            model_name="ligneecriture",
            name="centre_cout",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="lignes_ecriture",
                to="compta.centrecout",
                verbose_name="Centre de coût",
            ),
        ),
        migrations.AddConstraint(
            model_name="centrecout",
            constraint=models.UniqueConstraint(
                fields=("company", "code"),
                name="uniq_centrecout_code",
            ),
        ),
    ]
