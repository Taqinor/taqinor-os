"""ACAL146 — fichier météo déposé : le fournisseur SAISI est conservé et
rejoué, le fichier retenu est servi (``GET meteo-fichier/``), et une pièce
d'une autre société n'est jamais lue.

Constat C-ACAL-073 : le fournisseur saisi au dépôt n'était stocké nulle
part — la simulation publiait ``meteo.fournisseur = null`` ; la pièce
« meteo/… » était cherchée SANS filtre société.

Base de test réelle, stockage MinIO de test réel (``stocker_image_toiture``),
client HTTP réel, simulation réelle (``simuler_calepinage``) ; seuls le
matériel et la section ``simulation`` des réglages sont injectés par le
helper documenté des livrables (le stock n'a pas de fiche ici).

Run :
    python manage.py test apps.calepinage.tests.test_acal_meteo_fichier_fournisseur -v2
"""
from __future__ import annotations

import copy

from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.calepinage.models import Calepinage
from apps.calepinage.selectors import resultat_servi
from apps.calepinage.services.simulation import (
    fichier_meteo_depose, simuler_calepinage,
)
from apps.records.models import Attachment

from .acal_livrables_helpers import patch_materiel
from .test_api_liste import BaseApiCalepinage
from .test_calx5_simulation import LAYOUT, MATERIEL, _ClientRejoue
from .test_calx62_meteo_fichier import _csv, _instants

BASE = '/api/django/calepinage/calepinages/'


class MeteoFichierFournisseurTest(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Météo 146',
            roof_layout=copy.deepcopy(LAYOUT))
        self.url = f'{BASE}{self.calepinage.pk}/meteo-fichier/'

    def _deposer(self, fournisseur='Meteonorm', nom='site.csv'):
        fichier = SimpleUploadedFile(
            nom, _csv(_instants(48)).encode('utf-8'), content_type='text/csv')
        reponse = self.api.post(self.url, {'fichier': fichier,
                                           'fournisseur': fournisseur},
                                format='multipart')
        self.assertEqual(reponse.status_code, 201, reponse.content[:300])
        return reponse.data

    def _simuler(self):
        with patch_materiel():
            return simuler_calepinage(
                self.calepinage, client=_ClientRejoue(), materiel=MATERIEL,
                enregistrer=True, forcer=True)['blocs']

    def test_fournisseur_rejoue_dans_la_simulation(self):
        self._deposer()

        blocs = self._simuler()

        self.assertEqual(blocs['meteo']['fournisseur'], 'Meteonorm')
        self.assertEqual(blocs['meteo']['fichier'],
                         {'nom': 'site.csv', 'fournisseur': 'Meteonorm'})
        entete = blocs['simulation']['meteo_fichier']
        self.assertTrue(entete['piece_jointe'])
        self.assertEqual(len(entete['sha256']), 64)

    def test_get_sert_le_fichier_retenu(self):
        vide = self.api.get(self.url)
        self.assertEqual(vide.status_code, 200)
        self.assertIsNone(vide.data)

        depot = self._deposer()
        servi = self.api.get(self.url)

        self.assertEqual(servi.status_code, 200, servi.content[:300])
        self.assertEqual(servi.data['piece_jointe'], depot['piece_jointe'])
        self.assertEqual(servi.data['fournisseur'], 'Meteonorm')
        self.assertEqual(servi.data['nom'], 'site.csv')
        self.assertEqual(len(servi.data['sha256']), 64)
        self.assertTrue(servi.data['depose_le'])
        # Même fournisseur et même empreinte que la simulation qui le lit.
        blocs = self._simuler()
        self.assertEqual(blocs['simulation']['meteo_fichier']['sha256'],
                         servi.data['sha256'])

    def test_nouveau_depot_perime_la_simulation(self):
        self._deposer()
        self._simuler()
        with patch_materiel():
            self.assertFalse(
                resultat_servi(self.calepinage)['simulation_perimee'])

        self._deposer(fournisseur='Solargis', nom='autre.csv')

        with patch_materiel():
            servi = resultat_servi(self.calepinage)
        self.assertTrue(servi['simulation_perimee'])

    def test_piece_meteo_d_une_autre_societe_jamais_lue(self):
        Attachment.objects.create(
            company=self.autre,
            content_type=ContentType.objects.get_for_model(Calepinage),
            object_id=self.calepinage.pk, file_key='meteo/x.csv',
            filename='x.csv', size=10, mime='text/csv')

        self.assertFalse(fichier_meteo_depose(self.calepinage))
        servi = self.api.get(self.url)
        self.assertEqual(servi.status_code, 200)
        self.assertIsNone(servi.data)
        blocs = self._simuler()
        self.assertIsNone(blocs['meteo']['fichier'])
        self.assertIsNone(blocs['simulation']['meteo_fichier'])
