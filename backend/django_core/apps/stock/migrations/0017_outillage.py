import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0008_customuser_avatar_key_customuser_poste"),
        ("stock", "0016_boncommandefournisseur"),
    ]

    operations = [
        migrations.CreateModel(
            name="Outillage",
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
                ("nom", models.CharField(max_length=150)),
                ("categorie", models.CharField(blank=True, default="", max_length=80)),
                ("asset_tag", models.CharField(blank=True, default="", max_length=60)),
                ("numero_serie", models.CharField(blank=True, default="", max_length=120)),
                (
                    "emplacement",
                    models.CharField(
                        choices=[
                            ("depot", "Dépôt"),
                            ("camionnette", "Camionnette"),
                            ("en_intervention", "En intervention"),
                        ],
                        default="depot",
                        max_length=20,
                    ),
                ),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("disponible", "Disponible"),
                            ("en_intervention", "En intervention"),
                            ("en_reparation", "En réparation"),
                            ("perdu", "Perdu"),
                        ],
                        default="disponible",
                        max_length=20,
                    ),
                ),
                ("date_achat", models.DateField(blank=True, null=True)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                (
                    "company",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="outillages",
                        to="authentication.company",
                    ),
                ),
            ],
            options={
                "verbose_name": "Outil (outillage)",
                "verbose_name_plural": "Outillage",
                "ordering": ["nom", "id"],
            },
        ),
        migrations.AddConstraint(
            model_name="outillage",
            constraint=models.UniqueConstraint(
                condition=models.Q(("asset_tag", ""), _negated=True),
                fields=("company", "asset_tag"),
                name="uniq_outillage_asset_tag_per_company",
            ),
        ),
    ]
