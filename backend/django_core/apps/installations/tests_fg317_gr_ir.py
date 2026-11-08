"""
FG317 — Réceptionné-non-facturé (GR/IR), dette latente provisionnée.

Couvre :
  * création via l'API : société + ``created_by`` posés CÔTÉ SERVEUR ;
  * un BCF / une réception d'une autre société rejetés ;
  * montant_a_provisionner = montant_provision tant que non lettré, 0 après ;
  * l'action `lettrer` (idempotente, pose la facture validée tenant) ;
  * une facture d'une autre société est rejetée au lettrage ;
  * le scope société et la barrière de rôle (écriture responsable/admin).

Run :
    python manage.py test apps.installations.tests_fg317_gr_ir -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import ReceptionNonFacturee

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'fg317-co-{n}', defaults={'nom': nom or f'FG317 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'fg317-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_bcf(company):
    from apps.stock.models import Fournisseur, BonCommandeFournisseur
    n = next(_seq)
    f = Fournisseur.objects.create(company=company, nom=f'Four-{n}')
    return BonCommandeFournisseur.objects.create(
        company=company, reference=f'BCF-{n}', fournisseur=f)


def make_facture(company):
    from apps.stock.models import Fournisseur, FactureFournisseur
    n = next(_seq)
    f = Fournisseur.objects.create(company=company, nom=f'FF-{n}')
    return FactureFournisseur.objects.create(
        company=company, reference=f'FF-{n}', fournisseur=f, montant_ht=1000)


class TestProvisionCreation(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.bcf = make_bcf(self.company)

    def test_create_server_side(self):
        r = self.api.post(f'{BASE}/receptions-non-facturees/', {
            'bon_commande': self.bcf.id, 'montant_provision': '25000',
            'libelle': 'Panneaux reçus, facture en attente',
        })
        self.assertEqual(r.status_code, 201, r.data)
        prov = ReceptionNonFacturee.objects.get(id=r.data['id'])
        self.assertEqual(prov.company_id, self.company.id)
        self.assertEqual(prov.created_by_id, self.user.id)
        self.assertFalse(prov.lettre)
        self.assertEqual(float(r.data['montant_a_provisionner']), 25000.0)

    def test_montant_negatif_400_nomme(self):
        # api-fuzz full : borne basse publiée (motif sans signe `-`).
        r = self.api.post(f'{BASE}/receptions-non-facturees/', {
            'bon_commande': self.bcf.id, 'montant_provision': '-10.05',
        })
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('montant_provision', r.data)

    def test_foreign_bcf_rejected(self):
        autre = make_company()
        bcf_o = make_bcf(autre)
        r = self.api.post(f'{BASE}/receptions-non-facturees/', {
            'bon_commande': bcf_o.id, 'montant_provision': '1',
        })
        self.assertEqual(r.status_code, 404, r.data)


class TestLettrer(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.bcf = make_bcf(self.company)
        self.prov = ReceptionNonFacturee.objects.create(
            company=self.company, bon_commande=self.bcf,
            montant_provision=10000)

    def test_lettrer_clears_provision(self):
        facture = make_facture(self.company)
        r = self.api.post(
            f'{BASE}/receptions-non-facturees/{self.prov.id}/lettrer/',
            {'facture': facture.id})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data['lettre'])
        self.assertIsNotNone(r.data['date_lettrage'])
        self.assertEqual(r.data['facture'], facture.id)
        self.assertEqual(float(r.data['montant_a_provisionner']), 0.0)

    def test_lettrer_idempotent_without_facture(self):
        self.api.post(
            f'{BASE}/receptions-non-facturees/{self.prov.id}/lettrer/')
        r2 = self.api.post(
            f'{BASE}/receptions-non-facturees/{self.prov.id}/lettrer/')
        self.assertEqual(r2.status_code, 200, r2.data)
        self.assertTrue(r2.data['lettre'])

    def test_lettrer_foreign_facture_rejected(self):
        autre = make_company()
        facture_o = make_facture(autre)
        r = self.api.post(
            f'{BASE}/receptions-non-facturees/{self.prov.id}/lettrer/',
            {'facture': facture_o.id})
        self.assertEqual(r.status_code, 404, r.data)  # ENF11 : id inconnu de la société


class TestScopeRole(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.bcf = make_bcf(self.company)

    def test_write_requires_role(self):
        normal = make_user(self.company, role='normal')
        api = auth(normal)
        r = api.post(f'{BASE}/receptions-non-facturees/', {
            'bon_commande': self.bcf.id, 'montant_provision': '1',
        })
        self.assertEqual(r.status_code, 403, r.data)

    def test_technicien_sans_prix_achat_403(self):
        """AAPV61 — rôles système sans `prix_achat_voir`/`achats_payer` : 403
        partout ; `prix_achat_voir` lit sans écrire ; Administrateur 200/204."""
        from django.core.management import call_command
        from apps.roles.models import Role
        call_command('init_roles', verbosity=0)

        def api_role(nom, perms=None):
            if perms is None:
                role = Role.objects.get(company=self.company, nom=nom)
            else:
                role = Role.objects.create(
                    company=self.company, nom=f'AAPV61 {next(_seq)}',
                    permissions=perms)
            u = User.objects.create_user(
                username=f'aapv61-{next(_seq)}', password='x',
                company=self.company, role=role)
            return auth(u)
        prov = ReceptionNonFacturee.objects.create(
            company=self.company, bon_commande=self.bcf,
            montant_provision=1000)
        url = f'{BASE}/receptions-non-facturees/'
        for nom in ('Technicien', 'Technicien responsable'):
            with self.subTest(role=nom):
                api = api_role(nom)
                self.assertEqual(api.get(url).status_code, 403)
                self.assertEqual(
                    api.post(f'{url}{prov.id}/lettrer/', {}).status_code, 403)
                self.assertEqual(api.delete(f'{url}{prov.id}/').status_code, 403)
                self.assertEqual(api.post(url, {
                    'bon_commande': self.bcf.id, 'montant_provision': '5',
                }).status_code, 403)
        prov.refresh_from_db()
        self.assertFalse(prov.lettre)
        lecteur = api_role(None, ['prix_achat_voir'])
        self.assertEqual(lecteur.get(url).status_code, 200)
        self.assertEqual(
            lecteur.post(f'{url}{prov.id}/lettrer/', {}).status_code, 403)
        payeur = api_role(None, ['achats_payer'])
        self.assertEqual(
            payeur.post(f'{url}{prov.id}/lettrer/', {}).status_code, 200)
        admin = api_role('Administrateur')
        self.assertEqual(admin.get(url).status_code, 200)
        self.assertEqual(admin.delete(f'{url}{prov.id}/').status_code, 204)

    def test_scope_isolation(self):
        other = make_company()
        bcf_o = make_bcf(other)
        ReceptionNonFacturee.objects.create(
            company=other, bon_commande=bcf_o, montant_provision=1)
        ReceptionNonFacturee.objects.create(
            company=self.company, bon_commande=self.bcf, montant_provision=1)
        r = self.api.get(f'{BASE}/receptions-non-facturees/')
        results = r.data['results'] if 'results' in r.data else r.data
        self.assertEqual(len(results), 1)

    def test_filter_lettre(self):
        ReceptionNonFacturee.objects.create(
            company=self.company, bon_commande=self.bcf,
            montant_provision=1, lettre=True)
        ReceptionNonFacturee.objects.create(
            company=self.company, bon_commande=self.bcf,
            montant_provision=2, lettre=False)
        r = self.api.get(f'{BASE}/receptions-non-facturees/?lettre=false')
        results = r.data['results'] if 'results' in r.data else r.data
        self.assertEqual(len(results), 1)
