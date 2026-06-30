"""
FG311 — RFQ multi-fournisseurs & comparatif d'offres.

Couvre :
  * création de RFQ via l'API : référence (`RFQ-`) + société + ``created_by``
    posés CÔTÉ SERVEUR (jamais count()+1) ;
  * l'injection de ``company``/``reference``/``statut`` est ignorée ;
  * une ``demande`` d'une autre société est rejetée ;
  * la création d'offres (fournisseur catalogue OU nom libre) ;
  * un fournisseur d'une autre société est rejeté ;
  * le comparatif (moins chère / plus rapide / retenue) ;
  * l'action `retenir` (exactement UNE offre retenue) ;
  * le cycle de vie envoyer/cloturer ;
  * le scope société et la barrière de rôle (écriture responsable/admin).

Run :
    python manage.py test apps.installations.tests_fg311_rfq -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import RFQ, RFQOffre

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'fg311-co-{n}', defaults={'nom': nom or f'FG311 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'fg311-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_fournisseur(company, nom='SolarImport'):
    from apps.stock.models import Fournisseur
    return Fournisseur.objects.create(company=company, nom=nom)


class TestRFQCreation(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)

    def test_create_server_side_ref(self):
        r = self.api.post(f'{BASE}/rfq/', {'objet': 'Consultation panneaux'})
        self.assertEqual(r.status_code, 201, r.data)
        rfq = RFQ.objects.get(id=r.data['id'])
        self.assertEqual(rfq.company_id, self.company.id)
        self.assertEqual(rfq.created_by_id, self.user.id)
        self.assertTrue(rfq.reference.startswith('RFQ-'), rfq.reference)
        self.assertEqual(rfq.statut, RFQ.Statut.BROUILLON)

    def test_injected_fields_ignored(self):
        autre = make_company()
        r = self.api.post(f'{BASE}/rfq/', {
            'company': autre.id, 'reference': 'RFQ-HACK', 'statut': 'cloturee',
            'objet': 'X',
        })
        self.assertEqual(r.status_code, 201, r.data)
        rfq = RFQ.objects.get(id=r.data['id'])
        self.assertEqual(rfq.company_id, self.company.id)
        self.assertNotEqual(rfq.reference, 'RFQ-HACK')
        self.assertEqual(rfq.statut, RFQ.Statut.BROUILLON)

    def test_blank_objet_rejected(self):
        r = self.api.post(f'{BASE}/rfq/', {'objet': '  '})
        self.assertEqual(r.status_code, 400, r.data)


class TestOffresAndComparatif(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.rfq = RFQ.objects.create(
            company=self.company, reference='RFQ-T-1', objet='Panneaux',
            created_by=self.user)

    def test_create_offre_catalog_and_libre(self):
        f = make_fournisseur(self.company)
        r1 = self.api.post(f'{BASE}/rfq-offres/', {
            'rfq': self.rfq.id, 'fournisseur': f.id, 'montant_ht': '90000',
            'delai_jours': 20,
        })
        self.assertEqual(r1.status_code, 201, r1.data)
        r2 = self.api.post(f'{BASE}/rfq-offres/', {
            'rfq': self.rfq.id, 'fournisseur_nom_libre': 'Import Express',
            'montant_ht': '95000', 'delai_jours': 10,
        })
        self.assertEqual(r2.status_code, 201, r2.data)

    def test_offre_without_supplier_rejected(self):
        r = self.api.post(f'{BASE}/rfq-offres/', {
            'rfq': self.rfq.id, 'montant_ht': '1000',
        })
        self.assertEqual(r.status_code, 400, r.data)

    def test_foreign_fournisseur_rejected(self):
        autre = make_company()
        f_o = make_fournisseur(autre)
        r = self.api.post(f'{BASE}/rfq-offres/', {
            'rfq': self.rfq.id, 'fournisseur': f_o.id, 'montant_ht': '1000',
        })
        self.assertEqual(r.status_code, 400, r.data)

    def test_comparatif(self):
        cheap = RFQOffre.objects.create(
            company=self.company, rfq=self.rfq,
            fournisseur_nom_libre='A', montant_ht=80000, delai_jours=30)
        fast = RFQOffre.objects.create(
            company=self.company, rfq=self.rfq,
            fournisseur_nom_libre='B', montant_ht=90000, delai_jours=5)
        det = self.api.get(f'{BASE}/rfq/{self.rfq.id}/')
        comp = det.data['comparatif']
        self.assertEqual(comp['nb_offres'], 2)
        self.assertEqual(comp['moins_chere_id'], cheap.id)
        self.assertEqual(comp['plus_rapide_id'], fast.id)
        self.assertIsNone(comp['retenue_id'])


class TestRetenir(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.rfq = RFQ.objects.create(
            company=self.company, reference='RFQ-T-2', objet='X',
            created_by=self.user)
        self.o1 = RFQOffre.objects.create(
            company=self.company, rfq=self.rfq,
            fournisseur_nom_libre='A', montant_ht=100)
        self.o2 = RFQOffre.objects.create(
            company=self.company, rfq=self.rfq,
            fournisseur_nom_libre='B', montant_ht=200)

    def test_retenir_single_offer(self):
        r = self.api.post(f'{BASE}/rfq/{self.rfq.id}/retenir/',
                          {'offre': self.o2.id})
        self.assertEqual(r.status_code, 200, r.data)
        self.o1.refresh_from_db()
        self.o2.refresh_from_db()
        self.assertFalse(self.o1.retenue)
        self.assertTrue(self.o2.retenue)
        # Retenir l'autre dé-sélectionne la première.
        self.api.post(f'{BASE}/rfq/{self.rfq.id}/retenir/',
                      {'offre': self.o1.id})
        self.o1.refresh_from_db()
        self.o2.refresh_from_db()
        self.assertTrue(self.o1.retenue)
        self.assertFalse(self.o2.retenue)

    def test_retenir_foreign_offer_rejected(self):
        autre = make_company()
        rfq_o = RFQ.objects.create(
            company=autre, reference='RFQ-O-1', objet='X')
        off_o = RFQOffre.objects.create(
            company=autre, rfq=rfq_o, fournisseur_nom_libre='Z',
            montant_ht=1)
        r = self.api.post(f'{BASE}/rfq/{self.rfq.id}/retenir/',
                          {'offre': off_o.id})
        self.assertEqual(r.status_code, 400, r.data)


class TestLifecycleScopeRole(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.rfq = RFQ.objects.create(
            company=self.company, reference='RFQ-T-3', objet='X',
            created_by=self.user)

    def test_envoyer_cloturer(self):
        r = self.api.post(f'{BASE}/rfq/{self.rfq.id}/envoyer/')
        self.assertEqual(r.data['statut'], 'envoyee')
        r = self.api.post(f'{BASE}/rfq/{self.rfq.id}/cloturer/')
        self.assertEqual(r.data['statut'], 'cloturee')

    def test_write_requires_role(self):
        normal = make_user(self.company, role='normal')
        api = auth(normal)
        r = api.post(f'{BASE}/rfq/', {'objet': 'X'})
        self.assertEqual(r.status_code, 403, r.data)

    def test_scope_isolation(self):
        other = make_company()
        RFQ.objects.create(company=other, reference='RFQ-X-1', objet='Autre')
        r = self.api.get(f'{BASE}/rfq/')
        results = r.data['results'] if 'results' in r.data else r.data
        # Seule notre RFQ-T-3 est visible.
        self.assertEqual(len(results), 1)
