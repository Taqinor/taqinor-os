"""Tests FG180 — Émargement de remise EPI (accusé de réception signé).

Accusé de réception signé prouvant la remise d'un EPI (exigible CNSS / accident
du travail), sur le modèle e-sign IN-APP loi 53-05 (aucun prestataire externe).
Couvre :
* Émargement : crée un ``EmargementEpi``, enregistre les preuves
  (nom dactylographié, IP, user agent, méthode), marque la dotation ACCUSÉE
  (``accuse_remise`` + ``date_accuse``).
* Acteur + société posés CÔTÉ SERVEUR (jamais lus du corps) ; ``company`` de la
  dotation ; ``signataire`` = utilisateur agissant.
* Nom du signataire requis (loi 53-05) → 400.
* Second émargement (témoin) toléré ; ``date_accuse`` figée au premier accusé.
* Rôle normal refusé (403) ; isolation multi-société (404 sur dotation d'autrui).
* Historique ``emargements/`` scopé société.
* RUNTIME-SAFETY : ``ip_adresse`` ≤ 45 (IPv6) ; ``user_agent`` long en
  ``TextField`` ; index ``rh_emepi_comp_dot_idx`` ≤ 30 chars.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import services
from apps.rh.models import (
    DossierEmploye, DotationEpi, EmargementEpi, EpiCatalogue,
)

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


def make_epi(company, type_epi='harnais', designation='Harnais Petzl'):
    return EpiCatalogue.objects.create(
        company=company, type_epi=type_epi, designation=designation)


def make_dotation(company, employe, epi, taille='M'):
    return DotationEpi.objects.create(
        company=company, employe=employe, epi=epi, taille=taille)


def auth(user, **extra):
    api = APIClient()
    api.credentials(
        HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}', **extra)
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


class EmargementEpiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('emep-a', 'A')
        self.co_b = make_company('emep-b', 'B')
        self.user_a = make_user(self.co_a, 'emep-user-a')
        self.user_b = make_user(self.co_b, 'emep-user-b')
        self.emp_a = make_employe(self.co_a, 'EA1')
        self.epi_a = make_epi(self.co_a)
        self.dot_a = make_dotation(self.co_a, self.emp_a, self.epi_a)

    def url_emarger(self, dotation):
        return f'{DOT}{dotation.id}/emarger/'

    def url_emargements(self, dotation):
        return f'{DOT}{dotation.id}/emargements/'

    def test_emarger_cree_preuve_et_accuse(self):
        resp = auth(
            self.user_a,
            HTTP_USER_AGENT='Mozilla/5.0 Tablette',
            REMOTE_ADDR='10.1.2.3',
        ).post(self.url_emarger(self.dot_a), {
            'signataire_nom': 'Ahmed Benani',
            'mention': 'Reçu en bon état',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(resp.data['accuse_remise'])
        self.assertFalse(resp.data['deja_accusee'])
        # La dotation est marquée accusée côté DB.
        self.dot_a.refresh_from_db()
        self.assertTrue(self.dot_a.accuse_remise)
        self.assertIsNotNone(self.dot_a.date_accuse)
        # L'émargement porte les preuves, posées côté serveur.
        em = EmargementEpi.objects.get(id=resp.data['emargement']['id'])
        self.assertEqual(em.company, self.co_a)
        self.assertEqual(em.dotation, self.dot_a)
        self.assertEqual(em.signataire_nom, 'Ahmed Benani')
        self.assertEqual(em.signataire, self.user_a)
        self.assertEqual(em.ip_adresse, '10.1.2.3')
        self.assertEqual(em.user_agent, 'Mozilla/5.0 Tablette')
        self.assertEqual(em.mention, 'Reçu en bon état')
        self.assertEqual(em.role_signataire, 'employe')
        self.assertEqual(em.methode, 'typed')

    def test_company_et_signataire_ignores_du_corps(self):
        resp = auth(self.user_a).post(self.url_emarger(self.dot_a), {
            'signataire_nom': 'Sara',
            'company': self.co_b.id,       # ignoré
            'signataire': self.user_b.id,  # ignoré
            'ip_adresse': '8.8.8.8',       # ignoré (preuve serveur)
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        em = EmargementEpi.objects.get(id=resp.data['emargement']['id'])
        self.assertEqual(em.company, self.co_a)
        self.assertEqual(em.signataire, self.user_a)
        self.assertNotEqual(em.ip_adresse, '8.8.8.8')

    def test_nom_requis(self):
        resp = auth(self.user_a).post(self.url_emarger(self.dot_a), {
            'signataire_nom': '   ',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.dot_a.refresh_from_db()
        self.assertFalse(self.dot_a.accuse_remise)

    def test_second_emargement_temoin_fige_date_accuse(self):
        first = auth(self.user_a).post(self.url_emarger(self.dot_a), {
            'signataire_nom': 'Employé',
        }, format='json')
        self.assertEqual(first.status_code, 201, first.data)
        self.dot_a.refresh_from_db()
        date_premier = self.dot_a.date_accuse
        # Un témoin émarge à son tour : toléré, dotation déjà accusée.
        second = auth(self.user_a).post(self.url_emarger(self.dot_a), {
            'signataire_nom': 'Témoin',
            'role_signataire': 'temoin',
        }, format='json')
        self.assertEqual(second.status_code, 201, second.data)
        self.assertTrue(second.data['deja_accusee'])
        self.dot_a.refresh_from_db()
        self.assertEqual(self.dot_a.date_accuse, date_premier)
        self.assertEqual(self.dot_a.emargements.count(), 2)

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'emep-normal', role='normal')
        resp = auth(normal).post(self.url_emarger(self.dot_a), {
            'signataire_nom': 'X',
        }, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_isolation_dotation_autre_societe(self):
        resp = auth(self.user_b).post(self.url_emarger(self.dot_a), {
            'signataire_nom': 'Intrus',
        }, format='json')
        self.assertEqual(resp.status_code, 404)
        self.dot_a.refresh_from_db()
        self.assertFalse(self.dot_a.accuse_remise)

    def test_historique_emargements_scope_societe(self):
        services.emarger_dotation(
            self.dot_a, signataire_nom='Employé', signataire=self.user_a)
        resp = auth(self.user_a).get(self.url_emargements(self.dot_a))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(rows(resp)), 1)
        self.assertEqual(rows(resp)[0]['signataire_nom'], 'Employé')
        # Une autre société ne voit pas cette dotation (404).
        resp_b = auth(self.user_b).get(self.url_emargements(self.dot_a))
        self.assertEqual(resp_b.status_code, 404)


class EmargementEpiServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('emsvc', 'C')
        self.emp = make_employe(self.co, 'E1')
        self.epi = make_epi(self.co)
        self.dot = make_dotation(self.co, self.emp, self.epi)

    def test_service_marque_accuse_et_pose_company(self):
        out = services.emarger_dotation(
            self.dot, signataire_nom='  Nadia  ')
        self.dot.refresh_from_db()
        self.assertTrue(self.dot.accuse_remise)
        self.assertIsNotNone(self.dot.date_accuse)
        self.assertFalse(out['deja_accusee'])
        self.assertEqual(out['emargement'].company, self.co)
        # Nom débarrassé des espaces (fait foi loi 53-05).
        self.assertEqual(out['emargement'].signataire_nom, 'Nadia')

    def test_service_nom_vide_leve_erreur(self):
        with self.assertRaises(services.EmargementError):
            services.emarger_dotation(self.dot, signataire_nom='')
        self.dot.refresh_from_db()
        self.assertFalse(self.dot.accuse_remise)
        self.assertEqual(self.dot.emargements.count(), 0)

    def test_ip_tronquee_a_45(self):
        out = services.emarger_dotation(
            self.dot, signataire_nom='Y', ip_adresse='9' * 60)
        self.assertEqual(len(out['emargement'].ip_adresse), 45)


class EmargementEpiRuntimeSafetyTests(TestCase):
    def test_ip_adresse_max_length_45(self):
        field = EmargementEpi._meta.get_field('ip_adresse')
        self.assertEqual(field.max_length, 45)

    def test_user_agent_est_textfield(self):
        from django.db import models as dj_models
        field = EmargementEpi._meta.get_field('user_agent')
        self.assertIsInstance(field, dj_models.TextField)

    def test_codes_bornes_tiennent_dans_max_length(self):
        for name, choices in (
            ('role_signataire', EmargementEpi.RoleSignataire.choices),
            ('methode', EmargementEpi.Methode.choices),
        ):
            field = EmargementEpi._meta.get_field(name)
            for value, _label in choices:
                self.assertLessEqual(
                    len(value), field.max_length,
                    f'{name}={value!r} dépasse max_length={field.max_length}')

    def test_index_name_max_30(self):
        names = [idx.name for idx in EmargementEpi._meta.indexes]
        self.assertIn('rh_emepi_comp_dot_idx', names)
        for name in names:
            self.assertLessEqual(len(name), 30, name)
