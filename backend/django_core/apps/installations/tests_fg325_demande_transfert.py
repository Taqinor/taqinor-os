"""
FG325 — Demande de transfert inter-emplacements (workflow).

Couvre :
  * création d'une demande : référence (`DTR-`) + société + `created_by` serveur ;
  * source == destination rejeté ; quantité <= 0 rejetée ;
  * un emplacement d'une autre société rejeté ;
  * cycle approuver (pose `approuve_par`/date) / refuser / executer ;
  * une demande non « demandé » ne peut être approuvée (409) ;
  * scope société + barrière de rôle.

Run :
    python manage.py test apps.installations.tests_fg325_demande_transfert -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import DemandeTransfert

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'fg325-co-{n}', defaults={'nom': nom or f'FG325 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'fg325-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_emplacement(company, nom='Dépôt'):
    from apps.stock.models import EmplacementStock
    return EmplacementStock.objects.create(company=company, nom=nom)


def make_produit(company, nom='Panneau 550W'):
    from apps.stock.models import Produit
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=1500, prix_achat=0)


class TestDemandeTransfert(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.src = make_emplacement(self.company, 'Dépôt principal')
        self.dst = make_emplacement(self.company, 'Camionnette 1')
        self.produit = make_produit(self.company)

    def _payload(self, **over):
        base = {
            'produit': self.produit.id, 'source': self.src.id,
            'destination': self.dst.id, 'quantite': 5,
        }
        base.update(over)
        return base

    def test_create_sets_reference_company_server_side(self):
        resp = self.api.post(f'{BASE}/demandes-transfert/',
                             self._payload(company=999, reference='HACK'),
                             format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        dt = DemandeTransfert.objects.get(id=resp.data['id'])
        self.assertEqual(dt.company_id, self.company.id)
        self.assertEqual(dt.created_by_id, self.user.id)
        self.assertTrue(dt.reference.startswith('DTR-'))
        self.assertEqual(dt.statut, DemandeTransfert.Statut.DEMANDE)

    def test_same_source_destination_rejected(self):
        resp = self.api.post(f'{BASE}/demandes-transfert/',
                             self._payload(destination=self.src.id),
                             format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_zero_quantite_rejected(self):
        resp = self.api.post(f'{BASE}/demandes-transfert/',
                             self._payload(quantite=0), format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_emplacement_other_company_rejected(self):
        other = make_company()
        dst_other = make_emplacement(other)
        resp = self.api.post(f'{BASE}/demandes-transfert/',
                             self._payload(destination=dst_other.id),
                             format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_workflow_approuver_executer(self):
        dt = DemandeTransfert.objects.create(
            company=self.company, reference='DTR-X', produit=self.produit,
            source=self.src, destination=self.dst, quantite=3)
        r1 = self.api.post(
            f'{BASE}/demandes-transfert/{dt.id}/approuver/', {}, format='json')
        self.assertEqual(r1.status_code, 200, r1.content)
        dt.refresh_from_db()
        self.assertEqual(dt.statut, DemandeTransfert.Statut.APPROUVE)
        self.assertEqual(dt.approuve_par_id, self.user.id)
        self.assertIsNotNone(dt.date_approbation)
        r2 = self.api.post(
            f'{BASE}/demandes-transfert/{dt.id}/executer/', {}, format='json')
        self.assertEqual(r2.status_code, 200, r2.content)
        dt.refresh_from_db()
        self.assertEqual(dt.statut, DemandeTransfert.Statut.EXECUTE)
        self.assertIsNotNone(dt.date_execution)

    def test_refuser(self):
        dt = DemandeTransfert.objects.create(
            company=self.company, reference='DTR-Y', produit=self.produit,
            source=self.src, destination=self.dst, quantite=3)
        resp = self.api.post(
            f'{BASE}/demandes-transfert/{dt.id}/refuser/',
            {'motif_refus': 'Stock insuffisant'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        dt.refresh_from_db()
        self.assertEqual(dt.statut, DemandeTransfert.Statut.REFUSE)
        self.assertEqual(dt.motif_refus, 'Stock insuffisant')

    def test_cannot_execute_unapproved(self):
        dt = DemandeTransfert.objects.create(
            company=self.company, reference='DTR-Z', produit=self.produit,
            source=self.src, destination=self.dst, quantite=3)
        resp = self.api.post(
            f'{BASE}/demandes-transfert/{dt.id}/executer/', {}, format='json')
        self.assertEqual(resp.status_code, 409, resp.content)


class TestScopingAndRoles(TestCase):
    def setUp(self):
        self.company = make_company()
        self.other = make_company()
        self.src = make_emplacement(self.company, 'A')
        self.dst = make_emplacement(self.company, 'B')
        self.produit = make_produit(self.company)

    def test_commercial_cannot_write(self):
        api = auth(make_user(self.company, role='commercial'))
        resp = api.post(f'{BASE}/demandes-transfert/', {
            'produit': self.produit.id, 'source': self.src.id,
            'destination': self.dst.id, 'quantite': 1,
        }, format='json')
        self.assertEqual(resp.status_code, 403, resp.content)

    def test_other_company_cannot_see(self):
        DemandeTransfert.objects.create(
            company=self.company, reference='DTR-S', produit=self.produit,
            source=self.src, destination=self.dst, quantite=1)
        api = auth(make_user(self.other))
        resp = api.get(f'{BASE}/demandes-transfert/')
        results = resp.data.get('results', resp.data)
        self.assertEqual(len(results), 0)
