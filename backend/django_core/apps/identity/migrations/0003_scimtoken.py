import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("identity", "0002_identityprovider"),
    ]

    operations = [
        migrations.CreateModel(
            name="ScimToken",
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
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("label", models.CharField(blank=True, default="", max_length=120)),
                (
                    "token_hash",
                    models.CharField(db_index=True, max_length=64, unique=True),
                ),
                ("prefix", models.CharField(blank=True, default="", max_length=20)),
                ("actif", models.BooleanField(default=True)),
                ("last_used_at", models.DateTimeField(blank=True, null=True)),
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
                "verbose_name": "Jeton SCIM",
                "verbose_name_plural": "Jetons SCIM",
            },
        ),
        migrations.AddIndex(
            model_name="scimtoken",
            index=models.Index(
                fields=["company", "actif"], name="identity_sc_company_actif_idx"
            ),
        ),
    ]
