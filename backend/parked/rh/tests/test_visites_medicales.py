"""Tests FG177 — Visite médicale du travail par employé (aptitude + échéance).

Famille DISTINCTE des habilitations (FG173) et certifications (FG174). Couvre :
* Création : company posée côté serveur (jamais lue du corps), employe validé.
* Calcul ``a_jour`` : visite active sans prochaine échéance → à jour ; échéance
  future → à jour ; échéance passée → pas à jour ; visite inactive → pas à jour.
* Aptitude « inapte » : enregistrée et relue telle quelle.
* Cohérence des dates : prochaine visite avant la visite refusée (400).
* Filtre/endpoint expirantes : visites à renouveler dans N jours + déjà échues ;
  ``?expire_within=`` borne la fenêtre ; ``?inclure_expirees=0`` exclut les échues.
* Cross-société : employé d'une autre société refusé (400).
* Isolation multi-société : B ne voit pas les visites de A.
* Permission : un rôle normal est refusé (403).
* Runtime-safety : tous les codes d'aptitude tiennent dans ``max_length``.
* Échéances RH unifiées (FG175) : la visite médicale alimente ``echeances_rh``.
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import selectors
from apps.rh.models import DossierEmploye, VisiteMedicale

User = get_user_model()

VISITE = '/api/django/rh/visites-medicales/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_employe(company, matricule):
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, nom='Test', prenom='E')


def make_visite(company, employe, aptitude='apte',
                prochaine_visite=None, actif=True):
    return VisiteMedicale.objects.create(
        company=company, employe=employe, aptitude=aptitude,
        prochaine_visite=prochaine_visite, actif=actif)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


class VisiteMedicaleCreateTests(TestCase):
    def setUp(self):
        self.co_a = make_company('vismed-a', 'A')
        self.co_b = make_company('vismed-b', 'B')
        self.user_a = make_user(self.co_a, 'vismed-user-a')
        self.user_b = make_user(self.co_b, 'vismed-user-b')
        self.emp_a = make_employe(self.co_a, 'EA1')
        self.emp_b = make_employe(self.co_b, 'EB1')

    def test_create_company_posee_cote_serveur(self):
        today = timezone.localdate()
        prochaine = today + timedelta(days=365)
        resp = auth(self.user_a).post(VISITE, {
            'employe': self.emp_a.id,
            'aptitude': 'apte',
            'date_visite': today.isoformat(),
            'prochaine_visite': prochaine.isoformat(),
            'medecin': 'Dr Alaoui',
            'organisme': 'OMT Casablanca',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        visite = VisiteMedicale.objects.get(id=resp.data['id'])
        self.assertEqual(visite.company, self.co_a)
        self.assertEqual(visite.aptitude, 'apte')
        self.assertTrue(resp.data['a_jour'])

    def test_employe_ne_lit_pas_company_du_corps(self):
        # ``company`` du corps est ignorée : la société vient du serveur.
        resp = auth(self.user_a).post(VISITE, {
            'employe': self.emp_a.id,
            'aptitude': 'apte',
            'company': self.co_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        visite = VisiteMedicale.objects.get(id=resp.data['id'])
        self.assertEqual(visite.company, self.co_a)

    def test_employe_autre_societe_refuse(self):
        resp = auth(self.user_a).post(VISITE, {
            'employe': self.emp_b.id, 'aptitude': 'apte',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_aptitude_inapte_enregistree(self):
        resp = auth(self.user_a).post(VISITE, {
            'employe': self.emp_a.id, 'aptitude': 'inapte',
            'restrictions': 'Pas de travail en hauteur',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        visite = VisiteMedicale.objects.get(id=resp.data['id'])
        self.assertEqual(visite.aptitude, 'inapte')
        self.assertEqual(resp.data['aptitude_display'], 'Inapte')
        self.assertEqual(visite.restrictions, 'Pas de travail en hauteur')

    def test_prochaine_avant_visite_refuse(self):
        today = timezone.localdate()
        resp = auth(self.user_a).post(VISITE, {
            'employe': self.emp_a.id, 'aptitude': 'apte',
            'date_visite': today.isoformat(),
            'prochaine_visite': (today - timedelta(days=5)).isoformat(),
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_historique_plusieurs_visites_ok(self):
        # Pas d'unicité : on garde l'historique des visites d'un employé.
        make_visite(self.co_a, self.emp_a, 'apte')
        resp = auth(self.user_a).post(VISITE, {
            'employe': self.emp_a.id, 'aptitude': 'apte_avec_restrictions',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(
            VisiteMedicale.objects.filter(employe=self.emp_a).count(), 2)

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'vismed-normal', role='normal')
        resp = auth(normal).get(VISITE)
        self.assertEqual(resp.status_code, 403)

    def test_isolation_list(self):
        make_visite(self.co_a, self.emp_a, 'apte')
        resp = auth(self.user_b).get(VISITE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_tous_les_codes_tiennent_dans_max_length(self):
        # Runtime-safety (FG136) : aucun code d'aptitude ne dépasse max_length.
        field = VisiteMedicale._meta.get_field('aptitude')
        for value, _label in VisiteMedicale.Aptitude.choices:
            self.assertLessEqual(
                len(value), field.max_length,
                f'Le code {value!r} dépasse max_length={field.max_length}')

    def test_filtre_aptitude(self):
        make_visite(self.co_a, self.emp_a, 'inapte')
        make_visite(self.co_a, self.emp_a, 'apte')
        resp = auth(self.user_a).get(VISITE + '?aptitude=inapte')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            [v['aptitude'] for v in rows(resp)], ['inapte'])


class VisiteMedicaleAJourTests(TestCase):
    def setUp(self):
        self.co_a = make_company('vismedj-a', 'A')
        self.emp_a = make_employe(self.co_a, 'EA1')

    def test_a_jour_actif_sans_echeance(self):
        visite = make_visite(
            self.co_a, self.emp_a, 'apte', prochaine_visite=None)
        self.assertTrue(visite.a_jour)

    def test_a_jour_echeance_future(self):
        prochaine = timezone.localdate() + timedelta(days=10)
        visite = make_visite(
            self.co_a, self.emp_a, 'apte', prochaine_visite=prochaine)
        self.assertTrue(visite.a_jour)

    def test_pas_a_jour_echeance_passee(self):
        prochaine = timezone.localdate() - timedelta(days=1)
        visite = make_visite(
            self.co_a, self.emp_a, 'apte', prochaine_visite=prochaine)
        self.assertFalse(visite.a_jour)

    def test_pas_a_jour_inactif(self):
        prochaine = timezone.localdate() + timedelta(days=365)
        visite = make_visite(
            self.co_a, self.emp_a, 'apte',
            prochaine_visite=prochaine, actif=False)
        self.assertFalse(visite.a_jour)

    def test_a_jour_jour_echeance_inclus(self):
        today = timezone.localdate()
        visite = make_visite(
            self.co_a, self.emp_a, 'apte', prochaine_visite=today)
        self.assertTrue(visite.a_jour)


class VisiteMedicaleExpirantesTests(TestCase):
    def setUp(self):
        self.co_a = make_company('vismedx-a', 'A')
        self.co_b = make_company('vismedx-b', 'B')
        self.user_a = make_user(self.co_a, 'vismedx-user-a')
        self.user_b = make_user(self.co_b, 'vismedx-user-b')
        self.emp_a = make_employe(self.co_a, 'EA1')
        self.emp_b = make_employe(self.co_b, 'EB1')
        today = timezone.localdate()
        # À renouveler bientôt (dans 10 jours).
        self.bientot = make_visite(
            self.co_a, self.emp_a, 'apte',
            prochaine_visite=today + timedelta(days=10))
        # Déjà échue (hier).
        self.echue = make_visite(
            self.co_a, self.emp_a, 'apte',
            prochaine_visite=today - timedelta(days=1))
        # Lointaine (dans 200 jours) — hors fenêtre 30 j.
        self.lointaine = make_visite(
            self.co_a, self.emp_a, 'apte',
            prochaine_visite=today + timedelta(days=200))
        # Sans prochaine échéance — jamais listée comme expirante.
        self.sans_echeance = make_visite(
            self.co_a, self.emp_a, 'apte', prochaine_visite=None)

    def test_expirantes_inclut_bientot_et_echues(self):
        resp = auth(self.user_a).get(VISITE + 'expirantes/')
        self.assertEqual(resp.status_code, 200, resp.data)
        ids = {v['id'] for v in rows(resp)}
        self.assertIn(self.bientot.id, ids)
        self.assertIn(self.echue.id, ids)
        self.assertNotIn(self.lointaine.id, ids)
        self.assertNotIn(self.sans_echeance.id, ids)

    def test_expire_within_elargit_la_fenetre(self):
        resp = auth(self.user_a).get(VISITE + 'expirantes/?expire_within=365')
        ids = {v['id'] for v in rows(resp)}
        self.assertIn(self.lointaine.id, ids)

    def test_inclure_expirees_0_exclut_les_echues(self):
        resp = auth(self.user_a).get(
            VISITE + 'expirantes/?inclure_expirees=0')
        ids = {v['id'] for v in rows(resp)}
        self.assertIn(self.bientot.id, ids)
        self.assertNotIn(self.echue.id, ids)

    def test_expirantes_isolation_societe(self):
        # B a une visite expirante, mais ne voit jamais celles de A.
        make_visite(
            self.co_b, self.emp_b, 'apte',
            prochaine_visite=timezone.localdate() + timedelta(days=5))
        resp = auth(self.user_b).get(VISITE + 'expirantes/')
        self.assertEqual(resp.status_code, 200)
        ids = {v['id'] for v in rows(resp)}
        self.assertNotIn(self.bientot.id, ids)
        self.assertNotIn(self.echue.id, ids)


class VisiteMedicaleEcheancesRhTests(TestCase):
    """La visite médicale (FG177) alimente le moteur d'échéances RH (FG175)."""

    def setUp(self):
        self.co = make_company('vismede-a', 'A')
        self.emp = make_employe(self.co, 'E001')
        self.today = date(2026, 6, 1)

    def test_visite_apparait_dans_echeances_rh(self):
        make_visite(
            self.co, self.emp, 'apte',
            prochaine_visite=self.today + timedelta(days=15))
        rows_ = selectors.echeances_rh(
            self.co, within_days=30, today=self.today)
        types = [r['type'] for r in rows_]
        self.assertIn('visite_medicale', types)
        row = next(r for r in rows_ if r['type'] == 'visite_medicale')
        self.assertEqual(row['employe_id'], self.emp.id)
        self.assertEqual(row['jours_restants'], 15)

    def test_visite_echue_incluse(self):
        make_visite(
            self.co, self.emp, 'apte',
            prochaine_visite=self.today - timedelta(days=3))
        rows_ = selectors.echeances_rh(
            self.co, within_days=30, today=self.today)
        row = next(r for r in rows_ if r['type'] == 'visite_medicale')
        self.assertEqual(row['jours_restants'], -3)

    def test_visite_sans_echeance_ou_inactive_exclue(self):
        make_visite(self.co, self.emp, 'apte', prochaine_visite=None)
        make_visite(
            self.co, self.emp, 'apte',
            prochaine_visite=self.today + timedelta(days=5), actif=False)
        rows_ = selectors.echeances_rh(
            self.co, within_days=30, today=self.today)
        self.assertEqual(
            [r for r in rows_ if r['type'] == 'visite_medicale'], [])
