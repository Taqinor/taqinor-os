"""PVLV2 (fondateur 21/08/2026) — les 15/20 kW Deye n'existent qu'en BASSE tension.

« I only know 15 and 20 kw on LV — i dont even have them in high voltage » :
OND-H-DEY-15T/20T sont les SG05LP3 BASSE TENSION du parc réel, avec leurs
prix d'origine. L'identification « SG01HP3 haute tension » (PVG4) était une
supposition de recherche jamais validée par le fondateur ; elle avait produit
(a) des fiches techniques seedées avec les valeurs du MAUVAIS appareil et
(b) deux SKU doublons « Basse Tension » créés le 18/08
(OND-DEY-15K-LV/20K-LV, prix vides). Cette migration remet les bases
existantes d'équerre, par société :

  * ARCHIVE les deux SKU doublons (jamais supprimés — même patron que les
    artefacts Huawei mono, ``ARTEFACTS_ONDULEUR_SKUS`` côté seeder, qui les
    archive aussi à chaque passage) ;
  * RECALE champ par champ la fiche technique de OND-H-DEY-15T/20T des
    valeurs SG01HP3 seedées vers les valeurs SG05LP3 sourcées
    (deyeinverter.com datasheet_sun-14-20k-sg05lp3-eu-sm2_240601_en.pdf) —
    UNIQUEMENT quand le champ porte encore l'ancienne valeur seedée : une
    saisie fondateur divergente n'est JAMAIS touchée ;
  * ne touche à AUCUN prix (les prix fondateur des 15T/20T n'ont jamais
    bougé en base) ni à aucune quantité.

Champs recalés (ancien SG01HP3 → nouveau SG05LP3) : mppt_v_min 150→160,
mppt_v_max 850→650, v_max_abs 1000→800, v_demarrage_v 180→160,
bat_v_min 160→40, bat_v_max 700→60, et i_max_mppt_a 26→20 pour le seul 20T
(le 15T portait déjà 20 A, valeur commune aux deux fiches). Les champs encore
NULL (``ond_isc_max_mppt_a``…) sont l'affaire de la migration 0125, qui lit
le dictionnaire du seeder — désormais corrigé.

RÉVERSIBLE : non — ``noop`` (même doctrine que 0125/0127 : impossible de
distinguer après coup un champ recalé d'une saisie postérieure).
"""
from decimal import Decimal

from django.db import migrations

_SKUS_DOUBLONS = ('OND-DEY-15K-LV', 'OND-DEY-20K-LV')

#: (champ, ancienne valeur seedée SG01HP3, nouvelle valeur SG05LP3)
_RECALAGES_COMMUNS = (
    ('ond_mppt_v_min', Decimal('150.0'), Decimal('160.0')),
    ('ond_mppt_v_max', Decimal('850.0'), Decimal('650.0')),
    ('ond_v_max_abs', Decimal('1000.0'), Decimal('800.0')),
    ('ond_v_demarrage_v', Decimal('180.0'), Decimal('160.0')),
    ('ond_bat_v_min', Decimal('160.0'), Decimal('40.0')),
    ('ond_bat_v_max', Decimal('700.0'), Decimal('60.0')),
)
_RECALAGES_PAR_SKU = {
    'OND-H-DEY-15T': _RECALAGES_COMMUNS,
    'OND-H-DEY-20T': _RECALAGES_COMMUNS + (
        ('ond_i_max_mppt_a', Decimal('26.0'), Decimal('20.0')),
    ),
}


def corriger_gamme_lv(apps, schema_editor):
    Produit = apps.get_model('stock', 'Produit')
    FicheTechnique = apps.get_model('stock', 'FicheTechnique')

    Produit.objects.filter(
        sku__in=_SKUS_DOUBLONS, is_archived=False).update(is_archived=True)

    for sku, recalages in _RECALAGES_PAR_SKU.items():
        for fiche in FicheTechnique.objects.filter(
                produit__sku=sku).iterator():
            champs = []
            for champ, ancienne, nouvelle in recalages:
                if getattr(fiche, champ) == ancienne:
                    setattr(fiche, champ, nouvelle)
                    champs.append(champ)
            if champs:
                fiche.save(update_fields=champs)


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0125_pvfch_combler_fiches_manquantes'),
    ]

    operations = [
        migrations.RunPython(corriger_gamme_lv, migrations.RunPython.noop),
    ]
