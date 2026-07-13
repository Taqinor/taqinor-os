from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0059_odx13_partenaires_split"),
    ]

    operations = [
        migrations.CreateModel(
            name="LeadActivityArchive",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name="ID"),
                ),
                (
                    "original_id",
                    models.BigIntegerField(
                        help_text="PK de la LeadActivity d'origine "
                                  "(table vive)."),
                ),
                ("company_id", models.BigIntegerField(blank=True, null=True)),
                ("lead_id", models.BigIntegerField(blank=True, null=True)),
                ("kind", models.CharField(max_length=15)),
                ("field", models.CharField(
                    blank=True, max_length=100, null=True)),
                ("field_label", models.CharField(
                    blank=True, max_length=150, null=True)),
                ("old_value", models.TextField(blank=True, null=True)),
                ("new_value", models.TextField(blank=True, null=True)),
                ("body", models.TextField(blank=True, null=True)),
                ("outcome", models.CharField(
                    blank=True, default="", max_length=20)),
                ("attachment_id", models.BigIntegerField(
                    blank=True, null=True)),
                ("bulk", models.BooleanField(default=False)),
                ("user_id", models.BigIntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField()),
                ("archived_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Activité lead (archive)",
                "verbose_name_plural": "Activités lead (archive)",
            },
        ),
    ]
