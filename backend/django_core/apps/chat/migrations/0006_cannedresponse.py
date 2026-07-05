import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0012_customuser_must_change_password_and_more"),
        ("chat", "0005_scheduled_reminders_bookmarks"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CannedResponse",
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
                ("shortcut", models.CharField(max_length=64)),
                ("body", models.TextField()),
                (
                    "scope",
                    models.CharField(
                        choices=[
                            ("personal", "Personnel"),
                            ("company", "Société"),
                        ],
                        default="personal",
                        max_length=10,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chat_canned_responses",
                        to="authentication.company",
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chat_canned_responses",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Réponse enregistrée",
                "verbose_name_plural": "Réponses enregistrées",
                "ordering": ["shortcut"],
            },
        ),
        migrations.AddIndex(
            model_name="cannedresponse",
            index=models.Index(
                fields=["company", "scope"], name="chat_canned_co_scope_idx"
            ),
        ),
        migrations.AlterUniqueTogether(
            name="cannedresponse",
            unique_together={("company", "owner", "shortcut")},
        ),
    ]
