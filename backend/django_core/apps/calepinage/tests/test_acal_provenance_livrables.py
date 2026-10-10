"""ACAL145 — les livrables impriment l'empreinte de la SIMULATION
(``resultat.simulation.hash_entree`` + ``version_simulation``, ACAL48), lue
par ``provenance_document.provenance_de_simulation`` — plus une clé RACINE
que personne n'écrit (empreinte vide), plus ``layout_hash`` imprimé sous le
nom ``hash_entree`` (constat C-ACAL-073).

L'en-tête ``simulation`` vient de la VRAIE chaîne (``simuler_calepinage``,
client rejoué CALX5) ; le résultat porte la forme STOCKÉE : aucune empreinte
à la racine.

Run :
    python manage.py test apps.calepinage.tests.test_acal_provenance_livrables -v2
"""
from __future__ import annotations

import copy
import json
import pathlib
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.calepinage.services import rapport_ombrage
from apps.calepinage.services.documents.document_asbuilt import (
    _construire_document, _html_de_document,
)
from apps.calepinage.services.documents.gabarit_document import pied_html
from apps.calepinage.services.documents.manuel_proprietaire import (
    _construire_manuel,
)
from apps.calepinage.services.rapport import construire_rapport, html_de_rapport

from .test_acal_completude_simulation import _simuler
from .test_calx316_manuel_proprietaire import GABARIT_CONSIGNES
from .test_calx317_rapport_ombrage import (
    MATRICE_12X24, PANS_DEUX, FauxCalepinage,
)
from .test_calx318_document_asbuilt import ECARTS_3_PANS_1_RELEVE

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]
ECHANTILLON = json.loads(
    (RACINE_APP / 'contract_samples' / 'calepinage_resultat.json')
    .read_text(encoding='utf-8'))

SITE = {'ville': 'Bouskoura', 'adresse': 'Zone industrielle',
        'source': 'roof_point', 'pin': None, 'outline': None}
STYLES = {'nom_affiche': 'Soleil Atlas', 'logo_url': '',
          'couleur_primaire': '', 'couleur_secondaire': ''}

_ENTETE = {}


def _entete():
    """L'en-tête ``simulation`` publié par la simulation RÉELLE."""
    if 'simulation' not in _ENTETE:
        _ENTETE['simulation'] = _simuler()['simulation']
    return copy.deepcopy(_ENTETE['simulation'])


def _resultat_stocke():
    """Le résultat sous sa forme stockée : l'empreinte vit dans
    ``simulation``, JAMAIS à la racine."""
    resultat = copy.deepcopy(ECHANTILLON['exemple'])
    resultat.pop('hash_entree', None)
    resultat.pop('entree_hash', None)
    resultat['simulation'] = _entete()
    return resultat


def _identite(titre):
    return {'titre_document': titre, 'projet': 'Villa Anfa',
            'client': 'Mme Bennani', 'produit_le': '23/09/2026'}


class ProvenanceLivrablesTest(SimpleTestCase):

    def setUp(self):
        self.entete = _entete()
        self.empreinte = self.entete['hash_entree']
        self.assertTrue(self.empreinte)
        self.assertTrue(self.entete['version_simulation'])

    def _verifier(self, provenance):
        self.assertEqual(provenance['hash_entree'], self.empreinte)
        self.assertEqual(provenance['version_simulation'],
                         self.entete['version_simulation'])
        pied = pied_html(provenance)
        self.assertIn('entrée %s' % self.empreinte[:12], pied)
        self.assertIn('simulation %s' % self.entete['version_simulation'],
                      pied)

    def test_rapport_imprime_l_empreinte_de_la_simulation(self):
        nu = SimpleNamespace(company=None, client_id=None, lead_id=None,
                             titre='Villa Anfa', resultat=None, pk=None)
        rapport = construire_rapport(
            nu, resultat=_resultat_stocke(), site=SITE,
            identite=_identite("Rapport d'étude"), styles=STYLES)
        self._verifier(rapport['provenance'])
        html = html_de_rapport(rapport)
        self.assertIn('entrée %s' % self.empreinte[:12], html)

    def test_manuel_et_ombrage_meme_empreinte(self):
        nu = SimpleNamespace(company=None, client_id=None, lead_id=None,
                             pk=None, titre='Villa Anfa', resultat=None)
        manuel = _construire_manuel(
            nu, resultat=_resultat_stocke(), gabarit=GABARIT_CONSIGNES,
            site=SITE, identite=_identite('Manuel du propriétaire'),
            styles=STYLES)
        self._verifier(manuel['provenance'])

        calepinage = FauxCalepinage(roof_layout={
            'shading12x24': MATRICE_12X24,
            'zones': [{'id': 'PAN-A', 'label': 'PAN-A',
                       'geometry': {'solarAccess': {'values': [90.0]}}}],
        })
        resultat = {
            'version_moteur': 'calepinage-1.0.0',
            'pose': {'pans': [PANS_DEUX[0]]},
            'ombrage': {'par_pan': [{'pan': 'PAN-A',
                                     'acces_solaire_moyen_pct': 90.0,
                                     'motif_omission': ''}]},
            'production': {'par_pan': [{'pan': 'PAN-A', 'tof': 0.97,
                                        'tsrf': 0.94}]},
            'electrique': {},
            'simulation': _entete(),
        }
        ombrage = rapport_ombrage.construire_rapport_ombrage(
            calepinage, resultat=resultat, etat={})
        self._verifier(ombrage['provenance'])
        self.assertEqual(ombrage['provenance']['hash_entree'],
                         manuel['provenance']['hash_entree'])

    def test_asbuilt_ne_confond_plus_layout_hash(self):
        layout_hash = 'c' * 64
        self.assertNotEqual(layout_hash, self.empreinte)
        nu = SimpleNamespace(company=None, client_id=None, lead_id=None,
                             pk=None, titre='Villa Anfa',
                             layout_hash=layout_hash, version_moteur='',
                             resultat={'simulation': _entete()})
        document = _construire_document(
            nu, ecarts=ECARTS_3_PANS_1_RELEVE, photos=[], svg_planche='',
            site=SITE, identite=_identite('Document as-built'),
            styles=STYLES)
        self._verifier(document['provenance'])
        self.assertNotIn(layout_hash[:12], _html_de_document(document))

        # Jamais simulé : aucune empreinte de calcul imprimée — et surtout
        # pas celle du document de pose sous ce nom.
        jamais = SimpleNamespace(company=None, client_id=None, lead_id=None,
                                 pk=None, titre='Villa Anfa',
                                 layout_hash=layout_hash, version_moteur='',
                                 resultat=None)
        vide = _construire_document(
            jamais, ecarts=ECARTS_3_PANS_1_RELEVE, photos=[], svg_planche='',
            site=SITE, identite=_identite('Document as-built'),
            styles=STYLES)
        self.assertEqual(vide['provenance']['hash_entree'], '')
