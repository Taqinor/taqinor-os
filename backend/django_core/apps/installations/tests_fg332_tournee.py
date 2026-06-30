"""
FG332 — Optimisation de tournée de livraison multi-sites.

Couvre :
  * la tournée n'inclut que les livraisons du jour (planifiées/en transit) ;
  * l'ordre est calculé par plus proche voisin depuis un point de départ ;
  * les livraisons sans GPS sont listées à part (ordre None) ;
  * `jour` requis / invalide rejeté ;
  * scope société (autre société ne voit pas) + lecture tout rôle.

Run :
    python manage.py test apps.installations.tests_fg332_tournee -v2
"""
import itertools
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation, Livraison

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'
JOUR = '2026-07-15'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'fg332-co-{n}', defaults={'nom': nom or f'FG332 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'fg332-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_installation(company, ref, lat=None, lng=None):
    client = Client.objects.create(
        company=company, nom='Client', prenom='Test',
        email=f'tn-{company.id}-{ref}@example.invalid')
    return Installation.objects.create(
        company=company, reference=ref, client=client,
        statut=Installation.Statut.RECEPTIONNE,
        type_installation='residentiel',
        puissance_installee_kwc=Decimal('6.5'),
        gps_lat=lat, gps_lng=lng)


def make_livraison(company, inst, ref, jour=JOUR,
                   statut=Livraison.Statut.PLANIFIEE):
    return Livraison.objects.create(
        company=company, installation=inst, reference=ref,
        date_prevue=date.fromisoformat(jour), statut=statut)


class TestTournee(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)

    def test_nearest_neighbour_order(self):
        # Trois sites alignés ; départ proche de A → ordre A, B, C
        a = make_installation(self.company, 'A', Decimal('33.50'),
                              Decimal('-7.60'))
        b = make_installation(self.company, 'B', Decimal('33.60'),
                              Decimal('-7.60'))
        c = make_installation(self.company, 'C', Decimal('33.80'),
                              Decimal('-7.60'))
        make_livraison(self.company, c, 'LIV-C')
        make_livraison(self.company, a, 'LIV-A')
        make_livraison(self.company, b, 'LIV-B')
        resp = self.api.get(
            f'{BASE}/tournee-livraison/?jour={JOUR}'
            f'&depart_lat=33.49&depart_lng=-7.60')
        self.assertEqual(resp.status_code, 200, resp.content)
        refs = [t['reference'] for t in resp.data['tournee']]
        self.assertEqual(refs, ['LIV-A', 'LIV-B', 'LIV-C'])

    def test_sans_gps_listed_apart(self):
        with_gps = make_installation(self.company, 'G', Decimal('33.5'),
                                     Decimal('-7.6'))
        no_gps = make_installation(self.company, 'N')
        make_livraison(self.company, with_gps, 'LIV-G')
        make_livraison(self.company, no_gps, 'LIV-N')
        resp = self.api.get(f'{BASE}/tournee-livraison/?jour={JOUR}')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(len(resp.data['tournee']), 1)
        self.assertEqual(len(resp.data['sans_gps']), 1)
        self.assertEqual(resp.data['total'], 2)

    def test_only_that_day(self):
        inst = make_installation(self.company, 'D', Decimal('33.5'),
                                 Decimal('-7.6'))
        make_livraison(self.company, inst, 'LIV-TODAY')
        make_livraison(self.company, inst, 'LIV-OTHER', jour='2026-08-01')
        resp = self.api.get(f'{BASE}/tournee-livraison/?jour={JOUR}')
        self.assertEqual(resp.data['total'], 1)

    def test_jour_required(self):
        resp = self.api.get(f'{BASE}/tournee-livraison/')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_jour_invalid(self):
        resp = self.api.get(f'{BASE}/tournee-livraison/?jour=notadate')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_other_company_not_included(self):
        other = make_company()
        inst_other = make_installation(other, 'O', Decimal('33.5'),
                                       Decimal('-7.6'))
        make_livraison(other, inst_other, 'LIV-OC')
        resp = self.api.get(f'{BASE}/tournee-livraison/?jour={JOUR}')
        self.assertEqual(resp.data['total'], 0)

    def test_commercial_can_read(self):
        api = auth(make_user(self.company, role='commercial'))
        resp = api.get(f'{BASE}/tournee-livraison/?jour={JOUR}')
        self.assertEqual(resp.status_code, 200, resp.content)
