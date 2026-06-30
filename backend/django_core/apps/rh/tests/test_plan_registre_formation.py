"""Tests FG188 — Plan & registre de formation (historique + besoins OFPPT/CSF).

Couvre :
* Registre de formation par employé (sélecteur + endpoint REST) : agrège ses
  inscriptions avec détail de session / présence / résultat ; ``total`` et
  ``total_realisees`` ; isolation société (le registre d'un employé d'une autre
  société renvoie 404 via ``get_object`` ; le sélecteur ne fuit rien).
* ``BesoinFormation`` : création ``company`` posée CÔTÉ SERVEUR ; drapeau
  d'obligation réglementaire (OFPPT / CSF) ; FK même société (employé /
  session liée d'une autre société refusés) ; filtres ; CRUD.
* Transition ``satisfaire`` : passe le besoin en ``satisfait`` ; garde-fou
  session non réalisée (400) ; idempotente ; scopée société (404 autre tenant).
* Permission : un rôle normal est refusé (403).
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import selectors
from apps.rh.models import (
    BesoinFormation,
    DossierEmploye,
    InscriptionFormation,
    SessionFormation,
)

User = get_user_model()

BESOINS_URL = '/api/django/rh/besoins-formation/'
EMPLOYES_URL = '/api/django/rh/employes/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_employe(company, matricule, nom='Nom', prenom='Prenom'):
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, nom=nom, prenom=prenom)


def make_session(company, intitule='Sécurité', statut='planifiee', **kwargs):
    return SessionFormation.objects.create(
        company=company, intitule=intitule,
        date_debut=kwargs.pop('date_debut', timezone.localdate()),
        statut=statut, **kwargs)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


class RegistreFormationSelectorTests(TestCase):
    def setUp(self):
        self.co_a = make_company('rf-a', 'A')
        self.co_b = make_company('rf-b', 'B')
        self.emp_a = make_employe(self.co_a, 'A-EMP', 'Bennani', 'Karim')
        self.emp_b = make_employe(self.co_b, 'B-EMP')
        # Deux sessions A pour emp_a : une réalisée, une planifiée.
        self.s_old = make_session(
            self.co_a, 'Ancienne', statut='realisee',
            date_debut=date(2026, 1, 1))
        self.s_new = make_session(
            self.co_a, 'Récente', statut='planifiee',
            date_debut=date(2026, 6, 1))
        InscriptionFormation.objects.create(
            company=self.co_a, session=self.s_old, participant=self.emp_a,
            present=True, resultat='reussi')
        InscriptionFormation.objects.create(
            company=self.co_a, session=self.s_new, participant=self.emp_a,
            present=False)

    def test_agrege_historique_trie_recent_dabord(self):
        reg = selectors.registre_formation_employe(self.co_a, self.emp_a.id)
        self.assertEqual(reg['employe'], self.emp_a.id)
        self.assertEqual(reg['total'], 2)
        self.assertEqual(reg['total_realisees'], 1)
        # La plus récente vient en premier.
        self.assertEqual(reg['lignes'][0]['intitule'], 'Récente')
        self.assertEqual(reg['lignes'][1]['intitule'], 'Ancienne')
        # Détail présence / résultat porté par l'inscription.
        ligne_old = reg['lignes'][1]
        self.assertTrue(ligne_old['present'])
        self.assertEqual(ligne_old['resultat'], 'reussi')
        self.assertTrue(ligne_old['realisee'])

    def test_isolation_societe(self):
        # Une inscription de B pour emp_b ne doit jamais apparaître dans A,
        # et la société A ne voit pas l'employé B.
        s_b = make_session(self.co_b, 'B-session')
        InscriptionFormation.objects.create(
            company=self.co_b, session=s_b, participant=self.emp_b,
            present=True)
        reg = selectors.registre_formation_employe(self.co_a, self.emp_b.id)
        self.assertEqual(reg['total'], 0)
        self.assertEqual(reg['lignes'], [])


class RegistreFormationEndpointTests(TestCase):
    def setUp(self):
        self.co_a = make_company('rfe-a', 'A')
        self.co_b = make_company('rfe-b', 'B')
        self.user_a = make_user(self.co_a, 'rfe-user-a')
        self.user_b = make_user(self.co_b, 'rfe-user-b')
        self.emp_a = make_employe(self.co_a, 'A-EMP')
        self.session = make_session(self.co_a, 'Travail en hauteur',
                                    statut='realisee')
        InscriptionFormation.objects.create(
            company=self.co_a, session=self.session, participant=self.emp_a,
            present=True, resultat='reussi')

    def test_endpoint_renvoie_registre(self):
        resp = auth(self.user_a).get(
            f'{EMPLOYES_URL}{self.emp_a.id}/registre-formation/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['total'], 1)
        self.assertEqual(resp.data['total_realisees'], 1)
        self.assertEqual(
            resp.data['lignes'][0]['intitule'], 'Travail en hauteur')

    def test_endpoint_autre_societe_404(self):
        resp = auth(self.user_b).get(
            f'{EMPLOYES_URL}{self.emp_a.id}/registre-formation/')
        self.assertEqual(resp.status_code, 404)

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'rfe-normal', role='normal')
        resp = auth(normal).get(
            f'{EMPLOYES_URL}{self.emp_a.id}/registre-formation/')
        self.assertEqual(resp.status_code, 403)


class BesoinFormationCrudTests(TestCase):
    def setUp(self):
        self.co_a = make_company('bf-a', 'A')
        self.co_b = make_company('bf-b', 'B')
        self.user_a = make_user(self.co_a, 'bf-user-a')
        self.user_b = make_user(self.co_b, 'bf-user-b')
        self.emp_a = make_employe(self.co_a, 'A-EMP')

    def test_create_company_cote_serveur_avec_obligation(self):
        resp = auth(self.user_a).post(BESOINS_URL, {
            'employe': self.emp_a.id,
            'theme': 'Habilitation électrique B1V',
            'priorite': 'haute',
            'echeance': '2026-12-31',
            'obligation_reglementaire': True,
            'type_obligation': 'ofppt',
            'notes': 'Obligation annuelle.',
            'company': self.co_b.id,  # doit être ignorée
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        besoin = BesoinFormation.objects.get(id=resp.data['id'])
        self.assertEqual(besoin.company, self.co_a)
        self.assertEqual(besoin.priorite, 'haute')
        self.assertTrue(besoin.obligation_reglementaire)
        self.assertEqual(besoin.type_obligation, 'ofppt')
        self.assertEqual(besoin.statut, 'identifie')

    def test_employe_autre_societe_refuse(self):
        emp_b = make_employe(self.co_b, 'B-EMP')
        resp = auth(self.user_a).post(BESOINS_URL, {
            'employe': emp_b.id,
            'theme': 'X',
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('employe', resp.data)

    def test_session_liee_autre_societe_refuse(self):
        s_b = make_session(self.co_b, 'B-session')
        resp = auth(self.user_a).post(BESOINS_URL, {
            'employe': self.emp_a.id,
            'theme': 'X',
            'session_liee': s_b.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('session_liee', resp.data)

    def test_filtre_obligation_et_statut(self):
        BesoinFormation.objects.create(
            company=self.co_a, employe=self.emp_a, theme='Reg',
            obligation_reglementaire=True, type_obligation='csf',
            statut='identifie')
        BesoinFormation.objects.create(
            company=self.co_a, employe=self.emp_a, theme='Libre',
            obligation_reglementaire=False, statut='planifie')
        resp = auth(self.user_a).get(f'{BESOINS_URL}?obligation=1')
        self.assertEqual(resp.status_code, 200)
        themes = {r['theme'] for r in rows(resp)}
        self.assertEqual(themes, {'Reg'})
        resp2 = auth(self.user_a).get(f'{BESOINS_URL}?statut=planifie')
        themes2 = {r['theme'] for r in rows(resp2)}
        self.assertEqual(themes2, {'Libre'})

    def test_isolation_list(self):
        emp_b = make_employe(self.co_b, 'B-EMP')
        BesoinFormation.objects.create(
            company=self.co_b, employe=emp_b, theme='B-besoin')
        resp = auth(self.user_a).get(BESOINS_URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'bf-normal', role='normal')
        resp = auth(normal).get(BESOINS_URL)
        self.assertEqual(resp.status_code, 403)


class BesoinFormationSatisfaireTests(TestCase):
    def setUp(self):
        self.co_a = make_company('bfs-a', 'A')
        self.co_b = make_company('bfs-b', 'B')
        self.user_a = make_user(self.co_a, 'bfs-user-a')
        self.user_b = make_user(self.co_b, 'bfs-user-b')
        self.emp_a = make_employe(self.co_a, 'A-EMP')

    def test_satisfaire_sans_session(self):
        besoin = BesoinFormation.objects.create(
            company=self.co_a, employe=self.emp_a, theme='X')
        resp = auth(self.user_a).post(
            f'{BESOINS_URL}{besoin.id}/satisfaire/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        besoin.refresh_from_db()
        self.assertEqual(besoin.statut, 'satisfait')

    def test_satisfaire_session_realisee_ok(self):
        session = make_session(self.co_a, 'Tenue', statut='realisee')
        besoin = BesoinFormation.objects.create(
            company=self.co_a, employe=self.emp_a, theme='X',
            session_liee=session, statut='planifie')
        resp = auth(self.user_a).post(
            f'{BESOINS_URL}{besoin.id}/satisfaire/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        besoin.refresh_from_db()
        self.assertEqual(besoin.statut, 'satisfait')

    def test_satisfaire_session_non_realisee_refuse(self):
        session = make_session(self.co_a, 'Planifiée', statut='planifiee')
        besoin = BesoinFormation.objects.create(
            company=self.co_a, employe=self.emp_a, theme='X',
            session_liee=session, statut='planifie')
        resp = auth(self.user_a).post(
            f'{BESOINS_URL}{besoin.id}/satisfaire/', {}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        besoin.refresh_from_db()
        self.assertEqual(besoin.statut, 'planifie')

    def test_satisfaire_idempotent(self):
        besoin = BesoinFormation.objects.create(
            company=self.co_a, employe=self.emp_a, theme='X',
            statut='satisfait')
        resp = auth(self.user_a).post(
            f'{BESOINS_URL}{besoin.id}/satisfaire/', {}, format='json')
        self.assertEqual(resp.status_code, 200)
        besoin.refresh_from_db()
        self.assertEqual(besoin.statut, 'satisfait')

    def test_satisfaire_autre_societe_404(self):
        besoin = BesoinFormation.objects.create(
            company=self.co_a, employe=self.emp_a, theme='X')
        resp = auth(self.user_b).post(
            f'{BESOINS_URL}{besoin.id}/satisfaire/', {}, format='json')
        self.assertEqual(resp.status_code, 404)
