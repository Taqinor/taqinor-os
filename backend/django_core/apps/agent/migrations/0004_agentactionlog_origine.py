# Copilote vague 2 (FND7) — origine du journal des actions IA. Additive :
# toutes les lignes existantes valent « confirmee » (comportement d'avant).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("agent", "0003_assistantevent"),
    ]

    operations = [
        migrations.AddField(
            model_name="agentactionlog",
            name="origine",
            field=models.CharField(
                choices=[("confirmee", "Confirmée par l'utilisateur"),
                         ("interne", "Écriture interne de l'assistant")],
                default="confirmee", max_length=10, verbose_name="Origine"),
        ),
    ]
