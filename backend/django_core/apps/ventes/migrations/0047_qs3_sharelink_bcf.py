# QS3 — ShareLink → stock.BonCommandeFournisseur (lien tokenisé vers le PDF du
# bon de commande FOURNISSEUR). Additif/nullable : les liens existants
# (devis/facture) sont inchangés. String-FK (ventes → stock).
#
# La dépendance ventes 0046_qj29_multivilla est créée par la lane « quote
# engine » et existera au fold ; on chaîne dessus (pas sur 0045) pour éviter une
# collision de migrations dans la même app.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ventes", "0046_qj29_multivilla"),
        ("stock", "0027_fichetechnique"),
    ]

    operations = [
        migrations.AddField(
            model_name="sharelink",
            name="bon_commande_fournisseur",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="share_links",
                to="stock.boncommandefournisseur",
            ),
        ),
    ]
