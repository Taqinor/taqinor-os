import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0020_company_benchmarking_opt_in"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("core", "0037_ntsec21_sharingrule"),
    ]

    operations = [
        migrations.CreateModel(
            name="FieldPermissionRule",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name="ID"),
                ),
                ("field_name", models.CharField(max_length=100)),
                ("role_id", models.CharField(max_length=64)),
                (
                    "acces",
                    models.CharField(
                        choices=[("masque", "Masqué"),
                                 ("lecture", "Lecture seule"),
                                 ("ecriture", "Écriture")],
                        default="lecture", max_length=8),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="field_permission_rules",
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
                "verbose_name": "Règle de permission champ",
                "verbose_name_plural": "Règles de permission champ",
            },
        ),
        migrations.AddConstraint(
            model_name="fieldpermissionrule",
            constraint=models.UniqueConstraint(
                fields=("company", "content_type", "field_name", "role_id"),
                name="uniq_fieldperm_par_societe_modele_champ_role"),
        ),
        migrations.AddIndex(
            model_name="fieldpermissionrule",
            index=models.Index(
                fields=["company", "content_type", "role_id"],
                name="core_fieldperm_comp_role_idx"),
        ),
    ]
