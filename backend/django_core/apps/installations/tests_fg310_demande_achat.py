"""
FG310 — Demande d'achat (réquisition) → approbation.

Couvre :
  * création via l'API avec référence (`DA-`) + société + ``created_by`` posés
    CÔTÉ SERVEUR (jamais count()+1) ;
  * l'injection de ``company``/``reference``/``statut`` est ignorée ;
  * chantier/programme/fournisseur_suggere d'une autre société rejetés ;
  * le cycle de vie soumettre → approuver / refuser → marquer_commandee et leurs
    gardes d'état ;
  * une ligne (produit catalogue OU désignation libre) + montant_estime ;
  * une ligne pointant un produit d'une autre société est rejetée ;
  * le scope société et la barrière de rôle (écriture/approbation
    responsable/admin).

Run :
    python manage.py test apps.installations.tests_fg310_demande_achat -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import DemandeAchat

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'fg310-co-{n}', defaults={'nom': nom or f'FG310 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'fg310-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_produit(company, nom='Panneau 550W'):
    from apps.stock.models import Produit
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=1500, prix_achat=1000)


def make_fournisseur(company, nom='SolarImport'):
    from apps.stock.models import Fournisseur
    return Fournisseur.objects.create(company=company, nom=nom)


class TestDemandeCreation(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)

    def test_create_server_side_ref(self):
        r = self.api.post(f'{BASE}/demandes-achat/', {
            'objet': '12 panneaux pour chantier Khouribga',
            'priorite': 'haute',
        })
        self.assertEqual(r.status_code, 201, r.data)
        da = DemandeAchat.objects.get(id=r.data['id'])
        self.assertEqual(da.company_id, self.company.id)
        self.assertEqual(da.created_by_id, self.user.id)
        self.assertTrue(da.reference.startswith('DA-'), da.reference)
        self.assertEqual(da.statut, DemandeAchat.Statut.BROUILLON)

    def test_injected_fields_ignored(self):
        autre = make_company()
        r = self.api.post(f'{BASE}/demandes-achat/', {
            'company': autre.id, 'reference': 'DA-HACK', 'statut': 'approuvee',
            'objet': 'Test',
        })
        self.assertEqual(r.status_code, 201, r.data)
        da = DemandeAchat.objects.get(id=r.data['id'])
        self.assertEqual(da.company_id, self.company.id)
        self.assertNotEqual(da.reference, 'DA-HACK')
        self.assertEqual(da.statut, DemandeAchat.Statut.BROUILLON)

    def test_foreign_fournisseur_rejected(self):
        autre = make_company()
        f_o = make_fournisseur(autre)
        r = self.api.post(f'{BASE}/demandes-achat/', {
            'objet': 'Test', 'fournisseur_suggere': f_o.id,
        })
        self.assertEqual(r.status_code, 400, r.data)

    def test_blank_objet_rejected(self):
        r = self.api.post(f'{BASE}/demandes-achat/', {'objet': '   '})
        self.assertEqual(r.status_code, 400, r.data)


class TestLifecycle(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.da = DemandeAchat.objects.create(
            company=self.company, reference='DA-T-1', objet='Test',
            created_by=self.user)

    def test_full_approval_flow(self):
        r = self.api.post(f'{BASE}/demandes-achat/{self.da.id}/soumettre/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['statut'], 'soumise')

        r = self.api.post(f'{BASE}/demandes-achat/{self.da.id}/approuver/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['statut'], 'approuvee')
        self.assertEqual(r.data['approuvee_par'], self.user.id)
        self.assertIsNotNone(r.data['date_decision'])

        r = self.api.post(
            f'{BASE}/demandes-achat/{self.da.id}/marquer_commandee/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['statut'], 'commandee')

    def test_cannot_approve_unsubmitted(self):
        r = self.api.post(f'{BASE}/demandes-achat/{self.da.id}/approuver/')
        self.assertEqual(r.status_code, 400, r.data)

    def test_refuser_with_motif(self):
        self.api.post(f'{BASE}/demandes-achat/{self.da.id}/soumettre/')
        r = self.api.post(f'{BASE}/demandes-achat/{self.da.id}/refuser/',
                          {'motif_refus': 'Budget dépassé'})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['statut'], 'refusee')
        self.assertEqual(r.data['motif_refus'], 'Budget dépassé')

    def test_cannot_order_unapproved(self):
        r = self.api.post(
            f'{BASE}/demandes-achat/{self.da.id}/marquer_commandee/')
        self.assertEqual(r.status_code, 400, r.data)


class TestLignes(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.da = DemandeAchat.objects.create(
            company=self.company, reference='DA-T-2', objet='Test',
            created_by=self.user)
        self.produit = make_produit(self.company)

    def test_create_ligne_and_montant(self):
        r = self.api.post(f'{BASE}/demandes-achat-lignes/', {
            'demande': self.da.id, 'produit': self.produit.id,
            'quantite': '12', 'prix_estime': '1000',
        })
        self.assertEqual(r.status_code, 201, r.data)
        # montant estimé de la demande = 12 × 1000 = 12000.
        det = self.api.get(f'{BASE}/demandes-achat/{self.da.id}/')
        self.assertEqual(float(det.data['montant_estime']), 12000.0)

    def test_ligne_designation_libre(self):
        r = self.api.post(f'{BASE}/demandes-achat-lignes/', {
            'demande': self.da.id, 'designation': 'Boulonnerie inox',
            'quantite': '50', 'prix_estime': '5',
        })
        self.assertEqual(r.status_code, 201, r.data)

    def test_ligne_without_produit_or_designation_rejected(self):
        r = self.api.post(f'{BASE}/demandes-achat-lignes/', {
            'demande': self.da.id, 'quantite': '1', 'prix_estime': '1',
        })
        self.assertEqual(r.status_code, 400, r.data)

    def test_foreign_produit_rejected(self):
        autre = make_company()
        p_o = make_produit(autre)
        r = self.api.post(f'{BASE}/demandes-achat-lignes/', {
            'demande': self.da.id, 'produit': p_o.id,
            'quantite': '1', 'prix_estime': '1',
        })
        self.assertEqual(r.status_code, 400, r.data)


class TestScopeAndRole(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)

    def test_write_requires_role(self):
        normal = make_user(self.company, role='normal')
        api = auth(normal)
        r = api.post(f'{BASE}/demandes-achat/', {'objet': 'Test'})
        self.assertEqual(r.status_code, 403, r.data)

    def test_scope_isolation(self):
        other = make_company()
        DemandeAchat.objects.create(
            company=other, reference='DA-O-1', objet='Autre')
        DemandeAchat.objects.create(
            company=self.company, reference='DA-M-1', objet='Mien')
        r = self.api.get(f'{BASE}/demandes-achat/')
        results = r.data['results'] if 'results' in r.data else r.data
        self.assertEqual(len(results), 1)
