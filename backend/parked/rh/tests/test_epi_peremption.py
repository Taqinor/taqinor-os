"""Tests FG179 — Suivi péremption/contrôle des EPI à durée de vie.

EPI à durée de vie limitée (harnais antichute, gants isolants…) : le catalogue
porte ``duree_vie_mois`` / ``intervalle_controle_mois`` ; la dotation dérive et
stocke ``date_peremption`` (date_dotation + durée de vie) et
``date_prochain_controle`` (date_dotation + intervalle de contrôle). Couvre :

* Dérivation : ``date_peremption`` / ``date_prochain_controle`` calculées à la
  sauvegarde ; recalculées si la date de dotation change ; NULL sans durée ou
  sans date de dotation ; arithmétique de fin de mois (31 janv + 1 mois).
* Calcul ``perime`` / ``a_controler`` : déterministe, ``today`` injectable ;
  jour d'échéance inclus = encore valide, lendemain = périmé/à contrôler.
* Sélecteur ``epi_a_remplacer_ou_controler`` : fenêtre ``within_days``
  (péremption OU contrôle proche/dépassé), ``today`` injectable, exclut les EPI
  sans durée de vie, restreint par employé, scopé société.
* Endpoint ``a-remplacer-controler/``.
* Moteur d'échéances RH (FG175) : famille ``epi_peremption`` (et
  ``epi_controle``) sans casser ``dotation_epi`` ni les autres familles.
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import selectors
from apps.rh.models import DossierEmploye, DotationEpi, EpiCatalogue

User = get_user_model()

DOT = '/api/django/rh/dotations-epi/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_employe(company, matricule):
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, nom='Test', prenom='E')


def make_epi(company, type_epi='harnais', designation='Harnais antichute',
             duree_vie_mois=None, intervalle_controle_mois=None, actif=True):
    return EpiCatalogue.objects.create(
        company=company, type_epi=type_epi, designation=designation,
        duree_vie_mois=duree_vie_mois,
        intervalle_controle_mois=intervalle_controle_mois, actif=actif)


def make_dotation(company, employe, epi, date_dotation=None,
                  date_renouvellement=None, quantite=1):
    return DotationEpi.objects.create(
        company=company, employe=employe, epi=epi,
        date_dotation=date_dotation,
        date_renouvellement=date_renouvellement, quantite=quantite)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


class DotationEpiDerivationTests(TestCase):
    def setUp(self):
        self.co = make_company('per-a', 'A')
        self.emp = make_employe(self.co, 'EA1')

    def test_date_peremption_derivee_de_la_duree_de_vie(self):
        epi = make_epi(self.co, duree_vie_mois=120)  # harnais 10 ans
        dot = make_dotation(
            self.co, self.emp, epi, date_dotation=date(2026, 1, 15))
        self.assertEqual(dot.date_peremption, date(2036, 1, 15))

    def test_date_prochain_controle_derivee_de_l_intervalle(self):
        epi = make_epi(self.co, intervalle_controle_mois=12)
        dot = make_dotation(
            self.co, self.emp, epi, date_dotation=date(2026, 3, 10))
        self.assertEqual(dot.date_prochain_controle, date(2027, 3, 10))

    def test_les_deux_echeances_ensemble(self):
        epi = make_epi(
            self.co, duree_vie_mois=120, intervalle_controle_mois=12)
        dot = make_dotation(
            self.co, self.emp, epi, date_dotation=date(2026, 6, 1))
        self.assertEqual(dot.date_peremption, date(2036, 6, 1))
        self.assertEqual(dot.date_prochain_controle, date(2027, 6, 1))

    def test_clamp_fin_de_mois(self):
        # 31 janvier + 1 mois doit retomber sur le 28/29 février, pas planter.
        epi = make_epi(self.co, intervalle_controle_mois=1)
        dot = make_dotation(
            self.co, self.emp, epi, date_dotation=date(2026, 1, 31))
        self.assertEqual(dot.date_prochain_controle, date(2026, 2, 28))

    def test_sans_duree_de_vie_aucune_echeance(self):
        epi = make_epi(self.co, duree_vie_mois=None,
                       intervalle_controle_mois=None)
        dot = make_dotation(
            self.co, self.emp, epi, date_dotation=date(2026, 1, 15))
        self.assertIsNone(dot.date_peremption)
        self.assertIsNone(dot.date_prochain_controle)

    def test_sans_date_dotation_aucune_echeance(self):
        epi = make_epi(self.co, duree_vie_mois=120, intervalle_controle_mois=12)
        dot = make_dotation(self.co, self.emp, epi, date_dotation=None)
        self.assertIsNone(dot.date_peremption)
        self.assertIsNone(dot.date_prochain_controle)

    def test_recalcul_quand_la_date_de_dotation_change(self):
        epi = make_epi(self.co, duree_vie_mois=12)
        dot = make_dotation(
            self.co, self.emp, epi, date_dotation=date(2026, 1, 1))
        self.assertEqual(dot.date_peremption, date(2027, 1, 1))
        dot.date_dotation = date(2026, 7, 1)
        dot.save()
        self.assertEqual(dot.date_peremption, date(2027, 7, 1))


class PerimeAControlerTests(TestCase):
    def setUp(self):
        self.co = make_company('pac-a', 'A')
        self.emp = make_employe(self.co, 'EA1')

    def test_perime_today_injectable_jour_inclus_valide(self):
        epi = make_epi(self.co, duree_vie_mois=12)
        dot = make_dotation(
            self.co, self.emp, epi, date_dotation=date(2025, 6, 1))
        peremption = dot.date_peremption  # 2026-06-01
        # Le jour de péremption inclus : encore valide.
        self.assertFalse(dot.perime(today=peremption))
        # Le lendemain : périmé.
        self.assertTrue(dot.perime(today=peremption + timedelta(days=1)))
        # Bien avant : valide.
        self.assertFalse(dot.perime(today=peremption - timedelta(days=30)))

    def test_a_controler_today_injectable(self):
        epi = make_epi(self.co, intervalle_controle_mois=12)
        dot = make_dotation(
            self.co, self.emp, epi, date_dotation=date(2025, 6, 1))
        controle = dot.date_prochain_controle  # 2026-06-01
        self.assertFalse(dot.a_controler(today=controle))
        self.assertTrue(
            dot.a_controler(today=controle + timedelta(days=1)))

    def test_sans_echeance_jamais_perime_ni_a_controler(self):
        epi = make_epi(self.co)
        dot = make_dotation(
            self.co, self.emp, epi, date_dotation=date(2020, 1, 1))
        self.assertFalse(dot.perime(today=date(2030, 1, 1)))
        self.assertFalse(dot.a_controler(today=date(2030, 1, 1)))


class EpiARemplacerOuControlerSelectorTests(TestCase):
    def setUp(self):
        self.co_a = make_company('sel-a', 'A')
        self.co_b = make_company('sel-b', 'B')
        self.emp_a = make_employe(self.co_a, 'EA1')
        self.emp_a2 = make_employe(self.co_a, 'EA2')
        self.emp_b = make_employe(self.co_b, 'EB1')
        self.today = date(2026, 6, 1)

    def _epi(self, company, **kw):
        return make_epi(company, **kw)

    def test_fenetre_inclut_peremption_proche_et_depassee(self):
        epi = self._epi(self.co_a, duree_vie_mois=12)
        # Péremption dans 10 jours.
        proche = make_dotation(
            self.co_a, self.emp_a, epi,
            date_dotation=date(2025, 6, 11))  # +12m = 2026-06-11
        # Péremption dépassée.
        depassee = make_dotation(
            self.co_a, self.emp_a, epi,
            date_dotation=date(2025, 5, 1))  # +12m = 2026-05-01
        # Péremption lointaine (hors fenêtre 30j).
        lointaine = make_dotation(
            self.co_a, self.emp_a, epi,
            date_dotation=date(2026, 5, 1))  # +12m = 2027-05-01
        qs = selectors.epi_a_remplacer_ou_controler(
            self.co_a, within_days=30, today=self.today)
        ids = set(qs.values_list('id', flat=True))
        self.assertIn(proche.id, ids)
        self.assertIn(depassee.id, ids)
        self.assertNotIn(lointaine.id, ids)

    def test_inclut_aussi_le_controle(self):
        epi = self._epi(self.co_a, intervalle_controle_mois=12)
        a_controler = make_dotation(
            self.co_a, self.emp_a, epi,
            date_dotation=date(2025, 6, 10))  # contrôle 2026-06-10
        qs = selectors.epi_a_remplacer_ou_controler(
            self.co_a, within_days=30, today=self.today)
        self.assertIn(a_controler.id, set(qs.values_list('id', flat=True)))

    def test_exclut_epi_sans_duree_de_vie(self):
        epi = self._epi(self.co_a)  # ni durée ni intervalle
        sans = make_dotation(
            self.co_a, self.emp_a, epi, date_dotation=date(2020, 1, 1))
        qs = selectors.epi_a_remplacer_ou_controler(
            self.co_a, within_days=30, today=self.today)
        self.assertNotIn(sans.id, set(qs.values_list('id', flat=True)))

    def test_restreint_par_employe(self):
        epi = self._epi(self.co_a, duree_vie_mois=12)
        d1 = make_dotation(
            self.co_a, self.emp_a, epi, date_dotation=date(2025, 6, 5))
        make_dotation(
            self.co_a, self.emp_a2, epi, date_dotation=date(2025, 6, 5))
        qs = selectors.epi_a_remplacer_ou_controler(
            self.co_a, within_days=30, today=self.today,
            employe_id=self.emp_a.id)
        self.assertEqual(set(qs.values_list('id', flat=True)), {d1.id})

    def test_scope_societe(self):
        epi_b = self._epi(self.co_b, duree_vie_mois=12)
        make_dotation(
            self.co_b, self.emp_b, epi_b, date_dotation=date(2025, 6, 5))
        qs = selectors.epi_a_remplacer_ou_controler(
            self.co_a, within_days=30, today=self.today)
        self.assertEqual(qs.count(), 0)

    def test_company_none_renvoie_vide(self):
        qs = selectors.epi_a_remplacer_ou_controler(
            None, within_days=30, today=self.today)
        self.assertEqual(qs.count(), 0)


class EpiARemplacerControlerEndpointTests(TestCase):
    def setUp(self):
        self.co_a = make_company('ep-a', 'A')
        self.co_b = make_company('ep-b', 'B')
        self.user_a = make_user(self.co_a, 'ep-user-a')
        self.user_b = make_user(self.co_b, 'ep-user-b')
        self.emp_a = make_employe(self.co_a, 'EA1')
        self.emp_b = make_employe(self.co_b, 'EB1')

    def test_endpoint_retourne_les_epi_a_remplacer(self):
        today = timezone.localdate()
        epi = make_epi(self.co_a, duree_vie_mois=12)
        # Péremption dans 10 jours : dotée il y a ~12m - 10j.
        proche = make_dotation(
            self.co_a, self.emp_a, epi,
            date_dotation=today - timedelta(days=355))
        lointaine = make_dotation(
            self.co_a, self.emp_a, epi, date_dotation=today)
        resp = auth(self.user_a).get(DOT + 'a-remplacer-controler/')
        self.assertEqual(resp.status_code, 200, resp.data)
        ids = {d['id'] for d in rows(resp)}
        self.assertIn(proche.id, ids)
        self.assertNotIn(lointaine.id, ids)

    def test_endpoint_isolation_societe(self):
        today = timezone.localdate()
        epi_b = make_epi(self.co_b, duree_vie_mois=12)
        make_dotation(
            self.co_b, self.emp_b, epi_b,
            date_dotation=today - timedelta(days=355))
        resp = auth(self.user_a).get(DOT + 'a-remplacer-controler/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_serializer_expose_perime_et_dates(self):
        today = timezone.localdate()
        epi = make_epi(self.co_a, duree_vie_mois=12, intervalle_controle_mois=6)
        make_dotation(
            self.co_a, self.emp_a, epi,
            date_dotation=today - timedelta(days=400))  # périmé
        resp = auth(self.user_a).get(DOT + 'a-remplacer-controler/')
        self.assertEqual(resp.status_code, 200, resp.data)
        row = rows(resp)[0]
        self.assertIn('date_peremption', row)
        self.assertIn('date_prochain_controle', row)
        self.assertTrue(row['perime'])


class EcheancesRhEpiPeremptionTests(TestCase):
    """La péremption/le contrôle des EPI alimentent le moteur RH (FG175)."""

    def setUp(self):
        self.co = make_company('ech179-a', 'A')
        self.emp = make_employe(self.co, 'EA1')

    def test_echeances_rh_inclut_epi_peremption(self):
        today = date(2026, 6, 1)
        epi = make_epi(self.co, designation='Harnais Petzl', duree_vie_mois=12)
        make_dotation(
            self.co, self.emp, epi,
            date_dotation=date(2025, 6, 11))  # péremption 2026-06-11
        rows_ = selectors.echeances_rh(self.co, within_days=30, today=today)
        types = {r['type'] for r in rows_}
        self.assertIn('epi_peremption', types)
        row = next(r for r in rows_ if r['type'] == 'epi_peremption')
        self.assertEqual(row['employe_id'], self.emp.id)
        self.assertEqual(row['jours_restants'], 10)
        self.assertIn('Harnais Petzl', row['libelle'])

    def test_echeances_rh_inclut_epi_controle(self):
        today = date(2026, 6, 1)
        epi = make_epi(self.co, designation='Gants 1000V',
                       intervalle_controle_mois=12)
        make_dotation(
            self.co, self.emp, epi,
            date_dotation=date(2025, 6, 6))  # contrôle 2026-06-06
        rows_ = selectors.echeances_rh(self.co, within_days=30, today=today)
        types = {r['type'] for r in rows_}
        self.assertIn('epi_controle', types)

    def test_echeances_rh_ignore_epi_sans_duree(self):
        today = date(2026, 6, 1)
        epi = make_epi(self.co)  # ni durée ni intervalle
        make_dotation(
            self.co, self.emp, epi, date_dotation=date(2020, 1, 1))
        rows_ = selectors.echeances_rh(self.co, within_days=30, today=today)
        self.assertEqual(
            [r for r in rows_ if r['type'] in ('epi_peremption',
                                               'epi_controle')], [])

    def test_echeances_rh_preserve_dotation_epi_renouvellement(self):
        # FG178 (date_renouvellement) ne doit pas être cassé par FG179.
        today = date(2026, 6, 1)
        epi = make_epi(self.co, designation='Casque', duree_vie_mois=None)
        make_dotation(
            self.co, self.emp, epi,
            date_renouvellement=date(2026, 6, 11))
        rows_ = selectors.echeances_rh(self.co, within_days=30, today=today)
        types = {r['type'] for r in rows_}
        self.assertIn('dotation_epi', types)
        self.assertNotIn('epi_peremption', types)
