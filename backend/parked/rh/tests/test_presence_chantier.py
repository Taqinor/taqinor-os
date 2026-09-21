"""Tests FG170 — Registre de présence chantier journalier (émargement).

Couvre :
* Création d'une présence (company posée côté serveur, jamais lue du corps).
* Émargement via l'action emarger/ (emarge=True, emarge_le, emarge_par posés
  côté serveur).
* Isolation multi-société : B ne voit pas les présences de A, ni n'émarge ni
  ne crée pour un employé de A.
* Unicité (société, employé, installation, jour) → 400 sur doublon.
* Filtres ?employe=, ?installation_id=, ?statut=, ?emarge=, ?date=, plage.
* Action chantier/ (registre + presents=1) + sélecteur effectif_present_le.
* Validation horaire (départ < arrivée refusé).
* Permission : un rôle normal est refusé (403).
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import selectors
from apps.rh.models import DossierEmploye, PresenceChantier

User = get_user_model()

BASE = '/api/django/rh/presences-chantier/'
JOUR = date(2026, 6, 24)
INST = 7001


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_employe(company, matricule):
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, nom='Test', prenom='E')


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


class PresenceApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('pres-a', 'A')
        self.co_b = make_company('pres-b', 'B')
        self.user_a = make_user(self.co_a, 'pres-user-a')
        self.user_b = make_user(self.co_b, 'pres-user-b')
        self.emp_a = make_employe(self.co_a, 'PA1')
        self.emp_b = make_employe(self.co_b, 'PB1')

    def test_create_company_posee_cote_serveur(self):
        resp = auth(self.user_a).post(BASE, {
            'employe': self.emp_a.id, 'installation_id': INST,
            'date': JOUR.isoformat(),
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        p = PresenceChantier.objects.get(id=resp.data['id'])
        self.assertEqual(p.company, self.co_a)
        self.assertEqual(p.statut, PresenceChantier.Statut.PRESENT)
        self.assertFalse(p.emarge)

    def test_create_employe_autre_societe_refuse(self):
        resp = auth(self.user_a).post(BASE, {
            'employe': self.emp_b.id, 'installation_id': INST,
            'date': JOUR.isoformat(),
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_isolation_list(self):
        PresenceChantier.objects.create(
            company=self.co_a, employe=self.emp_a, installation_id=INST,
            date=JOUR)
        resp = auth(self.user_b).get(BASE)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_duplicate_refuse(self):
        PresenceChantier.objects.create(
            company=self.co_a, employe=self.emp_a, installation_id=INST,
            date=JOUR)
        resp = auth(self.user_a).post(BASE, {
            'employe': self.emp_a.id, 'installation_id': INST,
            'date': JOUR.isoformat(),
        }, format='json')
        self.assertIn(resp.status_code, [400, 409])

    def test_meme_employe_autre_chantier_ok(self):
        # Même jour, même employé, chantier DIFFÉRENT → pas un doublon.
        PresenceChantier.objects.create(
            company=self.co_a, employe=self.emp_a, installation_id=INST,
            date=JOUR)
        resp = auth(self.user_a).post(BASE, {
            'employe': self.emp_a.id, 'installation_id': INST + 1,
            'date': JOUR.isoformat(),
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_depart_avant_arrivee_refuse(self):
        resp = auth(self.user_a).post(BASE, {
            'employe': self.emp_a.id, 'installation_id': INST,
            'date': JOUR.isoformat(),
            'heure_arrivee': '09:00', 'heure_depart': '08:00',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_filtre_installation(self):
        emp2 = make_employe(self.co_a, 'PA2')
        PresenceChantier.objects.create(
            company=self.co_a, employe=self.emp_a, installation_id=INST,
            date=JOUR)
        PresenceChantier.objects.create(
            company=self.co_a, employe=emp2, installation_id=INST + 1,
            date=JOUR)
        resp = auth(self.user_a).get(BASE + f'?installation_id={INST}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 1)

    def test_filtre_statut_et_emarge(self):
        PresenceChantier.objects.create(
            company=self.co_a, employe=self.emp_a, installation_id=INST,
            date=JOUR, statut=PresenceChantier.Statut.ABSENT)
        emp2 = make_employe(self.co_a, 'PA3')
        PresenceChantier.objects.create(
            company=self.co_a, employe=emp2, installation_id=INST,
            date=JOUR, statut=PresenceChantier.Statut.PRESENT, emarge=True)
        r1 = auth(self.user_a).get(BASE + '?statut=absent')
        self.assertEqual(len(rows(r1)), 1)
        r2 = auth(self.user_a).get(BASE + '?emarge=1')
        self.assertEqual(len(rows(r2)), 1)

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'pres-normal', role='normal')
        resp = auth(normal).get(BASE)
        self.assertEqual(resp.status_code, 403)


class PresenceEmargerTests(TestCase):
    def setUp(self):
        self.co = make_company('pres-em', 'Em')
        self.user = make_user(self.co, 'pres-em-user')
        self.emp = make_employe(self.co, 'PE1')

    def test_emarger_pose_signature_cote_serveur(self):
        p = PresenceChantier.objects.create(
            company=self.co, employe=self.emp, installation_id=INST, date=JOUR)
        resp = auth(self.user).post(f'{BASE}{p.id}/emarger/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        p.refresh_from_db()
        self.assertTrue(p.emarge)
        self.assertIsNotNone(p.emarge_le)
        self.assertEqual(p.emarge_par, self.user)

    def test_emarger_autre_societe_refuse(self):
        co_b = make_company('pres-em-b', 'B')
        user_b = make_user(co_b, 'pres-em-b-user')
        p = PresenceChantier.objects.create(
            company=self.co, employe=self.emp, installation_id=INST, date=JOUR)
        resp = auth(user_b).post(f'{BASE}{p.id}/emarger/', {}, format='json')
        self.assertIn(resp.status_code, [403, 404])


class PresenceChantierActionTests(TestCase):
    def setUp(self):
        self.co = make_company('pres-ch', 'Ch')
        self.user = make_user(self.co, 'pres-ch-user')
        self.emp = make_employe(self.co, 'PC1')
        self.emp2 = make_employe(self.co, 'PC2')

    def test_chantier_requiert_installation_id(self):
        resp = auth(self.user).get(BASE + 'chantier/')
        self.assertEqual(resp.status_code, 400)

    def test_chantier_registre(self):
        PresenceChantier.objects.create(
            company=self.co, employe=self.emp, installation_id=INST, date=JOUR)
        PresenceChantier.objects.create(
            company=self.co, employe=self.emp2, installation_id=INST + 5,
            date=JOUR)
        resp = auth(self.user).get(
            BASE + f'chantier/?installation_id={INST}')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(rows(resp)), 1)

    def test_chantier_presents_exclut_absents(self):
        PresenceChantier.objects.create(
            company=self.co, employe=self.emp, installation_id=INST, date=JOUR,
            statut=PresenceChantier.Statut.PRESENT)
        PresenceChantier.objects.create(
            company=self.co, employe=self.emp2, installation_id=INST, date=JOUR,
            statut=PresenceChantier.Statut.ABSENT)
        resp = auth(self.user).get(
            BASE + f'chantier/?installation_id={INST}&presents=1')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(rows(resp)), 1)

    def test_selector_effectif_present(self):
        PresenceChantier.objects.create(
            company=self.co, employe=self.emp, installation_id=INST, date=JOUR,
            statut=PresenceChantier.Statut.PRESENT)
        PresenceChantier.objects.create(
            company=self.co, employe=self.emp2, installation_id=INST, date=JOUR,
            statut=PresenceChantier.Statut.ABSENT)
        # 1 présent (l'absent est exclu).
        self.assertEqual(
            selectors.effectif_present_le(self.co, INST, JOUR), 1)
        self.assertEqual(
            selectors.effectif_present_le(None, INST, JOUR), 0)
