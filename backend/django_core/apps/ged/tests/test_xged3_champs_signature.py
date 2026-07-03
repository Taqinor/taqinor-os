"""XGED3 — Zones de champs positionnées sur le PDF à signer (modèles de
signature).

Couvre :
  * placement d'un champ sur une demande (position en %, requis/optionnel) ;
  * garde exactement-une-cible (demande XOR modèle) ;
  * la page publique expose les champs positionnés (rétrocompatible : liste
    vide sans aucun champ) ;
  * remplissage : les champs `requis` (hors signature/initiales) doivent être
    fournis avant de signer, sinon 400 ;
  * l'aplatissement PDF final honore les positions (avec PyMuPDF) et dégrade
    proprement (annexe/inchangé) sans la lib ;
  * scoping société.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged import services
from apps.ged.models import (
    CHAMP_TYPE_CASE, CHAMP_TYPE_SIGNATURE, CHAMP_TYPE_TEXTE, Cabinet,
    ChampSignature, Document, DocumentVersion, Folder, SIGNATURE_SIGNE,
)

User = get_user_model()


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


class XGed3Base(TestCase):
    def setUp(self):
        self.co_a = make_company('xged3-a', 'Xged3 A')
        self.co_b = make_company('xged3-b', 'Xged3 B')
        self.admin_a = make_user(self.co_a, 'xged3-admin-a', 'admin')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Admin')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Dossier A')
        self.doc_a = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Contrat à signer')
        self.version_a = DocumentVersion.objects.create(
            company=self.co_a, document=self.doc_a, version=1,
            file_key='ged/xged3/doc-a.pdf', filename='doc-a.pdf',
            mime='application/pdf')
        self.demande = services.demander_signature(
            self.doc_a, signataire_nom='Jean Client',
            signataire_email='jean@example.com', company=self.co_a,
            created_by=self.admin_a)


class ModelGuardTests(XGed3Base):
    def test_exactly_one_target_required(self):
        champ = ChampSignature(
            company=self.co_a, demande=None, modele=None,
            type_champ=CHAMP_TYPE_SIGNATURE)
        with self.assertRaises(Exception):
            champ.full_clean()

    def test_champ_on_demande_valid(self):
        champ = ChampSignature.objects.create(
            company=self.co_a, demande=self.demande,
            type_champ=CHAMP_TYPE_SIGNATURE, page=0,
            x=10, y=20, largeur=30, hauteur=10)
        champ.full_clean()  # ne lève pas
        self.assertEqual(champ.demande_id, self.demande.id)


class ServiceTests(XGed3Base):
    def test_champs_pour_demande_empty_by_default(self):
        self.assertEqual(services.champs_pour_demande(self.demande).count(), 0)

    def test_enregistrer_valeurs_champs(self):
        champ = ChampSignature.objects.create(
            company=self.co_a, demande=self.demande,
            type_champ=CHAMP_TYPE_TEXTE, page=0)
        maj = services.enregistrer_valeurs_champs(
            self.demande, {str(champ.id): 'Fonction: Gérant'})
        self.assertEqual(len(maj), 1)
        champ.refresh_from_db()
        self.assertEqual(champ.valeur, 'Fonction: Gérant')

    def test_enregistrer_valeurs_ignores_signature_type(self):
        """Un champ `signature`/`initiales` n'est jamais rempli par
        enregistrer_valeurs_champs (il utilise la signature de la cérémonie)."""
        champ = ChampSignature.objects.create(
            company=self.co_a, demande=self.demande,
            type_champ=CHAMP_TYPE_SIGNATURE, page=0)
        maj = services.enregistrer_valeurs_champs(
            self.demande, {str(champ.id): 'ignored'})
        self.assertEqual(len(maj), 0)
        champ.refresh_from_db()
        self.assertEqual(champ.valeur, '')

    def test_signer_avec_champs_requiert_champs_requis(self):
        ChampSignature.objects.create(
            company=self.co_a, demande=self.demande,
            type_champ=CHAMP_TYPE_TEXTE, page=0, requis=True)
        with self.assertRaises(ValueError):
            services.signer_demande_publique_avec_champs(
                self.demande, consentement=True, signature_texte='Jean')

    def test_signer_avec_champs_fills_and_signs(self):
        champ = ChampSignature.objects.create(
            company=self.co_a, demande=self.demande,
            type_champ=CHAMP_TYPE_TEXTE, page=0, requis=True)
        with mock.patch('apps.records.storage.fetch_attachment',
                        return_value=(b'data', None)):
            demande = services.signer_demande_publique_avec_champs(
                self.demande, consentement=True, signature_texte='Jean',
                valeurs_champs={str(champ.id): 'Gérant'})
        self.assertEqual(demande.statut, SIGNATURE_SIGNE)
        champ.refresh_from_db()
        self.assertEqual(champ.valeur, 'Gérant')

    def test_signer_avec_champs_no_champs_is_backward_compatible(self):
        """Une demande SANS aucun champ signe exactement comme XGED1."""
        with mock.patch('apps.records.storage.fetch_attachment',
                        return_value=(b'data', None)):
            demande = services.signer_demande_publique_avec_champs(
                self.demande, consentement=True, signature_texte='Jean')
        self.assertEqual(demande.statut, SIGNATURE_SIGNE)

    def test_optional_field_not_required(self):
        ChampSignature.objects.create(
            company=self.co_a, demande=self.demande,
            type_champ=CHAMP_TYPE_CASE, page=0, requis=False)
        with mock.patch('apps.records.storage.fetch_attachment',
                        return_value=(b'data', None)):
            demande = services.signer_demande_publique_avec_champs(
                self.demande, consentement=True, signature_texte='Jean')
        self.assertEqual(demande.statut, SIGNATURE_SIGNE)


class FlattenPdfTests(XGed3Base):
    def test_flatten_without_pymupdf_degrades_to_original(self):
        champ = ChampSignature.objects.create(
            company=self.co_a, demande=self.demande,
            type_champ=CHAMP_TYPE_TEXTE, page=0, x=10, y=10)
        with mock.patch.dict('sys.modules', {'fitz': None}):
            out, aplati = services._flatten_champs_pdf(
                b'%PDF-1.4 fake', [champ])
        self.assertFalse(aplati)
        self.assertEqual(out, b'%PDF-1.4 fake')

    def test_rendre_pdf_signe_sans_champs_returns_original(self):
        with mock.patch('apps.records.storage.fetch_attachment',
                        return_value=(b'%PDF data', None)):
            out, aplati = services.rendre_pdf_signe_avec_champs(self.demande)
        self.assertEqual(out, b'%PDF data')
        self.assertFalse(aplati)

    def test_rendre_pdf_signe_storage_unavailable_returns_none(self):
        with mock.patch('apps.records.storage.fetch_attachment',
                        return_value=(None, 'unreachable')):
            out, aplati = services.rendre_pdf_signe_avec_champs(self.demande)
        self.assertIsNone(out)
        self.assertFalse(aplati)


class PublicApiTests(XGed3Base):
    def test_get_includes_champs(self):
        ChampSignature.objects.create(
            company=self.co_a, demande=self.demande,
            type_champ=CHAMP_TYPE_TEXTE, page=0)
        resp = self.client.get(
            f'/api/django/ged/signature/{self.demande.token}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['champs']), 1)

    def test_get_no_champs_empty_list(self):
        resp = self.client.get(
            f'/api/django/ged/signature/{self.demande.token}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['champs'], [])

    def test_post_signer_missing_required_champ_400(self):
        ChampSignature.objects.create(
            company=self.co_a, demande=self.demande,
            type_champ=CHAMP_TYPE_TEXTE, page=0, requis=True)
        resp = self.client.post(
            f'/api/django/ged/signature/{self.demande.token}/',
            {'action': 'signer', 'consentement': True,
             'signature_texte': 'Jean'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_post_signer_with_valeurs_champs_succeeds(self):
        champ = ChampSignature.objects.create(
            company=self.co_a, demande=self.demande,
            type_champ=CHAMP_TYPE_TEXTE, page=0, requis=True)
        with mock.patch('apps.records.storage.fetch_attachment',
                        return_value=(b'data', None)):
            resp = self.client.post(
                f'/api/django/ged/signature/{self.demande.token}/',
                {'action': 'signer', 'consentement': True,
                 'signature_texte': 'Jean',
                 'valeurs_champs': {str(champ.id): 'Gérant'}}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], SIGNATURE_SIGNE)


class ScopingApiTests(XGed3Base):
    def test_champ_signature_scoped_by_company(self):
        ChampSignature.objects.create(
            company=self.co_a, demande=self.demande,
            type_champ=CHAMP_TYPE_TEXTE, page=0)
        admin_b = make_user(self.co_b, 'xged3-admin-b', 'admin')
        resp = auth(admin_b).get('/api/django/ged/champs-signature/')
        self.assertEqual(resp.status_code, 200)
        data = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        self.assertEqual(len(data), 0)

    def test_create_champ_via_api_sets_company_server_side(self):
        resp = auth(self.admin_a).post(
            '/api/django/ged/champs-signature/',
            {'demande': self.demande.id, 'type_champ': CHAMP_TYPE_TEXTE,
             'page': 0, 'x': 5, 'y': 5, 'largeur': 20, 'hauteur': 5,
             'company': self.co_b.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        champ = ChampSignature.objects.get(pk=resp.data['id'])
        self.assertEqual(champ.company_id, self.co_a.id)
