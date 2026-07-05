"""
YSTCK2 — FG325 demande de transfert : `executer` déplace enfin le stock (le
workflow d'approbation n'est plus décoratif).

Couvre :
  * exécuter une demande approuvée crée le `TransfertStock` et ventile
    source→destination (total canonique inchangé) ;
  * une source insuffisante bloque avec un message clair (409, aucun
    changement de statut) ;
  * re-exécuter (statut déjà EXECUTE) ne double jamais le transfert
    (garde de statut existante) ;
  * isolation multi-tenant.

Run :
    python manage.py test apps.installations.tests_ystck2_transfert_executer -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import DemandeTransfert
from apps.stock.models import TransfertStock

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'ystck2-co-{n}', defaults={'nom': nom or f'Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'ystck2-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_emplacement(company, nom, is_principal=False):
    from apps.stock.models import EmplacementStock
    return EmplacementStock.objects.create(
        company=company, nom=nom, is_principal=is_principal)


def make_produit(company, nom='Panneau 550W', stock=0):
    from apps.stock.models import Produit
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=1500, prix_achat=0,
        quantite_stock=stock)


def make_demande_approuvee(company, produit, source, destination, quantite):
    return DemandeTransfert.objects.create(
        company=company, reference=f'DTR-{next(_seq)}', produit=produit,
        source=source, destination=destination, quantite=quantite,
        statut=DemandeTransfert.Statut.APPROUVE)


class ExecuterVentileStockTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.src = make_emplacement(
            self.company, 'Dépôt principal', is_principal=True)
        self.dst = make_emplacement(self.company, 'Camionnette 1')
        self.produit = make_produit(self.company, stock=10)
        self.dt = make_demande_approuvee(
            self.company, self.produit, self.src, self.dst, 4)

    def test_executer_cree_transfert_et_ventile(self):
        r = self.api.post(
            f'{BASE}/demandes-transfert/{self.dt.id}/executer/', {},
            format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.dt.refresh_from_db()
        self.assertEqual(self.dt.statut, DemandeTransfert.Statut.EXECUTE)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 10)  # total inchangé
        transferts = TransfertStock.objects.filter(
            company=self.company, produit=self.produit,
            source=self.src, destination=self.dst)
        self.assertEqual(transferts.count(), 1)
        self.assertEqual(transferts.first().quantite, 4)

    def test_reexecuter_ne_double_pas(self):
        self.api.post(
            f'{BASE}/demandes-transfert/{self.dt.id}/executer/', {},
            format='json')
        r2 = self.api.post(
            f'{BASE}/demandes-transfert/{self.dt.id}/executer/', {},
            format='json')
        self.assertEqual(r2.status_code, 409, r2.content)
        self.assertEqual(
            TransfertStock.objects.filter(company=self.company).count(), 1)


class SourceInsuffisanteTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.src = make_emplacement(
            self.company, 'Dépôt principal', is_principal=True)
        self.dst = make_emplacement(self.company, 'Camionnette 1')
        self.produit = make_produit(self.company, stock=2)
        self.dt = make_demande_approuvee(
            self.company, self.produit, self.src, self.dst, 10)

    def test_executer_source_insuffisante_409_sans_changement_statut(self):
        r = self.api.post(
            f'{BASE}/demandes-transfert/{self.dt.id}/executer/', {},
            format='json')
        self.assertEqual(r.status_code, 409, r.content)
        self.dt.refresh_from_db()
        self.assertEqual(self.dt.statut, DemandeTransfert.Statut.APPROUVE)
        self.assertEqual(
            TransfertStock.objects.filter(company=self.company).count(), 0)


class IsolationSocieteTests(TestCase):
    def test_transfert_scope_societe(self):
        co1 = make_company()
        co2 = make_company()
        user1 = make_user(co1)
        src1 = make_emplacement(co1, 'Dépôt 1', is_principal=True)
        dst1 = make_emplacement(co1, 'Van 1')
        produit1 = make_produit(co1, stock=10)
        dt1 = make_demande_approuvee(co1, produit1, src1, dst1, 3)
        api1 = auth(user1)
        api1.post(
            f'{BASE}/demandes-transfert/{dt1.id}/executer/', {},
            format='json')
        self.assertEqual(
            TransfertStock.objects.filter(company=co1).count(), 1)
        self.assertEqual(
            TransfertStock.objects.filter(company=co2).count(), 0)
