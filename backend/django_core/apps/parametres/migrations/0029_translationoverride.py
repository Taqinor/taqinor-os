# N94 — surcharges de traduction de l'interface (par société/langue/clé).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0010_customuser_supervisor"),
        ("parametres", "0028_companyprofile_audit_retention_days"),
    ]

    operations = [
        migrations.CreateModel(
            name="TranslationOverride",
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
                    "locale",
                    models.CharField(
                        choices=[
                            ("fr", "Français"),
                            ("en", "English"),
                            ("ar", "العربية"),
                        ],
                        max_length=5,
                    ),
                ),
                ("key", models.CharField(max_length=120)),
                ("value", models.TextField(blank=True, default="")),
                ("date_creation", models.DateTimeField(auto_now_add=True)),
                ("date_modification", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="translation_overrides",
                        to="authentication.company",
                    ),
                ),
            ],
            options={
                "verbose_name": "Surcharge de traduction",
                "verbose_name_plural": "Surcharges de traduction",
                "ordering": ["locale", "key"],
                "unique_together": {("company", "locale", "key")},
            },
        ),
    ]
