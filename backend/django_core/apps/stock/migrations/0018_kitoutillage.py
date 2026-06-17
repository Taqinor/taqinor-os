import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0008_customuser_avatar_key_customuser_poste"),
        ("stock", "0017_outillage"),
    ]

    operations = [
        migrations.CreateModel(
            name="KitOutillage",
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
                ("nom", models.CharField(max_length=120)),
                ("type_intervention", models.CharField(blank=True, default="", max_length=40)),
                ("ordre", models.PositiveIntegerField(default=0)),
                ("actif", models.BooleanField(default=True)),
                ("protege", models.BooleanField(default=False)),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                (
                    "company",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="kits_outillage",
                        to="authentication.company",
                    ),
                ),
            ],
            options={
                "verbose_name": "Kit d'outillage",
                "verbose_name_plural": "Kits d'outillage",
                "ordering": ["ordre", "nom"],
            },
        ),
        migrations.CreateModel(
            name="KitOutillageItem",
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
                ("ordre", models.PositiveIntegerField(default=0)),
                (
                    "kit",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="stock.kitoutillage",
                    ),
                ),
                (
                    "outil",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="kit_items",
                        to="stock.outillage",
                    ),
                ),
            ],
            options={
                "verbose_name": "Outil du kit",
                "verbose_name_plural": "Outils du kit",
                "ordering": ["ordre", "id"],
                "unique_together": {("kit", "outil")},
            },
        ),
    ]
