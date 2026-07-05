import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0012_customuser_must_change_password_and_more"),
        ("chat", "0004_userchatstatus"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ScheduledMessage",
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
                ("body", models.TextField(blank=True, default="")),
                ("scheduled_at", models.DateTimeField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "En attente"),
                            ("sent", "Envoyé"),
                            ("cancelled", "Annulé"),
                            ("failed", "Échec"),
                        ],
                        default="pending",
                        max_length=10,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chat_scheduled_messages",
                        to="authentication.company",
                    ),
                ),
                (
                    "conversation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="scheduled_messages",
                        to="chat.conversation",
                    ),
                ),
                (
                    "sender",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chat_scheduled_messages",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "sent_message",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="chat.message",
                    ),
                ),
            ],
            options={
                "verbose_name": "Message programmé",
                "verbose_name_plural": "Messages programmés",
                "ordering": ["scheduled_at", "id"],
            },
        ),
        migrations.CreateModel(
            name="MessageReminder",
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
                ("remind_at", models.DateTimeField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "En attente"),
                            ("sent", "Envoyé"),
                            ("cancelled", "Annulé"),
                        ],
                        default="pending",
                        max_length=10,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "message",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reminders",
                        to="chat.message",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chat_message_reminders",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Rappel de message",
                "verbose_name_plural": "Rappels de message",
                "ordering": ["remind_at", "id"],
            },
        ),
        migrations.CreateModel(
            name="MessageBookmark",
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
                (
                    "message",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="bookmarks",
                        to="chat.message",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chat_bookmarks",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Signet de message",
                "verbose_name_plural": "Signets de message",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="scheduledmessage",
            index=models.Index(
                fields=["status", "scheduled_at"], name="chat_schedmsg_status_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="scheduledmessage",
            index=models.Index(
                fields=["company", "sender"], name="chat_schedmsg_co_sender_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="messagereminder",
            index=models.Index(
                fields=["status", "remind_at"], name="chat_reminder_status_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="messagereminder",
            index=models.Index(
                fields=["user", "message"], name="chat_reminder_user_msg_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="messagebookmark",
            index=models.Index(
                fields=["user", "message"], name="chat_bookmark_user_msg_idx"
            ),
        ),
        migrations.AlterUniqueTogether(
            name="messagebookmark",
            unique_together={("message", "user")},
        ),
    ]
