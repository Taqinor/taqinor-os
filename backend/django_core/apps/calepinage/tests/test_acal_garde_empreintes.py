"""ACAL318 — garde permanente : chaque clé du schéma ``roof_layout_v2`` est
CLASSÉE pour les deux empreintes (D-ACAL-4 + D-ACAL-21).

* ``volatile`` — état d'écran : hors empreinte « document »
  (``services.layout.CLES_VOLATILES``) et hors empreinte imprimée ;
* ``document`` — versionnée (empreinte document), jamais imprimée ;
* ``imprimee`` — change un chiffre que le client voit : dans les DEUX
  empreintes (``apps.ventes.domain.geometrie.CLES_IMPRIMEES``).

Le test mute chaque clé de l'``exemple`` du schéma (racine, puis propriétés
d'un pan) et vérifie que chaque empreinte bouge EXACTEMENT comme la classe le
dit. Une clé ajoutée au schéma sans classe fait échouer le test en la NOMMANT
(classe de constat : « empreinte aveugle » — C-ACAL-090).
"""
from __future__ import annotations

import copy
import json
import pathlib

from django.test import SimpleTestCase

from apps.calepinage.services.layout import (
    CLES_VOLATILES, empreinte_document,
)
from apps.ventes.domain.geometrie import CLES_IMPRIMEES, layout_hash

SCHEMA = pathlib.Path(__file__).resolve().parents[1] / (
    'contract_samples/roof_layout_v2.schema.json')

VOLATILE, DOCUMENT, IMPRIMEE = 'volatile', 'document', 'imprimee'

#: La classe de CHAQUE propriété racine du schéma.
CLASSEMENT_RACINE = {
    'activeAreaId': VOLATILE,
    'scene': VOLATILE,
    'zones': IMPRIMEE,
    'result': IMPRIMEE,
    'scenario': IMPRIMEE,
    'panelWatt': IMPRIMEE,
    'battery': IMPRIMEE,
    'poseSurfaces': IMPRIMEE,
    'exclusionZones': IMPRIMEE,
    'modules': IMPRIMEE,
    'shading12x24': IMPRIMEE,
    'environment': IMPRIMEE,
    'shadeObstructions': IMPRIMEE,
    'horizonProfile': IMPRIMEE,
    'alleeTechnique': DOCUMENT,
    'billKwh': DOCUMENT,
    'buildings': DOCUMENT,
    'choixConception': DOCUMENT,
    'consumption': DOCUMENT,
    'devisId': DOCUMENT,
    'electrical': DOCUMENT,
    'jeuReglages': DOCUMENT,
    'measurements': DOCUMENT,
    'optimisation': DOCUMENT,
    'outline': DOCUMENT,
    'parcelle': DOCUMENT,
    'pin': DOCUMENT,  # D-ACAL-13 : un recentrage est versionné
    'pinSource': DOCUMENT,
    'repere': DOCUMENT,
    'repereAcquitte': DOCUMENT,
    'setbacksM': DOCUMENT,
    'source': DOCUMENT,
    'underlay': DOCUMENT,
    'version': DOCUMENT,
}

#: Un pan est imprimé EN ENTIER (obstacles d'ombrage et ``hauteurM``
#: compris, D-ACAL-21) : chacune de ses propriétés est imprimée.
CLASSEMENT_PAN = {cle: IMPRIMEE for cle in (
    'buildingId', 'cotesReleve', 'edges', 'facingAzimuthDeg',
    'facingAzimuthPrecisionDeg', 'facingAzimuthSource', 'facingManual',
    'geometry', 'id', 'label', 'neededAuto', 'neededPanels', 'obstacles',
    'pitchDeg', 'pitchSource', 'pitchSuggestion', 'result', 'roofType',
    'shading12x24', 'vertices')}


def _schema():
    return json.loads(SCHEMA.read_text(encoding='utf-8'))


def _muter(valeur, cle):
    """Une valeur DIFFÉRENTE, non vide, et de « vérité » opposée pour
    ``battery`` (l'empreinte imprimée n'en lit que ``bool``)."""
    if cle == 'battery':
        return None if valeur else {'mutation': 'batterie'}
    return {'mutation': cle, 'avant': copy.deepcopy(valeur)}


def _classe_attendue_de_racine(cle):
    return CLASSEMENT_RACINE[cle]


class GardeEmpreintesTest(SimpleTestCase):

    def _verifier(self, base, mute, cle, classe):
        doc_avant, doc_apres = (empreinte_document(base),
                                empreinte_document(mute))
        imp_avant, imp_apres = layout_hash(base), layout_hash(mute)
        if classe == VOLATILE:
            self.assertEqual(doc_avant, doc_apres,
                             f'« {cle} » est volatile : l\'empreinte '
                             'document ne doit pas bouger.')
        else:
            self.assertNotEqual(doc_avant, doc_apres,
                                f'« {cle} » ({classe}) est aveugle pour '
                                "l'empreinte document.")
        if classe == IMPRIMEE:
            self.assertNotEqual(imp_avant, imp_apres,
                                f'« {cle} » est imprimée mais layout_hash '
                                'ne bouge pas.')
        else:
            self.assertEqual(imp_avant, imp_apres,
                             f'« {cle} » ({classe}) change layout_hash : '
                             "classez-la « imprimee » ou retirez-la de "
                             'CLES_IMPRIMEES.')

    def test_chaque_cle_du_schema_est_classee(self):
        schema = _schema()
        racine = set(schema['properties'])
        pan = set(schema['$defs']['zone']['properties'])
        self.assertEqual(sorted(racine - set(CLASSEMENT_RACINE)), [],
                         'clé(s) racine du schéma roof_layout_v2 SANS classe '
                         "d'empreinte (volatile / document / imprimee)")
        self.assertEqual(sorted(pan - set(CLASSEMENT_PAN)), [],
                         'propriété(s) de pan du schéma SANS classe '
                         "d'empreinte (volatile / document / imprimee)")

        exemple = schema['exemple']
        for cle in sorted(racine):
            classe = _classe_attendue_de_racine(cle)
            with self.subTest(cle=cle, classe=classe):
                mute = copy.deepcopy(exemple)
                mute[cle] = _muter(exemple.get(cle), cle)
                self._verifier(exemple, mute, cle, classe)
        for cle in sorted(pan):
            with self.subTest(cle=f'zones[].{cle}'):
                mute = copy.deepcopy(exemple)
                mute['zones'][0][cle] = _muter(
                    exemple['zones'][0].get(cle), cle)
                self._verifier(exemple, mute, f'zones[].{cle}',
                               CLASSEMENT_PAN[cle])

    def test_classement_coherent_avec_les_constantes(self):
        """Les constantes des deux empreintes et la table se répondent."""
        imprimees = {alias for entree in CLES_IMPRIMEES
                     for alias in entree.split('|')}
        for cle, classe in CLASSEMENT_RACINE.items():
            with self.subTest(cle=cle):
                self.assertEqual(cle in imprimees, classe == IMPRIMEE, cle)
                self.assertEqual(cle in CLES_VOLATILES, classe == VOLATILE,
                                 cle)

    def test_horodatages_volatils_d_un_pan(self):
        exemple = _schema()['exemple']
        mute = copy.deepcopy(exemple)
        geometrie = mute['zones'][0].setdefault('geometry', {})
        geometrie.setdefault('solarAccess', {})['computedAt'] = (
            '2099-01-01T00:00:00Z')
        mute.setdefault('consumption', {}).setdefault(
            'source', {})['saisi_le'] = '2099-01-01T00:00:00Z'
        # Hors empreinte document ; l'empreinte imprimée lit le pan entier,
        # elle n'est pas l'objet de ce cas.
        self.assertEqual(empreinte_document(exemple),
                         empreinte_document(mute))

    def test_une_cle_non_classee_est_nommee(self):
        """Test-du-test : une propriété factice ajoutée au schéma EN MÉMOIRE
        est détectée et NOMMÉE."""
        schema = _schema()
        schema['properties']['cleFactice'] = {'type': 'string'}
        manquantes = sorted(set(schema['properties'])
                            - set(CLASSEMENT_RACINE))
        self.assertEqual(manquantes, ['cleFactice'])
