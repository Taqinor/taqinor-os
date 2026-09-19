# NTP2P35 (complément stock) — seuil de purge des demandes d'achat restées
# BROUILLON, configurable par société. Additive : une colonne nouvelle avec
# défaut, aucune donnée touchée. `0` = « utiliser le défaut (90 jours) », donc
# toutes les sociétés existantes gardent exactement le comportement actuel.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0150_ntprt22_annonce_livraison_fournisseur'),
    ]

    operations = [
        migrations.AddField(
            model_name='achatsparametres',
            name='purge_brouillon_jours',
            field=models.PositiveIntegerField(
                default=0,
                help_text="NTP2P35 — ancienneté en jours au-delà de laquelle "
                          "une demande d'achat restée brouillon est purgée. "
                          '0 = utiliser le défaut (90 jours).'),
        ),
    ]
