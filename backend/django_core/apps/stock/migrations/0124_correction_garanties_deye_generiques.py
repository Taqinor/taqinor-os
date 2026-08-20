"""Corrige trois angles morts de garanties trouvés par l'audit du 2026-08-20
(lane DONNÉES CATALOGUE + FICHES WEB, contradictions O1/O3) — deux dans le
backfill structuré 0012_backfill_garanties, un dans le texte libre
``Produit.garantie`` que ``seed_catalogue.py`` a corrigé dans son dict
``FICHES`` mais qui ne se réécrit JAMAIS tout seul sur une base déjà seedée
(la boucle de sync ``FICHES`` ne pose que les clés PRÉSENTES dans le dict —
retirer une clé n'efface rien en base, exactement le problème qui a motivé
les migrations 0121/0123 pour ``nom``/``marque``).

Migration de DONNÉES uniquement (aucun changement de schéma) — MÊME PATRON
que 0121/0123 : une correction ciblée par SKU.

1) ONDULEURS DEYE (structuré) — 60 → 120 mois. La règle 0012 posait
   ``garantie_mois = 60`` pour « Onduleurs Deye (onduleurs seulement) », en la
   distinguant à tort de la règle Huawei (120). C'est FAUX : la garantie
   constructeur Deye officielle (« SUN Series Hybrid inverter 10-Year Limited
   Warranty for Installation in Europe », deyeinverter.com — couvre
   explicitement TOUTE la gamme SUN Series Hybrid) est de 10 ans, comme
   Huawei — c'était la contradiction concrète relevée par l'audit : bande
   « Nos garanties » du PDF affichant 10 ans (repli WARRANTIES) contre 60
   mois dans la colonne Garantie du tableau. La datasheet technique
   SG05LP3/SG05LP1 nuance elle-même : « Warranty : 5 Years/10 Years — the
   Warranty Period Depends the Final Installation Site of Inverter » — d'où
   le texte harmonisé posé côté ``seed_catalogue.py`` (« 5 à 10 ans selon
   site d'installation »), 120 restant la valeur structurée retenue (celle du
   document le plus favorable, déjà utilisée partout ailleurs, cf.
   warranty.ts côté web). Couvre aussi les deux SKU basse tension 15K/20K
   (PVG4/PVOND, ajoutés APRÈS le passage de 0012 — ``garantie_mois`` n'a donc
   jamais été posé dessus).

2) BATTERIES GÉNÉRIQUES NON SOURCÉES (structuré) — 120 → NULL. La règle 0012
   posait ``garantie_mois = 120`` pour « Batteries / stockage (toute
   marque) », sans distinguer la chimie ni la marque. Trois SKU n'ont AUCUNE
   garantie vérifiable (BAT-DYN-HV-16 : produit catalogue générique sans
   référence Dyness officielle à 16 kWh ; BAT-LIT-5 : marque « Lithium »
   générique, aucun fabricant identifiable ; BAT-GEL-22 : marque « Gel » —
   chimie plomb, sans rapport avec la règle LFP qui a justifié les 120 mois).
   Corrigé en NULL (omission), jamais un chiffre inventé.

3) TEXTE LIBRE ``garantie`` — RETIRÉ pour 38 SKU. ``seed_catalogue.py``
   FICHES a retiré la clé ``garantie`` de BAT-LIT-5, BAT-GEL-22, des 8 pompes
   génériques (PMP-IMM-*/PMP-SUR-*), des 16 variateurs VEICHI et des 11
   pompes OSP — toutes des « Garantie constructeur 2 ans » (ou « 5 ans · ≥
   6 000 cycles (80 % DoD) » pour BAT-LIT-5) SANS AUCUNE source datasheet
   vérifiable (marque générique ou introuvable — cf. commentaires du seeder).
   Sur une base DÉJÀ seedée, cette valeur reste écrite pour toujours tant
   qu'un ``RunPython`` ne l'efface pas explicitement (le seeder est additif,
   il ne désécrit rien). Cette migration vide ``Produit.garantie`` (chaîne
   vide) sur ces 38 SKU, pour que le texte omis côté seeder le soit aussi en
   base — jamais un chiffre non sourcé qui survit à un simple retrait de clé.

``BAT-DEY-5``/``BAT-DEY-10`` (batterie Dyness DL5.0C basse tension, la même
que la fiche web ``batterie-dyness``) et les onduleurs Huawei/Deye ne sont
PAS concernés par le point 3 : leur texte ``garantie`` a été CORRIGÉ (pas
retiré) dans ``seed_catalogue.py`` — la boucle de sync FICHES le réapplique
donc automatiquement à chaque déploiement, sans migration nécessaire.

RÉVERSIBILITÉ : ``reverse`` réapplique les valeurs D'AVANT cette correction
(60 mois pour Deye, 120 mois pour les trois batteries génériques, et les
anciens libellés « Garantie constructeur 2 ans » / « Garantie 5 ans · ≥ 6 000
cycles (80 % DoD) » pour le texte libre) — l'état d'AVANT, pas une histoire
plus profonde (même nuance assumée que 0121/0123).
"""
from django.db import migrations

_ONDULEURS_DEYE_SKUS = (
    'OND-H-DEY-5M', 'OND-H-DEY-10M', 'OND-H-DEY-10T',
    'OND-H-DEY-15T', 'OND-H-DEY-20T',
    'OND-DEY-15K-LV', 'OND-DEY-20K-LV',
)

_BATTERIES_NON_SOURCEES_SKUS = (
    'BAT-DYN-HV-16', 'BAT-LIT-5', 'BAT-GEL-22',
)

_ANCIEN_TEXTE_2_ANS = 'Garantie constructeur 2 ans'
_ANCIEN_TEXTE_BAT_LIT = 'Garantie 5 ans · ≥ 6 000 cycles (80 % DoD)'
_ANCIEN_TEXTE_BAT_GEL = 'Garantie 2 ans'

# SKU dont le texte libre ``garantie`` disait « Garantie constructeur 2 ans »
# sans aucune source vérifiable (marque générique ou introuvable) : pompes
# génériques (8), variateurs VEICHI (16), pompes OSP (11).
_SKUS_TEXTE_2_ANS_GENERIQUE = (
    'PMP-IMM-1.5M', 'PMP-IMM-3M', 'PMP-IMM-4T',
    'PMP-IMM-5.5T', 'PMP-IMM-7.5T', 'PMP-IMM-10T',
    'PMP-SUR-1.5M', 'PMP-SUR-3T',
    'VEI-SI22-AFF', 'VEI-SI22-2.2-220', 'VEI-SI23-2.2-220',
    'VEI-SI23-2.2-380', 'VEI-SI23-4-380', 'VEI-SI23-5.5-380',
    'VEI-SI23-7.5-380', 'VEI-SI23-11-380', 'VEI-SI23-15-380',
    'VEI-SI23-18-380', 'VEI-SI23-22-380', 'VEI-SI23-30-380',
    'VEI-SI23-37-380', 'VEI-SI23-45-380', 'VEI-SI23-55-380',
    'VEI-SI23-75-380',
    'PMP-OSP-30-8', 'PMP-OSP-30-11', 'PMP-OSP-30-13',
    'PMP-OSP-30-15', 'PMP-OSP-30-16', 'PMP-OSP-30-17',
    'PMP-OSP-30-20', 'PMP-OSP-30-21', 'PMP-OSP-30-25',
    'PMP-OSP-30-26', 'PMP-OSP-30-35',
)


def _set_garantie_mois(apps, sku_valeurs):
    """Pose ``garantie_mois`` sur chaque (sku, valeur) — idempotent (aucune
    écriture si déjà à la valeur cible), ne touche à rien d'autre."""
    Produit = apps.get_model('stock', 'Produit')
    for sku, valeur in sku_valeurs:
        for produit in Produit.objects.filter(sku=sku).iterator():
            if produit.garantie_mois != valeur:
                produit.garantie_mois = valeur
                produit.save(update_fields=['garantie_mois'])


def _set_garantie_texte(apps, sku_valeurs):
    """Pose ``garantie`` (texte libre) sur chaque (sku, valeur) — idempotent,
    ne touche à rien d'autre (ni prix, ni quantités, ni marque/description)."""
    Produit = apps.get_model('stock', 'Produit')
    for sku, valeur in sku_valeurs:
        for produit in Produit.objects.filter(sku=sku).iterator():
            if produit.garantie != valeur:
                produit.garantie = valeur
                produit.save(update_fields=['garantie'])


def corriger_garanties(apps, schema_editor):
    _set_garantie_mois(
        apps,
        [(sku, 120) for sku in _ONDULEURS_DEYE_SKUS]
        + [(sku, None) for sku in _BATTERIES_NON_SOURCEES_SKUS],
    )
    _set_garantie_texte(
        apps,
        [(sku, '') for sku in _SKUS_TEXTE_2_ANS_GENERIQUE]
        + [('BAT-LIT-5', ''), ('BAT-GEL-22', '')],
    )


def retablir_garanties_0012(apps, schema_editor):
    _set_garantie_mois(
        apps,
        [(sku, 60) for sku in _ONDULEURS_DEYE_SKUS]
        + [(sku, 120) for sku in _BATTERIES_NON_SOURCEES_SKUS],
    )
    _set_garantie_texte(
        apps,
        [(sku, _ANCIEN_TEXTE_2_ANS) for sku in _SKUS_TEXTE_2_ANS_GENERIQUE]
        + [('BAT-LIT-5', _ANCIEN_TEXTE_BAT_LIT),
           ('BAT-GEL-22', _ANCIEN_TEXTE_BAT_GEL)],
    )


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0123_cable_nexans_dans_le_nom'),
    ]

    operations = [
        migrations.RunPython(corriger_garanties, retablir_garanties_0012),
    ]
