"""XSTK14 — Revalorisation manuelle du stock (document trace).

Couvre :
  * creation en brouillon : snapshot ancien cout + quantite, delta calcule ;
  * motif obligatoire ;
  * la validation verrouille le document (statut + date_validation) ;
  * apres validation, le nouveau cout devient la couche de depart du cout
    moyen (`average_cost_with_source`) ; les receptions ANTERIEURES a la
    validation ne comptent plus, seules les POSTERIEURES s'y ajoutent ;
  * un document valide n'est plus modifiable ni supprimable (droits) ;
  * un second `valider/` sur le meme document est refuse.

Run:
    python manage.py test apps.stock.test_xstk14_revalorisation_stock -v 2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, LigneBonCommandeFournisseur,
    Produit, RevalorisationStock,
)
from apps.stock.services import (
    average_cost_with_source, creer_revalorisation, valider_revalorisation,
)

User = get_user_model()


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _user(company, username, is_admin=True, permissions=None):
    # Un Role fin n'est créé QUE si des permissions explicites sont passées :
    # sinon `is_admin_role`/`is_responsable` retombent sur
    # `'roles_gerer' in role.permissions` (False pour un rôle vide) au lieu du
    # repli légitime par `role_legacy` (ERR4, authentication/models.py).
    role = None
    if permissions is not None:
        role = Role.objects.create(
            company=company, nom=f'r-{username}', permissions=permissions)
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy='admin' if is_admin else 'responsable')


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Xstk14Base(TestCase):
    def setUp(self):
        self.company = _company('xstk14-co')
        self.admin = _user(self.company, 'xstk14-admin')
        self.api = _api(self.admin)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur XSTK14')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau XSTK14', sku='PAN-XSTK14',
            prix_vente=Decimal('4000'), prix_achat=Decimal('2000'),
            quantite_stock=10)

    def _bcf_recu(self, quantite, prix, date_bcf):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-XSTK14-{date_bcf}',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.RECU)
        BonCommandeFournisseur.objects.filter(pk=bc.pk).update(
            date_creation=datetime.datetime.combine(
                date_bcf, datetime.time(12, 0)))
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc, produit=self.produit, quantite=quantite,
            prix_achat_unitaire=Decimal(prix), quantite_recue=quantite)
        return bc


class CreerRevalorisationTests(Xstk14Base):
    def test_snapshot_ancien_cout_et_quantite(self):
        self._bcf_recu(10, '1500', datetime.date(2026, 1, 1))
        revalo = creer_revalorisation(
            company=self.company, produit=self.produit,
            nouveau_cout='1200', motif='Baisse mondiale du prix des panneaux',
            user=self.admin)
        self.assertEqual(revalo.ancien_cout, Decimal('1500.00'))
        self.assertEqual(revalo.nouveau_cout, Decimal('1200'))
        self.assertEqual(revalo.quantite_snapshot, 10)
        self.assertEqual(revalo.delta_valeur, Decimal('-3000.00'))
        self.assertEqual(revalo.statut, RevalorisationStock.Statut.BROUILLON)

    def test_motif_obligatoire(self):
        with self.assertRaises(ValueError):
            creer_revalorisation(
                company=self.company, produit=self.produit,
                nouveau_cout='1200', motif='', user=self.admin)

    def test_endpoint_creation(self):
        resp = self.api.post(
            '/api/django/stock/revalorisations-stock/',
            {'produit': self.produit.pk, 'nouveau_cout': '1800',
             'motif': 'Dépréciation'}, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()['statut'], 'brouillon')


class ValiderRevalorisationTests(Xstk14Base):
    def test_validation_verrouille_le_document(self):
        revalo = creer_revalorisation(
            company=self.company, produit=self.produit,
            nouveau_cout='1200', motif='Test', user=self.admin)
        valider_revalorisation(revalo)
        revalo.refresh_from_db()
        self.assertEqual(revalo.statut, RevalorisationStock.Statut.VALIDEE)
        self.assertIsNotNone(revalo.date_validation)

    def test_second_validation_refusee(self):
        revalo = creer_revalorisation(
            company=self.company, produit=self.produit,
            nouveau_cout='1200', motif='Test', user=self.admin)
        valider_revalorisation(revalo)
        with self.assertRaises(ValueError):
            valider_revalorisation(revalo)

    def test_apres_validation_nouveau_cout_couche_de_depart(self):
        # Reception anterieure a la revalo : ne doit plus compter seule.
        self._bcf_recu(10, '1500', datetime.date(2026, 1, 1))
        revalo = creer_revalorisation(
            company=self.company, produit=self.produit,
            nouveau_cout='1200', motif='Baisse marché', user=self.admin)
        valider_revalorisation(revalo)
        cout, source = average_cost_with_source(self.produit)
        self.assertEqual(cout, Decimal('1200.00'))
        self.assertEqual(source, 'revalorisation')

        # Une reception POSTERIEURE a la validation vient se moyenner avec
        # la nouvelle couche de depart (10 @ 1200 puis 10 @ 1400 -> 1300).
        future_bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-XSTK14-future',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.RECU)
        BonCommandeFournisseur.objects.filter(pk=future_bcf.pk).update(
            date_creation=revalo.date_validation + datetime.timedelta(days=1))
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=future_bcf, produit=self.produit, quantite=10,
            prix_achat_unitaire=Decimal('1400'), quantite_recue=10)
        cout, source = average_cost_with_source(self.produit)
        self.assertEqual(cout, Decimal('1300.00'))
        self.assertEqual(source, 'revalorisation')

    def test_document_valide_verrouille_endpoint(self):
        revalo = creer_revalorisation(
            company=self.company, produit=self.produit,
            nouveau_cout='1200', motif='Test', user=self.admin)
        valider_revalorisation(revalo)
        resp = self.api.patch(
            f'/api/django/stock/revalorisations-stock/{revalo.pk}/',
            {'motif': 'modifie'}, format='json')
        self.assertEqual(resp.status_code, 400)
        resp = self.api.delete(
            f'/api/django/stock/revalorisations-stock/{revalo.pk}/')
        self.assertEqual(resp.status_code, 400)

    def test_endpoint_valider(self):
        revalo = creer_revalorisation(
            company=self.company, produit=self.produit,
            nouveau_cout='1200', motif='Test', user=self.admin)
        resp = self.api.post(
            f'/api/django/stock/revalorisations-stock/{revalo.pk}/valider/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['statut'], 'validee')

    def test_endpoint_admin_only(self):
        non_admin = _user(
            self.company, 'xstk14-nonadmin', is_admin=False,
            permissions=['stock_voir'])
        api = _api(non_admin)
        resp = api.post(
            '/api/django/stock/revalorisations-stock/',
            {'produit': self.produit.pk, 'nouveau_cout': '1200',
             'motif': 'Test'}, format='json')
        self.assertEqual(resp.status_code, 403)
