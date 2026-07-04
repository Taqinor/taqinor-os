# XPUR23 — Destination de réception : dépôt/emplacement cible ou chantier
# (livraison directe). Additif : vide des deux côtés = comportement
# historique (l'entrée crédite le dépôt principal, dérivé implicitement).
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0050_xpur22_portail_fournisseur_token"),
        ("installations", "0062_xmfg14_gamme_etapes"),
    ]

    operations = [
        migrations.AddField(
            model_name="boncommandefournisseur",
            name="emplacement_destination",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="bons_commande_destination",
                to="stock.emplacementstock"),
        ),
        migrations.AddField(
            model_name="boncommandefournisseur",
            name="chantier_livraison",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="bons_commande_livraison_directe",
                to="installations.installation"),
        ),
    ]
