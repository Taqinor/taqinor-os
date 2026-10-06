"""ACAL256 — les réglages société de dégagement entrent dans le compte moteur.

Constat C-ACAL-033 : ``ParametresCalepinage.degagements`` (retrait de rive,
allée technique, dégagement par type) n'atteignait JAMAIS le compte de modules
serveur (``compte_moteur_du_layout``, AOF164) : l'entrée villa posait toujours
``RETRAIT_VILLA_M`` et ignorait le type des obstacles, et
``services/traduction.entree_depuis_layout`` — qui applique ces règles — n'avait
aucun appelant. Drapeau ``USE_MOTEUR_CALEPINAGE`` levé : chaque pan passe par
le traducteur avec la section de la société (et l'allée propre au document) ;
drapeau baissé : l'appel d'hier, au bit près.

Test-du-test : ne pas transmettre la section ``degagements`` au traducteur ⇒
le compte traduit (retrait atelier 0,50 m) n'est plus inférieur au compte
villa ⇒ ``test_retrait_societe_reduit_le_compte_moteur`` rougit.
"""
from __future__ import annotations

import math

from django.test import TestCase, override_settings

from apps.calepinage.services.parametres import enregistrer_parametres
from apps.ventes.services import compte_moteur_du_layout
from authentication.models import Company

_M_PAR_DEG = math.pi / 180.0 * 6378137.0


def _rectangle(lon0, lat0, largeur_m, hauteur_m):
    dlon = largeur_m / (_M_PAR_DEG * math.cos(math.radians(lat0))) / 2.0
    dlat = hauteur_m / _M_PAR_DEG / 2.0
    return [[lon0 - dlon, lat0 - dlat], [lon0 + dlon, lat0 - dlat],
            [lon0 + dlon, lat0 + dlat], [lon0 - dlon, lat0 + dlat]]


def _layout(**racine):
    """Un toit plat de 14 × 10 m plein sud, cotes du module dans le document
    (mêmes cotes que le kit villa 720 Wc : seul le dégagement diffère)."""
    document = {
        'version': 2,
        'pin': {'lat': 33.5, 'lng': -7.6},
        'panelWatt': 720,
        'panelLengthM': 2.384,
        'panelWidthM': 1.303,
        'zones': [{
            'id': 'Z1', 'label': 'Toit principal', 'roofType': 'flat',
            'pitchDeg': 0, 'facingAzimuthDeg': 180, 'obstacles': [],
            'vertices': _rectangle(-7.6, 33.5, 14.0, 10.0),
        }],
    }
    document.update(racine)
    return document


class DegagementsSocieteCompteTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.reglee = Company.objects.create(nom='ACAL256 réglée',
                                            slug='acal256-reglee')
        cls.muette = Company.objects.create(nom='ACAL256 muette',
                                            slug='acal256-muette')
        enregistrer_parametres(cls.reglee, {'degagements': {
            'retrait_rive_m': 1.2, 'allee_technique_m': 1.2,
            'source': 'Consigne ACAL256'}})

    @override_settings(USE_MOTEUR_CALEPINAGE=True)
    def test_retrait_societe_reduit_le_compte_moteur(self):
        sans = compte_moteur_du_layout(_layout(), company=self.muette)
        avec = compte_moteur_du_layout(_layout(), company=self.reglee)
        self.assertIsNotNone(sans)
        self.assertIsNotNone(avec)
        self.assertGreater(sans['modules'], 0)
        self.assertLess(avec['modules'], sans['modules'])
        # La provenance des règles voyage avec le pan.
        pan = avec['pans'][0]
        self.assertIn('1.20 m', pan['regle_retrait'])
        self.assertIn('Consigne ACAL256', pan['regle_retrait'])
        self.assertIn('1.20 m', pan['regle_allee'])
        # Sans réglage, le repli d'hier (entrée villa) : aucune règle publiée.
        self.assertNotIn('regle_retrait', sans['pans'][0])

    @override_settings(USE_MOTEUR_CALEPINAGE=True)
    def test_allee_du_document_avant_celle_de_la_societe(self):
        mesure = compte_moteur_du_layout(
            _layout(alleeTechnique={'largeurM': 2.0}), company=self.reglee)
        self.assertIn('2.00 m', mesure['pans'][0]['regle_allee'])
        self.assertIn('saisie sur ce calepinage',
                      mesure['pans'][0]['regle_allee'])

    @override_settings(USE_MOTEUR_CALEPINAGE=False)
    def test_drapeau_off_bit_identique(self):
        hier = compte_moteur_du_layout(_layout())
        reglee = compte_moteur_du_layout(_layout(), company=self.reglee)
        muette = compte_moteur_du_layout(_layout(), company=self.muette)
        self.assertEqual(reglee, hier)
        self.assertEqual(muette, hier)
        self.assertNotIn('regle_retrait', reglee['pans'][0])
