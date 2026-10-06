# -*- coding: utf-8 -*-
"""ACAL313 — ``norme.coefficients_publies`` et
``p50p90.variabilite_interannuelle`` BRANCHÉES.

Constats C-ACAL-145 / C-ACAL-076. Les deux fonctions n'avaient aucun appelant
hors de leur module. Désormais :

* ``troncons_du_calepinage`` lit les coefficients de section/chute sur
  ``coefficients_publies`` (saisi société AVEC référence > noyau) — un
  coefficient saisi change la section calculée ;
* l'annexe « Hypothèses » du rapport imprime chaque coefficient APPLIQUÉ avec
  sa référence et sa source ;
* la composante météo de ``bloc_incertitude`` vient de
  ``variabilite_interannuelle`` (années OBSERVÉES), ``origine: 'observee'`` ;
  moins de deux années ⇒ composante omise, motif nommé (aucune valeur
  inventée, D-ACAL-7).

Run :
    python manage.py test apps.calepinage.tests.test_acal_norme_et_variabilite
"""
from __future__ import annotations

from django.test import SimpleTestCase

from apps.calepinage.services import troncons as service
from apps.calepinage.services.incertitude import (
    COMPOSANTE_METEO, bloc_incertitude,
)
from apps.calepinage.services.norme import (
    coefficients_publies, norme_applicable,
)
from apps.calepinage.services.rapport.annexe_hypotheses import (
    html_de_section,
)

REFERENCE_SAISIE = 'NF C 15-100 §525 — note interne du bureau d’études (essai)'

#: Un tronçon DC de 30 m sous 600 V portant 18 A.
DOCUMENT = {'electrical': {'cheminements': [
    {'id': 'ch1', 'cote': 'dc', 'de': 'n1', 'vers': 'n2',
     'longueurSaisieM': 30.0, 'points': []}]}}
COURANTS = {'ch1': {'ib_a': 18.0, 'tension_v': 600.0}}


def _norme(coefficients=None):
    section = {}
    if coefficients is not None:
        section['coefficients'] = coefficients
    return norme_applicable({'imagerie': {'pays': 'fr'},
                             'norme_electrique': section})


def _section(norme):
    paquet = service._troncons_du_document(
        DOCUMENT, {'norme': norme, 'courants': COURANTS})
    return paquet['troncons'][0]


class CoefficientsPubliesTest(SimpleTestCase):

    def test_coefficient_saisi_avec_reference_change_la_section_du_troncon(self):
        noyau = _section(_norme())
        saisi = _section(_norme({'chute_dc_cible_pct': {
            'valeur': 0.3, 'reference': REFERENCE_SAISIE}}))
        self.assertIsNotNone(noyau['section_mm2'])
        self.assertGreater(saisi['section_mm2'], noyau['section_mm2'])
        self.assertIn(REFERENCE_SAISIE, saisi['regle_source'])

        # Sans référence : refusé, le noyau s'applique (aucune valeur muette).
        valeurs, refus = coefficients_publies({'coefficients': {
            'chute_dc_cible_pct': {'valeur': 0.3}}})
        self.assertTrue(refus)
        self.assertEqual(valeurs['chute_dc_cible_pct']['source'], 'noyau')
        self.assertEqual(
            _section(_norme({'chute_dc_cible_pct': {'valeur': 0.3}}))
            ['section_mm2'], noyau['section_mm2'])

    def test_annexe_hypotheses_cite_la_reference(self):
        norme = _norme({'chute_dc_cible_pct': {
            'valeur': 0.3, 'reference': REFERENCE_SAISIE}})
        html = html_de_section({
            'resultat': {'norme': norme}, 'langue': 'fr',
            'section': {'code': 'hypotheses', 'motif_si_absent': ''}})
        self.assertIn('Coefficients de la norme électrique', html)
        self.assertIn('chute_dc_cible_pct', html)
        self.assertIn('NF C 15-100 §525', html)
        self.assertIn('saisi par la société', html)
        # Les coefficients du NOYAU sont cités aussi, avec leur texte.
        self.assertIn('UTE C 15-712-1', html)
        self.assertIn('jeu du moteur', html)

    def test_sans_norme_l_annexe_le_dit(self):
        norme = norme_applicable({'imagerie': {'pays': 'ma'},
                                  'norme_electrique': {}})
        html = html_de_section({
            'resultat': {'norme': norme}, 'langue': 'fr',
            'section': {'code': 'hypotheses', 'motif_si_absent': ''}})
        self.assertIn('aucune norme électrique sélectionnée', html)


class VariabiliteObserveeTest(SimpleTestCase):

    def _meteo(self, bloc):
        return next((c for c in bloc['composantes']
                     if c['nom'] == COMPOSANTE_METEO), None)

    def test_sigma_meteo_depuis_les_annees_observees(self):
        bloc = bloc_incertitude(
            10000.0, totaux_par_annee={2019: 9500.0, 2020: 10000.0,
                                       2021: 10500.0})
        meteo = self._meteo(bloc)
        self.assertIsNotNone(meteo)
        self.assertGreater(meteo['sigma_relatif'], 0.0)
        self.assertAlmostEqual(meteo['sigma_relatif'], 0.05, places=6)
        self.assertEqual(meteo['origine'], 'observee')
        self.assertEqual(meteo['annees'], 3)

    def test_une_seule_annee_omet_la_composante_nommee(self):
        bloc = bloc_incertitude(10000.0, totaux_par_annee={2020: 10000.0})
        self.assertIsNone(self._meteo(bloc))
        self.assertIsNone(bloc['sigma_total'])
        self.assertIn("une seule année", bloc['motif_refus'])
        self.assertIsNone(bloc['quantiles']['p90_kwh'])
