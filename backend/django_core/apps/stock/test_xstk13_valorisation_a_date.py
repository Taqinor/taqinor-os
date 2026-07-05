"""XSTK13 — Valorisation a date (as-of) + inventaire annuel legal (CGNC).

Couvre :
  * `valorisation_a_date` reconstruit la quantite ET le cout a une date
    passee a partir des mouvements/receptions anterieures (une reception
    posterieure a la date n'est pas comptee) ;
  * un produit sans mouvement avant la date -> absent du rapport ;
  * `figer_inventaire_annuel` archive un snapshot complet, se relit a
    l'identique, et refuse un second figement pour le meme exercice ;
  * l'endpoint `produits/valorisation-a-date/` est admin-only et valide la
    date.

Run:
    python manage.py test apps.stock.test_xstk13_valorisation_a_date -v 2
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
    BonCommandeFournisseur, Fournisseur, InventaireAnnuel,
    LigneBonCommandeFournisseur, MouvementStock, Produit,
)
from apps.stock.services import figer_inventaire_annuel, valorisation_a_date

User = get_user_model()


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _user(company, username, is_admin=True, permissions=None):
    role = Role.objects.create(
        company=company, nom=f'r-{username}', permissions=permissions or [])
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy='admin' if is_admin else 'responsable')


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Xstk13Base(TestCase):
    def setUp(self):
        self.company = _company('xstk13-co')
        self.admin = _user(self.company, 'xstk13-admin')
        self.api = _api(self.admin)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur XSTK13')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur XSTK13', sku='OND-XSTK13',
            prix_vente=Decimal('3000'), prix_achat=Decimal('1500'),
            quantite_stock=0)

    def _bcf_recu(self, quantite, prix, date_bcf):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-XSTK13-{date_bcf}',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.RECU)
        BonCommandeFournisseur.objects.filter(pk=bc.pk).update(
            date_creation=datetime.datetime.combine(
                date_bcf, datetime.time(12, 0)))
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc, produit=self.produit, quantite=quantite,
            prix_achat_unitaire=Decimal(prix), quantite_recue=quantite)
        avant = self.produit.quantite_stock
        apres = avant + quantite
        mvt = MouvementStock.objects.create(
            company=self.company, produit=self.produit,
            type_mouvement=MouvementStock.TypeMouvement.ENTREE,
            quantite=quantite, quantite_avant=avant, quantite_apres=apres,
            reference=bc.reference)
        MouvementStock.objects.filter(pk=mvt.pk).update(
            date=datetime.datetime.combine(date_bcf, datetime.time(12, 0)))
        self.produit.quantite_stock = apres
        self.produit.save(update_fields=['quantite_stock'])
        return bc


class ValorisationADateTests(Xstk13Base):
    def test_reconstruit_quantite_et_cout_a_une_date_passee(self):
        # Reception de 10 @ 1000 en janvier, puis 10 @ 1400 en mars.
        self._bcf_recu(10, '1000', datetime.date(2026, 1, 15))
        self._bcf_recu(10, '1400', datetime.date(2026, 3, 15))

        # A la date de fevrier : seule la 1ere reception compte.
        rapport_fevrier = valorisation_a_date(
            self.company, datetime.date(2026, 2, 1))
        ligne = rapport_fevrier['lignes'][0]
        self.assertEqual(ligne['quantite'], 10)
        self.assertEqual(ligne['cout_moyen'], Decimal('1000.00'))
        self.assertEqual(ligne['valeur'], Decimal('10000.00'))

        # A la date d'avril : les deux receptions comptent (moyenne ponderee).
        rapport_avril = valorisation_a_date(
            self.company, datetime.date(2026, 4, 1))
        ligne = rapport_avril['lignes'][0]
        self.assertEqual(ligne['quantite'], 20)
        self.assertEqual(ligne['cout_moyen'], Decimal('1200.00'))
        self.assertEqual(ligne['valeur'], Decimal('24000.00'))

    def test_produit_sans_mouvement_avant_la_date_absent(self):
        self._bcf_recu(10, '1000', datetime.date(2026, 6, 1))
        rapport = valorisation_a_date(self.company, datetime.date(2026, 1, 1))
        self.assertEqual(rapport['lignes'], [])

    def test_endpoint_valorisation_a_date(self):
        self._bcf_recu(5, '800', datetime.date(2026, 1, 1))
        resp = self.api.get(
            '/api/django/stock/produits/valorisation-a-date/'
            '?date=2026-02-01')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()['lignes']), 1)

    def test_endpoint_exige_le_parametre_date(self):
        resp = self.api.get('/api/django/stock/produits/valorisation-a-date/')
        self.assertEqual(resp.status_code, 400)

    def test_endpoint_date_invalide(self):
        resp = self.api.get(
            '/api/django/stock/produits/valorisation-a-date/?date=pas-une-date')
        self.assertEqual(resp.status_code, 400)

    def test_endpoint_admin_only(self):
        non_admin = _user(
            self.company, 'xstk13-nonadmin', is_admin=False,
            permissions=['stock_voir'])
        api = _api(non_admin)
        resp = api.get(
            '/api/django/stock/produits/valorisation-a-date/?date=2026-01-01')
        self.assertEqual(resp.status_code, 403)


class InventaireAnnuelTests(Xstk13Base):
    def test_figer_archive_snapshot_complet(self):
        self._bcf_recu(10, '1000', datetime.date(2026, 1, 15))
        inventaire = figer_inventaire_annuel(self.company, 2026, self.admin)
        self.assertEqual(inventaire.exercice, 2026)
        self.assertEqual(inventaire.date_reference, datetime.date(2026, 12, 31))
        self.assertEqual(inventaire.total_valeur, Decimal('10000.00'))
        self.assertEqual(inventaire.nb_lignes, 1)
        self.assertEqual(inventaire.donnees['lignes'][0]['sku'], 'OND-XSTK13')

    def test_relit_a_l_identique(self):
        self._bcf_recu(10, '1000', datetime.date(2026, 1, 15))
        inventaire = figer_inventaire_annuel(self.company, 2026, self.admin)
        relu = InventaireAnnuel.objects.get(pk=inventaire.pk)
        self.assertEqual(relu.donnees, inventaire.donnees)
        self.assertEqual(relu.total_valeur, inventaire.total_valeur)

    def test_second_figement_refuse(self):
        self._bcf_recu(10, '1000', datetime.date(2026, 1, 15))
        figer_inventaire_annuel(self.company, 2026, self.admin)
        with self.assertRaises(ValueError):
            figer_inventaire_annuel(self.company, 2026, self.admin)
        # toujours un seul enregistrement pour cet exercice
        self.assertEqual(
            InventaireAnnuel.objects.filter(
                company=self.company, exercice=2026).count(), 1)

    def test_ne_peut_plus_etre_modifie_via_le_serializer(self):
        self._bcf_recu(10, '1000', datetime.date(2026, 1, 15))
        inventaire = figer_inventaire_annuel(self.company, 2026, self.admin)
        resp = self.api.patch(
            f'/api/django/stock/inventaires-annuels/{inventaire.pk}/',
            {'total_valeur': '999999'}, format='json')
        # ReadOnlyModelViewSet : PATCH non route (405)
        self.assertEqual(resp.status_code, 405)

    def test_endpoint_figer(self):
        self._bcf_recu(10, '1000', datetime.date(2026, 1, 15))
        resp = self.api.post(
            '/api/django/stock/inventaires-annuels/figer/',
            {'exercice': 2026}, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()['exercice'], 2026)

    def test_endpoint_figer_deuxieme_fois_refuse(self):
        self._bcf_recu(10, '1000', datetime.date(2026, 1, 15))
        self.api.post(
            '/api/django/stock/inventaires-annuels/figer/',
            {'exercice': 2026}, format='json')
        resp = self.api.post(
            '/api/django/stock/inventaires-annuels/figer/',
            {'exercice': 2026}, format='json')
        self.assertEqual(resp.status_code, 400)
