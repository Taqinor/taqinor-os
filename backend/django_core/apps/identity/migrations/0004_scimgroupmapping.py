import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("identity", "0003_scimtoken"),
    ]

    operations = [
        migrations.CreateModel(
            name="ScimGroupMapping",
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
                    "scim_group_name",
                    models.CharField(max_length=200, verbose_name="Groupe SCIM"),
                ),
                (
                    "role_id",
                    models.CharField(max_length=64, verbose_name="Rôle (id)"),
                ),
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
                "verbose_name": "Mapping groupe SCIM",
                "verbose_name_plural": "Mappings groupes SCIM",
            },
        ),
        migrations.AddConstraint(
            model_name="scimgroupmapping",
            constraint=models.UniqueConstraint(
                fields=("company", "scim_group_name"),
                name="uniq_scimgroup_par_societe",
            ),
        ),
    ]
