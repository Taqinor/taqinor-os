# XSTK8 — contrôle du stock négatif (garde configurable). Additif : flag
# société sur AchatsParametres (défaut False = garde ACTIF, comportement
# nouveau mais sûr) posé à côté des autres réglages achats/stock déjà
# accumulés sur ce modèle (XPUR1/XPUR2/XPUR10/XPUR13/XSTK6) plutôt que sur
# `apps.parametres` (foundation app hors périmètre de ce lot stock).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0055_xstk6_lot_entrepot"),
    ]

    operations = [
        migrations.AddField(
            model_name="achatsparametres",
            name="stock_negatif_autorise",
            field=models.BooleanField(default=False),
        ),
    ]
