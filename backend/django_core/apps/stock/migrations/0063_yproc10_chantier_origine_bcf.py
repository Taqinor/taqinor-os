# YPROC10 — chantier D'ORIGINE du besoin matériel sur le BCF (distinct de
# chantier_livraison/XPUR23, qui trace la LIVRAISON). Additif : vide =
# comportement historique (stock libre à la réception).
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0062_xstk15_unites_conditionnements"),
        ("installations", "0077_yserv6_intervention_annulee"),
    ]

    operations = [
        migrations.AddField(
            model_name="boncommandefournisseur",
            name="chantier_origine",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="bons_commande_besoin_origine",
                to="installations.installation"),
        ),
    ]
