"""Tests FG169 — Planning d'équipes / roster (shifts).

Couvre :
* Création d'une affectation (company posée côté serveur, jamais lue du corps).
* Calcul côté serveur de ``semaine_du`` (lundi) et de ``conflit_conge``.
* Détection de conflit : un technicien affecté un jour où il a un congé VALIDÉ
  → conflit_conge=True ; un congé SOUMIS (non validé) ne déclenche pas le conflit.
* Isolation multi-société : B ne voit pas le roster de A, ni n'affecte un
  employé de A.
* Filtres ?employe=, ?equipe=, ?date=, ?semaine=, ?conflit=1.
* Actions semaine/ et conflits/.
* Service unitaire ``detecter_conflit_conge`` / ``lundi_de_la_semaine``.
* Permission : un rôle normal est refusé (403).
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import services
from apps.rh.models import (
    AffectationRoster,
    DemandeConge,
    DossierEmploye,
    TypeAbsence,
)

User = get_user_model()

BASE = '/api/django/rh/roster/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_employe(company, matricule):
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, nom='Test', prenom='E')


def make_type_absence(company, code='CP', deduit=True):
    return TypeAbsence.objects.create(
        company=company, code=code, libelle='Congé payé',
        decompte_jours_ouvres=True, deduit_solde=deduit)


def make_conge(company, employe, type_absence, debut, fin,
               statut=DemandeConge.Statut.VALIDEE):
    return DemandeConge.objects.create(
        company=company, employe=employe, type_absence=type_absence,
        date_debut=debut, date_fin=fin, jours=1, statut=statut)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


# Un mercredi connu (2026-06-24 est un mercredi ; lundi = 2026-06-22).
JOUR = date(2026, 6, 24)
LUNDI = date(2026, 6, 22)


class RosterServiceTests(TestCase):
    """Tests unitaires des helpers de service (logique pure)."""

    def setUp(self):
        self.co = make_company('rost-svc', 'SvcCo')
        self.emp = make_employe(self.co, 'RS1')
        self.ta = make_type_absence(self.co)

    def test_lundi_de_la_semaine(self):
        self.assertEqual(services.lundi_de_la_semaine(JOUR), LUNDI)
        # Un lundi reste lui-même.
        self.assertEqual(services.lundi_de_la_semaine(LUNDI), LUNDI)
        self.assertIsNone(services.lundi_de_la_semaine(None))

    def test_detecter_conflit_avec_conge_valide(self):
        make_conge(self.co, self.emp, self.ta, JOUR, JOUR)
        self.assertTrue(
            services.detecter_conflit_conge(self.co, self.emp.id, JOUR))

    def test_pas_de_conflit_sans_conge(self):
        self.assertFalse(
            services.detecter_conflit_conge(self.co, self.emp.id, JOUR))

    def test_pas_de_conflit_avec_conge_soumis(self):
        # Une demande SOUMISE (non validée) ne bloque pas l'affectation.
        make_conge(self.co, self.emp, self.ta, JOUR, JOUR,
                   statut=DemandeConge.Statut.SOUMISE)
        self.assertFalse(
            services.detecter_conflit_conge(self.co, self.emp.id, JOUR))

    def test_appliquer_roster_pose_semaine_et_conflit(self):
        make_conge(self.co, self.emp, self.ta, JOUR, JOUR)
        aff = AffectationRoster(
            company=self.co, employe=self.emp, equipe='Nord', date=JOUR)
        services.appliquer_roster(aff)
        self.assertEqual(aff.semaine_du, LUNDI)
        self.assertTrue(aff.conflit_conge)


class RosterApiTests(TestCase):
    """Tests CRUD/API de l'affectation roster."""

    def setUp(self):
        self.co_a = make_company('rost-a', 'A')
        self.co_b = make_company('rost-b', 'B')
        self.user_a = make_user(self.co_a, 'rost-user-a')
        self.user_b = make_user(self.co_b, 'rost-user-b')
        self.emp_a = make_employe(self.co_a, 'EA1')
        self.emp_b = make_employe(self.co_b, 'EB1')
        self.ta_a = make_type_absence(self.co_a)

    def test_create_company_posee_cote_serveur(self):
        resp = auth(self.user_a).post(BASE, {
            'employe': self.emp_a.id, 'equipe': 'Nord',
            'date': JOUR.isoformat(),
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        aff = AffectationRoster.objects.get(id=resp.data['id'])
        self.assertEqual(aff.company, self.co_a)
        # semaine_du calculée côté serveur.
        self.assertEqual(aff.semaine_du, LUNDI)
        self.assertFalse(aff.conflit_conge)

    def test_create_avec_conflit_conge(self):
        """Affecter un technicien un jour de congé validé → conflit_conge=True."""
        make_conge(self.co_a, self.emp_a, self.ta_a, JOUR, JOUR)
        resp = auth(self.user_a).post(BASE, {
            'employe': self.emp_a.id, 'equipe': 'Sud',
            'date': JOUR.isoformat(),
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(resp.data['conflit_conge'])
        aff = AffectationRoster.objects.get(id=resp.data['id'])
        self.assertTrue(aff.conflit_conge)

    def test_create_avec_vehicule(self):
        resp = auth(self.user_a).post(BASE, {
            'employe': self.emp_a.id, 'equipe': 'Nord',
            'date': JOUR.isoformat(), 'vehicule_id': 42,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['vehicule_id'], 42)

    def test_employe_autre_societe_refuse(self):
        resp = auth(self.user_a).post(BASE, {
            'employe': self.emp_b.id, 'equipe': 'Nord',
            'date': JOUR.isoformat(),
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_equipe_vide_refuse(self):
        resp = auth(self.user_a).post(BASE, {
            'employe': self.emp_a.id, 'equipe': '   ',
            'date': JOUR.isoformat(),
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_isolation_list(self):
        AffectationRoster.objects.create(
            company=self.co_a, employe=self.emp_a, equipe='Nord', date=JOUR)
        resp = auth(self.user_b).get(BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_update_recalcule_conflit(self):
        aff = AffectationRoster.objects.create(
            company=self.co_a, employe=self.emp_a, equipe='Nord', date=JOUR,
            conflit_conge=False)
        # Un congé validé apparaît APRÈS la création.
        make_conge(self.co_a, self.emp_a, self.ta_a, JOUR, JOUR)
        resp = auth(self.user_a).patch(
            f'{BASE}{aff.id}/', {'equipe': 'Sud'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        aff.refresh_from_db()
        self.assertEqual(aff.equipe, 'Sud')
        self.assertTrue(aff.conflit_conge)

    def test_filtre_employe(self):
        emp2 = make_employe(self.co_a, 'EA2')
        AffectationRoster.objects.create(
            company=self.co_a, employe=self.emp_a, equipe='Nord', date=JOUR)
        AffectationRoster.objects.create(
            company=self.co_a, employe=emp2, equipe='Nord', date=JOUR)
        resp = auth(self.user_a).get(BASE + f'?employe={self.emp_a.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 1)

    def test_filtre_equipe(self):
        emp2 = make_employe(self.co_a, 'EA3')
        AffectationRoster.objects.create(
            company=self.co_a, employe=self.emp_a, equipe='Nord', date=JOUR)
        AffectationRoster.objects.create(
            company=self.co_a, employe=emp2, equipe='Sud', date=JOUR)
        resp = auth(self.user_a).get(BASE + '?equipe=Nord')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 1)

    def test_filtre_conflit(self):
        emp2 = make_employe(self.co_a, 'EA4')
        make_conge(self.co_a, self.emp_a, self.ta_a, JOUR, JOUR)
        a1 = AffectationRoster.objects.create(
            company=self.co_a, employe=self.emp_a, equipe='Nord', date=JOUR)
        services.appliquer_roster(a1)
        a1.save()
        AffectationRoster.objects.create(
            company=self.co_a, employe=emp2, equipe='Nord', date=JOUR)
        resp = auth(self.user_a).get(BASE + '?conflit=1')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 1)
        self.assertTrue(rows(resp)[0]['conflit_conge'])

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'rost-normal', role='normal')
        resp = auth(normal).get(BASE)
        self.assertEqual(resp.status_code, 403)


class RosterActionsTests(TestCase):
    """Tests des actions semaine/ et conflits/."""

    def setUp(self):
        self.co = make_company('rost-act', 'Act')
        self.user = make_user(self.co, 'rost-act-user')
        self.emp = make_employe(self.co, 'EC1')
        self.emp2 = make_employe(self.co, 'EC2')
        self.ta = make_type_absence(self.co)

    def test_semaine_renvoie_la_semaine(self):
        # Une affectation dans la semaine, une hors semaine (semaine suivante).
        AffectationRoster.objects.create(
            company=self.co, employe=self.emp, equipe='Nord', date=JOUR,
            semaine_du=LUNDI)
        AffectationRoster.objects.create(
            company=self.co, employe=self.emp2, equipe='Nord',
            date=JOUR + timedelta(days=7),
            semaine_du=LUNDI + timedelta(days=7))
        resp = auth(self.user).get(BASE + f'semaine/?lundi={LUNDI.isoformat()}')
        self.assertEqual(resp.status_code, 200, resp.data)
        data = rows(resp)
        self.assertEqual(len(data), 1)

    def test_semaine_normalise_un_jour_quelconque(self):
        # Passer un mercredi doit ramener au lundi de la même semaine.
        AffectationRoster.objects.create(
            company=self.co, employe=self.emp, equipe='Nord', date=JOUR,
            semaine_du=LUNDI)
        resp = auth(self.user).get(BASE + f'semaine/?lundi={JOUR.isoformat()}')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(rows(resp)), 1)

    def test_conflits_action(self):
        make_conge(self.co, self.emp, self.ta, JOUR, JOUR)
        a1 = AffectationRoster.objects.create(
            company=self.co, employe=self.emp, equipe='Nord', date=JOUR)
        services.appliquer_roster(a1)
        a1.save()
        AffectationRoster.objects.create(
            company=self.co, employe=self.emp2, equipe='Nord', date=JOUR)
        resp = auth(self.user).get(
            f'{BASE}conflits/?debut={JOUR.isoformat()}&fin={JOUR.isoformat()}')
        self.assertEqual(resp.status_code, 200, resp.data)
        data = rows(resp)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['employe'], self.emp.id)


class RosterUniqueTests(TestCase):
    """Une seule affectation par (société, employé, jour)."""

    def setUp(self):
        self.co = make_company('rost-uni', 'Uni')
        self.user = make_user(self.co, 'rost-uni-user')
        self.emp = make_employe(self.co, 'EU1')

    def test_duplicate_meme_jour_refuse(self):
        AffectationRoster.objects.create(
            company=self.co, employe=self.emp, equipe='Nord', date=JOUR)
        resp = auth(self.user).post(BASE, {
            'employe': self.emp.id, 'equipe': 'Sud',
            'date': JOUR.isoformat(),
        }, format='json')
        # unique_together (company, employe, date) → 400 (IntegrityError DRF).
        self.assertIn(resp.status_code, [400, 409])
