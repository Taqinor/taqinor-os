# XMKT18 - branches d'engagement dans les sequences : condition d'execution
# + action alternative sur EtapeSequence, branche prise trace sur
# ExecutionEtapeSequence. Additif : defaut 'toujours' + champs vides =
# comportement actuel (etape toujours executee, lineaire).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compta", "0083_xmkt17_cout_roi_campagne"),
    ]

    operations = [
        migrations.AddField(
            model_name="etapesequence",
            name="condition",
            field=models.CharField(
                choices=[
                    ("toujours", "Toujours"), ("a_ouvert", "A ouvert"),
                    ("a_clique", "A cliqué"),
                    ("n_a_pas_ouvert", "N'a pas ouvert"),
                    ("a_repondu", "A répondu (WhatsApp)"),
                ],
                default="toujours", max_length=20,
                verbose_name="Condition d'exécution"),
        ),
        migrations.AddField(
            model_name="etapesequence",
            name="action_alternative",
            field=models.CharField(
                blank=True, default="", max_length=30,
                verbose_name="Action alternative si condition fausse"),
        ),
        migrations.AddField(
            model_name="executionetapesequence",
            name="branche_prise",
            field=models.CharField(
                blank=True, default="", max_length=20,
                verbose_name="Branche prise (XMKT18)"),
        ),
    ]
