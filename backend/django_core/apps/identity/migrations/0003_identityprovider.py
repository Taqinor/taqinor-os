import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0020_company_benchmarking_opt_in"),
        ("identity", "0002_trusteddevice"),
    ]

    operations = [
        migrations.CreateModel(
            name="IdentityProvider",
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
                (
                    "protocol",
                    models.CharField(
                        choices=[("saml", "SAML 2.0"), ("oidc", "OpenID Connect")],
                        max_length=8,
                        verbose_name="Protocole",
                    ),
                ),
                ("nom", models.CharField(max_length=120, verbose_name="Nom")),
                ("actif", models.BooleanField(default=False, verbose_name="Actif")),
                (
                    "metadata_url",
                    models.URLField(blank=True, default="", max_length=500),
                ),
                ("metadata_xml", models.TextField(blank=True, default="")),
                (
                    "entity_id",
                    models.CharField(blank=True, default="", max_length=500),
                ),
                (
                    "sso_url",
                    models.URLField(blank=True, default="", max_length=500),
                ),
                ("x509_cert", models.TextField(blank=True, default="")),
                ("attribute_map", models.JSONField(blank=True, default=dict)),
                ("auto_provision", models.BooleanField(default=False)),
                (
                    "default_role_id",
                    models.CharField(blank=True, default="", max_length=64),
                ),
                ("enforce_sso", models.BooleanField(default=False)),
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
                "verbose_name": "Fournisseur d'identité",
                "verbose_name_plural": "Fournisseurs d'identité",
            },
        ),
        migrations.AddConstraint(
            model_name="identityprovider",
            constraint=models.UniqueConstraint(
                condition=models.Q(("actif", True)),
                fields=("company", "protocol"),
                name="uniq_idp_actif_par_societe_protocole",
            ),
        ),
    ]
