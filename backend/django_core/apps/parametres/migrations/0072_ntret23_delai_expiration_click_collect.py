# NTRET23 — Click & Collect (XPOS15) : délai de libération automatique d'une
# réservation jamais retirée, configurable dans Paramètres POS (onglet Point
# de vente). Additif — NULL/0 = désactivé, comportement historique inchangé.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parametres", "0071_merge_20260814_0356"),
    ]

    operations = [
        migrations.AddField(
            model_name="parametrespos",
            name="delai_expiration_click_collect_jours",
            field=models.PositiveSmallIntegerField(
                blank=True, null=True,
                help_text="Click & Collect : délai (jours) avant libération "
                          "automatique d'une réservation non retirée. "
                          "Vide/0 = désactivé."),
        ),
    ]
