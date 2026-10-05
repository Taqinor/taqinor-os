"""ACAL232 - la parcelle n'a qu'UNE cle : ``parcelle`` (schema v2).

import-layout puis plan-masse.pdf = 200 ; une parcelle a 2 points est refusee
a l'import sous ``roof_layout.parcelle`` ; les alias ``parcel`` et
``parcelleCadastrale`` (zero ecrivain) ne sont plus lus ; le motif d'un plan de
masse sans parcelle renvoie a l'atelier 3D. Essais PURS (le service et le
rendu SVG, comme ``test_cal194_plans.py``).

Run :
    python manage.py test apps.calepinage.tests.test_acal_parcelle -v2
"""
import copy
import json
import pathlib

from django.test import SimpleTestCase

from apps.calepinage.services.io_layout import (
    ImportLayoutRefuse, valider_document,
)
from apps.calepinage.services.planche import (
    CONTENU_MASSE, MOTIF_SANS_PARCELLE, PlancheRefusee, geometrie_de_planche,
    rendre_plan_svg,
)
from apps.calepinage.views.sorties import SANS_PARCELLE

from .test_cal171_planche import LAYOUT
from .test_cal173_empreinte import FauxCalepinage

SCHEMA = (pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
          / 'roof_layout_v2.schema.json')
DOCUMENT_VALIDE = json.loads(SCHEMA.read_text(encoding='utf-8'))['exemple']
SOMMETS = [[-7.6002, 33.4998], [-7.5997, 33.4998], [-7.5997, 33.5003],
           [-7.6002, 33.5003]]


def avec_parcelle(document=None, sommets=SOMMETS):
    layout = copy.deepcopy(document or LAYOUT)
    layout['parcelle'] = {'vertices': copy.deepcopy(sommets)}
    return layout


class ImportPuisPlanDeMasseTest(SimpleTestCase):
    def test_import_layout_puis_plan_masse_200(self):
        valider_document(avec_parcelle(DOCUMENT_VALIDE))   # ne leve pas
        calepinage = FauxCalepinage(roof_layout=avec_parcelle())
        svg = rendre_plan_svg(calepinage, contenu=CONTENU_MASSE)
        self.assertIn('<svg', svg)

    def test_export_layout_restitue_la_parcelle_identique(self):
        document = avec_parcelle(DOCUMENT_VALIDE)
        valider_document(document)
        aller_retour = json.loads(json.dumps(document))
        self.assertEqual(aller_retour['parcelle'], document['parcelle'])
        self.assertEqual(aller_retour['parcelle']['vertices'], SOMMETS)

    def test_parcelle_a_deux_points_refusee_nommee_roof_layout_parcelle(self):
        court = avec_parcelle(DOCUMENT_VALIDE, SOMMETS[:2])
        with self.assertRaises(ImportLayoutRefuse) as refus:
            valider_document(court)
        self.assertEqual(refus.exception.champ, 'roof_layout.parcelle')


class UneSeuleCleTest(SimpleTestCase):
    def test_alias_parcel_et_parcelleCadastrale_ne_sont_plus_lus(self):
        for alias in ('parcel', 'parcelleCadastrale'):
            layout = copy.deepcopy(LAYOUT)
            layout[alias] = {'vertices': SOMMETS}
            self.assertEqual(geometrie_de_planche(layout)['parcelle'], [],
                             alias)

    def test_motif_sans_parcelle_renvoie_a_l_atelier(self):
        with self.assertRaises(PlancheRefusee) as refus:
            rendre_plan_svg(FauxCalepinage(), contenu=CONTENU_MASSE)
        self.assertEqual(refus.exception.champ, 'parcelle')
        self.assertIn("atelier 3D", str(refus.exception))
        self.assertIn('Parcelle', str(refus.exception))
        # UNE constante, partagee avec l'inventaire des sorties.
        self.assertIs(SANS_PARCELLE, MOTIF_SANS_PARCELLE)
