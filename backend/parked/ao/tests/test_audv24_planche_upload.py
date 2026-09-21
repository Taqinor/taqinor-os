"""AUDV24 (DRAFT165-5, AOF140) — ``POST /ao/planches/upload/`` (multipart).

Constat qui motive ces tests : ``PlancheAO`` n'avait AUCUN ViewSet/serializer/
URL — ``services.generer_indice_planche`` existait déjà, testé en profondeur
(``test_aof_planches_indices.py``, non dupliqué ici), mais aucune route ne
l'appelait : un utilisateur ne pouvait pas verser une révision de planche par
l'API. Ce fichier couvre le nouveau chemin d'UPLOAD (empreinte SHA-256 du
FICHIER pilote le versionnement) + le câblage HTTP.

Run:
    python manage.py test apps.ao.tests.test_audv24_planche_upload -v 2
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ao import services
from apps.ao.models import AppelOffre, BatimentAO, PlancheAO, ToitureAO
from apps.records.models import Attachment
from apps.roles.models import DIRECTEUR_PERMISSIONS, Role
from authentication.models import Company

User = get_user_model()

URL = '/api/django/ao/planches/upload/'

#: Un PDF minimal : ce sont les octets magiques qui décident du format côté
#: stockage partagé, jamais l'extension du nom de fichier.
PDF_V1 = b'%PDF-1.4\nplanche 05 rev A\n%%EOF\n'
PDF_V2 = b'%PDF-1.4\nplanche 05 rev B (obstacle ecarte)\n%%EOF\n'


def _stockage_factice(mime='application/pdf'):
    """Remplace MinIO : compte les téléversements RÉELS, sans réseau."""
    ecrits = []

    def store(fichier, audio=False, company=None):
        donnees = fichier.read()
        ecrits.append(donnees)
        return ({'file_key': 'attachments/%s/planche-%d'
                 % (getattr(company, 'id', 0), len(ecrits)),
                 'filename': getattr(fichier, 'name', 'planche.pdf'),
                 'size': len(donnees), 'mime': mime}, None)
    return store, ecrits


class TestApiUploadPlanche(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='AUDV24 Co', slug='audv24-co')
        role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='audv24_user', password='x', company=self.company,
            role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-AUDV24-1', objet='Planches')
        batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=self.ao, code='C')
        self.toiture = ToitureAO.objects.create(
            company=self.company, batiment=batiment, code_document='05')

    @staticmethod
    def _fichier(contenu=PDF_V1, nom='planche.pdf'):
        return SimpleUploadedFile(nom, contenu, content_type='application/pdf')

    def _upload(self, store, contenu=PDF_V1, **extra):
        payload = {
            'appel_offre': self.ao.id, 'code_document': '05',
            'fichier': self._fichier(contenu),
        }
        payload.update(extra)
        with patch('apps.records.storage.store_attachment', store):
            return self.api.post(URL, payload, format='multipart')

    def test_premier_upload_cree_l_indice_A_avec_attachment(self):
        store, ecrits = _stockage_factice()
        r = self._upload(store)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['indice'], 'A')
        self.assertEqual(r.data['reference_complete'], '05A')
        self.assertIsNotNone(r.data['attachment'])
        attachement = Attachment.objects.get(pk=r.data['attachment'])
        self.assertEqual(attachement.company_id, self.company.id)
        self.assertEqual(attachement.uploaded_by_id, self.user.id)
        self.assertEqual(len(ecrits), 1)

    def test_meme_contenu_reenvoye_ne_cree_rien(self):
        store, ecrits = _stockage_factice()
        premier = self._upload(store)
        second = self._upload(store)  # même contenu PDF_V1
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(second.data['id'], premier.data['id'])
        self.assertEqual(second.data['indice'], 'A')
        self.assertEqual(PlancheAO.objects.count(), 1)
        self.assertEqual(len(ecrits), 1)  # aucun 2e téléversement réel

    def test_contenu_different_incremente_et_archive_l_ancienne(self):
        store, ecrits = _stockage_factice()
        premiere = self._upload(store, contenu=PDF_V1)
        seconde = self._upload(
            store, contenu=PDF_V2, motif='Obstacle écarté')
        self.assertEqual(seconde.status_code, 201, seconde.data)
        self.assertEqual(seconde.data['indice'], 'B')
        self.assertNotEqual(seconde.data['id'], premiere.data['id'])
        self.assertNotEqual(seconde.data['attachment'], premiere.data['attachment'])
        self.assertEqual(len(ecrits), 2)

        ancienne = PlancheAO.objects.get(pk=premiere.data['id'])
        self.assertEqual(ancienne.statut, PlancheAO.Statut.ARCHIVEE)
        nouvelle = PlancheAO.objects.get(pk=seconde.data['id'])
        self.assertEqual(nouvelle.statut, PlancheAO.Statut.ACTIVE)
        self.assertEqual(nouvelle.motif_revision, 'Obstacle écarté')
        self.assertEqual(
            nouvelle.empreinte, services.empreinte_fichier(PDF_V2))

    def test_sans_fichier_400_motive(self):
        r = self.api.post(URL, {
            'appel_offre': self.ao.id, 'code_document': '05',
        }, format='multipart')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('fichier', r.data)
        self.assertEqual(PlancheAO.objects.count(), 0)

    def test_format_refuse_par_le_stockage_400_motive(self):
        r = self.api.post(URL, {
            'appel_offre': self.ao.id, 'code_document': '05',
            'fichier': SimpleUploadedFile(
                'toiture.dxf', b'0\nSECTION\n2\nHEADER\n',
                content_type='application/dxf'),
        }, format='multipart')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('fichier', r.data)
        self.assertEqual(PlancheAO.objects.count(), 0)
        self.assertFalse(Attachment.objects.exists())

    def test_appel_offre_d_une_autre_societe_est_introuvable(self):
        autre = Company.objects.create(nom='AUDV24 X', slug='audv24-x')
        ao_autre = AppelOffre.objects.create(
            company=autre, reference='AO-AUDV24-X', objet='X')
        store, ecrits = _stockage_factice()
        with patch('apps.records.storage.store_attachment', store):
            r = self.api.post(URL, {
                'appel_offre': ao_autre.id, 'code_document': '05',
                'fichier': self._fichier(),
            }, format='multipart')
        self.assertEqual(r.status_code, 404, r.data)
        self.assertEqual(ecrits, [])
