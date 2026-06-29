"""Tests FG132 — échéancier & relevé fournisseur (balance âgée AP + relevé).

Miroir AP de la balance âgée clients. Tout se déduit du grand livre de la compta
(lignes du compte 4411 Fournisseurs, auxiliarisées par ``tiers_id``). Couvre :
* le bucketing par ancienneté (0–30 / 31–60 / 61–90 / 90+) à partir de la date
  d'écriture ;
* la prise en compte des règlements (débit) qui diminuent l'encours dû ;
* l'exclusion des lignes lettrées (soldées) ;
* l'isolation multi-société (un fournisseur d'une autre société n'apparaît pas) ;
* le relevé chronologique avec solde courant cumulé ;
* les endpoints API + gate de rôle (Admin/Responsable uniquement).
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import EcritureComptable, Journal

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


class _APSetup(TestCase):
    def setUp(self):
        self.co = make_company('fg132', 'FG132 Co')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.today = timezone.localdate()
        self.fournisseurs = services.get_compte(self.co, '4411')
        self.achats = services.get_compte(self.co, '6111')
        self.banque = services.get_compte(self.co, '5141')
        self.journal_ach = Journal.objects.filter(
            company=self.co, type_journal=Journal.Type.ACHAT).first()
        self.journal_bnk = Journal.objects.filter(
            company=self.co, type_journal=Journal.Type.BANQUE).first()

    def _facture_fournisseur(self, tiers_id, montant, jours_anciennete,
                             lettrage=''):
        """Passe une dette fournisseur (crédit 4411 / débit 6111) datée."""
        d = self.today - timedelta(days=jours_anciennete)
        services.creer_ecriture(
            self.co, self.journal_ach, d, f'Facture F{tiers_id}',
            [
                {'compte': self.achats, 'debit': Decimal(montant),
                 'credit': Decimal('0'), 'libelle': 'Achat'},
                {'compte': self.fournisseurs, 'debit': Decimal('0'),
                 'credit': Decimal(montant), 'libelle': 'Dette',
                 'tiers_type': 'fournisseur', 'tiers_id': tiers_id},
            ],
            statut=EcritureComptable.Statut.VALIDEE)
        if lettrage:
            from apps.compta.models import LigneEcriture
            LigneEcriture.objects.filter(
                company=self.co, compte=self.fournisseurs,
                tiers_id=tiers_id).update(lettrage=lettrage)

    def _reglement_fournisseur(self, tiers_id, montant, jours_anciennete):
        """Passe un règlement (débit 4411 / crédit 5141) qui diminue l'encours."""
        d = self.today - timedelta(days=jours_anciennete)
        services.creer_ecriture(
            self.co, self.journal_bnk, d, f'Règlement F{tiers_id}',
            [
                {'compte': self.fournisseurs, 'debit': Decimal(montant),
                 'credit': Decimal('0'), 'libelle': 'Règlement',
                 'tiers_type': 'fournisseur', 'tiers_id': tiers_id},
                {'compte': self.banque, 'debit': Decimal('0'),
                 'credit': Decimal(montant), 'libelle': 'Banque'},
            ],
            statut=EcritureComptable.Statut.VALIDEE)


class BalanceAgeeFournisseursTests(_APSetup):
    def test_bucketing_par_anciennete(self):
        self._facture_fournisseur(1, '1000', 10)    # 0–30
        self._facture_fournisseur(1, '500', 45)     # 31–60
        self._facture_fournisseur(1, '200', 80)     # 61–90
        self._facture_fournisseur(1, '300', 200)    # 90+
        rows = selectors.balance_agee_fournisseurs(self.co)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['tiers_id'], 1)
        self.assertEqual(row['b0_30'], Decimal('1000'))
        self.assertEqual(row['b31_60'], Decimal('500'))
        self.assertEqual(row['b61_90'], Decimal('200'))
        self.assertEqual(row['b90_plus'], Decimal('300'))
        self.assertEqual(row['total'], Decimal('2000'))

    def test_reglement_diminue_encours(self):
        self._facture_fournisseur(2, '1000', 10)
        self._reglement_fournisseur(2, '400', 5)
        rows = selectors.balance_agee_fournisseurs(self.co)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['total'], Decimal('600'))

    def test_lignes_lettrees_exclues(self):
        self._facture_fournisseur(3, '700', 20, lettrage='A')
        rows = selectors.balance_agee_fournisseurs(self.co)
        self.assertEqual(rows, [])

    def test_solde_nul_ou_debiteur_omis(self):
        # Avance fournisseur seule (débit 4411) → solde débiteur, non listée.
        self._reglement_fournisseur(4, '300', 5)
        rows = selectors.balance_agee_fournisseurs(self.co)
        self.assertEqual(rows, [])

    def test_tri_par_total_decroissant(self):
        self._facture_fournisseur(5, '100', 10)
        self._facture_fournisseur(6, '900', 10)
        rows = selectors.balance_agee_fournisseurs(self.co)
        self.assertEqual([r['tiers_id'] for r in rows], [6, 5])

    def test_isolation_multi_societe(self):
        other = make_company('fg132-other', 'Autre')
        services.seed_plan_comptable(other)
        services.seed_journaux(other)
        self._facture_fournisseur(7, '500', 10)
        rows_other = selectors.balance_agee_fournisseurs(other)
        self.assertEqual(rows_other, [])
        rows_self = selectors.balance_agee_fournisseurs(self.co)
        self.assertEqual(len(rows_self), 1)


class ReleveFournisseurTests(_APSetup):
    def test_releve_chronologique_avec_solde(self):
        self._facture_fournisseur(10, '1000', 30)
        self._reglement_fournisseur(10, '400', 10)
        data = selectors.releve_fournisseur(self.co, 10)
        self.assertEqual(len(data['lignes']), 2)
        # La facture (crédit) précède le règlement (débit) chronologiquement.
        self.assertEqual(data['lignes'][0]['credit'], Decimal('1000'))
        self.assertEqual(data['lignes'][0]['solde_courant'], Decimal('1000'))
        self.assertEqual(data['lignes'][1]['debit'], Decimal('400'))
        self.assertEqual(data['lignes'][1]['solde_courant'], Decimal('600'))
        self.assertEqual(data['totaux']['credit'], Decimal('1000'))
        self.assertEqual(data['totaux']['debit'], Decimal('400'))
        self.assertEqual(data['totaux']['solde_du'], Decimal('600'))

    def test_releve_isolation_societe(self):
        other = make_company('fg132-rel-other', 'Autre Rel')
        services.seed_plan_comptable(other)
        services.seed_journaux(other)
        self._facture_fournisseur(11, '800', 10)
        data = selectors.releve_fournisseur(other, 11)
        self.assertEqual(data['lignes'], [])
        self.assertEqual(data['totaux']['solde_du'], Decimal('0'))


class BalanceFournisseurApiTests(_APSetup):
    def test_balance_agee_endpoint(self):
        self._facture_fournisseur(20, '1500', 10)
        user = make_user(self.co, 'resp-fg132')
        api = auth(user)
        resp = api.get('/api/django/compta/etats/balance-agee-fournisseurs/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(Decimal(str(resp.data[0]['total'])), Decimal('1500'))

    def test_releve_endpoint(self):
        self._facture_fournisseur(21, '600', 10)
        user = make_user(self.co, 'resp2-fg132')
        api = auth(user)
        resp = api.get('/api/django/compta/etats/releve-fournisseur/21/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['lignes']), 1)
        self.assertEqual(
            Decimal(str(resp.data['totaux']['solde_du'])), Decimal('600'))

    def test_role_gate_refuse_commercial(self):
        user = make_user(self.co, 'comm-fg132', role='commercial')
        api = auth(user)
        resp = api.get('/api/django/compta/etats/balance-agee-fournisseurs/')
        self.assertEqual(resp.status_code, 403)
