"""RPDF (fondateur 27/10/2026) — garanties réelles au Maroc, sans « selon ».

Plainte fondateur sur le PDF résidentiel : « pourquoi tu parles de garantie
selon site… on travaille au Maroc… c'est stupide de montrer qu'on ne sait pas
au client, même chose pour la batterie ». Le PDF imprimait page 2 « Garantie
constructeur 5 à 10 ans (selon site d'installation) » et page 3 la tuile
« Onduleur 10 ans » (``garantie_mois`` = 120 posé par 0124).

1) ONDULEURS DEYE — 5 ans (décision fondateur du 27/10 : « 5 ans »). Source :
   Deye, « Deye Inverter Warranty Terms and Conditions » v1.7
   (deyeinverter.com) : toutes régions hors Chine continentale, « The
   warranty period is 5 Years (10 Years Optional) » — les 10 ans « for
   Installation in Europe » ne couvrent que l'Europe, l'option payante n'est
   pas achetée. Texte libre ET ``garantie_mois`` (120 → 60), pour que la
   page 2 et la tuile de la page 3 disent la même chose.
2) BATTERIE DYNESS DL5.0C (BAT-DEY-5/10) — 10 ans, sans la réserve
   « variante régionale : 7 ans » : le document officiel Dyness version
   Afrique donne 10 ans ; ``garantie_mois`` reste 120.

Le seeder ne réécrit jamais une valeur déjà saisie (ASTK176) : cette
migration ne touche QUE les produits qui portent encore EXACTEMENT l'ancienne
valeur semée — une garantie saisie par le fondateur reste à lui.
"""
from django.db import migrations

_ONDULEURS_DEYE_SKUS = (
    'OND-H-DEY-5M', 'OND-H-DEY-10M', 'OND-H-DEY-10T',
    'OND-H-DEY-15T', 'OND-H-DEY-20T',
    'OND-DEY-15K-LV', 'OND-DEY-20K-LV',
)
_DYNESS_SKUS = ('BAT-DEY-5', 'BAT-DEY-10')

ANCIEN_TEXTE_DEYE = "Garantie constructeur 5 à 10 ans (selon site d'installation)"
NOUVEAU_TEXTE_DEYE = 'Garantie constructeur 5 ans'
ANCIEN_TEXTE_DYNESS = 'Garantie 10 ans (variante régionale : 7 ans) · ≥ 6 000 cycles'
NOUVEAU_TEXTE_DYNESS = 'Garantie constructeur 10 ans · ≥ 6 000 cycles'


def _appliquer(apps, textes_deye, mois_deye, textes_dyness):
    """Quelques dizaines de lignes au plus (SKU semés × sociétés) : parcours
    par ``.iterator()`` et sauvegarde ciblée, jamais un update global."""
    Produit = apps.get_model('stock', 'Produit')
    avant_deye, apres_deye = textes_deye
    mois_avant, mois_apres = mois_deye
    for p in Produit.objects.filter(sku__in=_ONDULEURS_DEYE_SKUS).iterator():
        champs = []
        if p.garantie == avant_deye:
            p.garantie = apres_deye
            champs.append('garantie')
        if p.garantie_mois == mois_avant:
            p.garantie_mois = mois_apres
            champs.append('garantie_mois')
        if champs:
            p.save(update_fields=champs)
    avant_dyness, apres_dyness = textes_dyness
    for p in Produit.objects.filter(
            sku__in=_DYNESS_SKUS, garantie=avant_dyness).iterator():
        p.garantie = apres_dyness
        p.save(update_fields=['garantie'])


def corriger(apps, schema_editor):
    _appliquer(apps, (ANCIEN_TEXTE_DEYE, NOUVEAU_TEXTE_DEYE), (120, 60),
               (ANCIEN_TEXTE_DYNESS, NOUVEAU_TEXTE_DYNESS))


def retablir(apps, schema_editor):
    _appliquer(apps, (NOUVEAU_TEXTE_DEYE, ANCIEN_TEXTE_DEYE), (60, 120),
               (NOUVEAU_TEXTE_DYNESS, ANCIEN_TEXTE_DYNESS))


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0173_merge_20261023_2327'),
    ]

    operations = [
        migrations.RunPython(corriger, retablir),
    ]
