"""XSTK6 — Registre de lots en entrepôt + sortie FEFO + blocage du périmé.

Couvre :
  * confirmer une réception dont la ligne porte `numero_lot` alimente
    `LotEntrepot` (quantité reçue/restante) ;
  * une ligne SANS numero_lot ne crée aucun `LotEntrepot` (comportement
    historique inchangé) ;
  * la suggestion FEFO propose le lot à péremption la plus proche d'abord ;
  * sortir un lot PÉRIMÉ est bloqué par défaut (garde société ON) ;
  * `forcer=True` + motif contourne le blocage (tracé) ; sans motif → refus ;
  * sortir plus que le restant est refusé ;
  * endpoints `lots-entrepot/fefo/` et `lots-entrepot/{id}/sortir/`.

Run:
    python manage.py test apps.stock.test_xstk6_lot_entrepot -v 2
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import (
    AchatsParametres, BonCommandeFournisseur, Fournisseur, LotEntrepot,
    Produit, ReceptionFournisseur,
)
from apps.stock.services import (
    confirm_reception_fournisseur, sortir_lot_entrepot, suggestion_fefo,
)

User = get_user_model()


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _user(company, username, permissions=None):
    role = Role.objects.create(
        company=company, nom=f'r-{username}', permissions=permissions or [])
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy='responsable')


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Xstk6Base(TestCase):
    def setUp(self):
        self.company = _company('xstk6-co')
        self.user = _user(
            self.company, 'xstk6-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur X6')
        self.produit = Produit.objects.create(
            company=self.company, nom='Batterie LFP', sku='BAT-X6',
            prix_vente=Decimal('8000'), prix_achat=Decimal('5000'),
            quantite_stock=0)

    def _bcf(self, quantite=10):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-X6-{Produit.objects.count()}',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        bc.lignes.create(
            produit=self.produit, quantite=quantite,
            prix_achat_unitaire=Decimal('5000'))
        return bc

    def _confirm_reception_avec_lot(
            self, quantite, numero_lot, date_peremption=None):
        bc = self._bcf(quantite=quantite)
        ligne = bc.lignes.first()
        reception = ReceptionFournisseur.objects.create(
            company=self.company, reference=f'REC-X6-{numero_lot}',
            bon_commande=bc)
        reception.lignes.create(
            ligne_commande=ligne, produit=self.produit, quantite=quantite,
            numero_lot=numero_lot, date_peremption=date_peremption)
        confirm_reception_fournisseur(reception, self.user)
        return reception


class TestAlimentationReception(Xstk6Base):
    def test_reception_avec_lot_alimente_lotentrepot(self):
        self._confirm_reception_avec_lot(10, 'LOT-A')
        lot = LotEntrepot.objects.get(
            company=self.company, produit=self.produit, numero_lot='LOT-A')
        self.assertEqual(lot.quantite_recue, 10)
        self.assertEqual(lot.quantite_restante, 10)

    def test_reception_sans_lot_ne_cree_rien(self):
        bc = self._bcf(quantite=5)
        ligne = bc.lignes.first()
        reception = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-X6-SANSLOT',
            bon_commande=bc)
        reception.lignes.create(
            ligne_commande=ligne, produit=self.produit, quantite=5)
        confirm_reception_fournisseur(reception, self.user)
        self.assertEqual(LotEntrepot.objects.count(), 0)

    def test_meme_lot_deux_receptions_cumule(self):
        self._confirm_reception_avec_lot(6, 'LOT-CUMUL')
        self._confirm_reception_avec_lot(4, 'LOT-CUMUL')
        lot = LotEntrepot.objects.get(
            company=self.company, produit=self.produit,
            numero_lot='LOT-CUMUL')
        self.assertEqual(lot.quantite_recue, 10)
        self.assertEqual(lot.quantite_restante, 10)


class TestSuggestionFefo(Xstk6Base):
    def test_lot_plus_proche_peremption_propose_dabord(self):
        today = timezone.now().date()
        self._confirm_reception_avec_lot(
            5, 'LOT-LOIN', today + timedelta(days=90))
        self._confirm_reception_avec_lot(
            5, 'LOT-PROCHE', today + timedelta(days=10))
        plan = suggestion_fefo(self.company, self.produit, 3)
        self.assertEqual(plan[0]['lot'].numero_lot, 'LOT-PROCHE')

    def test_plan_couvre_plusieurs_lots_si_necessaire(self):
        today = timezone.now().date()
        self._confirm_reception_avec_lot(
            3, 'LOT-1', today + timedelta(days=10))
        self._confirm_reception_avec_lot(
            5, 'LOT-2', today + timedelta(days=20))
        plan = suggestion_fefo(self.company, self.produit, 6)
        total = sum(p['quantite'] for p in plan)
        self.assertEqual(total, 6)
        self.assertEqual(plan[0]['lot'].numero_lot, 'LOT-1')


class TestGardePerime(Xstk6Base):
    def test_sortie_lot_perime_bloquee_par_defaut(self):
        yesterday = timezone.now().date() - timedelta(days=1)
        self._confirm_reception_avec_lot(5, 'LOT-PERIME', yesterday)
        lot = LotEntrepot.objects.get(numero_lot='LOT-PERIME')
        with self.assertRaises(ValueError):
            sortir_lot_entrepot(
                company=self.company, lot=lot, quantite=2, user=self.user)
        lot.refresh_from_db()
        self.assertEqual(lot.quantite_restante, 5)

    def test_sortie_lot_perime_forcee_avec_motif_ok(self):
        yesterday = timezone.now().date() - timedelta(days=1)
        self._confirm_reception_avec_lot(5, 'LOT-PERIME-2', yesterday)
        lot = LotEntrepot.objects.get(numero_lot='LOT-PERIME-2')
        sortir_lot_entrepot(
            company=self.company, lot=lot, quantite=2, user=self.user,
            forcer=True, motif='Contrôle qualité OK malgré péremption')
        lot.refresh_from_db()
        self.assertEqual(lot.quantite_restante, 3)

    def test_sortie_lot_perime_forcee_sans_motif_refusee(self):
        yesterday = timezone.now().date() - timedelta(days=1)
        self._confirm_reception_avec_lot(5, 'LOT-PERIME-3', yesterday)
        lot = LotEntrepot.objects.get(numero_lot='LOT-PERIME-3')
        with self.assertRaises(ValueError):
            sortir_lot_entrepot(
                company=self.company, lot=lot, quantite=2, user=self.user,
                forcer=True)

    def test_sortie_lot_perime_autorisee_si_flag_off(self):
        yesterday = timezone.now().date() - timedelta(days=1)
        self._confirm_reception_avec_lot(5, 'LOT-PERIME-4', yesterday)
        lot = LotEntrepot.objects.get(numero_lot='LOT-PERIME-4')
        parametres = AchatsParametres.for_company(self.company)
        parametres.bloquer_stock_perime = False
        parametres.save()
        sortir_lot_entrepot(
            company=self.company, lot=lot, quantite=2, user=self.user)
        lot.refresh_from_db()
        self.assertEqual(lot.quantite_restante, 3)

    def test_sortie_lot_non_perime_ok(self):
        demain = timezone.now().date() + timedelta(days=30)
        self._confirm_reception_avec_lot(5, 'LOT-OK', demain)
        lot = LotEntrepot.objects.get(numero_lot='LOT-OK')
        sortir_lot_entrepot(
            company=self.company, lot=lot, quantite=5, user=self.user)
        lot.refresh_from_db()
        self.assertEqual(lot.quantite_restante, 0)

    def test_sortie_quantite_superieure_au_restant_refusee(self):
        demain = timezone.now().date() + timedelta(days=30)
        self._confirm_reception_avec_lot(5, 'LOT-OK-2', demain)
        lot = LotEntrepot.objects.get(numero_lot='LOT-OK-2')
        with self.assertRaises(ValueError):
            sortir_lot_entrepot(
                company=self.company, lot=lot, quantite=99, user=self.user)


class TestEndpoints(Xstk6Base):
    def test_endpoint_fefo(self):
        today = timezone.now().date()
        self._confirm_reception_avec_lot(
            5, 'LOT-EP-1', today + timedelta(days=5))
        resp = self.api.get(
            f'/api/django/stock/lots-entrepot/fefo/'
            f'?produit={self.produit.id}&quantite=3')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data[0]['numero_lot'], 'LOT-EP-1')
        self.assertEqual(resp.data[0]['quantite'], 3)

    def test_endpoint_sortir(self):
        demain = timezone.now().date() + timedelta(days=30)
        self._confirm_reception_avec_lot(5, 'LOT-EP-2', demain)
        lot = LotEntrepot.objects.get(numero_lot='LOT-EP-2')
        resp = self.api.post(
            f'/api/django/stock/lots-entrepot/{lot.id}/sortir/',
            {'quantite': 2}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['quantite_restante'], 3)

    def test_endpoint_sortir_perime_bloque_400(self):
        hier = timezone.now().date() - timedelta(days=1)
        self._confirm_reception_avec_lot(5, 'LOT-EP-3', hier)
        lot = LotEntrepot.objects.get(numero_lot='LOT-EP-3')
        resp = self.api.post(
            f'/api/django/stock/lots-entrepot/{lot.id}/sortir/',
            {'quantite': 2}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_endpoint_list_scoped_company(self):
        self._confirm_reception_avec_lot(5, 'LOT-EP-4')
        other = _company('xstk6-other')
        other_user = _user(other, 'xstk6-other-user')
        api = _api(other_user)
        resp = api.get('/api/django/stock/lots-entrepot/')
        results = resp.data.get('results', resp.data)
        self.assertEqual(len(results), 0)
