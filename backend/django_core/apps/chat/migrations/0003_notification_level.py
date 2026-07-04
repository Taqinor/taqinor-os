from django.db import migrations, models


def backfill_notification_level(apps, schema_editor):
    """Préserve l'existant : un membre déjà en sourdine (`is_muted=True`)
    obtient le niveau `muted` ; les autres restent `all` (défaut)."""
    ConversationMember = apps.get_model("chat", "ConversationMember")
    ConversationMember.objects.filter(is_muted=True).update(
        notification_level="muted")


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0002_threadfollow"),
    ]

    operations = [
        migrations.AddField(
            model_name="conversationmember",
            name="notification_level",
            field=models.CharField(
                choices=[
                    ("all", "Tout"),
                    ("mentions", "Mentions seulement"),
                    ("muted", "Muet"),
                ],
                default="all",
                max_length=10,
            ),
        ),
        migrations.RunPython(backfill_notification_level, noop_reverse),
    ]
