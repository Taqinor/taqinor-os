"""Tests ZPAI7 — Éclatement d'une saisie-arrêt multi-employés en fiches individuelles.

Couvre :
* ``creer_saisies_arret_lot`` — crée N ``SaisieArret`` distinctes (une par
  profil) en une transaction, mêmes montant/type ; refuse un profil d'une
  autre société ; idempotent par ``cle_lot`` (un re-run ne duplique pas).
* API ``saisies/creer-lot/`` — mêmes garanties + 400 sans ``cle_lot``.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company, CustomUser as User
from apps.paie.models import ProfilPaie, SaisieArret
from apps.paie.services import creer_saisies_arret_lot, ensure_defaults
from apps.rh.models import DossierEmploye


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


def make_profil(company, matricule):
    dossier = DossierEmploye.objects.create(
        company=company, matricule=matricule, nom='Test', prenom=matricule)
    return ProfilPaie.objects.create(
        company=company, employe=dossier,
        type_remuneration=ProfilPaie.TYPE_MENSUEL,
        salaire_base=Decimal('8000'))


class SaisiesLotServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('sa-lot')
        ensure_defaults(self.co)
        self.p1 = make_profil(self.co, 'L1')
        self.p2 = make_profil(self.co, 'L2')
        self.p3 = make_profil(self.co, 'L3')

    def test_cree_une_saisie_par_profil(self):
        saisies = creer_saisies_arret_lot(
            self.co, [self.p1, self.p2, self.p3],
            montant_total=Decimal('1000'), montant_echeance=Decimal('100'),
            date_debut=date(2026, 6, 1), creancier='Trésor',
            cle_lot='LOT-2026-06-A')
        self.assertEqual(len(saisies), 3)
        self.assertEqual(
            SaisieArret.objects.filter(company=self.co).count(), 3)
        for s in saisies:
            self.assertEqual(s.montant_total, Decimal('1000.00'))
            self.assertEqual(s.lot_reference, 'LOT-2026-06-A')

    def test_refuse_profil_autre_societe(self):
        autre_co = make_company('sa-lot-autre')
        p_autre = make_profil(autre_co, 'AUTRE1')
        with self.assertRaises(ValueError):
            creer_saisies_arret_lot(
                self.co, [self.p1, p_autre],
                montant_total=Decimal('500'), date_debut=date(2026, 6, 1),
                cle_lot='LOT-2026-06-B')

    def test_idempotent_meme_cle_lot(self):
        saisies1 = creer_saisies_arret_lot(
            self.co, [self.p1, self.p2],
            montant_total=Decimal('600'), date_debut=date(2026, 6, 1),
            cle_lot='LOT-2026-06-C')
        saisies2 = creer_saisies_arret_lot(
            self.co, [self.p1, self.p2],
            montant_total=Decimal('600'), date_debut=date(2026, 6, 1),
            cle_lot='LOT-2026-06-C')
        self.assertEqual(
            {s.id for s in saisies1}, {s.id for s in saisies2})
        self.assertEqual(
            SaisieArret.objects.filter(
                company=self.co, lot_reference='LOT-2026-06-C').count(),
            2)

    def test_refuse_sans_cle_lot(self):
        with self.assertRaises(ValueError):
            creer_saisies_arret_lot(
                self.co, [self.p1], montant_total=Decimal('100'),
                date_debut=date(2026, 6, 1), cle_lot='')


class SaisiesLotApiTests(TestCase):
    BASE = '/api/django/paie/saisies/'

    def setUp(self):
        self.co = make_company('sa-lot-api')
        ensure_defaults(self.co)
        self.p1 = make_profil(self.co, 'LA1')
        self.p2 = make_profil(self.co, 'LA2')
        self.user = make_user(self.co, 'sa-lot-api-user')

    def test_creer_lot_api(self):
        resp = auth(self.user).post(
            f'{self.BASE}creer-lot/',
            {
                'profils': [self.p1.id, self.p2.id],
                'montant_total': '900',
                'date_debut': '2026-06-01',
                'creancier': 'CNSS',
                'cle_lot': 'LOT-API-1',
            }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data), 2)

    def test_creer_lot_sans_cle_lot_400(self):
        resp = auth(self.user).post(
            f'{self.BASE}creer-lot/',
            {'profils': [self.p1.id], 'montant_total': '100',
             'date_debut': '2026-06-01'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_creer_lot_profil_autre_societe_400(self):
        autre_co = make_company('sa-lot-api-autre')
        p_autre = make_profil(autre_co, 'AUTRE2')
        resp = auth(self.user).post(
            f'{self.BASE}creer-lot/',
            {
                'profils': [self.p1.id, p_autre.id],
                'montant_total': '100', 'date_debut': '2026-06-01',
                'cle_lot': 'LOT-API-2',
            }, format='json')
        self.assertEqual(resp.status_code, 400)
