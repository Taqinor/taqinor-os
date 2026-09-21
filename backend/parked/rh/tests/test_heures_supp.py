"""Tests FG168 — Heures supplémentaires & calcul majoré (entrée de paie).

Couvre :
* Calcul pur (``services.calculer_majoration``) — répartition jour ouvrable
  (seuil 8 h, 25 % jour / 50 % nuit) et jour de repos/férié (50 % jour / 100 %
  nuit), bornage des heures de nuit, montant majoré valorisé.
* Création API : company posée côté serveur, majoration calculée côté serveur
  (jamais lue du corps), taux pris du dossier employé.
* Mise à jour : recalcul de la majoration.
* Isolation multi-société : un utilisateur de B ne voit pas les HS de A et ne
  peut pas en saisir pour un employé de A.
* Action export-paie + sélecteur ``heures_supp_pour_paie`` (agrégation période).
* Accès réservé Administrateur/Responsable (rôle normal → 403).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import selectors, services
from apps.rh.models import DossierEmploye, HeuresSupp

User = get_user_model()

BASE = '/api/django/rh/heures-supp/'
EXPORT_URL = BASE + 'export-paie/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_employe(company, matricule, cout_horaire=Decimal('50')):
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, nom='Test', prenom='E',
        cout_horaire=cout_horaire)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


class MajorationCalculTests(TestCase):
    """Tests unitaires du calcul pur (services.calculer_majoration)."""

    def test_jour_ouvrable_sous_le_seuil_pas_de_hs(self):
        res = services.calculer_majoration(8)
        self.assertEqual(res['heures_normales'], Decimal('8.00'))
        self.assertEqual(res['total_hs'], Decimal('0.00'))
        self.assertEqual(res['hs_25'], Decimal('0.00'))

    def test_jour_ouvrable_hs_de_jour_25(self):
        # 10 h, aucune nuit, seuil 8 → 2 h HS toutes à 25 %.
        res = services.calculer_majoration(10, heures_nuit=0)
        self.assertEqual(res['heures_normales'], Decimal('8.00'))
        self.assertEqual(res['hs_25'], Decimal('2.00'))
        self.assertEqual(res['hs_50'], Decimal('0.00'))
        self.assertEqual(res['hs_100'], Decimal('0.00'))
        self.assertEqual(res['total_hs'], Decimal('2.00'))

    def test_jour_ouvrable_hs_de_nuit_50(self):
        # 11 h dont 2 h de nuit, seuil 8 → 3 h HS : 2 h nuit (50 %) + 1 h jour.
        res = services.calculer_majoration(11, heures_nuit=2)
        self.assertEqual(res['hs_50'], Decimal('2.00'))
        self.assertEqual(res['hs_25'], Decimal('1.00'))
        self.assertEqual(res['total_hs'], Decimal('3.00'))

    def test_jour_repos_ferie_tout_majore(self):
        # Jour de repos/férié : 6 h dont 2 h de nuit → 4 h à 50 % + 2 h à 100 %.
        res = services.calculer_majoration(
            6, heures_nuit=2, jour_repos_ferie=True)
        self.assertEqual(res['heures_normales'], Decimal('0.00'))
        self.assertEqual(res['hs_50'], Decimal('4.00'))
        self.assertEqual(res['hs_100'], Decimal('2.00'))
        self.assertEqual(res['hs_25'], Decimal('0.00'))

    def test_heures_nuit_bornees(self):
        # heures_nuit > total → bornées au total.
        res = services.calculer_majoration(10, heures_nuit=20)
        # 2 h HS, toutes de nuit → 50 %.
        self.assertEqual(res['hs_50'], Decimal('2.00'))
        self.assertEqual(res['hs_25'], Decimal('0.00'))

    def test_seuil_personnalise(self):
        res = services.calculer_majoration(11, seuil_journalier=10)
        self.assertEqual(res['hs_25'], Decimal('1.00'))

    def test_montant_majore_valorise(self):
        # 2 h HS jour à 25 %, taux 50 → base 2*50=100 + majo 2*0.25*50=25 = 125.
        res = services.calculer_majoration(10, taux_horaire=Decimal('50'))
        self.assertEqual(res['montant_majore'], Decimal('125.00'))

    def test_montant_none_sans_taux(self):
        res = services.calculer_majoration(10)
        self.assertIsNone(res['montant_majore'])

    def test_heures_negatives_bornees_a_zero(self):
        res = services.calculer_majoration(-5)
        self.assertEqual(res['total_hs'], Decimal('0.00'))
        self.assertEqual(res['heures_normales'], Decimal('0.00'))


class HeuresSuppModelTests(TestCase):
    def setUp(self):
        self.co = make_company('hs-model', 'ModelCo')
        self.emp = make_employe(self.co, 'HM1')

    def test_total_hs_property(self):
        hs = HeuresSupp(
            company=self.co, employe=self.emp,
            date='2026-06-24', heures_travaillees=Decimal('10'),
            hs_25=Decimal('1'), hs_50=Decimal('1'), hs_100=Decimal('0.5'))
        self.assertEqual(hs.total_hs, Decimal('2.5'))


class HeuresSuppApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('hs-a', 'A')
        self.co_b = make_company('hs-b', 'B')
        self.user_a = make_user(self.co_a, 'hs-user-a')
        self.user_b = make_user(self.co_b, 'hs-user-b')
        self.emp_a = make_employe(self.co_a, 'EA1', cout_horaire=Decimal('40'))
        self.emp_b = make_employe(self.co_b, 'EB1')

    def test_create_calcule_cote_serveur(self):
        """company + décomptes majorés posés côté serveur, taux pris du dossier."""
        resp = auth(self.user_a).post(BASE, {
            'employe': self.emp_a.id,
            'date': '2026-06-24',
            'heures_travaillees': '10',
            'heures_nuit': '0',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        hs = HeuresSupp.objects.get(id=resp.data['id'])
        self.assertEqual(hs.company, self.co_a)
        self.assertEqual(hs.hs_25, Decimal('2.00'))
        self.assertEqual(hs.heures_normales, Decimal('8.00'))
        self.assertEqual(hs.taux_horaire, Decimal('40'))
        # base 2*40=80 + majo 2*0.25*40=20 = 100.
        self.assertEqual(hs.montant_majore, Decimal('100.00'))

    def test_create_ignore_decomptes_du_corps(self):
        """Les décomptes envoyés dans le corps sont ignorés (read-only)."""
        resp = auth(self.user_a).post(BASE, {
            'employe': self.emp_a.id,
            'date': '2026-06-24',
            'heures_travaillees': '9',
            'hs_25': '999',
            'montant_majore': '999',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        hs = HeuresSupp.objects.get(id=resp.data['id'])
        self.assertEqual(hs.hs_25, Decimal('1.00'))

    def test_create_ferie_majore_50_100(self):
        resp = auth(self.user_a).post(BASE, {
            'employe': self.emp_a.id,
            'date': '2026-07-30',
            'heures_travaillees': '5',
            'heures_nuit': '2',
            'jour_repos_ferie': True,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        hs = HeuresSupp.objects.get(id=resp.data['id'])
        self.assertEqual(hs.hs_50, Decimal('3.00'))
        self.assertEqual(hs.hs_100, Decimal('2.00'))

    def test_update_recalcule(self):
        resp = auth(self.user_a).post(BASE, {
            'employe': self.emp_a.id,
            'date': '2026-06-24',
            'heures_travaillees': '9',
        }, format='json')
        hs_id = resp.data['id']
        resp = auth(self.user_a).patch(
            f'{BASE}{hs_id}/', {'heures_travaillees': '12'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        hs = HeuresSupp.objects.get(id=hs_id)
        self.assertEqual(hs.hs_25, Decimal('4.00'))

    def test_employe_autre_societe_refuse(self):
        resp = auth(self.user_a).post(BASE, {
            'employe': self.emp_b.id,
            'date': '2026-06-24',
            'heures_travaillees': '10',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_isolation_list(self):
        HeuresSupp.objects.create(
            company=self.co_a, employe=self.emp_a,
            date='2026-06-24', heures_travaillees=Decimal('10'))
        resp = auth(self.user_b).get(BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'hs-normal', role='normal')
        resp = auth(normal).get(BASE)
        self.assertEqual(resp.status_code, 403)

    def test_filtre_employe(self):
        emp2 = make_employe(self.co_a, 'EA2')
        HeuresSupp.objects.create(
            company=self.co_a, employe=self.emp_a,
            date='2026-06-24', heures_travaillees=Decimal('10'))
        HeuresSupp.objects.create(
            company=self.co_a, employe=emp2,
            date='2026-06-24', heures_travaillees=Decimal('10'))
        resp = auth(self.user_a).get(BASE + f'?employe={self.emp_a.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 1)


class HeuresSuppPaieSelectorTests(TestCase):
    """Sélecteur cross-app heures_supp_pour_paie + action export-paie."""

    def setUp(self):
        self.co = make_company('hs-paie', 'Paie')
        self.user = make_user(self.co, 'hs-paie-user')
        self.emp = make_employe(self.co, 'EP1', cout_horaire=Decimal('40'))

    def _create(self, date, heures, **kw):
        hs = HeuresSupp(
            company=self.co, employe=self.emp, date=date,
            heures_travaillees=Decimal(str(heures)), **kw)
        services.appliquer_majoration(hs)
        hs.save()
        return hs

    def test_selecteur_agrege_par_employe(self):
        self._create('2026-06-10', 10)   # 2 h à 25 %
        self._create('2026-06-20', 11)   # 3 h à 25 %
        rows_ = selectors.heures_supp_pour_paie(
            self.co, '2026-06-01', '2026-06-30')
        self.assertEqual(len(rows_), 1)
        row = rows_[0]
        self.assertEqual(row['employe_id'], self.emp.id)
        self.assertEqual(row['hs_25'], Decimal('5.00'))
        self.assertEqual(row['total_hs'], Decimal('5.00'))
        # 5 h HS valorisées : (5*40) + (5*0.25*40) = 200 + 50 = 250.
        self.assertEqual(row['montant_majore'], Decimal('250.00'))

    def test_selecteur_hors_periode_exclu(self):
        self._create('2026-05-10', 10)
        rows_ = selectors.heures_supp_pour_paie(
            self.co, '2026-06-01', '2026-06-30')
        self.assertEqual(rows_, [])

    def test_selecteur_company_none(self):
        self.assertEqual(
            selectors.heures_supp_pour_paie(None, '2026-06-01', '2026-06-30'),
            [])

    def test_export_paie_action(self):
        self._create('2026-06-15', 10)
        resp = auth(self.user).get(
            EXPORT_URL + '?debut=2026-06-01&fin=2026-06-30')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(Decimal(str(resp.data[0]['hs_25'])), Decimal('2.00'))
