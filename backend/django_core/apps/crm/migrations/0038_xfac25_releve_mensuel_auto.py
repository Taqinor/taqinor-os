# XFAC25 — Envoi programmé des relevés de compte clients (mensuel, opt-in).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crm", "0037_xmkt37_chatsessionpublique"),
    ]

    operations = [
        migrations.AddField(
            model_name="client",
            name="releve_mensuel_auto",
            field=models.BooleanField(
                default=False,
                verbose_name="Envoi mensuel automatique du relevé",
                help_text="Envoie automatiquement le relevé de compte PDF "
                          "le 1er du mois si l'encours n'est pas nul. "
                          "Désactivé par défaut."),
        ),
    ]
