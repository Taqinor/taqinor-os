"""GED30 — Signature électronique (point d'intégration + STUB no-op).

Couvre :
  * `demander_signature` crée une demande `en_attente` avec `company`/`created_by`
    posés CÔTÉ SERVEUR (jamais lus du corps) ;
  * `esign_active()` faux par défaut → STUB no-op : aucun provider, aucun
    `provider_ref`, résultat déterministe LOCAL, aucun appel réseau ;
  * `marquer_signe` enregistre la complétion (statut `signe` + horodatage),
    idempotent ;
  * isolation par société (A ne voit pas les demandes de B) ;
  * document d'une AUTRE société rejeté (404 cross-société à l'API ;
    `PermissionError` au service) ;
  * `company`/`created_by` posés côté serveur via l'API (jamais du corps).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.ged import selectors, services
from apps.ged.models import (
    Cabinet, DemandeSignatureDocument, Document, Folder,
    SIGNATURE_EN_ATTENTE, SIGNATURE_PROVIDER_AUCUN, SIGNATURE_SIGNE,
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


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


class SignatureBase(TestCase):
    URL = '/api/django/ged/demandes-signature/'

    def setUp(self):
        self.co_a = make_company('ged30-a', 'Ged30 A')
        self.co_b = make_company('ged30-b', 'Ged30 B')
        self.admin_a = make_user(self.co_a, 'ged30-admin-a', 'admin')
        self.admin_b = make_user(self.co_b, 'ged30-admin-b', 'admin')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Admin')
        self.cab_b = Cabinet.objects.create(company=self.co_b, nom='Admin')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='Dossier A')
        self.folder_b = Folder.objects.create(
            company=self.co_b, cabinet=self.cab_b, nom='Dossier B')
        self.doc_a = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='Contrat à signer')
        self.doc_b = Document.objects.create(
            company=self.co_b, folder=self.folder_b, nom='Doc B')


class SignatureServiceTests(SignatureBase):
    def test_esign_inactive_by_default(self):
        """Sans flag, l'e-sign est INACTIVE → mode STUB no-op."""
        self.assertFalse(services.esign_active())
        self.assertEqual(
            services.esign_provider_name(), SIGNATURE_PROVIDER_AUCUN)

    def test_demander_signature_creates_request_server_side(self):
        """demander_signature crée une demande en_attente, company/created_by
        posés côté serveur."""
        demande = services.demander_signature(
            self.doc_a,
            signataire_nom='Jean Client',
            signataire_email='jean@example.com',
            company=self.co_a,
            created_by=self.admin_a)
        self.assertEqual(demande.company_id, self.co_a.id)
        self.assertEqual(demande.document_id, self.doc_a.id)
        self.assertEqual(demande.created_by_id, self.admin_a.id)
        self.assertEqual(demande.statut, SIGNATURE_EN_ATTENTE)
        self.assertTrue(demande.is_pending)
        self.assertEqual(demande.signataire_nom, 'Jean Client')

    def test_demander_signature_stub_noop_deterministic(self):
        """En mode stub (esign inactive) : provider 'aucun', provider_ref vide,
        statut en_attente — déterministe, aucun appel réseau."""
        demande = services.demander_signature(
            self.doc_a,
            signataire_nom='Jean',
            signataire_email='jean@example.com',
            company=self.co_a)
        self.assertFalse(services.esign_active())
        self.assertEqual(demande.provider, SIGNATURE_PROVIDER_AUCUN)
        self.assertEqual(demande.provider_ref, '')
        self.assertEqual(demande.statut, SIGNATURE_EN_ATTENTE)
        self.assertIsNone(demande.date_signature)

    def test_demander_signature_cross_company_rejected(self):
        """Un document d'une AUTRE société est rejeté (PermissionError)."""
        with self.assertRaises(PermissionError):
            services.demander_signature(
                self.doc_b,
                signataire_nom='X',
                signataire_email='x@example.com',
                company=self.co_a)

    def test_marquer_signe_records_signature(self):
        """marquer_signe bascule en signe + horodate, idempotent."""
        demande = services.demander_signature(
            self.doc_a,
            signataire_nom='Jean',
            signataire_email='jean@example.com',
            company=self.co_a)
        demande = services.marquer_signe(demande, provider_ref='ref-123')
        self.assertEqual(demande.statut, SIGNATURE_SIGNE)
        self.assertIsNotNone(demande.date_signature)
        self.assertEqual(demande.provider_ref, 'ref-123')
        # Idempotent : un second appel ne change pas l'horodatage.
        date1 = demande.date_signature
        demande = services.marquer_signe(demande)
        self.assertEqual(demande.statut, SIGNATURE_SIGNE)
        self.assertEqual(demande.date_signature, date1)


class SignatureApiTests(SignatureBase):
    def test_create_sets_company_created_by_server_side(self):
        """POST crée une demande ; company/created_by posés côté serveur (jamais
        du corps)."""
        api = auth(self.admin_a)
        resp = api.post(self.URL, {
            'document': self.doc_a.id,
            'signataire_nom': 'Jean Client',
            'signataire_email': 'jean@example.com',
            # Tentative d'injection — ignorée côté serveur.
            'company': self.co_b.id,
            'statut': SIGNATURE_SIGNE,
            'provider': 'docusign',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        demande = DemandeSignatureDocument.objects.get(pk=resp.data['id'])
        self.assertEqual(demande.company_id, self.co_a.id)
        self.assertEqual(demande.created_by_id, self.admin_a.id)
        # Statut/provider non lus du corps : restent en mode stub.
        self.assertEqual(demande.statut, SIGNATURE_EN_ATTENTE)
        self.assertEqual(demande.provider, SIGNATURE_PROVIDER_AUCUN)

    def test_create_requires_signataire(self):
        """Nom/email du signataire requis."""
        api = auth(self.admin_a)
        resp = api.post(self.URL, {
            'document': self.doc_a.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_create_cross_company_document_404(self):
        """Un document d'une autre société → 404 (jamais de fuite cross-société)."""
        api = auth(self.admin_a)
        resp = api.post(self.URL, {
            'document': self.doc_b.id,
            'signataire_nom': 'X',
            'signataire_email': 'x@example.com',
        }, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_list_isolated_by_company(self):
        """A ne voit pas les demandes de B (isolation société)."""
        services.demander_signature(
            self.doc_a, signataire_nom='A', signataire_email='a@x.com',
            company=self.co_a)
        services.demander_signature(
            self.doc_b, signataire_nom='B', signataire_email='b@x.com',
            company=self.co_b)
        resp = auth(self.admin_a).get(self.URL)
        self.assertEqual(resp.status_code, 200)
        data = rows(resp)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['document'], self.doc_a.id)
        # Le selector borne aussi à la société.
        self.assertEqual(
            selectors.demandes_signature_for_company(self.co_a).count(), 1)
        self.assertEqual(
            selectors.demandes_signature_for_company(self.co_b).count(), 1)

    def test_marquer_signe_action(self):
        """POST <id>/marquer-signe/ enregistre la signature."""
        demande = services.demander_signature(
            self.doc_a, signataire_nom='A', signataire_email='a@x.com',
            company=self.co_a)
        api = auth(self.admin_a)
        resp = api.post(f'{self.URL}{demande.id}/marquer-signe/', {},
                        format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], SIGNATURE_SIGNE)
        demande.refresh_from_db()
        self.assertEqual(demande.statut, SIGNATURE_SIGNE)
        self.assertIsNotNone(demande.date_signature)
