# -*- coding: utf-8 -*-
"""D-ACAL-169 (rejeu) — le panneau par défaut DÉSIGNÉ et le devis automatique.

Constat du rejeu : 715 Wc désigné (fiche Isc 22,30 A), « Devis automatique »
compose le CS 710W et aucun écran ne dit pourquoi. Cause : le couple
panneau / onduleur (PVCOMPAT, ``composition_residentielle``) juge le 715
INCOMPATIBLE avec les deux 5 kW (Isc 22,3 A > 22,0 A publiés par entrée) et
le remplace par le 710 ; la sonde de wattage (``etape_composer.sonder_wattage``)
jetait l'avertissement, le balayage tournait à 710 et la décision perdait le
désigné sans rien dire. La quantité en stock n'y entre pas.

Run :
    python manage.py test apps.ventes.tests.test_panneau_defaut_rejeu -v 2
"""
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from apps.ventes.tests.test_pvcompat_verdicts import (
    _batterie, _FausseFiche, _FauxProduit, _onduleur, _onduleur_5k_mono, _panneau_710)

DESIGNE_ID = 1165
NOM_715 = 'Panneau Canadien Solar 715W'
_RESUME = 'apps.stock.selectors_panneau_defaut.resume_panneau_par_defaut'
_REGLAGES = 'apps.ventes.domain.etape_composer.reglages_de_composition'


def _panneau_715(isc):
    """Le 715 désigné : fiche du rejeu (Isc 22,30 A) ou une fiche qui passe (18,0 A). Stock à 0 :
    la quantité n'est pas un critère."""
    return _FauxProduit(DESIGNE_ID, NOM_715, prix_vente='1200', quantite_stock=0, fiche=_FausseFiche(
        'module', pmax_wc=Decimal('715.00'), voc_v=Decimal('48.50'), vmp_v=Decimal('40.60'),
        isc_a=Decimal(isc), imp_a=Decimal('17.60'), temp_coeff_voc_pct_c=Decimal('-0.250'),
        temp_coeff_pmax_pct_c=Decimal('-0.290'), longueur_mm=2384, largeur_mm=1303))


def _onduleur_reseau_5k():
    """L'onduleur réseau 5 kW mono du rejeu : 22,0 A d'Isc maxi par entrée, 90-560 V, 600 V absolus."""
    return _onduleur(55, 'Onduleur réseau Huawei 5kW Monophasé', ond_ac_kw=Decimal('5.00'), ond_phases=1,
                     ond_mppt_v_min=Decimal('90.0'), ond_mppt_v_max=Decimal('560.0'),
                     ond_v_max_abs=Decimal('600.0'), ond_v_demarrage_v=Decimal('90.0'),
                     ond_i_max_mppt_a=Decimal('22.0'), ond_isc_max_mppt_a=Decimal('22.0'),
                     ond_bat_aucune=True, ond_bat_v_min=None, ond_bat_v_max=None)


def _catalogue(isc):
    return [_panneau_710(pk=1070, nom='Panneau Canadien Solar 710W'), _panneau_715(isc),
            _onduleur_reseau_5k(), _onduleur_5k_mono(), _batterie()]


def _reglages(isc):
    return SimpleNamespace(catalogue=_catalogue(isc), marques={}, ordre_lignes=None)


def _resume():
    return {'produit_id': DESIGNE_ID, 'nom': NOM_715, 'pmax_wc': 715, 'source': 'designe', 'motif': None}


class LaCompositionDitPourquoiElleRemplaceLeDefaut(SimpleTestCase):
    """``composition_residentielle`` — le point d'entrée réel des lignes."""

    def _composer(self, isc):
        from apps.ventes.domain.composition_residentielle import composition_residentielle
        avertissements = []
        lignes = composition_residentielle(
            _catalogue(isc), kwc=4.29, panel_watt=715, nb_panneaux=6, avec_batterie=True,
            avertissements=avertissements, panneau_prefere_id=DESIGNE_ID)
        return lignes, [ligne.designation for ligne in lignes]

    def test_eligible_le_designe_est_compose_a_sa_puissance(self):
        lignes, designations = self._composer('18.00')
        self.assertIn(NOM_715, designations)
        self.assertNotIn('Panneau Canadien Solar 710W', designations)
        self.assertIn(DESIGNE_ID, [getattr(ligne.produit, 'pk', None) for ligne in lignes])
        self.assertEqual(lignes.panel_watt_reel, 715)
        self.assertIsNone(lignes.panneau_prefere_refuse)

    def test_incompatible_le_designe_est_remplace_et_la_raison_est_nommee(self):
        lignes, designations = self._composer('22.30')
        self.assertIn('Panneau Canadien Solar 710W', designations)
        self.assertNotIn(NOM_715, designations)
        raison = lignes.panneau_prefere_refuse
        self.assertIn('« Onduleur hybride Deye 5kW Monophasé »', raison)
        self.assertIn('22,3 A', raison)


class LeDevisAutomatiqueDitPourquoiLeDefautNEstPasRetenu(SimpleTestCase):
    """``decisions.decider_taille_residentielle`` — le moteur horaire dimensionne sur la sonde réelle
    (``sonder_wattage`` → composition) ; la décision sert la raison au vendeur (journal ``alertes``)."""

    def _decider(self, isc):
        from apps.ventes.conception.decisions import decider_taille_residentielle
        from apps.ventes.domain.etape_composer import contexte_sonde_neuf, sonder_wattage
        reglages = _reglages(isc)

        def dimensionner(*, lead, company, phase):
            # Le balayage de tailles : sonde du contexte NEUF (panneau par défaut), comme balayer_tailles.
            watt = sonder_wattage(contexte_sonde_neuf(company=company, reglages=reglages, phase=phase))
            return 6, watt, 'moteur_horaire', None

        lead = SimpleNamespace(taille_souhaitee_kwc=None, batterie_souhaitee='sans', phase='')
        with mock.patch(_RESUME, return_value=_resume()), \
                mock.patch(_REGLAGES, return_value=reglages), \
                mock.patch('apps.ventes.etude_horaire.controle_kwh_declare_du_lead', return_value=None), \
                mock.patch('apps.ventes.domain.taille.phase_et_isolement_du_lead', return_value=(None, False)), \
                mock.patch('apps.ventes.domain.geometrie.zone_toit_depuis_contour', return_value=None):
            return decider_taille_residentielle(lead=lead, company=SimpleNamespace(pk=1),
                                                dimensionner=dimensionner)

    def _alertes(self, decision):
        return [a for a in decision.journal.get('alertes', []) if a.get('code') == 'panneau_par_defaut']

    def test_eligible_le_devis_automatique_retient_le_designe(self):
        decision = self._decider('18.00')
        self.assertEqual((decision.watt, decision.panneau_prefere_id), (715, DESIGNE_ID))
        self.assertEqual(self._alertes(decision), [])

    def test_incompatible_regle_d_aujourd_hui_et_raison_servie(self):
        decision = self._decider('22.30')
        self.assertEqual((decision.watt, decision.panneau_prefere_id), (710, None))
        alertes = self._alertes(decision)
        self.assertEqual(len(alertes), 1, decision.journal)
        message = alertes[0]['message']
        self.assertIn('« %s »' % NOM_715, message)
        self.assertIn('« Onduleur réseau Huawei 5kW Monophasé »', message)
        self.assertIn('22,3 A', message)
