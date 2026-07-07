# XMKT19 - actions CRM dans les etapes de sequence : type_etape
# (message/action_crm) + config JSON de l'action CRM. Additif : defaut
# 'message' + JSON vide = comportement actuel (etape = envoi de message).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compta", "0084_xmkt18_branches_engagement_sequence"),
    ]

    operations = [
        migrations.AddField(
            model_name="etapesequence",
            name="type_etape",
            field=models.CharField(
                choices=[
                    ("message", "Message (canal)"),
                    ("action_crm", "Action CRM"),
                ],
                default="message", max_length=12,
                verbose_name="Type d'étape"),
        ),
        migrations.AddField(
            model_name="etapesequence",
            name="action_crm",
            field=models.JSONField(
                blank=True, default=dict, verbose_name="Action CRM (JSON)"),
        ),
    ]
