# XSTK13 — fix2: `InventaireAnnuel.donnees` (JSONField) manquait
# `encoder=DjangoJSONEncoder`, ce qui levait une TypeError (Decimal non
# serialisable en JSON) a chaque figement (`figer_inventaire_annuel` stocke
# des cout_moyen/valeur Decimal dans le snapshot). Pur changement d'etat
# Django (deconstruct() de JSONField) : aucune colonne/donnee modifiee.
from django.core.serializers.json import DjangoJSONEncoder
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0066_xctr1_produit_recurrent"),
    ]

    operations = [
        migrations.AlterField(
            model_name="inventaireannuel",
            name="donnees",
            field=models.JSONField(
                encoder=DjangoJSONEncoder,
                help_text="Snapshot complet et immuable de la valorisation."),
        ),
    ]
