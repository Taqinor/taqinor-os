"""Tests FG173 — Habilitations électriques par employé (titre + validité).

Couvre :
* Création : company posée côté serveur (jamais lue du corps), employe validé.
* Calcul ``valide`` : titre actif sans échéance → valide ; échéance future →
  valide ; échéance passée → non valide ; titre inactif → non valide.
* Cohérence des dates : validité avant obtention refusée (400).
* Unicité (employé, titre) : un même titre deux fois refusé (400).
* Filtre/endpoint expirantes : titres expirant dans N jours + déjà expirés ;
  ``?expire_within=`` borne la fenêtre ; ``?inclure_expirees=0`` exclut les échus.
* Cross-société : employé d'une autre société refusé (400).
* Isolation multi-société : B ne voit pas les habilitations de A.
* Permission : un rôle normal est refusé (403).
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import DossierEmploye, Habilitation

User = get_user_model()

HAB = '/api/django/rh/habilitations/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_employe(company, matricule):
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, nom='Test', prenom='E')


def make_habilitation(company, employe, type_habilitation='b1v',
                      date_validite=None, actif=True):
    return Habilitation.objects.create(
        company=company, employe=employe,
        type_habilitation=type_habilitation,
        date_validite=date_validite, actif=actif)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


class HabilitationCreateTests(TestCase):
    def setUp(self):
        self.co_a = make_company('hab-a', 'A')
        self.co_b = make_company('hab-b', 'B')
        self.user_a = make_user(self.co_a, 'hab-user-a')
        self.user_b = make_user(self.co_b, 'hab-user-b')
        self.emp_a = make_employe(self.co_a, 'EA1')
        self.emp_b = make_employe(self.co_b, 'EB1')

    def test_create_company_posee_cote_serveur(self):
        echeance = timezone.localdate() + timedelta(days=365)
        resp = auth(self.user_a).post(HAB, {
            'employe': self.emp_a.id,
            'type_habilitation': 'b1v',
            'organisme': 'AFPA Casablanca',
            'date_validite': echeance.isoformat(),
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        hab = Habilitation.objects.get(id=resp.data['id'])
        self.assertEqual(hab.company, self.co_a)
        self.assertEqual(hab.type_habilitation, 'b1v')
        self.assertTrue(resp.data['valide'])

    def test_employe_ne_lit_pas_company_du_corps(self):
        # ``company`` du corps est ignorée : la société vient du serveur.
        resp = auth(self.user_a).post(HAB, {
            'employe': self.emp_a.id,
            'type_habilitation': 'br',
            'company': self.co_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        hab = Habilitation.objects.get(id=resp.data['id'])
        self.assertEqual(hab.company, self.co_a)

    def test_employe_autre_societe_refuse(self):
        resp = auth(self.user_a).post(HAB, {
            'employe': self.emp_b.id, 'type_habilitation': 'b1v',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_validite_avant_obtention_refuse(self):
        today = timezone.localdate()
        resp = auth(self.user_a).post(HAB, {
            'employe': self.emp_a.id, 'type_habilitation': 'b2v',
            'date_obtention': today.isoformat(),
            'date_validite': (today - timedelta(days=5)).isoformat(),
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_unicite_employe_type(self):
        make_habilitation(self.co_a, self.emp_a, 'b1v')
        resp = auth(self.user_a).post(HAB, {
            'employe': self.emp_a.id, 'type_habilitation': 'b1v',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_meme_type_autre_employe_ok(self):
        make_habilitation(self.co_a, self.emp_a, 'b1v')
        emp2 = make_employe(self.co_a, 'EA2')
        resp = auth(self.user_a).post(HAB, {
            'employe': emp2.id, 'type_habilitation': 'b1v',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'hab-normal', role='normal')
        resp = auth(normal).get(HAB)
        self.assertEqual(resp.status_code, 403)

    def test_isolation_list(self):
        make_habilitation(self.co_a, self.emp_a, 'b1v')
        resp = auth(self.user_b).get(HAB)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)


class HabilitationValiditeTests(TestCase):
    def setUp(self):
        self.co_a = make_company('habv-a', 'A')
        self.emp_a = make_employe(self.co_a, 'EA1')

    def test_valide_actif_sans_echeance(self):
        hab = make_habilitation(self.co_a, self.emp_a, 'b0', date_validite=None)
        self.assertTrue(hab.valide)

    def test_valide_echeance_future(self):
        echeance = timezone.localdate() + timedelta(days=10)
        hab = make_habilitation(
            self.co_a, self.emp_a, 'b1v', date_validite=echeance)
        self.assertTrue(hab.valide)

    def test_non_valide_echeance_passee(self):
        echeance = timezone.localdate() - timedelta(days=1)
        hab = make_habilitation(
            self.co_a, self.emp_a, 'b2v', date_validite=echeance)
        self.assertFalse(hab.valide)

    def test_non_valide_inactif(self):
        echeance = timezone.localdate() + timedelta(days=365)
        hab = make_habilitation(
            self.co_a, self.emp_a, 'br', date_validite=echeance, actif=False)
        self.assertFalse(hab.valide)

    def test_valide_jour_echeance_inclus(self):
        today = timezone.localdate()
        hab = make_habilitation(self.co_a, self.emp_a, 'bc', date_validite=today)
        self.assertTrue(hab.valide)


class HabilitationExpirantesTests(TestCase):
    def setUp(self):
        self.co_a = make_company('habx-a', 'A')
        self.co_b = make_company('habx-b', 'B')
        self.user_a = make_user(self.co_a, 'habx-user-a')
        self.user_b = make_user(self.co_b, 'habx-user-b')
        self.emp_a = make_employe(self.co_a, 'EA1')
        self.emp_b = make_employe(self.co_b, 'EB1')
        today = timezone.localdate()
        # Expire bientôt (dans 10 jours).
        self.bientot = make_habilitation(
            self.co_a, self.emp_a, 'b1v',
            date_validite=today + timedelta(days=10))
        # Déjà expirée (hier).
        self.expiree = make_habilitation(
            self.co_a, self.emp_a, 'b2v',
            date_validite=today - timedelta(days=1))
        # Lointaine (dans 200 jours) — hors fenêtre 30 j.
        self.lointaine = make_habilitation(
            self.co_a, self.emp_a, 'br',
            date_validite=today + timedelta(days=200))
        # Sans échéance — jamais listée comme expirante.
        self.sans_echeance = make_habilitation(
            self.co_a, self.emp_a, 'b0', date_validite=None)

    def test_expirantes_inclut_bientot_et_expirees(self):
        resp = auth(self.user_a).get(HAB + 'expirantes/')
        self.assertEqual(resp.status_code, 200, resp.data)
        ids = {h['id'] for h in rows(resp)}
        self.assertIn(self.bientot.id, ids)
        self.assertIn(self.expiree.id, ids)
        self.assertNotIn(self.lointaine.id, ids)
        self.assertNotIn(self.sans_echeance.id, ids)

    def test_expire_within_elargit_la_fenetre(self):
        resp = auth(self.user_a).get(HAB + 'expirantes/?expire_within=365')
        ids = {h['id'] for h in rows(resp)}
        self.assertIn(self.lointaine.id, ids)

    def test_inclure_expirees_0_exclut_les_echues(self):
        resp = auth(self.user_a).get(
            HAB + 'expirantes/?inclure_expirees=0')
        ids = {h['id'] for h in rows(resp)}
        self.assertIn(self.bientot.id, ids)
        self.assertNotIn(self.expiree.id, ids)

    def test_expirantes_isolation_societe(self):
        # B a une habilitation expirante, mais ne voit jamais celles de A.
        make_habilitation(
            self.co_b, self.emp_b, 'b1v',
            date_validite=timezone.localdate() + timedelta(days=5))
        resp = auth(self.user_b).get(HAB + 'expirantes/')
        self.assertEqual(resp.status_code, 200)
        ids = {h['id'] for h in rows(resp)}
        self.assertNotIn(self.bientot.id, ids)
        self.assertNotIn(self.expiree.id, ids)

    def test_filtre_type_habilitation(self):
        resp = auth(self.user_a).get(HAB + '?type_habilitation=b2v')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            [h['type_habilitation'] for h in rows(resp)], ['b2v'])
