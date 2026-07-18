"""NTPRO16 — Photos comparatives entrée/sortie.

Couvre : upload d'une photo sur un élément (`records.storage` MOCKÉ — ce test
ne dépend d'aucun accès MinIO réel), le proxy de téléchargement, et la
comparaison automatique entrée/sortie (résolution par nom_piece/élément,
embarquée SANS requête supplémentaire manuelle dans la réponse API).
"""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.immobilier.models import (
    Bail, Batiment, EtatLieuxImmo, Local, Locataire, Niveau,
    PhotoEtatLieux, Site,
)
from apps.immobilier.selectors import photos_entree_comparables
from apps.immobilier.services import (
    PhotoInvalideError, ajouter_photo_element, creer_bail, creer_etat_lieux,
)

User = get_user_model()

FAKE_META = {
    'file_key': 'attachments/1/fake.jpg', 'filename': 'photo.jpg',
    'size': 1234, 'mime': 'image/jpeg',
}


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntpro16PhotosEtatLieuxTests(TestCase):
    def setUp(self):
        self.co_a = make_company('immo-ph-a', 'Immo PH A')
        self.admin_a = make_user(self.co_a, 'immo-ph-admin-a')
        site = Site.objects.create(company=self.co_a, nom='Résidence')
        batiment = Batiment.objects.create(
            company=self.co_a, site=site, nom='Bât A')
        niveau = Niveau.objects.create(
            company=self.co_a, batiment=batiment, numero='RDC')
        local = Local.objects.create(
            company=self.co_a, niveau=niveau, reference='RDC-01',
            type_local=Local.TypeLocal.HABITATION)
        locataire = Locataire.objects.create(company=self.co_a, nom='Bennani')
        self.bail = creer_bail(
            company=self.co_a, local=local, locataire=locataire,
            type_bail=Bail.TypeBail.HABITATION, date_debut=date(2026, 1, 1),
            duree_mois=12, loyer_mensuel_ht=Decimal('3000.00'))

        self.etat_entree = creer_etat_lieux(
            self.bail, EtatLieuxImmo.Moment.ENTREE, date=date(2026, 1, 1))
        self.etat_sortie = creer_etat_lieux(
            self.bail, EtatLieuxImmo.Moment.SORTIE, date=date(2027, 1, 1))
        self.piece_entree = self.etat_entree.pieces.get(nom_piece='Cuisine')
        self.element_entree = self.piece_entree.elements.get(element='sol')
        self.piece_sortie = self.etat_sortie.pieces.get(nom_piece='Cuisine')
        self.element_sortie = self.piece_sortie.elements.get(element='sol')

    def test_ajouter_photo_element_service(self):
        upload = SimpleUploadedFile('sol.jpg', b'fake', content_type='image/jpeg')
        with patch(
            'apps.records.storage.store_attachment',
            return_value=(dict(FAKE_META), None),
        ) as mock_store:
            photo = ajouter_photo_element(
                self.element_entree, upload, uploaded_by=self.admin_a)
        mock_store.assert_called_once()
        self.assertEqual(photo.element_id, self.element_entree.id)
        self.assertEqual(photo.file_key, FAKE_META['file_key'])
        self.assertEqual(photo.company_id, self.co_a.id)

    def test_ajouter_photo_fichier_refuse_leve_erreur(self):
        upload = SimpleUploadedFile('x.exe', b'fake')
        with patch(
            'apps.records.storage.store_attachment',
            return_value=(None, 'Format non supporté.'),
        ):
            with self.assertRaises(PhotoInvalideError):
                ajouter_photo_element(self.element_entree, upload)

    def test_api_upload_photo(self):
        api = auth(self.admin_a)
        upload = SimpleUploadedFile('sol.jpg', b'fake', content_type='image/jpeg')
        with patch(
            'apps.records.storage.store_attachment',
            return_value=(dict(FAKE_META), None),
        ):
            resp = api.post(
                f'/api/django/immobilier/etats-lieux/{self.etat_entree.id}/'
                f'elements/{self.element_entree.id}/photos/',
                {'photo': upload}, format='multipart')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['filename'], 'photo.jpg')
        self.assertEqual(
            PhotoEtatLieux.objects.filter(element=self.element_entree).count(), 1)

    def test_api_upload_sans_fichier_400(self):
        api = auth(self.admin_a)
        resp = api.post(
            f'/api/django/immobilier/etats-lieux/{self.etat_entree.id}/'
            f'elements/{self.element_entree.id}/photos/',
            {}, format='multipart')
        self.assertEqual(resp.status_code, 400)

    def test_api_upload_element_dun_autre_etat_lieux_404(self):
        api = auth(self.admin_a)
        upload = SimpleUploadedFile('sol.jpg', b'fake', content_type='image/jpeg')
        with patch(
            'apps.records.storage.store_attachment',
            return_value=(dict(FAKE_META), None),
        ):
            resp = api.post(
                # element de l'état SORTIE, POSTé sur l'état ENTRÉE.
                f'/api/django/immobilier/etats-lieux/{self.etat_entree.id}/'
                f'elements/{self.element_sortie.id}/photos/',
                {'photo': upload}, format='multipart')
        self.assertEqual(resp.status_code, 404)

    def test_api_telecharger_photo_proxy(self):
        photo = PhotoEtatLieux.objects.create(
            company=self.co_a, element=self.element_entree,
            file_key='attachments/1/fake.jpg', filename='sol.jpg',
            mime='image/jpeg')
        api = auth(self.admin_a)
        with patch(
            'apps.records.storage.fetch_attachment',
            return_value=(b'%JPEGFAKE%', None),
        ):
            resp = api.get(
                f'/api/django/immobilier/etats-lieux/{self.etat_entree.id}/'
                f'photos/{photo.id}/download/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, b'%JPEGFAKE%')
        self.assertEqual(resp['Content-Type'], 'image/jpeg')

    def test_photos_entree_comparables_resout_par_nom_piece_et_element(self):
        photo_entree = PhotoEtatLieux.objects.create(
            company=self.co_a, element=self.element_entree,
            file_key='attachments/1/entree.jpg', filename='entree.jpg')
        resultats = photos_entree_comparables(self.element_sortie)
        self.assertEqual([p.id for p in resultats], [photo_entree.id])

    def test_photos_entree_vide_sur_element_dentree(self):
        # Comparer un élément D'ENTRÉE ne renvoie rien (rien à comparer
        # contre lui-même).
        PhotoEtatLieux.objects.create(
            company=self.co_a, element=self.element_entree,
            file_key='attachments/1/entree.jpg', filename='entree.jpg')
        resultats = photos_entree_comparables(self.element_entree)
        self.assertEqual(resultats, [])

    def test_photos_entree_vide_sans_photo_entree(self):
        resultats = photos_entree_comparables(self.element_sortie)
        self.assertEqual(resultats, [])

    def test_api_element_sortie_embarque_photos_entree_sans_requete_manuelle(self):
        PhotoEtatLieux.objects.create(
            company=self.co_a, element=self.element_entree,
            file_key='attachments/1/entree.jpg', filename='entree.jpg')
        api = auth(self.admin_a)
        resp = api.get(
            f'/api/django/immobilier/etats-lieux/{self.etat_sortie.id}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        cuisine = next(
            p for p in resp.data['pieces'] if p['nom_piece'] == 'Cuisine')
        sol = next(e for e in cuisine['elements'] if e['element'] == 'sol')
        self.assertEqual(len(sol['photos_entree']), 1)
        self.assertEqual(sol['photos_entree'][0]['filename'], 'entree.jpg')
