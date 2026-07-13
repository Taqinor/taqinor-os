import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accessreview", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="SodRule",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name="ID"),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("permission_a", models.CharField(max_length=100)),
                ("permission_b", models.CharField(max_length=100)),
                (
                    "severite",
                    models.CharField(
                        choices=[("info", "Information"),
                                 ("warning", "Avertissement"),
                                 ("critique", "Critique")],
                        default="warning", max_length=10),
                ),
                ("libelle", models.CharField(
                    blank=True, default="", max_length=200)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="%(app_label)s_%(class)s_set",
                        to="authentication.company",
                        verbose_name="Société"),
                ),
            ],
            options={
                "verbose_name": "Règle SoD",
                "verbose_name_plural": "Règles SoD",
            },
        ),
        migrations.AddConstraint(
            model_name="sodrule",
            constraint=models.UniqueConstraint(
                fields=("company", "permission_a", "permission_b"),
                name="uniq_sodrule_par_societe_paire"),
        ),
    ]
