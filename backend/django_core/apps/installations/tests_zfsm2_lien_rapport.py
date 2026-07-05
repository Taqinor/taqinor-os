"""
ZFSM2 — Lien public tokenisé du compte-rendu d'intervention signé.

Couvre :
  * la génération lazy/idempotente du jeton via l'action ``lien-rapport``
    (jeton DISTINCT du lien « en route » XFSM7) ;
  * le jeton est posé AUTOMATIQUEMENT quand l'intervention passe « Validée » ;
  * la page publique (sans login) affiche le compte-rendu signé (photos,
    réserves, matériel consommé, signature) ;
  * aucune donnée interne (prix d'achat/marge) ne fuite dans le payload ;
  * le PDF est téléchargeable via le même jeton ;
  * un token inconnu renvoie 404.

Run :
    python manage.py test apps.installations.tests_zfsm2_lien_rapport -v2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.installations.models import Intervention
from apps.installations.services import create_installation_from_devis
from apps.ventes.models import Devis

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'
PUBLIC_BASE = '/api/django/public/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'zfsm2-co-{n}', defaults={'nom': nom or f'ZFSM2 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'zfsm2-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_chantier(company, user):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Site', prenom='Client',
        email=f'zfsm2-{company.id}-{n}@example.invalid')
    lead = Lead.objects.create(
        company=company, nom='Site', prenom='Client', stage='SIGNED',
        type_installation='residentiel')
    devis = Devis.objects.create(
        company=company, reference=f'DEV-ZFSM2-{company.id}-{n}', client=client,
        lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
        mode_installation='residentiel')
    inst, _ = create_installation_from_devis(devis, user, company)
    return inst


class TestLienRapportToken(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.inst = make_chantier(self.company, self.user)
        self.interv = Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='pose', created_by=self.user, technicien=self.user,
            statut=Intervention.Statut.VALIDEE,
            signataire_nom='Client Test')

    def test_lien_rapport_action_generates_token(self):
        resp = self.api.get(f'{BASE}/interventions/{self.interv.id}/lien-rapport/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.data['token'])
        self.interv.refresh_from_db()
        self.assertEqual(self.interv.lien_rapport_token, resp.data['token'])

    def test_lien_rapport_action_idempotent(self):
        r1 = self.api.get(f'{BASE}/interventions/{self.interv.id}/lien-rapport/')
        r2 = self.api.get(f'{BASE}/interventions/{self.interv.id}/lien-rapport/')
        self.assertEqual(r1.data['token'], r2.data['token'])

    def test_token_distinct_from_lien_client_token(self):
        r_rapport = self.api.get(
            f'{BASE}/interventions/{self.interv.id}/lien-rapport/')
        r_client = self.api.get(
            f'{BASE}/interventions/{self.interv.id}/lien-client/')
        self.assertNotEqual(r_rapport.data['token'], r_client.data['token'])

    def test_token_auto_generated_on_transition_to_validee(self):
        interv2 = Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='controle', created_by=self.user,
            statut=Intervention.Statut.TERMINEE)
        self.assertFalse(interv2.lien_rapport_token)
        resp = self.api.patch(
            f'{BASE}/interventions/{interv2.id}/',
            {'statut': Intervention.Statut.VALIDEE}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        interv2.refresh_from_db()
        self.assertTrue(interv2.lien_rapport_token)

    def test_public_page_no_login(self):
        token = self.interv.ensure_lien_rapport_token()
        pub = APIClient()
        resp = pub.get(f'{PUBLIC_BASE}/intervention-rapport/{token}/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['statut'], Intervention.Statut.VALIDEE)
        self.assertEqual(resp.data['signataire_nom'], 'Client Test')
        self.assertIn('photos', resp.data)
        self.assertIn('reserves', resp.data)
        self.assertIn('pdf_url', resp.data)
        # Aucune donnée interne (prix d'achat/marge) — payload restreint.
        self.assertNotIn('prix_achat', resp.data)
        self.assertNotIn('marge', resp.data)

    def test_public_page_unknown_token_404(self):
        pub = APIClient()
        resp = pub.get(f'{PUBLIC_BASE}/intervention-rapport/does-not-exist/')
        self.assertEqual(resp.status_code, 404)

    def test_public_pdf_downloadable_with_same_token(self):
        token = self.interv.ensure_lien_rapport_token()
        pub = APIClient()
        resp = pub.get(f'{PUBLIC_BASE}/intervention-rapport/{token}/pdf/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')

    def test_public_pdf_unknown_token_404(self):
        pub = APIClient()
        resp = pub.get(f'{PUBLIC_BASE}/intervention-rapport/nope/pdf/')
        self.assertEqual(resp.status_code, 404)

    def test_consommation_payload_never_leaks_prix_achat(self):
        """Le payload de consommation ne porte que designation/quantites —
        jamais de prix (miroir de la garde F19 sur intervention_pdf.py)."""
        token = self.interv.ensure_lien_rapport_token()
        pub = APIClient()
        resp = pub.get(f'{PUBLIC_BASE}/intervention-rapport/{token}/')
        for key in resp.data:
            self.assertNotIn('prix', key.lower())
