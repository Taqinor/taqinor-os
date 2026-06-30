"""Tests LITIGE5 — Capture du concurrent/motif sur deal perdu (étend FG242).

Couvre :
- pose et lecture des champs concurrent/motif sur une Reclamation (défauts +
  set/read), le lead perdu d'origine étant référencé par le couple lâche
  ``source_type='lead'`` / ``source_id`` (string-FK, aucun import apps.crm) ;
- l'API surface les champs en lecture/écriture et force la société côté serveur ;
- le sélecteur ``analyse_concurrents_perte`` agrège qui nous bat / à quel prix /
  sur quel motif, en ignorant les prix inconnus (jamais de division par zéro) ;
- isolation multi-société : les litiges d'une autre société ne fuient pas dans
  l'analyse, et l'endpoint applique le palier de permission du viewset.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.litiges.models import Reclamation
from apps.litiges.selectors import analyse_concurrents_perte

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Litige5ModelTests(TestCase):
    """Défauts et set/read des champs concurrent/motif sur la Reclamation."""

    def setUp(self):
        self.co = make_company('litige5-mod', 'M')

    def test_defaults_empty(self):
        r = Reclamation.objects.create(
            company=self.co, objet='Deal perdu',
            type_reclamation=Reclamation.TypeReclamation.COMMERCIAL)
        self.assertEqual(r.concurrent_nom, '')
        self.assertIsNone(r.concurrent_prix)
        self.assertEqual(r.concurrent_devise, 'MAD')
        self.assertEqual(r.motif_perte, '')

    def test_set_and_read_with_loose_lead_ref(self):
        r = Reclamation.objects.create(
            company=self.co, objet='Deal perdu',
            type_reclamation=Reclamation.TypeReclamation.COMMERCIAL,
            source_type='lead', source_id=42,
            concurrent_nom='SolarRival', concurrent_prix=Decimal('123456.78'),
            concurrent_devise='EUR', motif_perte='Prix')
        r.refresh_from_db()
        self.assertEqual(r.source_type, 'lead')
        self.assertEqual(r.source_id, 42)
        self.assertEqual(r.concurrent_nom, 'SolarRival')
        self.assertEqual(r.concurrent_prix, Decimal('123456.78'))
        self.assertEqual(r.concurrent_devise, 'EUR')
        self.assertEqual(r.motif_perte, 'Prix')


class Litige5SelectorTests(TestCase):
    """``analyse_concurrents_perte`` — agrégation concurrentielle scopée."""

    def setUp(self):
        self.co = make_company('litige5-sel', 'S')
        self.other = make_company('litige5-sel-other', 'O')

    def _make(self, company, nom, prix=None, devise='MAD', motif=''):
        return Reclamation.objects.create(
            company=company, objet='Deal perdu',
            type_reclamation=Reclamation.TypeReclamation.COMMERCIAL,
            concurrent_nom=nom,
            concurrent_prix=(Decimal(prix) if prix is not None else None),
            concurrent_devise=devise, motif_perte=motif)

    def test_empty_when_no_competitor(self):
        # Réclamation sans concurrent saisi → exclue de l'analyse.
        Reclamation.objects.create(company=self.co, objet='Sans concurrent')
        data = analyse_concurrents_perte(self.co)
        self.assertEqual(data['total_litiges_avec_concurrent'], 0)
        self.assertEqual(data['par_concurrent'], [])
        self.assertEqual(data['par_motif'], [])

    def test_aggregates_count_price_motif(self):
        self._make(self.co, 'AlphaSolar', '100000', 'MAD', 'Prix')
        self._make(self.co, 'AlphaSolar', '120000', 'MAD', 'Prix')
        self._make(self.co, 'BetaPV', '90000', 'MAD', 'Délai')
        data = analyse_concurrents_perte(self.co)
        self.assertEqual(data['total_litiges_avec_concurrent'], 3)
        # Trié plus fréquent d'abord → AlphaSolar (2) devant BetaPV (1).
        self.assertEqual(data['par_concurrent'][0]['concurrent'], 'AlphaSolar')
        self.assertEqual(data['par_concurrent'][0]['nombre'], 2)
        self.assertEqual(data['par_concurrent'][0]['prix_moyen'], '110000.00')
        self.assertEqual(data['par_concurrent'][0]['devise'], 'MAD')
        self.assertEqual(data['par_concurrent'][1]['concurrent'], 'BetaPV')
        # Motifs triés par fréquence.
        motifs = {m['motif']: m['nombre'] for m in data['par_motif']}
        self.assertEqual(motifs, {'Prix': 2, 'Délai': 1})

    def test_prix_moyen_none_when_no_price_known(self):
        self._make(self.co, 'GammaEnergie', prix=None, motif='')
        data = analyse_concurrents_perte(self.co)
        self.assertEqual(data['total_litiges_avec_concurrent'], 1)
        self.assertIsNone(data['par_concurrent'][0]['prix_moyen'])
        # Aucun motif renseigné → liste motifs vide.
        self.assertEqual(data['par_motif'], [])

    def test_prix_moyen_ignores_unknown_prices(self):
        self._make(self.co, 'DeltaSun', '200000', 'MAD')
        self._make(self.co, 'DeltaSun', prix=None)
        data = analyse_concurrents_perte(self.co)
        # Moyenne sur le seul prix connu, pas de division par 2.
        self.assertEqual(data['par_concurrent'][0]['prix_moyen'], '200000.00')

    def test_company_scoped(self):
        self._make(self.co, 'AlphaSolar', '100000')
        self._make(self.other, 'SecretRival', '999999')
        data = analyse_concurrents_perte(self.co)
        noms = [c['concurrent'] for c in data['par_concurrent']]
        self.assertIn('AlphaSolar', noms)
        self.assertNotIn('SecretRival', noms)


class Litige5ApiTests(TestCase):
    """L'API expose les champs et l'endpoint d'analyse (scopé société)."""

    BASE = '/api/django/litiges/reclamations/'

    def setUp(self):
        self.co_a = make_company('litige5-api-a', 'A')
        self.co_b = make_company('litige5-api-b', 'B')
        self.user_a = make_user(self.co_a, 'litige5-api-a')

    def test_create_with_competitor_forces_company(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE, {
            'objet': 'Deal perdu',
            'type_reclamation': Reclamation.TypeReclamation.COMMERCIAL,
            'source_type': 'lead', 'source_id': 7,
            'concurrent_nom': 'RivalCorp',
            'concurrent_prix': '88000.00',
            'concurrent_devise': 'MAD',
            'motif_perte': 'Prix trop élevé',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = Reclamation.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co_a)
        self.assertEqual(obj.concurrent_nom, 'RivalCorp')
        self.assertEqual(obj.concurrent_prix, Decimal('88000.00'))
        self.assertEqual(obj.motif_perte, 'Prix trop élevé')

    def test_detail_surfaces_competitor_fields(self):
        r = Reclamation.objects.create(
            company=self.co_a, objet='Deal perdu',
            concurrent_nom='RivalCorp', concurrent_prix=Decimal('88000.00'),
            concurrent_devise='MAD', motif_perte='Prix')
        resp = auth(self.user_a).get(f'{self.BASE}{r.id}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['concurrent_nom'], 'RivalCorp')
        self.assertEqual(resp.data['concurrent_prix'], '88000.00')
        self.assertEqual(resp.data['concurrent_devise'], 'MAD')
        self.assertEqual(resp.data['motif_perte'], 'Prix')

    def test_analyse_endpoint(self):
        Reclamation.objects.create(
            company=self.co_a, objet='Deal perdu 1',
            concurrent_nom='RivalCorp', concurrent_prix=Decimal('80000'),
            motif_perte='Prix')
        Reclamation.objects.create(
            company=self.co_a, objet='Deal perdu 2',
            concurrent_nom='RivalCorp', concurrent_prix=Decimal('100000'),
            motif_perte='Prix')
        resp = auth(self.user_a).get(f'{self.BASE}analyse-concurrents/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['total_litiges_avec_concurrent'], 2)
        self.assertEqual(resp.data['par_concurrent'][0]['concurrent'],
                         'RivalCorp')
        self.assertEqual(resp.data['par_concurrent'][0]['prix_moyen'],
                         '90000.00')

    def test_analyse_endpoint_company_scoped(self):
        Reclamation.objects.create(
            company=self.co_b, objet='Deal perdu B',
            concurrent_nom='SecretRival', concurrent_prix=Decimal('1'))
        resp = auth(self.user_a).get(f'{self.BASE}analyse-concurrents/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['total_litiges_avec_concurrent'], 0)

    def test_analyse_endpoint_forbidden_for_limited_role(self):
        limited = make_user(self.co_a, 'litige5-limited', role='normal')
        resp = auth(limited).get(f'{self.BASE}analyse-concurrents/')
        self.assertEqual(resp.status_code, 403, getattr(resp, 'data', resp))
