import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("identity", "0005_scimgroupmapping"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="BreakGlassGrant",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name="ID"),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("motif", models.TextField()),
                ("active_jusqu_a", models.DateTimeField()),
                ("revoque_le", models.DateTimeField(blank=True, null=True)),
                ("role_legacy_avant", models.CharField(
                    blank=True, default="", max_length=32)),
                ("role_id_avant", models.CharField(
                    blank=True, default="", max_length=64)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="%(app_label)s_%(class)s_set",
                        to="authentication.company",
                        verbose_name="Société"),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="break_glass_grants",
                        to=settings.AUTH_USER_MODEL),
                ),
                (
                    "accorde_par",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="break_glass_accordes",
                        to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={
                "verbose_name": "Accès break-glass",
                "verbose_name_plural": "Accès break-glass",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="breakglassgrant",
            index=models.Index(
                fields=["company", "user", "revoque_le"],
                name="identity_bg_company_user_idx"),
        ),
    ]
