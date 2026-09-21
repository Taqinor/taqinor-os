"""SOLMVP — coquille de migrations de l'app « chat ».

Migration d'ÉTAT SEUL générée par ``manage.py parquer_app chat`` :
``database_operations=[]`` — AUCUNE table supprimée, AUCUNE ligne de
``django_migrations`` touchée. Les modèles sortent seulement de l'état
Django ; les données restent intégralement en base.

Retour du module : ``manage.py migrate chat 0010_rename_chat_canned_co_scope_idx_chat_canned_company_83cb34_idx_and_more`` (renverse cet état),
puis suppression de ce fichier — docs/parked-modules.md §5.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0010_rename_chat_canned_co_scope_idx_chat_canned_company_83cb34_idx_and_more'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='CannedResponse'),
                migrations.DeleteModel(name='ConversationMember'),
                migrations.DeleteModel(name='MessageAttachment'),
                migrations.DeleteModel(name='MessageBookmark'),
                migrations.DeleteModel(name='MessageMention'),
                migrations.DeleteModel(name='MessageReaction'),
                migrations.DeleteModel(name='MessageReminder'),
                migrations.DeleteModel(name='PollVote'),
                migrations.DeleteModel(name='RetentionPolicy'),
                migrations.DeleteModel(name='RetentionSweepRun'),
                migrations.DeleteModel(name='ScheduledMessage'),
                migrations.DeleteModel(name='ThreadFollow'),
                migrations.DeleteModel(name='UserChatStatus'),
                migrations.DeleteModel(name='PollOption'),
                migrations.DeleteModel(name='Poll'),
                migrations.DeleteModel(name='Message'),
                migrations.DeleteModel(name='Conversation'),
            ],
            database_operations=[],
        ),
    ]
