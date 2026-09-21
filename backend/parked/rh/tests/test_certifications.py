"""Tests FG174 — Certifications spécifiques par employé (titre + validité).

Famille DISTINCTE des habilitations électriques (FG173). Couvre :
* Création : company posée côté serveur (jamais lue du corps), employe validé.
* Calcul ``valide`` : titre actif sans échéance → valide ; échéance future →
  valide ; échéance passée → non valide ; titre inactif → non valide.
* Cohérence des dates : validité avant obtention refusée (400).
* Unicité (employé, type) : un même type deux fois refusé (400).
* Filtre/endpoint expirantes : titres expirant dans N jours + déjà expirés ;
  ``?expire_within=`` borne la fenêtre ; ``?inclure_expirees=0`` exclut les échus.
* Cross-société : employé d'une autre société refusé (400).
* Isolation multi-société : B ne voit pas les certifications de A.
* Permission : un rôle normal est refusé (403).
* Runtime-safety : tous les codes de type tiennent dans ``max_length``.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import Certification, DossierEmploye

User = get_user_model()

CERT = '/api/django/rh/certifications/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_employe(company, matricule):
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, nom='Test', prenom='E')


def make_certification(company, employe, type_certification='travail_hauteur',
                       date_validite=None, actif=True):
    return Certification.objects.create(
        company=company, employe=employe,
        type_certification=type_certification,
        date_validite=date_validite, actif=actif)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


class CertificationCreateTests(TestCase):
    def setUp(self):
        self.co_a = make_company('cert-a', 'A')
        self.co_b = make_company('cert-b', 'B')
        self.user_a = make_user(self.co_a, 'cert-user-a')
        self.user_b = make_user(self.co_b, 'cert-user-b')
        self.emp_a = make_employe(self.co_a, 'EA1')
        self.emp_b = make_employe(self.co_b, 'EB1')

    def test_create_company_posee_cote_serveur(self):
        echeance = timezone.localdate() + timedelta(days=365)
        resp = auth(self.user_a).post(CERT, {
            'employe': self.emp_a.id,
            'type_certification': 'travail_hauteur',
            'organisme': 'OFPPT Casablanca',
            'date_validite': echeance.isoformat(),
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        cert = Certification.objects.get(id=resp.data['id'])
        self.assertEqual(cert.company, self.co_a)
        self.assertEqual(cert.type_certification, 'travail_hauteur')
        self.assertTrue(resp.data['valide'])

    def test_employe_ne_lit_pas_company_du_corps(self):
        # ``company`` du corps est ignorée : la société vient du serveur.
        resp = auth(self.user_a).post(CERT, {
            'employe': self.emp_a.id,
            'type_certification': 'caces_nacelle',
            'company': self.co_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        cert = Certification.objects.get(id=resp.data['id'])
        self.assertEqual(cert.company, self.co_a)

    def test_employe_autre_societe_refuse(self):
        resp = auth(self.user_a).post(CERT, {
            'employe': self.emp_b.id, 'type_certification': 'harnais',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_validite_avant_obtention_refuse(self):
        today = timezone.localdate()
        resp = auth(self.user_a).post(CERT, {
            'employe': self.emp_a.id, 'type_certification': 'secourisme_sst',
            'date_obtention': today.isoformat(),
            'date_validite': (today - timedelta(days=5)).isoformat(),
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_unicite_employe_type(self):
        make_certification(self.co_a, self.emp_a, 'harnais')
        resp = auth(self.user_a).post(CERT, {
            'employe': self.emp_a.id, 'type_certification': 'harnais',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_meme_type_autre_employe_ok(self):
        make_certification(self.co_a, self.emp_a, 'conduite')
        emp2 = make_employe(self.co_a, 'EA2')
        resp = auth(self.user_a).post(CERT, {
            'employe': emp2.id, 'type_certification': 'conduite',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'cert-normal', role='normal')
        resp = auth(normal).get(CERT)
        self.assertEqual(resp.status_code, 403)

    def test_isolation_list(self):
        make_certification(self.co_a, self.emp_a, 'travail_hauteur')
        resp = auth(self.user_b).get(CERT)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_tous_les_codes_tiennent_dans_max_length(self):
        # Runtime-safety (FG136) : aucun code de type ne dépasse ``max_length``.
        field = Certification._meta.get_field('type_certification')
        for value, _label in Certification.TypeCertification.choices:
            self.assertLessEqual(
                len(value), field.max_length,
                f'Le code {value!r} dépasse max_length={field.max_length}')


class CertificationValiditeTests(TestCase):
    def setUp(self):
        self.co_a = make_company('certv-a', 'A')
        self.emp_a = make_employe(self.co_a, 'EA1')

    def test_valide_actif_sans_echeance(self):
        cert = make_certification(
            self.co_a, self.emp_a, 'conduite', date_validite=None)
        self.assertTrue(cert.valide)

    def test_valide_echeance_future(self):
        echeance = timezone.localdate() + timedelta(days=10)
        cert = make_certification(
            self.co_a, self.emp_a, 'travail_hauteur', date_validite=echeance)
        self.assertTrue(cert.valide)

    def test_non_valide_echeance_passee(self):
        echeance = timezone.localdate() - timedelta(days=1)
        cert = make_certification(
            self.co_a, self.emp_a, 'harnais', date_validite=echeance)
        self.assertFalse(cert.valide)

    def test_non_valide_inactif(self):
        echeance = timezone.localdate() + timedelta(days=365)
        cert = make_certification(
            self.co_a, self.emp_a, 'caces_nacelle',
            date_validite=echeance, actif=False)
        self.assertFalse(cert.valide)

    def test_valide_jour_echeance_inclus(self):
        today = timezone.localdate()
        cert = make_certification(
            self.co_a, self.emp_a, 'secourisme_sst', date_validite=today)
        self.assertTrue(cert.valide)


class CertificationExpirantesTests(TestCase):
    def setUp(self):
        self.co_a = make_company('certx-a', 'A')
        self.co_b = make_company('certx-b', 'B')
        self.user_a = make_user(self.co_a, 'certx-user-a')
        self.user_b = make_user(self.co_b, 'certx-user-b')
        self.emp_a = make_employe(self.co_a, 'EA1')
        self.emp_b = make_employe(self.co_b, 'EB1')
        today = timezone.localdate()
        # Expire bientôt (dans 10 jours).
        self.bientot = make_certification(
            self.co_a, self.emp_a, 'travail_hauteur',
            date_validite=today + timedelta(days=10))
        # Déjà expirée (hier).
        self.expiree = make_certification(
            self.co_a, self.emp_a, 'harnais',
            date_validite=today - timedelta(days=1))
        # Lointaine (dans 200 jours) — hors fenêtre 30 j.
        self.lointaine = make_certification(
            self.co_a, self.emp_a, 'caces_nacelle',
            date_validite=today + timedelta(days=200))
        # Sans échéance — jamais listée comme expirante.
        self.sans_echeance = make_certification(
            self.co_a, self.emp_a, 'conduite', date_validite=None)

    def test_expirantes_inclut_bientot_et_expirees(self):
        resp = auth(self.user_a).get(CERT + 'expirantes/')
        self.assertEqual(resp.status_code, 200, resp.data)
        ids = {c['id'] for c in rows(resp)}
        self.assertIn(self.bientot.id, ids)
        self.assertIn(self.expiree.id, ids)
        self.assertNotIn(self.lointaine.id, ids)
        self.assertNotIn(self.sans_echeance.id, ids)

    def test_expire_within_elargit_la_fenetre(self):
        resp = auth(self.user_a).get(CERT + 'expirantes/?expire_within=365')
        ids = {c['id'] for c in rows(resp)}
        self.assertIn(self.lointaine.id, ids)

    def test_inclure_expirees_0_exclut_les_echues(self):
        resp = auth(self.user_a).get(
            CERT + 'expirantes/?inclure_expirees=0')
        ids = {c['id'] for c in rows(resp)}
        self.assertIn(self.bientot.id, ids)
        self.assertNotIn(self.expiree.id, ids)

    def test_expirantes_isolation_societe(self):
        # B a une certification expirante, mais ne voit jamais celles de A.
        make_certification(
            self.co_b, self.emp_b, 'travail_hauteur',
            date_validite=timezone.localdate() + timedelta(days=5))
        resp = auth(self.user_b).get(CERT + 'expirantes/')
        self.assertEqual(resp.status_code, 200)
        ids = {c['id'] for c in rows(resp)}
        self.assertNotIn(self.bientot.id, ids)
        self.assertNotIn(self.expiree.id, ids)

    def test_filtre_type_certification(self):
        resp = auth(self.user_a).get(CERT + '?type_certification=harnais')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            [c['type_certification'] for c in rows(resp)], ['harnais'])
