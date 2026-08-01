"""NTMOB16 — signature client tracée sur le bon de livraison chantier.

Couvre l'action ``POST installations/chantiers/<id>/signer-client/`` (même
patron que FG69 ``Intervention.signer_client``) : enregistrement de la
signature + horodatage serveur, garde de rôle, corps invalide, isolation
société. Le rendu PDF (embarquement du trait dans le gabarit) est couvert
côté ``apps.documents`` (``test_documents.py``).
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.installations.services import create_installation_from_devis
from apps.ventes.models import Devis

User = get_user_model()
_seq = itertools.count(1)


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    slug = slug or f'ntmob16-co-{n}'
    nom = nom or f'NTMOB16 Co {n}'
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_chantier(company, user):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Site', prenom='Client',
        email=f'ntmob16-{company.id}-{n}@example.invalid')
    lead = Lead.objects.create(
        company=company, nom='Site', prenom='Client', stage='SIGNED')
    devis = Devis.objects.create(
        company=company, reference=f'DEV-NTMOB16-{company.id}-{n}',
        client=client, lead=lead, statut=Devis.Statut.ACCEPTE,
        taux_tva=Decimal('20'))
    inst, _ = create_installation_from_devis(devis, user, company)
    return inst


class SignerClientEndpointTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.other_company = make_company()
        self.user = User.objects.create_user(
            username='ntmob16-resp', password='x', role_legacy='responsable',
            company=self.company)
        self.normal_user = User.objects.create_user(
            username='ntmob16-normal', password='x', role_legacy='normal',
            company=self.company)
        self.api = auth(self.user)
        self.inst = make_chantier(self.company, self.user)

    def _url(self, inst_id=None):
        return f'/api/django/installations/chantiers/{inst_id or self.inst.id}/signer-client/'

    def test_records_signature_and_stamps_server_time(self):
        resp = self.api.post(self._url(), {
            'signature_client': 'data:image/png;base64,AAAA',
            'signataire_nom': 'Karim Bennani',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.inst.refresh_from_db()
        self.assertEqual(self.inst.signature_client, 'data:image/png;base64,AAAA')
        self.assertEqual(self.inst.signataire_nom, 'Karim Bennani')
        self.assertIsNotNone(self.inst.signe_le)

    def test_signataire_nom_optional(self):
        resp = self.api.post(self._url(), {
            'signature_client': 'data:image/png;base64,AAAA',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.inst.refresh_from_db()
        self.assertEqual(self.inst.signature_client, 'data:image/png;base64,AAAA')
        self.assertIsNotNone(self.inst.signe_le)

    def test_empty_signature_rejected(self):
        resp = self.api.post(self._url(), {'signature_client': ''}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.inst.refresh_from_db()
        self.assertIsNone(self.inst.signature_client)

    def test_missing_signature_rejected(self):
        resp = self.api.post(self._url(), {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_normal_role_forbidden(self):
        api = auth(self.normal_user)
        resp = api.post(self._url(), {
            'signature_client': 'data:image/png;base64,AAAA',
        }, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_other_company_installation_404(self):
        other_user = User.objects.create_user(
            username='ntmob16-other', password='x', role_legacy='responsable',
            company=self.other_company)
        other_inst = make_chantier(self.other_company, other_user)
        resp = self.api.post(self._url(other_inst.id), {
            'signature_client': 'data:image/png;base64,AAAA',
        }, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_logs_chatter_note(self):
        self.api.post(self._url(), {
            'signature_client': 'data:image/png;base64,AAAA',
            'signataire_nom': 'Karim Bennani',
        }, format='json')
        note = self.inst.activites.filter(
            kind='note', body__icontains='Signature client').order_by('-id').first()
        self.assertIsNotNone(note)
        self.assertIn('Karim Bennani', note.body)
