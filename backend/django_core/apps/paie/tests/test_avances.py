"""Tests PAIE28 — Avance / prêt salarié + déduction mensuelle.

Couvre :
* ``echeance_avance`` — montant retenu un mois donné (inactif/soldé/non commencé
  → 0 ; dernière échéance bornée au solde restant).
* ``echeances_avances_periode`` — somme des échéances actives sur une période.
* ``calculer_bulletin`` — l'échéance figure en retenue et diminue le net.
* ``valider_bulletin`` → ``appliquer_remboursements_avances`` impute le
  remboursement UNE fois (montant_rembourse incrémenté ; pas au recalcul d'un
  brouillon).
* Multi-tenant — isolation société.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.paie.models import AvanceSalarie, PeriodePaie, ProfilPaie
from apps.paie.services import (
    calculer_bulletin,
    echeance_avance,
    echeances_avances_periode,
    ensure_defaults,
    generer_bulletin,
    valider_bulletin,
)
from apps.rh.models import DossierEmploye

User = get_user_model()


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class EcheanceAvanceTests(TestCase):
    def setUp(self):
        self.co = make_company('av-ech')
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='V1', nom='Test', prenom='Avance')
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'))

    def _avance(self, **kw):
        defaults = dict(
            company=self.co, profil=self.profil, montant_total=Decimal('3000'),
            montant_echeance=Decimal('1000'), nombre_echeances=3,
            date_debut=date(2026, 6, 1))
        defaults.update(kw)
        return AvanceSalarie.objects.create(**defaults)

    def test_echeance_normale(self):
        av = self._avance()
        self.assertEqual(
            echeance_avance(av, date(2026, 6, 1)), Decimal('1000.00'))

    def test_inactive_ou_non_commencee(self):
        av = self._avance(actif=False)
        self.assertEqual(echeance_avance(av, date(2026, 6, 1)), Decimal('0.00'))
        av2 = self._avance(date_debut=date(2026, 7, 1))
        self.assertEqual(
            echeance_avance(av2, date(2026, 6, 1)), Decimal('0.00'))

    def test_derniere_echeance_bornee_au_solde(self):
        av = self._avance(montant_rembourse=Decimal('2500'))
        # Solde restant = 500 < échéance 1000 → on ne retient que 500.
        self.assertEqual(
            echeance_avance(av, date(2026, 6, 1)), Decimal('500.00'))

    def test_soldee_ne_retient_rien(self):
        av = self._avance(montant_rembourse=Decimal('3000'))
        self.assertEqual(echeance_avance(av, date(2026, 6, 1)), Decimal('0.00'))


class BulletinAvanceTests(TestCase):
    def setUp(self):
        self.co = make_company('av-bull')
        ensure_defaults(self.co)
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='V2', nom='Test', prenom='Bull')
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'), affilie_cnss=True, affilie_amo=True)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        self.avance = AvanceSalarie.objects.create(
            company=self.co, profil=self.profil, montant_total=Decimal('2000'),
            montant_echeance=Decimal('1000'), nombre_echeances=2,
            date_debut=date(2026, 6, 1))

    def test_echeance_en_retenue_et_baisse_net(self):
        total, lignes = echeances_avances_periode(self.profil, self.periode)
        self.assertEqual(total, Decimal('1000.00'))
        self.assertEqual(len(lignes), 1)
        res = calculer_bulletin(self.profil, self.periode)
        self.assertEqual(res['retenues'], Decimal('1000.00'))
        self.assertTrue(
            any(ligne['code'] == 'AVANCE' for ligne in res['lignes']))

    def test_imputation_uniquement_a_la_validation(self):
        bulletin = generer_bulletin(self.profil, self.periode)
        # Recalcul brouillon → montant_rembourse inchangé.
        generer_bulletin(self.profil, self.periode)
        self.avance.refresh_from_db()
        self.assertEqual(self.avance.montant_rembourse, Decimal('0'))
        # Validation → imputation d'UNE échéance.
        valider_bulletin(bulletin)
        self.avance.refresh_from_db()
        self.assertEqual(self.avance.montant_rembourse, Decimal('1000.00'))
        self.assertEqual(self.avance.solde_restant, Decimal('1000.00'))


# ── API : une avance créée SANS montant_echeance explicite (fix money) ─────

class AvanceApiEcheanceTests(TestCase):
    """Une avance créée via l'API (le client — dialogue WIR197 — n'envoie
    jamais `montant_echeance`) doit quand même se retenir sur le bulletin
    suivant : le serveur calcule `montant_total / nombre_echeances`
    (ROUND_HALF_UP au centime), jamais 0 par défaut."""
    BASE = '/api/django/paie/avances/'

    def setUp(self):
        self.co = make_company('av-api')
        ensure_defaults(self.co)
        self.user = make_user(self.co, 'av-api-user')
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='V3', nom='Test', prenom='Api')
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'), affilie_cnss=True, affilie_amo=True)

    def test_creation_sans_echeance_la_calcule_et_se_retient(self):
        resp = auth(self.user).post(self.BASE, {
            'profil': self.profil.id,
            'montant_total': '3000',
            'nombre_echeances': 3,
            'date_debut': '2026-06-01',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['montant_echeance'], '1000.00')

        avance = AvanceSalarie.objects.get(pk=resp.data['id'])
        self.assertEqual(avance.montant_echeance, Decimal('1000.00'))

        periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        res = calculer_bulletin(self.profil, periode)
        self.assertEqual(res['retenues'], Decimal('1000.00'))
        self.assertTrue(
            any(ligne['code'] == 'AVANCE' for ligne in res['lignes']))

    def test_division_non_entiere_arrondie_au_centime(self):
        """1000 / 3 = 333,333... -> 333.33 (ROUND_HALF_UP), jamais 0."""
        resp = auth(self.user).post(self.BASE, {
            'profil': self.profil.id,
            'montant_total': '1000',
            'nombre_echeances': 3,
            'date_debut': '2026-06-01',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['montant_echeance'], '333.33')

    def test_echeance_explicite_du_client_jamais_ecrasee(self):
        """Un client qui fournit bien `montant_echeance` garde SA valeur —
        le calcul serveur n'intervient qu'en son absence/à zéro."""
        resp = auth(self.user).post(self.BASE, {
            'profil': self.profil.id,
            'montant_total': '3000',
            'montant_echeance': '1500',
            'nombre_echeances': 3,
            'date_debut': '2026-06-01',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['montant_echeance'], '1500.00')
