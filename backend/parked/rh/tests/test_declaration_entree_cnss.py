"""Tests XRH5 — déclaration d'entrée CNSS/AMO (suivi de conformité).

Couvre :
* un embauché non déclaré (statut ``a_faire``) apparaît dans
  ``employes/a-declarer/`` et dans la famille ``declaration_entree`` du
  sélecteur unifié ``echeances_rh`` (FG175) ;
* marquer déclaré (``employes/{id}/marquer-declare``) pose la date CÔTÉ
  SERVEUR et retire l'employé des deux ;
* ``non_requis``/``declaree`` n'apparaissent jamais ;
* XRH4 : la checklist d'intégration porte toujours l'item bloquant
  « Déclaration d'entrée CNSS/AMO » ;
* isolation multi-société.
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.rh import selectors, services
from apps.rh.models import DossierEmploye

User = get_user_model()

EMPLOYES = '/api/django/rh/employes/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ADeclarerEndpointTests(TestCase):
    def setUp(self):
        self.co_a = make_company('decl-a', 'A')
        self.co_b = make_company('decl-b', 'B')
        self.user_a = make_user(self.co_a, 'decl-a')
        self.user_b = make_user(self.co_b, 'decl-b')

    def test_a_faire_apparait_dans_a_declarer(self):
        emp = DossierEmploye.objects.create(
            company=self.co_a, matricule='E1', nom='X', prenom='Y',
            date_embauche=date(2026, 6, 1))
        resp = auth(self.user_a).get(f'{EMPLOYES}a-declarer/')
        self.assertEqual(resp.status_code, 200, resp.data)
        ids = [row['id'] for row in resp.data.get(
            'results', resp.data)]
        self.assertIn(emp.id, ids)

    def test_declaree_absente_de_a_declarer(self):
        DossierEmploye.objects.create(
            company=self.co_a, matricule='E2', nom='X', prenom='Y',
            declaration_entree_statut=(
                DossierEmploye.DeclarationEntreeStatut.DECLAREE),
            declaration_entree_date=date(2026, 6, 1))
        resp = auth(self.user_a).get(f'{EMPLOYES}a-declarer/')
        rows = resp.data.get('results', resp.data)
        self.assertEqual(rows, [])

    def test_non_requis_absent_de_a_declarer(self):
        DossierEmploye.objects.create(
            company=self.co_a, matricule='E3', nom='X', prenom='Y',
            declaration_entree_statut=(
                DossierEmploye.DeclarationEntreeStatut.NON_REQUIS))
        resp = auth(self.user_a).get(f'{EMPLOYES}a-declarer/')
        rows = resp.data.get('results', resp.data)
        self.assertEqual(rows, [])

    def test_marquer_declare_pose_date_cote_serveur_et_retire(self):
        emp = DossierEmploye.objects.create(
            company=self.co_a, matricule='E4', nom='X', prenom='Y',
            date_embauche=date(2026, 6, 1))
        resp = auth(self.user_a).post(
            f'{EMPLOYES}{emp.id}/marquer-declare/',
            {'declaration_entree_date': '2020-01-01'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        emp.refresh_from_db()
        self.assertEqual(
            emp.declaration_entree_statut,
            DossierEmploye.DeclarationEntreeStatut.DECLAREE)
        # La date posée n'est JAMAIS celle envoyée dans le corps.
        self.assertNotEqual(emp.declaration_entree_date, date(2020, 1, 1))
        self.assertIsNotNone(emp.declaration_entree_date)
        resp2 = auth(self.user_a).get(f'{EMPLOYES}a-declarer/')
        rows = resp2.data.get('results', resp2.data)
        self.assertEqual(rows, [])

    def test_isolation_tenant_cross_company_404(self):
        emp = DossierEmploye.objects.create(
            company=self.co_a, matricule='E5', nom='X', prenom='Y')
        resp = auth(self.user_b).post(
            f'{EMPLOYES}{emp.id}/marquer-declare/')
        self.assertEqual(resp.status_code, 404)


class EcheanceDeclarationEntreeSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company('decl-eche-a', 'A')
        self.today = date(2026, 6, 15)

    def test_a_faire_toujours_dans_la_fenetre(self):
        emp = DossierEmploye.objects.create(
            company=self.co, matricule='E1', nom='X', prenom='Y',
            date_embauche=date(2026, 1, 1))
        rows = selectors.echeances_rh(self.co, within_days=30, today=self.today)
        types = {r['type'] for r in rows}
        self.assertIn('declaration_entree', types)
        row = next(r for r in rows if r['type'] == 'declaration_entree')
        self.assertEqual(row['employe_id'], emp.id)

    def test_declaree_absente_du_selecteur(self):
        DossierEmploye.objects.create(
            company=self.co, matricule='E2', nom='X', prenom='Y',
            declaration_entree_statut=(
                DossierEmploye.DeclarationEntreeStatut.DECLAREE))
        rows = selectors.echeances_rh(self.co, within_days=30, today=self.today)
        self.assertEqual(
            [r for r in rows if r['type'] == 'declaration_entree'], [])

    def test_isolation_societe(self):
        co_b = make_company('decl-eche-b', 'B')
        DossierEmploye.objects.create(
            company=co_b, matricule='B1', nom='X', prenom='Y',
            date_embauche=date(2026, 1, 1))
        rows = selectors.echeances_rh(self.co, within_days=30, today=self.today)
        self.assertEqual(
            [r for r in rows if r['type'] == 'declaration_entree'], [])


class ChecklistItemBloquantTests(TestCase):
    """XRH4 x XRH5 : l'item bloquant CNSS/AMO figure toujours."""

    def test_item_bloquant_toujours_present(self):
        co = make_company('decl-checklist-a', 'A')
        emp = DossierEmploye.objects.create(
            company=co, matricule='E1', nom='X', prenom='Y')
        lignes = services.instancier_integration(emp)
        self.assertTrue(
            any('CNSS' in ligne.libelle for ligne in lignes))
