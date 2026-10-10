"""ACAL259 — UN SEUL « modules posés / kWc » dans les livrables et écrans du
module (constats C-ACAL-118, C-ACAL-035).

Le calepinage QA-CAL-RT : pan zA pavé (``geometry.count`` 30, un
``geometry.kwc`` d'OUTIL calculé à 720 W), pan zB dessiné SANS géométrie
(``neededPanels`` 6 — jamais un compte posé), fiche du module 710 Wc,
``panelWatt`` de l'outil 720. Puis un champ au sol de 340 modules.

Tous les lecteurs rendent le MÊME total, celui de
``services/mesures.py:mesures_du_document`` : 30 modules, 30 × 0,710 =
21,3 kWc (zB : 0, motif « non pavé »), et 340 pour le champ au sol.

Le résultat vient de la VRAIE chaîne : ``electrique.resultat_calepinage``
(``GET resultat/``, bloc ``pose`` = ``chaines.bloc_pose``, fiche du module du
cas CALX5 à 710 Wc) ; pour le champ au sol, ``bloc_pose`` sur la conception
réelle. ``selectors._mesures_variante`` est hors du périmètre de la tâche.

Run :
    python manage.py test apps.calepinage.tests.test_acal_parite_compte_modules -v2
"""
from __future__ import annotations

import copy
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from apps.calepinage.serializers import peremption_du_calepinage
from apps.calepinage.services import (
    asbuilt, comparaison_projets, diff_versions, export_projet, journal,
    lestage, reglementaire,
)
from apps.calepinage.services.chaines import bloc_pose
from apps.calepinage.services.documents.presentation_compacte import (
    construire_presentation,
)
from apps.calepinage.services.electrique import (
    conception_du_calepinage, resultat_calepinage,
)
from apps.calepinage.services.mesures import (
    MOTIF_NON_PAVE, mesures_du_document,
)

from .test_calx5_simulation import MATERIEL, REGLAGES, _Calepinage

STYLES = {'nom_affiche': 'Soleil Atlas', 'logo_url': '',
          'couleur_primaire': '', 'couleur_secondaire': ''}

#: QA-CAL-RT — zA pavé (30), zB non pavé (neededPanels 6), outil à 720 W.
QA_CAL_RT = {
    'version': 2,
    'pin': {'lat': 33.5731, 'lng': -7.5898},
    'panelWatt': 720,
    'zones': [
        {'id': 'zA', 'label': 'zA',
         'geometry': {'count': 30, 'kwc': 21.6, 'azimuthDeg': 180.0,
                      'tiltDeg': 15.0, 'family': 'surimposition'}},
        {'id': 'zB', 'label': 'zB', 'neededPanels': 6},
    ],
}

#: Un champ au sol de 340 modules (fiche 710 Wc).
SOL_340 = {
    'version': 2,
    'pin': {'lat': 33.5731, 'lng': -7.5898},
    'zones': [],
    'poseSurfaces': [{
        'id': 'champ-1', 'kind': 'sol', 'label': 'Champ sud',
        'moduleWc': 710, 'tiltDeg': 20, 'rowAzimuthDeg': 90,
        'engine': {'modules': 340},
    }],
}


def _pivot(layout):
    return _Calepinage(layout=copy.deepcopy(layout))


def _lecteurs(layout, resultat):
    """``{lecteur: (modules, kwc)}`` — ``kwc`` vaut ``...`` pour un lecteur
    qui ne publie que le compte."""
    pivot = _pivot(layout)
    pivot.resultat = resultat
    lus = {}

    totaux = construire_presentation(
        SimpleNamespace(company=None, pk=None, titre='QA-CAL-RT',
                        roof_layout=layout, resultat=None, layout_hash='',
                        version_moteur=''),
        resultat=resultat, roof_layout=layout, svg_planche='',
        styles=STYLES)['totaux']
    lus['presentation_compacte'] = (totaux['total_modules'],
                                    totaux['total_kwc'])

    infos = reglementaire.infos_du_calepinage(
        SimpleNamespace(company=None, client=None, roof_layout=layout),
        resultat=resultat)
    lus['reglementaire'] = (infos['nombre_modules'], infos['puissance_kwc'])

    prevus, _source = asbuilt._pans_prevus(
        SimpleNamespace(roof_layout=layout))
    lus['asbuilt'] = (sum(p['modules'] for p in prevus), ...)

    masse = lestage.masse_du_layout(layout)
    lus['lestage'] = (masse['total_modules'], ...)

    lus['journal'] = (int(journal._modules(layout)), ...)

    grandeurs = diff_versions._grandeurs(SimpleNamespace(
        roof_layout=layout, resultat=resultat, version_moteur=''))
    lus['diff_versions'] = (grandeurs['modules'][1], grandeurs['kwc'][1])

    lus['comparaison_projets'] = comparaison_projets._mesures_du_calepinage(
        pivot, simule=True)

    lus['export_projet'] = (export_projet._modules_du_document(layout), ...)

    calepinage = SimpleNamespace(roof_layout=layout)
    with mock.patch('apps.ventes.selectors.peremption_layout_devis',
                    return_value={'layout_stale': None,
                                  'conception_divergente': None,
                                  'layout_nb_panneaux': 999,
                                  'calepinage_nb_panneaux': 999}):
        badge = peremption_du_calepinage(SimpleNamespace(), calepinage)
    lus['serializers'] = (badge['layout_nb_panneaux'], ...)
    return lus


class PariteCompteModulesTest(SimpleTestCase):

    def _verifier(self, lus, modules, kwc):
        self.assertEqual(len(lus), 9, sorted(lus))
        for lecteur, (compte, puissance) in lus.items():
            self.assertEqual(compte, modules, lecteur)
            if puissance is not ...:
                self.assertEqual(puissance, kwc, lecteur)

    def test_meme_total_tous_lecteurs(self):
        servi = resultat_calepinage(_pivot(QA_CAL_RT), materiel=MATERIEL,
                                    reglages=REGLAGES)
        # La vraie chaîne : 30 modules à la fiche 710 Wc (jamais 720).
        self.assertEqual(servi['pose']['total_modules'], 30)
        self.assertEqual(servi['pose']['kwc'], 21.3)

        mesures = mesures_du_document(QA_CAL_RT, servi)
        self.assertEqual((mesures['modules'], mesures['kwc']), (30, 21.3))
        zb = next(p for p in mesures['pans'] if p['pan'] == 'zB')
        self.assertEqual((zb['modules'], zb['kwc'], zb['motif']),
                         (0, None, MOTIF_NON_PAVE))

        self._verifier(_lecteurs(QA_CAL_RT, servi), 30, 21.3)

    def test_champ_au_sol_340_partout(self):
        pivot = _pivot(SOL_340)
        conception = conception_du_calepinage(pivot, materiel=MATERIEL)[0]
        resultat = {'pose': bloc_pose(conception)}
        self.assertEqual(resultat['pose']['total_modules'], 340)

        self._verifier(_lecteurs(SOL_340, resultat), 340, 241.4)

    def test_sans_resultat_jamais_le_wattage_de_l_outil(self):
        # Document seul, sans fiche déclarée : le kWc n'est pas inventé
        # (jamais 30 × 720 W, jamais geometry.kwc).
        mesures = mesures_du_document(QA_CAL_RT)
        self.assertEqual(mesures['modules'], 30)
        self.assertIsNone(mesures['kwc'])
        # Fiche DÉCLARÉE par le document : modules × pmax de la fiche.
        avec_fiche = copy.deepcopy(QA_CAL_RT)
        avec_fiche['modules'] = [{'id': 'm710', 'pmaxWc': 710}]
        avec_fiche['zones'][0]['geometry']['moduleId'] = 'm710'
        self.assertEqual(mesures_du_document(avec_fiche)['kwc'], 21.3)
