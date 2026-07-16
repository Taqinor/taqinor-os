import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0020_company_benchmarking_opt_in"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("core", "0036_yapic9_idempotencyrecord"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SharingRule",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name="ID"),
                ),
                ("object_id", models.CharField(max_length=64)),
                (
                    "principal_type",
                    models.CharField(
                        choices=[("user", "Utilisateur"), ("role", "Rôle"),
                                 ("team", "Équipe")],
                        max_length=8),
                ),
                ("principal_id", models.CharField(max_length=64)),
                (
                    "niveau",
                    models.CharField(
                        choices=[("lecture", "Lecture"),
                                 ("ecriture", "Écriture")],
                        default="lecture", max_length=8),
                ),
                ("expire_le", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "accorde_par",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="sharing_rules_accordees",
                        to=settings.AUTH_USER_MODEL),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sharing_rules",
                        to="authentication.company",
                        verbose_name="Société"),
                ),
                (
                    "content_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="contenttypes.contenttype"),
                ),
            ],
            options={
                "verbose_name": "Règle de partage",
                "verbose_name_plural": "Règles de partage",
            },
        ),
        migrations.AddIndex(
            model_name="sharingrule",
            index=models.Index(
                fields=["company", "content_type", "object_id"],
                name="core_sharin_company_ct_obj_idx"),
        ),
        migrations.AddIndex(
            model_name="sharingrule",
            index=models.Index(
                fields=["principal_type", "principal_id"],
                name="core_sharin_principal_idx"),
        ),
    ]
