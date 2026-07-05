# XPOS9 — Capture n° de série à la vente comptoir -> équipement SAV garanti
# sans chantier. `installation` devient nullable (un équipement vendu au
# comptoir n'a pas d'Installation) et `client_vente` porte le lien client
# direct dans ce cas. Additif : toutes les lignes existantes ont déjà une
# `installation` renseignée -> aucun changement de comportement.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0001_initial'),
        ('installations', '0001_initial'),
        ('sav', '0028_xmfg10_pieceretiree'),
    ]

    operations = [
        migrations.AlterField(
            model_name='equipement',
            name='installation',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='equipements', to='installations.installation'),
        ),
        migrations.AddField(
            model_name='equipement',
            name='client_vente',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='equipements_vente_directe', to='crm.client'),
        ),
    ]
