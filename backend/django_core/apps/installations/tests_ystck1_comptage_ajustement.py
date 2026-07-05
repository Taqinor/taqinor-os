"""
YSTCK1 — FG324 comptage cyclique : la validation poste enfin l'écart en
AJUSTEMENT (le document n'est plus mort).

Couvre :
  * terminer une session cyclique avec un écart poste EXACTEMENT un
    `MouvementStock` AJUSTEMENT et aligne `Produit.quantite_stock` sur le
    compté ;
  * une ligne SANS écart (comptée == théorique) ne poste aucun mouvement ;
  * une ligne sans produit catalogue (désignation libre) ou non comptée
    (`quantite_comptee` None) est ignorée ;
  * re-terminer une session déjà TERMINE ne re-poste jamais (idempotence) ;
  * cross-tenant : un produit d'une autre société n'est jamais ajusté.

Run :
    python manage.py test apps.installations.tests_ystck1_comptage_ajustement -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import SessionComptage, ComptageLigne
from apps.stock.models import MouvementStock

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'ystck1-co-{n}', defaults={'nom': nom or f'Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'ystck1-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_produit(company, nom='Panneau 550W', stock=42):
    from apps.stock.models import Produit
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=1500, prix_achat=0,
        quantite_stock=stock)


def make_session(company, user, reference=None):
    return SessionComptage.objects.create(
        company=company, reference=reference or f'CYC-{next(_seq)}',
        created_by=user)


class TerminerAvecEcartTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.produit = make_produit(self.company, stock=42)
        self.session = make_session(self.company, self.user)
        self.ligne = ComptageLigne.objects.create(
            session=self.session, produit=self.produit,
            designation=self.produit.nom, quantite_theorique=42,
            quantite_comptee=45, compte=True)

    def test_terminer_poste_ajustement_et_aligne_stock(self):
        r = self.api.post(
            f'{BASE}/sessions-comptage/{self.session.id}/terminer/', {})
        self.assertEqual(r.status_code, 200, r.data)
        mouvements = MouvementStock.objects.filter(
            company=self.company, produit=self.produit,
            type_mouvement=MouvementStock.TypeMouvement.AJUSTEMENT)
        self.assertEqual(mouvements.count(), 1)
        mv = mouvements.first()
        self.assertEqual(mv.quantite_avant, 42)
        self.assertEqual(mv.quantite_apres, 45)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 45)

    def test_reterminer_ne_reposte_pas(self):
        self.api.post(
            f'{BASE}/sessions-comptage/{self.session.id}/terminer/', {})
        self.api.post(
            f'{BASE}/sessions-comptage/{self.session.id}/terminer/', {})
        mouvements = MouvementStock.objects.filter(
            company=self.company, produit=self.produit,
            type_mouvement=MouvementStock.TypeMouvement.AJUSTEMENT)
        self.assertEqual(mouvements.count(), 1)


class SansEcartTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.produit = make_produit(self.company, stock=10)
        self.session = make_session(self.company, self.user)
        ComptageLigne.objects.create(
            session=self.session, produit=self.produit,
            designation=self.produit.nom, quantite_theorique=10,
            quantite_comptee=10, compte=True)

    def test_aucun_ecart_aucun_mouvement(self):
        r = self.api.post(
            f'{BASE}/sessions-comptage/{self.session.id}/terminer/', {})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(
            MouvementStock.objects.filter(
                company=self.company, produit=self.produit,
                type_mouvement=MouvementStock.TypeMouvement.AJUSTEMENT
            ).count(), 0)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 10)


class LignesIgnoreesTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.session = make_session(self.company, self.user)

    def test_ligne_sans_produit_ignoree(self):
        ComptageLigne.objects.create(
            session=self.session, produit=None,
            designation='Prestation libre', quantite_theorique=5,
            quantite_comptee=8, compte=True)
        r = self.api.post(
            f'{BASE}/sessions-comptage/{self.session.id}/terminer/', {})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(MouvementStock.objects.filter(
            company=self.company).count(), 0)

    def test_ligne_non_comptee_ignoree(self):
        produit = make_produit(self.company, stock=5)
        ComptageLigne.objects.create(
            session=self.session, produit=produit,
            designation=produit.nom, quantite_theorique=5,
            quantite_comptee=None, compte=False)
        r = self.api.post(
            f'{BASE}/sessions-comptage/{self.session.id}/terminer/', {})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(MouvementStock.objects.filter(
            company=self.company, produit=produit).count(), 0)


class IsolationSocieteTests(TestCase):
    def test_ajustement_scope_societe(self):
        co1 = make_company()
        co2 = make_company()
        user1 = make_user(co1)
        produit1 = make_produit(co1, stock=20)
        produit2 = make_produit(co2, stock=20)
        session1 = make_session(co1, user1)
        ComptageLigne.objects.create(
            session=session1, produit=produit1, designation=produit1.nom,
            quantite_theorique=20, quantite_comptee=25, compte=True)
        api1 = auth(user1)
        api1.post(f'{BASE}/sessions-comptage/{session1.id}/terminer/', {})
        self.assertEqual(
            MouvementStock.objects.filter(produit=produit1).count(), 1)
        self.assertEqual(
            MouvementStock.objects.filter(produit=produit2).count(), 0)
