# XMKT11 - variantes de contenu par langue (fr/ar/darija) sur Campagne.
# Additif : JSON vide par defaut = comportement actuel (un seul corps FR).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compta", "0080_xmkt9_lientrackee_cliclien"),
    ]

    operations = [
        migrations.AddField(
            model_name="campagne",
            name="variantes_langue",
            field=models.JSONField(
                blank=True, default=dict,
                verbose_name="Variantes de contenu par langue (JSON)"),
        ),
    ]
