"""XSTK22 — suivi de livraison côté client : numéro de suivi + notification +
section portail.

Couvre :
  * ``Livraison.numero_suivi`` (nullable, additif) est exposé par l'API ;
  * la notification client part au passage en transit, UNE SEULE FOIS
    (ré-appeler ``expedier`` ne renvoie pas une 2e notification) ;
  * la section portail (scopée client) liste les livraisons de SES chantiers
    avec date prévue / statut / articles (désignation + quantité) ;
  * ``cout_transport`` (interne) ne fuit JAMAIS dans le payload portail ;
  * la POD (FG330) est indiquée disponible + son URL une fois livrée.

Run :
    python manage.py test apps.installations.tests_xstk22_livraison_client -v2
"""
import itertools

from django.core import mail
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import (
    Installation, Livraison, LivraisonLigne, PreuveLivraison,
)

_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'xstk22-co-{n}', defaults={'nom': nom or f'XSTK22 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_user(
        username=username or f'xstk22-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_client_crm(company, email=None, telephone=None):
    from apps.crm.models import Client
    return Client.objects.create(
        company=company, nom='Client Test', email=email, telephone=telephone)


def make_installation(company, client):
    n = next(_seq)
    return Installation.objects.create(
        company=company, client=client, reference=f'CH-XSTK22-{n}')


class TestNumeroSuivi(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.client_crm = make_client_crm(self.company)
        self.inst = make_installation(self.company, self.client_crm)
        self.liv = Livraison.objects.create(
            company=self.company, installation=self.inst,
            reference='LIV-XSTK22-1')

    def test_numero_suivi_writable_and_exposed(self):
        r = self.api.patch(
            f'{BASE}/livraisons/{self.liv.id}/', {'numero_suivi': 'DHL123456'})
        self.assertEqual(r.status_code, 200, r.data)
        self.liv.refresh_from_db()
        self.assertEqual(self.liv.numero_suivi, 'DHL123456')
        self.assertEqual(r.data['numero_suivi'], 'DHL123456')


class TestNotificationTransit(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.client_crm = make_client_crm(
            self.company, email='client@example.com', telephone='0612345678')
        self.inst = make_installation(self.company, self.client_crm)
        self.liv = Livraison.objects.create(
            company=self.company, installation=self.inst,
            reference='LIV-XSTK22-2')

    def test_expedier_sends_notification_once(self):
        r = self.api.post(f'{BASE}/livraisons/{self.liv.id}/expedier/')
        self.assertEqual(r.status_code, 200, r.data)
        self.liv.refresh_from_db()
        self.assertIsNotNone(self.liv.notifie_transit_le)
        self.assertEqual(len(mail.outbox), 1)

        first_notified_at = self.liv.notifie_transit_le
        # Ré-appeler expedier (déjà en transit) ne renvoie PAS une 2e fois.
        r2 = self.api.post(f'{BASE}/livraisons/{self.liv.id}/expedier/')
        self.assertEqual(r2.status_code, 200, r2.data)
        self.liv.refresh_from_db()
        self.assertEqual(self.liv.notifie_transit_le, first_notified_at)
        self.assertEqual(len(mail.outbox), 1)

    def test_no_client_no_crash(self):
        """Chantier sans client email/tel → aucune exception, pas d'envoi."""
        client_sans_contact = make_client_crm(self.company)
        inst2 = make_installation(self.company, client_sans_contact)
        liv2 = Livraison.objects.create(
            company=self.company, installation=inst2,
            reference='LIV-XSTK22-3')
        r = self.api.post(f'{BASE}/livraisons/{liv2.id}/expedier/')
        self.assertEqual(r.status_code, 200, r.data)


class TestPortailLivraisons(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.client_crm = make_client_crm(self.company)
        self.autre_client = make_client_crm(self.company)
        self.inst = make_installation(self.company, self.client_crm)
        self.autre_inst = make_installation(self.company, self.autre_client)
        self.liv = Livraison.objects.create(
            company=self.company, installation=self.inst,
            reference='LIV-XSTK22-4', numero_suivi='TRACK-1',
            cout_transport=500, statut=Livraison.Statut.LIVREE)
        LivraisonLigne.objects.create(
            livraison=self.liv, designation='Panneau 550W', quantite=10)
        PreuveLivraison.objects.create(
            company=self.company, livraison=self.liv,
            signataire_nom='M. Client')
        # Livraison d'un AUTRE client — ne doit jamais apparaître.
        Livraison.objects.create(
            company=self.company, installation=self.autre_inst,
            reference='LIV-XSTK22-5')

    def test_portail_scoped_to_client(self):
        r = self.api.get(
            f'{BASE}/livraisons/portail/', {'client': self.client_crm.id})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(len(r.data), 1)
        row = r.data[0]
        self.assertEqual(row['reference'], 'LIV-XSTK22-4')
        self.assertEqual(row['numero_suivi'], 'TRACK-1')
        self.assertEqual(len(row['articles']), 1)
        self.assertEqual(row['articles'][0]['designation'], 'Panneau 550W')
        self.assertEqual(row['articles'][0]['quantite'], 10)
        self.assertTrue(row['pod_disponible'])
        self.assertIsNotNone(row['pod_url'])

    def test_cout_transport_never_leaks(self):
        r = self.api.get(
            f'{BASE}/livraisons/portail/', {'client': self.client_crm.id})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('cout_transport', str(r.data))
        self.assertNotIn('500', str(r.data))

    def test_requires_client_param(self):
        r = self.api.get(f'{BASE}/livraisons/portail/')
        self.assertEqual(r.status_code, 400)
