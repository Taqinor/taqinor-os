"""Fondateur 17/11/2026 — borne panneaux des onduleurs + courants MPPT 15/20 kW.

Deux corrections de DONNÉES sur ``stock.FicheTechnique`` (aucun changement de
schéma), par société, sur les SKU du catalogue réel :

  1. ``OND-H-DEY-15T`` / ``OND-H-DEY-20T`` (Deye SG05LP3, révision actuelle
     vendue — datasheet SUN-14/15/16/18/20K-SG05LP3-EU-SM2 du 2026-09-11,
     https://www.deyeinverter.com/deyeinverter/2026/09/14/
     BDatasheetSUN-14-20K-SG05LP3-EU-SM220260911en.pdf) : « Max. Operating PV
     Input Current (A) » 36+36 et « Max. Input Short-Circuit Current (A) »
     54+54. ``ond_i_max_mppt_a`` 20 -> 36 et ``ond_isc_max_mppt_a`` 30 -> 54,
     UNIQUEMENT quand la valeur stockée est EXACTEMENT l'ancienne (fiche de
     juin 2024, tracker faible) : une valeur saisie autrement n'est jamais
     touchée.
  2. COMBLE les champs VIDES ``ond_dc_max_kwc`` (puissance PV maximale
     raccordable, kWc) et ``ond_chaines_max_par_mppt`` — jamais un champ déjà
     rempli. Valeurs lues sur les fiches constructeur (voir ``_A_COMBLER``) ;
     elles sont aussi dans ``seed_catalogue.FICHES_TECHNIQUES`` (le run nu du
     seeder ne comble que le vide : cette migration fait atteindre la
     production sans attendre un ``--reappliquer-fiches``).

No-op sur une base sans aucun de ces SKU.

RÉVERSIBLE : ``retablir`` remet 36 -> 20 / 54 -> 30 (seulement là où la valeur
est encore la nouvelle) et revide ``ond_dc_max_kwc`` / ``ond_chaines_max_par_mppt``
(seulement là où la valeur est encore EXACTEMENT celle posée ici). Limite
assumée : une valeur identique saisie à la main avant la migration serait
revidée aussi — indiscernable après coup.
"""
from decimal import Decimal

from django.db import migrations

#: sku -> ((champ, ancienne, nouvelle), …) — corrigé seulement si égal à l'ancienne.
_CORRECTIONS = {
    'OND-H-DEY-15T': (
        ('ond_i_max_mppt_a', Decimal('20.0'), Decimal('36.0')),
        ('ond_isc_max_mppt_a', Decimal('30.0'), Decimal('54.0')),
    ),
    'OND-H-DEY-20T': (
        ('ond_i_max_mppt_a', Decimal('20.0'), Decimal('36.0')),
        ('ond_isc_max_mppt_a', Decimal('30.0'), Decimal('54.0')),
    ),
}

#: sku -> ((champ, valeur), …) — posé seulement si le champ est VIDE.
#: Deye « Max. PV access power (W) » et « No. of MPP Trackers / No. of Strings
#: MPP Tracker » (2/2+2) :
#:   SUN-3/4/5/6/8/10/12K-SG05LP3-EU-SM2, 2026-09-11, https://www.deyeinverter.com/
#:   deyeinverter/2026/09/14/BDatasheetSUN-3-12K-SG05LP3-EU-SM220260911en.pdf
#:   (colonne 10K : 20000 W ; colonne 12K : 24000 W ; 8K-12K : 2/2+2) ;
#:   SUN-14/15/16/18/20K-SG05LP3-EU-SM2, 2026-09-11, .../
#:   BDatasheetSUN-14-20K-SG05LP3-EU-SM220260911en.pdf
#:   (colonne 15K : 30000 W ; colonne 20K : 40000 W ; 2/2+2).
#: Huawei « Recommended max. PV power » : 5KTL-L1 7500 Wp
#:   (solar.huawei.com/en/professionals/all-products/SUN2000-3-4-5-6KTL-L1/specs),
#:   10KTL-M1 15000 Wp (solar.huawei.com/en/products/sun2000-3-4-5-6-8-10ktl-m1/
#:   specs/), 15/20/25KTL-M5 22500 / 30000 / 37500 Wp (fiche
#:   SUN2000-12/15/17/20/25KTL-M5, Version 03-202403).
_A_COMBLER = {
    'OND-H-DEY-10T': (('ond_dc_max_kwc', Decimal('20.0')),
                      ('ond_chaines_max_par_mppt', 2)),
    'SUN-12K-SG05LP3': (('ond_dc_max_kwc', Decimal('24.0')),
                        ('ond_chaines_max_par_mppt', 2)),
    'OND-H-DEY-15T': (('ond_dc_max_kwc', Decimal('30.0')),
                      ('ond_chaines_max_par_mppt', 2)),
    'OND-H-DEY-20T': (('ond_dc_max_kwc', Decimal('40.0')),
                      ('ond_chaines_max_par_mppt', 2)),
    'OND-R-HUA-5M': (('ond_dc_max_kwc', Decimal('7.5')),),
    'OND-R-HUA-10T': (('ond_dc_max_kwc', Decimal('15.0')),),
    'OND-R-HUA-15T': (('ond_dc_max_kwc', Decimal('22.5')),),
    'OND-R-HUA-20T': (('ond_dc_max_kwc', Decimal('30.0')),),
    'OND-R-HUA-25T': (('ond_dc_max_kwc', Decimal('37.5')),),
}


def appliquer(apps, schema_editor):
    FicheTechnique = apps.get_model('stock', 'FicheTechnique')
    skus = set(_CORRECTIONS) | set(_A_COMBLER)
    for fiche in FicheTechnique.objects.filter(
            produit__sku__in=skus).select_related('produit').iterator():
        sku = fiche.produit.sku
        champs = []
        for champ, ancienne, nouvelle in _CORRECTIONS.get(sku, ()):
            if getattr(fiche, champ) == ancienne:
                setattr(fiche, champ, nouvelle)
                champs.append(champ)
        for champ, valeur in _A_COMBLER.get(sku, ()):
            if getattr(fiche, champ) is None:
                setattr(fiche, champ, valeur)
                champs.append(champ)
        if champs:
            fiche.save(update_fields=champs)


def retablir(apps, schema_editor):
    FicheTechnique = apps.get_model('stock', 'FicheTechnique')
    skus = set(_CORRECTIONS) | set(_A_COMBLER)
    for fiche in FicheTechnique.objects.filter(
            produit__sku__in=skus).select_related('produit').iterator():
        sku = fiche.produit.sku
        champs = []
        for champ, ancienne, nouvelle in _CORRECTIONS.get(sku, ()):
            if getattr(fiche, champ) == nouvelle:
                setattr(fiche, champ, ancienne)
                champs.append(champ)
        for champ, valeur in _A_COMBLER.get(sku, ()):
            if getattr(fiche, champ) == valeur:
                setattr(fiche, champ, None)
                champs.append(champ)
        if champs:
            fiche.save(update_fields=champs)


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0181_ntplt34_trgm_produit'),
    ]

    operations = [
        migrations.RunPython(appliquer, retablir),
    ]
