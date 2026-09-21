"""Tests NTHCM4 — postes budgétés vs pourvus (headcount planning).

Couvre :
* comptage des employés ACTIFS d'un poste (les sortis ne comptent pas) ;
* ``effectif_budgete=3`` avec 4 actifs ⇒ ``depassement=True`` ;
* ``effectif_budgete=0`` (valeur historique) ⇒ NEUTRE, jamais de dépassement ;
* comptage des ouvertures de poste ACTIVES ;
* endpoints ``postes/{id}/effectif/`` et ``postes/effectifs/`` ;
* isolation société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import selectors
from apps.rh.models import DossierEmploye, OuverturePoste, Poste

User = get_user_model()


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


class EffectifPosteTests(TestCase):
    def setUp(self):
        self.co = make_company('nthcm4-a', 'A')
        self.poste = Poste.objects.create(
            company=self.co, intitule='Technicien pose', effectif_budgete=3)

    def _employes(self, n, statut=DossierEmploye.Statut.ACTIF, prefix='E'):
        for i in range(n):
            DossierEmploye.objects.create(
                company=self.co, matricule=f'{prefix}-{i}',
                nom=f'Nom{i}', prenom='P', poste_ref=self.poste,
                statut=statut)

    def test_depassement_quand_pourvus_depasse_budgete(self):
        self._employes(4)
        res = selectors.effectif_poste(self.co, self.poste.id)
        self.assertEqual(res['budgete'], 3)
        self.assertEqual(res['pourvus'], 4)
        self.assertTrue(res['depassement'])

    def test_pas_de_depassement_a_l_effectif_exact(self):
        self._employes(3)
        res = selectors.effectif_poste(self.co, self.poste.id)
        self.assertEqual(res['pourvus'], 3)
        self.assertFalse(res['depassement'])

    def test_employes_sortis_ne_comptent_pas(self):
        self._employes(2)
        self._employes(3, statut=DossierEmploye.Statut.SORTI, prefix='S')
        res = selectors.effectif_poste(self.co, self.poste.id)
        self.assertEqual(res['pourvus'], 2)
        self.assertFalse(res['depassement'])

    def test_poste_sans_budget_reste_neutre(self):
        libre = Poste.objects.create(
            company=self.co, intitule='Sans budget', effectif_budgete=0)
        for i in range(9):
            DossierEmploye.objects.create(
                company=self.co, matricule=f'L-{i}', nom='X', prenom='Y',
                poste_ref=libre)
        res = selectors.effectif_poste(self.co, libre.id)
        self.assertEqual(res['budgete'], 0)
        self.assertEqual(res['pourvus'], 9)
        self.assertFalse(res['depassement'])

    def test_ouvertures_actives_comptees(self):
        OuverturePoste.objects.create(
            company=self.co, intitule='Technicien pose', poste_ref=self.poste,
            statut=OuverturePoste.Statut.OUVERT)
        OuverturePoste.objects.create(
            company=self.co, intitule='Technicien pose (2)',
            poste_ref=self.poste, statut=OuverturePoste.Statut.CLOS)
        res = selectors.effectif_poste(self.co, self.poste.id)
        self.assertEqual(res['ouverts'], 1)

    def test_isolation_societe_selector(self):
        co_b = make_company('nthcm4-b', 'B')
        self.assertIsNone(selectors.effectif_poste(co_b, self.poste.id))


class EffectifPosteApiTests(TestCase):
    def setUp(self):
        self.co = make_company('nthcm4-api', 'API')
        self.rh = make_user(self.co, 'nthcm4-rh')
        self.api = auth(self.rh)
        self.poste = Poste.objects.create(
            company=self.co, intitule='Chef de chantier', effectif_budgete=1)
        for i in range(2):
            DossierEmploye.objects.create(
                company=self.co, matricule=f'C-{i}', nom='N', prenom='P',
                poste_ref=self.poste)

    def test_endpoint_effectif_detail(self):
        resp = self.api.get(
            f'/api/django/rh/postes/{self.poste.id}/effectif/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['budgete'], 1)
        self.assertEqual(resp.data['pourvus'], 2)
        self.assertTrue(resp.data['depassement'])

    def test_endpoint_effectifs_liste(self):
        resp = self.api.get('/api/django/rh/postes/effectifs/')
        self.assertEqual(resp.status_code, 200, resp.data)
        lignes = {ligne['poste_id']: ligne for ligne in resp.data}
        self.assertIn(self.poste.id, lignes)
        self.assertTrue(lignes[self.poste.id]['depassement'])

    def test_effectif_budgete_expose_et_modifiable(self):
        resp = self.api.patch(
            f'/api/django/rh/postes/{self.poste.id}/',
            {'effectif_budgete': 5}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.poste.refresh_from_db()
        self.assertEqual(self.poste.effectif_budgete, 5)

    def test_isolation_societe_api(self):
        co_b = make_company('nthcm4-api-b', 'B')
        rh_b = make_user(co_b, 'nthcm4-rh-b')
        resp = auth(rh_b).get(
            f'/api/django/rh/postes/{self.poste.id}/effectif/')
        self.assertEqual(resp.status_code, 404)
        resp_liste = auth(rh_b).get('/api/django/rh/postes/effectifs/')
        self.assertEqual(resp_liste.status_code, 200, resp_liste.data)
        self.assertEqual(list(resp_liste.data), [])
