# NTPAY13 — Devise du run de paie et du bulletin (préparation multi-pays).
#
# Un pays non-MA paie dans SA monnaie. `PeriodePaie.devise` et
# `BulletinPaie.devise` portent désormais ce code ISO 4217 ; l'ordre de
# virement (qui avait déjà son champ `devise` depuis 0018) en hérite.
#
# RÉTRO-COMPATIBILITÉ STRICTE : défaut `MAD` sur les deux champs, donc toutes
# les périodes et tous les bulletins existants restent marocains au centime
# près. Aucune conversion de change n'est jamais faite — chaque pays reste
# dans sa propre monnaie.
#
# Migration ADDITIVE (deux CharField avec défaut) : aucune donnée réécrite.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('paie', '0051_ntpay8_baremes_par_pays'),
    ]

    operations = [
        migrations.AddField(
            model_name='periodepaie',
            name='devise',
            field=models.CharField(
                default='MAD', max_length=3, verbose_name='Devise'),
        ),
        migrations.AddField(
            model_name='bulletinpaie',
            name='devise',
            field=models.CharField(
                default='MAD', max_length=3, verbose_name='Devise'),
        ),
    ]
