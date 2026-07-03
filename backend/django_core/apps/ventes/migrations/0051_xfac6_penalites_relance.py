# XFAC6 — Pénalités & intérêts de retard par niveau de relance. Additif :
# deux champs nullable/défaut 0 sur FollowupLevel → comportement historique
# byte-identique tant qu'ils ne sont pas paramétrés.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ventes", "0050_xfac5_promesse_paiement"),
    ]

    operations = [
        migrations.AddField(
            model_name="followuplevel",
            name="taux_interet_annuel",
            field=models.DecimalField(
                blank=True, decimal_places=2, default=0, max_digits=5,
                null=True),
        ),
        migrations.AddField(
            model_name="followuplevel",
            name="frais_fixes",
            field=models.DecimalField(
                blank=True, decimal_places=2, default=0, max_digits=10,
                null=True),
        ),
    ]
