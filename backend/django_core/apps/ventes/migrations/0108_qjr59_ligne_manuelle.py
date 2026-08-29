"""QJR59 (audit L3 du 29/08/2026, décision fondateur D12) — une ligne de devis
SAIT enfin ce que le commercial a tapé à la main.

LE TROU QUE CECI FERME. ``LigneDevis`` ne portait AUCUN marqueur de saisie
manuelle (champs vérifiés : devis, produit, designation, quantite,
prix_unitaire, remise, type_ligne, ordre, taux_tva, groupe_index, groupe_label,
optionnelle, variante, lot). La resynchro réécrivait donc librement les
quantités — panneaux, mètres de câble, structures/socles — pendant que le PRIX
tapé sur la MÊME ligne était, lui, sacré. Deux entrées commerciales, deux
traitements opposés.

DÉCISION FONDATEUR D12 : le commercial garde la main TOTALE sur les PRIX **et**
les QUANTITÉS des lignes — ce sont des ENTRÉES commerciales, désormais
PERSISTANTES (elles survivent à ``?edit=`` et à la resynchro).

Additive et réversible : DEUX booléens ``default=False`` en UNE migration.
Aucun backfill : chaque ligne existante porte ``False`` sur les deux, donc
AUCUN comportement ne change sur les données actuelles — c'est le repli
``services._est_au_prix_catalogue`` qui continue de décider pour elles (le
supprimer traiterait rétroactivement des MILLIERS de prix négociés comme des
prix catalogue).

Aucun écrivain de resynchro n'est branché ici (QJR60).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0107_qjr58_devis_overrides'),
    ]

    operations = [
        migrations.AddField(
            model_name='lignedevis',
            name='quantite_manuelle',
            field=models.BooleanField(
                default=False,
                help_text="La quantité de cette ligne a été TAPÉE par le "
                          "commercial : la resynchro du calepinage ne la "
                          "réécrit plus (décision fondateur D12).",
                verbose_name='Quantité saisie à la main',
            ),
        ),
        migrations.AddField(
            model_name='lignedevis',
            name='prix_manuel',
            field=models.BooleanField(
                default=False,
                help_text="Le prix unitaire de cette ligne a été TAPÉ par le "
                          "commercial : aucun rafraîchissement tarifaire ne "
                          "l'écrase (décision fondateur D12).",
                verbose_name='Prix saisi à la main',
            ),
        ),
    ]
