import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0012_customuser_must_change_password_and_more"),
        ("chat", "0003_notification_level"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="UserChatStatus",
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
                    "status_text",
                    models.CharField(blank=True, default="", max_length=120),
                ),
                (
                    "status_emoji",
                    models.CharField(blank=True, default="", max_length=16),
                ),
                ("dnd_start", models.DateTimeField(blank=True, null=True)),
                ("dnd_end", models.DateTimeField(blank=True, null=True)),
                ("last_seen_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chat_user_statuses",
                        to="authentication.company",
                    ),
                ),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chat_status",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Statut de discussion",
                "verbose_name_plural": "Statuts de discussion",
                "ordering": ["id"],
            },
        ),
        migrations.AddIndex(
            model_name="userchatstatus",
            index=models.Index(
                fields=["company", "user"], name="chat_userchatstatus_co_idx"
            ),
        ),
    ]
