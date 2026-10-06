"""ACAL148 — « Retirer le fichier météo » : la pièce part à la corbeille, le
retour à PVGIS est tracé au journal, la simulation devient périmée ; un
nouveau dépôt dit qu'il REMPLACE l'ancien (D-ACAL-26).

Constat C-ACAL-073 : un fichier météo déposé ne pouvait ni être retiré ni être
remplacé en le sachant — la simulation lisait « le dernier » sans le dire.

Base de test réelle, stockage MinIO de test réel (``stocker_image_toiture``),
client HTTP réel, simulation réelle (``simuler_calepinage``) ; seuls le
matériel et la section ``simulation`` des réglages sont injectés par le helper
documenté des livrables. Le client PVGIS est REJOUÉ (``_ClientRejoue``) : il
compte les appels, ce qui prouve que la simulation suivante repart sur PVGIS.

Run :
    python manage.py test apps.calepinage.tests.test_acal_meteo_fichier_retrait -v2
"""
from __future__ import annotations

import copy

from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.calepinage.models import Calepinage
from apps.calepinage.selectors import resultat_servi
from apps.calepinage.services.simulation import simuler_calepinage
from apps.records.models import Activity, Attachment
from apps.trash.selectors import entree_active
from apps.trash.services import restaurer

from .acal_livrables_helpers import patch_materiel
from .test_api_liste import BaseApiCalepinage
from .test_calx5_simulation import LAYOUT, MATERIEL, _ClientRejoue
from .test_calx62_meteo_fichier import _csv, _instants

BASE = '/api/django/calepinage/calepinages/'


class MeteoFichierRetraitTest(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Météo 148',
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

    def _simuler(self, client=None):
        with patch_materiel():
            return simuler_calepinage(
                self.calepinage, client=client or _ClientRejoue(),
                materiel=MATERIEL, enregistrer=True, forcer=True)['blocs']

    def _journal(self):
        return [a.body for a in Activity.objects.filter(
            content_type=ContentType.objects.get_for_model(Calepinage),
            object_id=self.calepinage.pk)]

    def test_retrait_met_a_la_corbeille_et_trace(self):
        depot = self._deposer(nom='site.csv')
        piece = Attachment.objects.get(pk=depot['piece_jointe'])

        reponse = self.api.delete(self.url)

        self.assertEqual(reponse.status_code, 204, reponse.content[:300])
        # Jamais de suppression dure : la ligne existe toujours, en corbeille.
        self.assertTrue(Attachment.objects.filter(pk=piece.pk).exists())
        element = entree_active(piece)
        self.assertIsNotNone(element)
        self.assertEqual(element.supprime_par, self.user)
        # Le journal du calepinage porte la ligne, auteur posé par le serveur.
        self.assertIn('Fichier météo retiré : site.csv — retour à PVGIS',
                      self._journal())
        entree = Activity.objects.filter(
            object_id=self.calepinage.pk,
            body='Fichier météo retiré : site.csv — retour à PVGIS').first()
        self.assertEqual(entree.created_by, self.user)
        # GET meteo-fichier/ → null.
        servi = self.api.get(self.url)
        self.assertEqual(servi.status_code, 200)
        self.assertIsNone(servi.data)

    def test_retrait_sans_fichier_retenu_404_nomme(self):
        reponse = self.api.delete(self.url)

        self.assertEqual(reponse.status_code, 404)
        self.assertEqual(reponse.data['detail'],
                         "Aucun fichier météo n'est rattaché à ce calepinage.")

    def test_retrait_deux_fois_la_seconde_est_404(self):
        self._deposer()
        self.assertEqual(self.api.delete(self.url).status_code, 204)

        self.assertEqual(self.api.delete(self.url).status_code, 404)

    def test_retrait_reserve_a_la_gestion(self):
        self._deposer()

        reponse = self.api_sans.delete(self.url)

        self.assertEqual(reponse.status_code, 403)
        self.assertIsNotNone(self.api.get(self.url).data)

    def test_simulation_perimee_apres_retrait(self):
        self._deposer()
        self._simuler()
        with patch_materiel():
            self.assertFalse(
                resultat_servi(self.calepinage)['simulation_perimee'])

        self.assertEqual(self.api.delete(self.url).status_code, 204)

        with patch_materiel():
            servi = resultat_servi(self.calepinage)
        self.assertTrue(servi['simulation_perimee'])

    def test_simulation_suivante_sur_pvgis(self):
        self._deposer()
        self.assertEqual(self.api.delete(self.url).status_code, 204)
        client = _ClientRejoue()

        blocs = self._simuler(client)

        # PVGIS est interrogé (client rejoué) et aucun fichier n'est lu.
        self.assertGreater(len(client.demandes), 0)
        self.assertIsNone(blocs['meteo']['fichier'])
        self.assertIsNone(blocs['simulation']['meteo_fichier'])

    def test_nouveau_depot_annonce_le_remplacement(self):
        premier = self._deposer(nom='ancien.csv')
        ancienne = Attachment.objects.get(pk=premier['piece_jointe'])

        second = self._deposer(fournisseur='Solargis', nom='nouveau.csv')

        # Rien à remplacer au premier dépôt.
        self.assertIsNone(premier['remplace'])
        # Le second dit ce qu'il remplace : nom et date du dépôt.
        self.assertEqual(second['remplace']['nom'], 'ancien.csv')
        self.assertEqual(second['remplace']['depose_le'],
                         ancienne.created_at.isoformat())
        # L'ancien est à la corbeille, tracé ; le retenu est le nouveau.
        self.assertIsNotNone(entree_active(ancienne))
        self.assertTrue(Attachment.objects.filter(pk=ancienne.pk).exists())
        self.assertTrue(any('Fichier météo remplacé : ancien.csv par '
                            'nouveau.csv' in ligne
                            for ligne in self._journal()))
        servi = self.api.get(self.url)
        self.assertEqual(servi.data['nom'], 'nouveau.csv')
        self.assertEqual(servi.data['piece_jointe'], second['piece_jointe'])

    def test_piece_restaurable_depuis_la_corbeille(self):
        depot = self._deposer(nom='site.csv')
        piece = Attachment.objects.get(pk=depot['piece_jointe'])
        self.assertEqual(self.api.delete(self.url).status_code, 204)

        restaurer(entree_active(piece), user=self.user)

        servi = self.api.get(self.url)
        self.assertEqual(servi.data['piece_jointe'], piece.pk)

    def test_retrait_d_un_calepinage_voisin_est_introuvable(self):
        self._deposer()

        reponse = self.api_autre.delete(self.url)

        self.assertEqual(reponse.status_code, 404)
        self.assertIsNotNone(self.api.get(self.url).data)
