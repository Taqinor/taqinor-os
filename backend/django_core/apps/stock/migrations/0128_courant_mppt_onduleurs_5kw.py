"""DIM2 (fondateur 24/08/2026) — les deux onduleurs 5 kW acceptent les 710 Wc.

ORDRE FONDATEUR, verbatim : « change both inverter of 5kw to increase their
mppt current to more then 20A so they accept the canadian solar pannels ».

CE QUE ÇA CORRIGE. Les panneaux Canadian Solar 710 Wc du parc réel tirent
18,59 A d'Isc et ~17,4 A d'Impp. Les deux onduleurs 5 kW monophasés du
catalogue portaient des bornes MPPT lues sur datasheet — 13 A / 17 A d'Isc
pour le Deye SG05LP1, 12,5 A pour le Huawei SUN2000-5KTL-L1 (Isc non publiée)
— qui refusaient donc ce panneau. C'était le « trou de catalogue n° 2 » :
aucune option batterie possible à 5 kW monophasé. Le fondateur DÉCLARE des
bornes de 22 A (le plancher qui respecte « plus de 20 A ») ; le trou se
referme.

CE QUE ÇA NE CHANGE PAS. Le MÉCANISME de refus (règle L1 : un couple hors
des bornes publiées n'est pas vendable, verdict Isc souverain) est INTACT.
Seules DEUX fiches changent de bornes ; tous les autres paliers gardent les
leurs, et un panneau qui dépasse 22 A reste refusé sur ces deux-là.

RECALAGE CHAMP PAR CHAMP, JAMAIS EN BLOC — même doctrine que la migration
0126 : un champ n'est réécrit que s'il porte ENCORE la valeur seedée
d'origine. Une valeur saisie par le fondateur (ou par un commercial) sur une
base existante n'est jamais écrasée. Le cas du Huawei est le seul un peu
différent : ``ond_isc_max_mppt_a`` n'a JAMAIS été seedé pour lui (la
datasheet ne la publie pas), donc il n'est renseigné que s'il est encore
VIDE — poser 22 A par-dessus une saisie existante serait exactement ce que
cette prudence interdit.

RÉVERSIBLE : non — ``noop`` (même doctrine que 0125/0126/0127 : impossible de
distinguer après coup un champ recalé d'une saisie postérieure).
"""
from decimal import Decimal

from django.db import migrations

#: Borne DÉCLARÉE par le fondateur (24/08/2026) pour les deux 5 kW.
_DECLARE = Decimal('22.0')

#: (champ, ancienne valeur seedée, nouvelle valeur). ``None`` en ancienne
#: valeur = le champ n'a jamais été seedé : on ne le renseigne que s'il est
#: encore VIDE.
_RECALAGES_PAR_SKU = {
    # Deye SUN-5K-SG05LP1-EU : « 13+13 A » et « 17+17 A » d'Isc sur datasheet.
    'OND-H-DEY-5M': (
        ('ond_i_max_mppt_a', Decimal('13.0'), _DECLARE),
        ('ond_isc_max_mppt_a', Decimal('17.0'), _DECLARE),
    ),
    # Huawei SUN2000-5KTL-L1 : 12,5 A par MPPT, Isc jamais publiée ni seedée.
    'OND-R-HUA-5M': (
        ('ond_i_max_mppt_a', Decimal('12.5'), _DECLARE),
        ('ond_isc_max_mppt_a', None, _DECLARE),
    ),
}


def relever_courant_mppt_5kw(apps, schema_editor):
    FicheTechnique = apps.get_model('stock', 'FicheTechnique')
    for sku, recalages in _RECALAGES_PAR_SKU.items():
        for fiche in FicheTechnique.objects.filter(produit__sku=sku).iterator():
            champs = []
            for champ, ancienne, nouvelle in recalages:
                actuel = getattr(fiche, champ)
                attendu_vide = ancienne is None
                if attendu_vide and actuel is not None:
                    continue
                if not attendu_vide and actuel != ancienne:
                    continue
                setattr(fiche, champ, nouvelle)
                champs.append(champ)
            if champs:
                fiche.save(update_fields=champs)


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0127_pvlv_identite_batterie_bosb'),
    ]

    operations = [
        migrations.RunPython(relever_courant_mppt_5kw,
                             migrations.RunPython.noop),
    ]
