"""ACAL65 (C-ACAL-023) — la décision sur une suggestion de pente IGN, serveur.

``POST calepinages/<pk>/suggestions-pente/`` (proposer / accepter / refuser)
persiste la suggestion « pente du terrain » dans le pan, sous le jeton
``base_empreinte`` — SANS jamais écrire la pente du pan (D-ACAL-19) et sans
bloquer l'approbation.

Source réelle : ``services.lidar_ign`` + ``services.approbation`` + l'action
réelle, APIClient réel, base réelle. Seul l'altimètre IGN (le réseau
externe) est simulé, à la frontière.

Test-du-test : remettre ``pan['pitchDeg'] = trace['pitchDeg']`` dans
``accepter_suggestion`` ⇒ ``test_accepter_ne_touche_pas_la_pente_du_pan``
rougit.
"""
from __future__ import annotations

import copy
from unittest import mock

from apps.calepinage.models import Calepinage
from apps.calepinage.permissions import CAL_APPROUVER, CAL_GERER, CAL_VOIR
from apps.calepinage.services.layout import (
    empreinte_document, enregistrer_layout,
)
from apps.calepinage.services.parametres import enregistrer_parametres
from apps.roles.models import Role

from .test_api_liste import BaseApiCalepinage, User, url_detail

#: Un pan carré de ~20 m de côté près de Lyon (pays « fr »).
LON, LAT = 4.8357, 45.7640
COTE = 0.00025
DOCUMENT = {
    'version': 2,
    'zones': [{
        'id': 'z1', 'label': 'Pan sud', 'pitchDeg': 18,
        'vertices': [[LON, LAT], [LON + COTE, LAT],
                     [LON + COTE, LAT + COTE], [LON, LAT + COTE]],
    }],
}


def _altimetre_plan(points):
    """Un plan qui monte vers le nord (pente mesurable, hors réseau)."""
    return [0.2 * (lat - LAT) * 111000.0 for _lon, lat in points]


class SuggestionPenteApiTest(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        enregistrer_parametres(self.company, {'imagerie': {'pays': 'fr'}})
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='QA-ACAL65')
        enregistrer_layout(self.calepinage, copy.deepcopy(DOCUMENT),
                           user=self.user)
        self.url = f'{url_detail(self.calepinage.pk)}suggestions-pente/'
        self.url_layout = f'{url_detail(self.calepinage.pk)}layout/'

    def _lire(self):
        reponse = self.api.get(self.url_layout)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        return reponse.data

    def _poster(self, operation, base, api=None, **autres):
        corps = {'operation': operation, 'base_empreinte': base}
        corps.update(autres)
        with mock.patch('apps.calepinage.services.lidar_ign._altimetre_ign',
                        _altimetre_plan):
            return (api or self.api).post(self.url, corps, format='json')

    def _proposer(self):
        base = self._lire()['empreinte_document']
        reponse = self._poster('proposer', base)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        return reponse.data

    def _approuver(self):
        role = Role.objects.create(
            company=self.company, nom='Relecteur ACAL65',
            permissions=[CAL_VOIR, CAL_GERER, CAL_APPROUVER])
        relecteur = User.objects.create_user(
            username='acal65_relecteur', password='x', company=self.company,
            role=role)
        return self._client(relecteur).post(
            f'{url_detail(self.calepinage.pk)}approbation/',
            {'decision': 'approuve'}, format='json')

    def test_proposer_persiste_suggeree_sans_bloquer_l_approbation(self):
        donnees = self._proposer()
        pan = donnees['roof_layout']['zones'][0]
        self.assertEqual(pan['pitchSuggestion']['status'], 'suggeree')
        self.assertEqual(pan['pitchSuggestion']['libelle'],
                         'pente du terrain')
        self.assertIsInstance(pan['pitchSuggestion']['valeurDeg'], float)
        self.assertEqual(pan['pitchDeg'], 18)
        # Rouvrir : même état ; l'approbation reste possible.
        rouvert = self._lire()['roof_layout']['zones'][0]
        self.assertEqual(rouvert['pitchSuggestion'], pan['pitchSuggestion'])
        reponse = self._approuver()
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['etat'], 'approuve')

    def test_accepter_ne_touche_pas_la_pente_du_pan(self):
        donnees = self._proposer()
        valeur = donnees['roof_layout']['zones'][0][
            'pitchSuggestion']['valeurDeg']
        reponse = self._poster('accepter', donnees['empreinte_document'],
                               zone_id='z1')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        pan = reponse.data['roof_layout']['zones'][0]
        self.assertEqual(pan['pitchSuggestion']['status'], 'validee')
        self.assertEqual(pan['pitchSuggestion']['valeurDeg'], valeur)
        self.assertEqual(pan['pitchDeg'], 18)
        self.assertNotIn('facingAzimuthDeg', pan)
        self.assertNotIn('facingManual', pan)
        rouvert = self._lire()['roof_layout']['zones'][0]
        self.assertEqual(rouvert['pitchSuggestion']['status'], 'validee')
        self.assertEqual(rouvert['pitchDeg'], 18)

    def test_refuser_persiste_refusee(self):
        donnees = self._proposer()
        reponse = self._poster('refuser', donnees['empreinte_document'],
                               zone_id='z1')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        pan = self._lire()['roof_layout']['zones'][0]
        self.assertEqual(pan['pitchSuggestion']['status'], 'refusee')
        self.assertEqual(pan['pitchDeg'], 18)

    def test_base_perimee_409(self):
        donnees = self._proposer()
        # Un autre écrivain modifie le document : le jeton lu est périmé.
        modifie = copy.deepcopy(donnees['roof_layout'])
        modifie['zones'][0]['label'] = 'Pan sud (renommé)'
        enregistrer_layout(self.calepinage, modifie, user=self.user)
        self.assertNotEqual(empreinte_document(modifie),
                            donnees['empreinte_document'])
        reponse = self._poster('accepter', donnees['empreinte_document'],
                               zone_id='z1')
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertEqual(reponse.data['code'], 'document_modifie')
        pan = self._lire()['roof_layout']['zones'][0]
        self.assertEqual(pan['pitchSuggestion']['status'], 'suggeree')

    def test_societe_hors_france_403_sans_ecriture(self):
        enregistrer_parametres(self.company, {'imagerie': {'pays': 'ma'}})
        avant = self._lire()
        reponse = self._poster('proposer', avant['empreinte_document'])
        self.assertEqual(reponse.status_code, 403, reponse.data)
        self.assertEqual(self._lire()['roof_layout'], avant['roof_layout'])

    def test_operation_inconnue_et_jeton_manquant_400(self):
        base = self._lire()['empreinte_document']
        self.assertEqual(self._poster('effacer', base).status_code, 400)
        reponse = self.api.post(self.url, {'operation': 'proposer'},
                                format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('base_empreinte', reponse.data)

    def test_autre_societe_404(self):
        base = self._lire()['empreinte_document']
        reponse = self._poster('proposer', base, api=self.api_autre)
        self.assertEqual(reponse.status_code, 404)
