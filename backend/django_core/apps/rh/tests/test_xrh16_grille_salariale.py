"""Tests XRH16 — Grille salariale par poste (bandes min/max, compa-ratio).

Couvre :
* un salaire hors bande est signalé (sous_bande / sur_bande) ;
* compa-ratio correct (salaire / milieu de bande) ;
* un rôle SANS ``salaires_voir`` reçoit 403 (CRUD grille + compa-ratio) ;
* isolation société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.rh.models import DossierEmploye, GrilleSalariale, Poste, Remuneration

User = get_user_model()

EMPLOYES = '/api/django/rh/employes/'
GRILLES = '/api/django/rh/grilles-salariales/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, permissions):
    role = Role.objects.create(
        company=company, nom=f'role-{username}', permissions=list(permissions))
    return User.objects.create_user(
        username=username, password='x', company=company, role=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class GrilleSalarialeTests(TestCase):
    def setUp(self):
        self.co = make_company('grille-a', 'A')
        self.rh = make_user(self.co, 'grille-rh', ['salaires_voir'])
        self.sans = make_user(
            self.co, 'grille-sans', ['crm_voir', 'ventes_voir'])
        self.poste = Poste.objects.create(
            company=self.co, intitule='Chef de chantier')
        self.grille = GrilleSalariale.objects.create(
            company=self.co, poste=self.poste,
            salaire_min=8000, salaire_max=12000, date_effet='2026-01-01')
        self.emp = DossierEmploye.objects.create(
            company=self.co, matricule='GR1', nom='Sekkat', prenom='Yasser',
            poste_ref=self.poste)

    def test_compa_ratio_dans_bande(self):
        Remuneration.objects.create(
            company=self.co, employe=self.emp, montant=10000,
            date_effet='2026-02-01')
        resp = auth(self.rh).get(f'{EMPLOYES}{self.emp.id}/compa-ratio/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'dans_bande')
        self.assertEqual(resp.data['compa_ratio_pct'], 100.0)

    def test_salaire_sous_bande_signale(self):
        Remuneration.objects.create(
            company=self.co, employe=self.emp, montant=6000,
            date_effet='2026-02-01')
        resp = auth(self.rh).get(f'{EMPLOYES}{self.emp.id}/compa-ratio/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'sous_bande')

    def test_salaire_sur_bande_signale(self):
        Remuneration.objects.create(
            company=self.co, employe=self.emp, montant=15000,
            date_effet='2026-02-01')
        resp = auth(self.rh).get(f'{EMPLOYES}{self.emp.id}/compa-ratio/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'sur_bande')

    def test_sans_salaires_voir_403(self):
        resp = auth(self.sans).get(f'{EMPLOYES}{self.emp.id}/compa-ratio/')
        self.assertEqual(resp.status_code, 403)
        resp = auth(self.sans).get(GRILLES)
        self.assertEqual(resp.status_code, 403)

    def test_grille_jamais_dans_pdf_ni_sortie_client(self):
        """XRH16 — vérifie que le champ salarial n'apparaît pas dans le
        sérialiseur employé standard (jamais de fuite hors du guichet dédié)."""
        resp = auth(self.rh).get(f'{EMPLOYES}{self.emp.id}/')
        self.assertNotIn('salaire_min', resp.data)
        self.assertNotIn('salaire_max', resp.data)

    def test_isolation_societe(self):
        co_b = make_company('grille-b', 'B')
        rh_b = make_user(co_b, 'grille-rh-b', ['salaires_voir'])
        resp = auth(rh_b).get(f'{EMPLOYES}{self.emp.id}/compa-ratio/')
        self.assertEqual(resp.status_code, 404)
