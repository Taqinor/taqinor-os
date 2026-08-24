# -*- coding: utf-8 -*-
"""L-22A (fondateur 24/08/2026) — les DEUX onduleurs 5 kW acceptent le 710 Wc.

« Change both inverter of 5kw to increase their mppt current to more then 20A
so they accept the canadian solar pannels. » Les deux bornes de courant
d'entrée MPPT de ``OND-H-DEY-5M`` (Deye hybride) et ``OND-R-HUA-5M`` (Huawei
réseau) passent à **22,0 A** — le plancher qui respecte « plus de 20 A ».

POURQUOI UNE MIGRATION EN PLUS DU SEEDER. ``manage.py seed_catalogue`` ne
COMBLE que les champs vides (``_fiche_champ_vide``) : une fiche déjà seedée
porte 13,0/17,0 A (Deye) ou 12,5 A (Huawei) et ne bougerait donc JAMAIS d'un
simple redéploiement. C'est le même trou que 0125/0126 refermaient : une base
existante n'atteint une correction de datasheet que par une migration.

RÈGLE — RECALAGE CHAMP PAR CHAMP, JAMAIS UN ÉCRASEMENT (motif 0126). Chaque
champ n'est réécrit que si la base porte EXACTEMENT l'ancienne valeur seedée ;
une saisie fondateur divergente est laissée intacte. Pour l'Isc du Huawei,
« l'ancienne valeur seedée » est l'ABSENCE (le champ n'a jamais figuré dans
``FICHES_TECHNIQUES``, il valait donc ``None`` partout) : seul un champ ``None``
est comblé, une valeur déjà saisie ne l'est pas.

EFFET MÉTIER. Une chaîne de CS7N-710 apporte 17,59 A d'Imp et 18,59 A d'Isc :
sous 22 A, elle cesse d'être un dépassement. Le couple 710 Wc ↔ Deye 5 kW
mono, jusqu'ici BLOQUANT (Isc 18,59 A > 17,0 A publiés — ``core.electrique.
chaines._verdicts_courant``, règle 1), devient compatible ; le couple
710 Wc ↔ Huawei 5 kW, jusqu'ici en ALERTE d'écrêtage permanent (Imp 17,59 A >
12,5 A — règle 2), cesse d'écrêter.

MULTI-TENANT : le SKU est apparié à travers TOUTES les sociétés (pas de filtre
société), comme 0125/0126.

RÉVERSIBLE : non — ``noop`` (même doctrine que 0125/0126/0127 : après coup,
rien ne distingue un champ recalé ici d'une saisie fondateur postérieure ;
revenir en arrière risquerait d'effacer une vraie saisie).
"""
from decimal import Decimal

from django.db import migrations

#: (champ, ancienne valeur seedée, nouvelle valeur). ``None`` en ancienne
#: valeur = le champ n'était pas seedé du tout : on ne comble QUE le vide.
_RECALAGES_PAR_SKU = {
    # Deye SUN-5K-SG05LP1-EU — datasheet 230731 : 13 A d'Imp, 17 A d'Isc.
    'OND-H-DEY-5M': (
        ('ond_i_max_mppt_a', Decimal('13.0'), Decimal('22.0')),
        ('ond_isc_max_mppt_a', Decimal('17.0'), Decimal('22.0')),
    ),
    # Huawei SUN2000-5KTL-L1 — 12,5 A d'Imp ; Isc jamais seedé (NULL).
    'OND-R-HUA-5M': (
        ('ond_i_max_mppt_a', Decimal('12.5'), Decimal('22.0')),
        ('ond_isc_max_mppt_a', None, Decimal('22.0')),
    ),
}


def relever_bornes_mppt_5kw(apps, schema_editor):
    FicheTechnique = apps.get_model('stock', 'FicheTechnique')

    for sku, recalages in _RECALAGES_PAR_SKU.items():
        for fiche in FicheTechnique.objects.filter(
                produit__sku=sku).iterator():
            champs = []
            for champ, ancienne, nouvelle in recalages:
                actuelle = getattr(fiche, champ)
                if ancienne is None:
                    # « Jamais seedé » : seul le vide est comblé.
                    if actuelle is not None:
                        continue
                elif actuelle != ancienne:
                    continue  # saisie fondateur (ou déjà recalé) — intouchée
                setattr(fiche, champ, nouvelle)
                champs.append(champ)
            if champs:
                fiche.save(update_fields=champs)


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0127_pvlv_identite_batterie_bosb'),
    ]

    operations = [
        migrations.RunPython(relever_bornes_mppt_5kw, migrations.RunPython.noop),
    ]
