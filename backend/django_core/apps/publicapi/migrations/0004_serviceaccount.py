import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0020_company_benchmarking_opt_in"),
        ("publicapi", "0003_rename_publicapi_i_company_53dd3b_idx_publicapi_i_company_033314_idx"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ServiceAccount",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name="ID"),
                ),
                ("nom", models.CharField(max_length=120)),
                ("scopes", models.JSONField(blank=True, default=list)),
                (
                    "token_hash",
                    models.CharField(db_index=True, max_length=64, unique=True),
                ),
                ("prefix", models.CharField(
                    blank=True, default="", max_length=20)),
                ("actif", models.BooleanField(default=True)),
                ("expire_le", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_used_at", models.DateTimeField(blank=True, null=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="service_accounts_crees",
                        to=settings.AUTH_USER_MODEL),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="service_accounts",
                        to="authentication.company"),
                ),
            ],
            options={
                "verbose_name": "Compte de service",
                "verbose_name_plural": "Comptes de service",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="serviceaccount",
            index=models.Index(
                fields=["company", "actif"],
                name="publicapi_svc_comp_actif_idx"),
        ),
    ]
