# -*- coding: utf-8 -*-
"""CALX213 (crochet applicatif) — les trois paliers du ratio DC/AC arrivent.

Le noyau sait lire les trois paliers du ratio DC/AC dans les réglages société
depuis CALX213 (``core/electrique/onduleurs.py::bornes_dc_ac``) — mais
``services/chaines.py::evaluer_onduleurs`` appelait ``dimensionner_onduleurs``
SANS ``reglages`` : la borne société n'atteignait jamais le verdict, et le
seuil BAS (qui n'a aucune constante de repli) ne pouvait rien prononcer.

Ce fichier vérifie le CROCHET, pas le noyau :

* ``evaluer_onduleurs(conception, reglages=…)`` transmet la section
  ``electrique_societe`` telle quelle ;
* ``verdicts_electriques(conception, reglages=…)`` fait juger le verdict
  ``ratio_dc_ac`` par la borne SOCIÉTÉ quand elle est saisie ;
* sans réglage, le comportement d'aujourd'hui est strictement inchangé.

Le verdict est lu par son CODE (CALX215), jamais par sa position.

``SimpleTestCase`` : aucune base.

Run :
    python manage.py test \
        apps.calepinage.tests.test_calx213_crochet_reglages -v2
"""
from django.test import SimpleTestCase

from apps.calepinage.services.chaines import (
    concevoir_par_pan, evaluer_onduleurs,
)
from apps.calepinage.services.electrique import (
    temperatures_site, verdicts_electriques,
)
from apps.calepinage.services.parametres_cles import (
    SECTION_ELECTRIQUE_SOCIETE, registre,
)
from core.electrique.onduleurs import (
    BORNE_USUELLE_DC_AC, CLE_BORNE_USUELLE_DC_AC, CLE_SEUIL_BAS_DC_AC,
    SOURCE_CONVENTION_ATELIER,
)

MODULE = {
    'vmp_v': 41.5, 'voc_v': 49.6, 'isc_a': 18.4, 'imp_a': 17.1,
    'pmax_wc': 710.0, 'temp_coeff_voc_pct_c': -0.27,
    'temp_coeff_pmax_pct_c': -0.35,
}
ONDULEUR = {
    'n_mppt': 2, 'mppt_v_min': 150.0, 'mppt_v_max': 800.0,
    'v_max_abs': 1000.0, 'i_max_mppt_a': 26.0, 'isc_max_mppt_a': 45.0,
    'ac_kw': 10.0, 'phases': 3,
}

#: 18 × 710 Wc = 12,78 kWc sur 10 kW AC → ratio 1,278.
LAYOUT = {'version': 2, 'zones': [
    {'label': 'PAN-SUD', 'geometry': {'count': 18, 'azimuthDeg': 180.0,
                                      'tiltDeg': 15.0}}]}


def _conception():
    return concevoir_par_pan(
        LAYOUT, module_specs=MODULE, onduleur_specs=ONDULEUR,
        temperatures=temperatures_site(
            saisie={'temperature_min_c': -5.0, 'temperature_max_c': 70.0}),
        onduleur_designation='Onduleur d essai')


def _verdict(verdicts, code):
    for verdict in verdicts:
        if verdict['code'] == code:
            return verdict
    return None


class CrochetEvaluerOnduleursTest(SimpleTestCase):
    """La section société traverse le service jusqu'au noyau."""

    def test_sans_reglage_les_bornes_restent_celles_du_noyau(self):
        evaluation = evaluer_onduleurs(_conception())

        self.assertEqual(evaluation.bornes.borne_usuelle.valeur,
                         BORNE_USUELLE_DC_AC)
        self.assertEqual(evaluation.bornes.borne_usuelle.source,
                         SOURCE_CONVENTION_ATELIER)
        # Le seuil BAS n'a aucune constante : non saisi, il ne contrôle rien.
        self.assertIsNone(evaluation.bornes.seuil_bas.valeur)

    def test_une_borne_saisie_remplace_la_convention_d_atelier(self):
        evaluation = evaluer_onduleurs(_conception(), reglages={
            CLE_BORNE_USUELLE_DC_AC: {'valeur': 1.1, 'source': 'societe'}})

        self.assertEqual(evaluation.bornes.borne_usuelle.valeur, 1.1)
        self.assertEqual(evaluation.bornes.borne_usuelle.source, 'societe')

    def test_le_seuil_bas_saisi_prononce_enfin(self):
        evaluation = evaluer_onduleurs(_conception(), reglages={
            CLE_SEUIL_BAS_DC_AC: {'valeur': 1.5, 'source': 'societe'}})

        self.assertTrue(evaluation.bornes.seuil_bas.controlee)
        self.assertTrue(any('sous-utilisé' in message
                            for message in evaluation.alertes))

    def test_une_valeur_sans_source_ne_s_applique_pas(self):
        evaluation = evaluer_onduleurs(_conception(), reglages={
            CLE_BORNE_USUELLE_DC_AC: {'valeur': 1.1}})

        self.assertEqual(evaluation.bornes.borne_usuelle.valeur,
                         BORNE_USUELLE_DC_AC)


class CrochetVerdictsElectriquesTest(SimpleTestCase):
    """C'est la borne SOCIÉTÉ qui juge le verdict ``ratio_dc_ac``."""

    def test_sans_reglage_le_ratio_reste_dans_les_bornes(self):
        verdict = _verdict(verdicts_electriques(_conception()), 'ratio_dc_ac')

        # 1,278 sous la borne usuelle 1,35 du noyau.
        self.assertTrue(verdict['conforme'])

    def test_une_borne_societe_plus_stricte_fait_basculer_le_verdict(self):
        verdicts = verdicts_electriques(_conception(), reglages={
            CLE_BORNE_USUELLE_DC_AC: {'valeur': 1.1, 'source': 'societe'}})
        verdict = _verdict(verdicts, 'ratio_dc_ac')

        self.assertFalse(verdict['conforme'])
        self.assertIn('1,10', verdict['detail'])


class LesTroisClesSontAuRegistreTest(SimpleTestCase):
    """Aucune clé inventée : le registre CALX145/CALX213 les déclare."""

    def test_les_trois_paliers_figurent_a_la_section_electrique_societe(self):
        connues = registre(SECTION_ELECTRIQUE_SOCIETE)

        for cle in ('borne_usuelle_dc_ac', 'seuil_alerte_dc_ac',
                    'seuil_bas_dc_ac'):
            self.assertIn(cle, connues)
