# NTRET31 — Écran client (customer-facing display) : snapshot best-effort du
# panier en cours de la session, lu en polling léger par l'écran dédié.
# Additif — NULL = comportement historique inchangé (aucun panier affichable).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pos", "0009_ntret29_prix_par_emplacement"),
    ]

    operations = [
        migrations.AddField(
            model_name="sessioncaisse",
            name="panier_courant",
            field=models.JSONField(blank=True, default=None, null=True),
        ),
        migrations.AddField(
            model_name="sessioncaisse",
            name="panier_maj_le",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
