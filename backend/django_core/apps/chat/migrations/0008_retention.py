import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0012_customuser_must_change_password_and_more"),
        ("chat", "0007_poll"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="RetentionPolicy",
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
                (
                    "conversation_kind",
                    models.CharField(
                        choices=[("dm", "Message direct"), ("channel", "Canal")],
                        max_length=10,
                    ),
                ),
                (
                    "retention_months",
                    models.PositiveIntegerField(blank=True, null=True),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chat_retention_policies",
                        to="authentication.company",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Politique de rétention (chat)",
                "verbose_name_plural": "Politiques de rétention (chat)",
                "ordering": ["conversation_kind"],
            },
        ),
        migrations.CreateModel(
            name="RetentionSweepRun",
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
                ("ran_at", models.DateTimeField(auto_now_add=True)),
                ("messages_purged", models.PositiveIntegerField(default=0)),
                ("detail", models.TextField(blank=True, default="")),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chat_retention_sweep_runs",
                        to="authentication.company",
                    ),
                ),
            ],
            options={
                "verbose_name": "Exécution de purge (chat)",
                "verbose_name_plural": "Exécutions de purge (chat)",
                "ordering": ["-ran_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="retentionsweeprun",
            index=models.Index(
                fields=["company", "ran_at"], name="chat_retention_run_co_idx"
            ),
        ),
        migrations.AlterUniqueTogether(
            name="retentionpolicy",
            unique_together={("company", "conversation_kind")},
        ),
    ]
