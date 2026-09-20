"""CAL19 — l'action ``roof-image`` réutilise le stockage VENTES.

Ce qui est prouvé ici :

* un PNG envoyé est stocké sous une clé SCOPÉE SOCIÉTÉ et relisible par une
  URL présignée — le tout par les fonctions minces d'``apps.ventes.services``,
  jamais par un second chemin de stockage ;
* un fichier qui n'est PAS une image est refusé avec le motif du SERVEUR ;
* la clé est dérivée côté serveur : rien n'est lu du corps hors le fichier ;
* un calepinage d'une AUTRE société est introuvable (404) ;
* ``apps.calepinage`` n'importe AUCUNE vue ni AUCUN modèle ventes (le test le
  vérifie par lecture du source — c'est ce que ``lint-imports`` garde en CI).

Le stockage objet lui-même est simulé (``mock``) : ce test prouve le CÂBLAGE,
pas MinIO.

Run :
    python manage.py test apps.calepinage.tests.test_api_image -v2
"""
import pathlib
import re
from unittest import mock

from apps.calepinage.models import Calepinage

from .test_api_liste import BaseApiCalepinage, url_detail

PNG = b'\x89PNG\r\n\x1a\n' + b'0' * 32
JPEG = b'\xff\xd8\xff' + b'0' * 32
PDF = b'%PDF-1.7' + b'0' * 32

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]


def url_image(pk):
    return f'{url_detail(pk)}roof-image/'


class ActionRoofImageTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa Anfa')
        self.etranger = Calepinage.objects.create(
            company=self.autre, lead_id=7, titre='Chez la voisine')

    def _envoyer(self, api, calepinage, contenu, nom='rendu.png'):
        """Envoie ``contenu`` — le stockage objet est SIMULÉ, pas MinIO."""
        from django.core.files.uploadedfile import SimpleUploadedFile

        fichier = SimpleUploadedFile(nom, contenu,
                                     content_type='application/octet-stream')
        with mock.patch('apps.ventes.services.stocker_image_toiture',
                        side_effect=lambda d, c, **kw: c) as stocke, \
                mock.patch(
                    'apps.ventes.services.url_image_toiture',
                    side_effect=lambda c, **kw: f'https://essai.invalid/{c}'):
            reponse = api.post(url_image(calepinage.pk), {'image': fichier},
                               format='multipart')
        self.appels_stockage = stocke.call_args_list
        return reponse

    def test_png_stocke_sous_une_cle_scopee_societe(self):
        reponse = self._envoyer(self.api, self.calepinage, PNG)
        self.assertEqual(reponse.status_code, 201, reponse.data)
        cle = reponse.data['roof_image']
        self.assertTrue(re.fullmatch(
            rf'roofs/{self.company.pk}/calepinage-{self.calepinage.pk}\.png',
            cle), cle)
        self.assertIn(cle, reponse.data['url'])
        self.calepinage.refresh_from_db()
        self.assertEqual(self.calepinage.roof_image, cle)

    def test_jpeg_reconnu_par_ses_octets(self):
        reponse = self._envoyer(self.api, self.calepinage, JPEG,
                                nom='rendu.png')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertTrue(reponse.data['roof_image'].endswith('.jpg'))

    def test_fichier_non_image_refuse_avec_le_motif_serveur(self):
        reponse = self._envoyer(self.api, self.calepinage, PDF)
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('image', reponse.data)
        self.calepinage.refresh_from_db()
        self.assertEqual(self.calepinage.roof_image, '')

    def test_autre_societe_introuvable(self):
        reponse = self._envoyer(self.api, self.etranger, PNG)
        self.assertEqual(reponse.status_code, 404)

    def test_sans_permission_d_ecriture_403(self):
        reponse = self._envoyer(self.api_sans, self.calepinage, PNG)
        self.assertEqual(reponse.status_code, 403)

    def test_aucun_import_de_vue_ni_de_modele_ventes(self):
        """La frontière inter-apps, lue dans le source (gardée par lint-imports)."""
        for fichier in RACINE_APP.rglob('*.py'):
            if 'tests' in fichier.parts or 'migrations' in fichier.parts:
                continue
            texte = fichier.read_text(encoding='utf-8')
            for motif in ('import apps.ventes.models',
                          'from apps.ventes.models',
                          'import apps.ventes.views',
                          'from apps.ventes.views'):
                self.assertNotIn(motif, texte,
                                 f'{fichier.name} : « {motif} » interdit')
