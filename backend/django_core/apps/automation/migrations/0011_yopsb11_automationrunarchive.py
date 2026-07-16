from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("automation", "0010_alter_automationrule_trigger_type"),
    ]

    operations = [
        migrations.CreateModel(
            name="AutomationRunArchive",
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
                        help_text="PK de l'AutomationRun d'origine "
                                  "(table vive)."),
                ),
                ("company_id", models.BigIntegerField(blank=True, null=True)),
                ("rule_id", models.BigIntegerField(blank=True, null=True)),
                ("target_model", models.CharField(
                    blank=True, default="", max_length=120)),
                ("target_id", models.PositiveIntegerField(
                    blank=True, null=True)),
                ("status", models.CharField(max_length=20)),
                ("message", models.TextField(blank=True, default="")),
                ("timestamp", models.DateTimeField()),
                ("archived_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Exécution d'automatisation (archive)",
                "verbose_name_plural": "Exécutions d'automatisation (archive)",
            },
        ),
    ]
