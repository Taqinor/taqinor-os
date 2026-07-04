import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0006_cannedresponse"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="message",
            name="kind",
            field=models.CharField(
                choices=[
                    ("text", "Texte"),
                    ("voice", "Mémo vocal"),
                    ("system", "Système"),
                    ("record", "Enregistrement partagé"),
                    ("poll", "Sondage"),
                ],
                default="text",
                max_length=10,
            ),
        ),
        migrations.CreateModel(
            name="Poll",
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
                ("question", models.CharField(max_length=255)),
                ("allow_multiple", models.BooleanField(default=False)),
                ("is_anonymous", models.BooleanField(default=False)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "message",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="poll",
                        to="chat.message",
                    ),
                ),
            ],
            options={
                "verbose_name": "Sondage",
                "verbose_name_plural": "Sondages",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.CreateModel(
            name="PollOption",
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
                ("label", models.CharField(max_length=255)),
                ("order", models.PositiveIntegerField(default=0)),
                (
                    "poll",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="options",
                        to="chat.poll",
                    ),
                ),
            ],
            options={
                "verbose_name": "Option de sondage",
                "verbose_name_plural": "Options de sondage",
                "ordering": ["order", "id"],
            },
        ),
        migrations.CreateModel(
            name="PollVote",
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
                    "option",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="votes",
                        to="chat.polloption",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chat_poll_votes",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Vote de sondage",
                "verbose_name_plural": "Votes de sondage",
                "ordering": ["id"],
            },
        ),
        migrations.AddIndex(
            model_name="pollvote",
            index=models.Index(
                fields=["option", "user"], name="chat_pollvote_opt_user_idx"
            ),
        ),
        migrations.AlterUniqueTogether(
            name="pollvote",
            unique_together={("option", "user")},
        ),
    ]
