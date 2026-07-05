# YHARD4 — traduction du contenu saisi (données maîtres), générique.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("authentication", "0014_customuser_account_lockout"),
        ("core", "0023_yhard5_secret_rotation"),
    ]

    operations = [
        migrations.CreateModel(
            name="ContentTranslation",
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
                ("object_id", models.CharField(max_length=64)),
                (
                    "locale",
                    models.CharField(
                        choices=[("fr", "Français"), ("en", "English"), ("ar", "العربية")],
                        max_length=5,
                        verbose_name="Langue",
                    ),
                ),
                ("field", models.CharField(max_length=100, verbose_name="Champ")),
                ("value", models.TextField(verbose_name="Valeur traduite")),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="content_translations",
                        to="authentication.company",
                        verbose_name="Société",
                    ),
                ),
                (
                    "content_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="contenttypes.contenttype",
                    ),
                ),
            ],
            options={
                "verbose_name": "Traduction de contenu",
                "verbose_name_plural": "Traductions de contenu",
            },
        ),
        migrations.AddIndex(
            model_name="contenttranslation",
            index=models.Index(
                fields=["company", "content_type", "object_id"],
                name="core_contenttrans_obj_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="contenttranslation",
            constraint=models.UniqueConstraint(
                fields=("company", "content_type", "object_id", "locale", "field"),
                name="core_contenttranslation_unique",
            ),
        ),
    ]
