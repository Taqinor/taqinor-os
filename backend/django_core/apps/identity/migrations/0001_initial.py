import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("authentication", "0020_company_benchmarking_opt_in"),
    ]

    operations = [
        migrations.CreateModel(
            name="NetworkPolicy",
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
                    "mode",
                    models.CharField(
                        choices=[
                            ("off", "Inactif"),
                            ("monitor", "Surveillance"),
                            ("enforce", "Application"),
                        ],
                        default="off",
                        max_length=10,
                        verbose_name="Mode",
                    ),
                ),
                (
                    "applies_to",
                    models.CharField(
                        choices=[
                            ("all", "Tous les utilisateurs"),
                            ("admins", "Administrateurs seulement"),
                        ],
                        default="all",
                        max_length=10,
                        verbose_name="Périmètre",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="%(app_label)s_%(class)s_set",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
            ],
            options={
                "verbose_name": "Politique réseau",
                "verbose_name_plural": "Politiques réseau",
            },
        ),
        migrations.CreateModel(
            name="IpAllowRule",
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
                    "cidr",
                    models.CharField(
                        help_text="Ex. 192.168.1.0/24 ou 41.92.0.10/32.",
                        max_length=64,
                        verbose_name="Plage CIDR",
                    ),
                ),
                (
                    "label",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=120,
                        verbose_name="Libellé",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="%(app_label)s_%(class)s_set",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "policy",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="rules",
                        to="identity.networkpolicy",
                        verbose_name="Politique",
                    ),
                ),
            ],
            options={
                "verbose_name": "Règle IP autorisée",
                "verbose_name_plural": "Règles IP autorisées",
            },
        ),
        migrations.AddConstraint(
            model_name="networkpolicy",
            constraint=models.UniqueConstraint(
                fields=("company",), name="uniq_networkpolicy_par_societe"
            ),
        ),
    ]
