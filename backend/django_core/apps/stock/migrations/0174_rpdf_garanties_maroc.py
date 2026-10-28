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
2) BATTERIES DYNESS — plus de « variante régionale » ni « version V2 ».
   BAT-DEY-5 (DL5.0C V2) : garantie Afrique V2-202502 = 7 ans de base,
   10 ans seulement par extension ACHETÉE → 7 ans, ``garantie_mois`` 120 → 84
   (même règle que Deye). BAT-DEY-10 (Powerbox Pro) : 10 ans, texte relu par
   D-BAT-2710 ; ``garantie_mois`` reste 120.

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
ANCIEN_TEXTE_DEYE = "Garantie constructeur 5 à 10 ans (selon site d'installation)"
NOUVEAU_TEXTE_DEYE = 'Garantie constructeur 5 ans'
ANCIEN_TEXTE_DYNESS = 'Garantie 10 ans (variante régionale : 7 ans) · ≥ 6 000 cycles'
# Texte D-BAT-2710 (seeder du 27/10, posé sur une base neuve avant 0174).
ANCIEN_TEXTE_DYNESS_V2 = ('Garantie 10 ans (version V2 : 7 ans, extensible à 10) · '
                          '6 000 cycles (0,2C, 25 °C, DoD 90 %)')
NOUVEAU_TEXTE_DYNESS_5 = ('Garantie constructeur 7 ans · '
                          '6 000 cycles (0,2C, 25 °C, DoD 90 %)')
NOUVEAU_TEXTE_DYNESS_10 = 'Garantie 10 ans · 6 000 cycles (0,2C, 25 °C, DoD 90 %)'


def _changer(qs, regles):
    """Quelques dizaines de lignes au plus (SKU semés × sociétés) : parcours
    par ``.iterator()`` et sauvegarde ciblée, jamais un update global.
    ``regles`` = {champ: {ancienne valeur: nouvelle}} — seule une valeur
    SEMÉE connue change ; une saisie du fondateur reste à lui."""
    for p in qs.iterator():
        champs = []
        for champ, table in regles.items():
            actuel = getattr(p, champ)
            if actuel in table:
                setattr(p, champ, table[actuel])
                champs.append(champ)
        if champs:
            p.save(update_fields=champs)


def corriger(apps, schema_editor):
    Produit = apps.get_model('stock', 'Produit')
    _changer(Produit.objects.filter(sku__in=_ONDULEURS_DEYE_SKUS), {
        'garantie': {ANCIEN_TEXTE_DEYE: NOUVEAU_TEXTE_DEYE},
        'garantie_mois': {120: 60}})
    _changer(Produit.objects.filter(sku='BAT-DEY-5'), {
        'garantie': {ANCIEN_TEXTE_DYNESS: NOUVEAU_TEXTE_DYNESS_5,
                     ANCIEN_TEXTE_DYNESS_V2: NOUVEAU_TEXTE_DYNESS_5},
        'garantie_mois': {120: 84}})
    _changer(Produit.objects.filter(sku='BAT-DEY-10'), {
        'garantie': {ANCIEN_TEXTE_DYNESS: NOUVEAU_TEXTE_DYNESS_10}})


def retablir(apps, schema_editor):
    Produit = apps.get_model('stock', 'Produit')
    _changer(Produit.objects.filter(sku__in=_ONDULEURS_DEYE_SKUS), {
        'garantie': {NOUVEAU_TEXTE_DEYE: ANCIEN_TEXTE_DEYE},
        'garantie_mois': {60: 120}})
    _changer(Produit.objects.filter(sku='BAT-DEY-5'), {
        'garantie': {NOUVEAU_TEXTE_DYNESS_5: ANCIEN_TEXTE_DYNESS},
        'garantie_mois': {84: 120}})
    _changer(Produit.objects.filter(sku='BAT-DEY-10'), {
        'garantie': {NOUVEAU_TEXTE_DYNESS_10: ANCIEN_TEXTE_DYNESS}})


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0173_merge_20261023_2327'),
    ]

    operations = [
        migrations.RunPython(corriger, retablir),
    ]
