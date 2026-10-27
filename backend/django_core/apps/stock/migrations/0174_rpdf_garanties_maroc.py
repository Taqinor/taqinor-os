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


def corriger(apps, schema_editor):
    Produit = apps.get_model('stock', 'Produit')
    deye = Produit.objects.filter(sku__in=_ONDULEURS_DEYE_SKUS)
    deye.filter(garantie=ANCIEN_TEXTE_DEYE).update(garantie=NOUVEAU_TEXTE_DEYE)
    deye.filter(garantie_mois=120).update(garantie_mois=60)
    Produit.objects.filter(
        sku__in=_DYNESS_SKUS, garantie=ANCIEN_TEXTE_DYNESS,
    ).update(garantie=NOUVEAU_TEXTE_DYNESS)


def retablir(apps, schema_editor):
    Produit = apps.get_model('stock', 'Produit')
    deye = Produit.objects.filter(sku__in=_ONDULEURS_DEYE_SKUS)
    deye.filter(garantie=NOUVEAU_TEXTE_DEYE).update(garantie=ANCIEN_TEXTE_DEYE)
    deye.filter(garantie_mois=60).update(garantie_mois=120)
    Produit.objects.filter(
        sku__in=_DYNESS_SKUS, garantie=NOUVEAU_TEXTE_DYNESS,
    ).update(garantie=ANCIEN_TEXTE_DYNESS)


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0173_merge_20261023_2327'),
    ]

    operations = [
        migrations.RunPython(corriger, retablir),
    ]
