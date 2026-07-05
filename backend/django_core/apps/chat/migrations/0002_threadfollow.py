import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ThreadFollow",
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
                ("last_read_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "root_message",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="thread_followers",
                        to="chat.message",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chat_thread_follows",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Suivi de fil",
                "verbose_name_plural": "Suivis de fil",
                "ordering": ["id"],
            },
        ),
        migrations.AddIndex(
            model_name="threadfollow",
            index=models.Index(
                fields=["user", "root_message"], name="chat_threadfollow_user_idx"
            ),
        ),
        migrations.AlterUniqueTogether(
            name="threadfollow",
            unique_together={("root_message", "user")},
        ),
    ]
