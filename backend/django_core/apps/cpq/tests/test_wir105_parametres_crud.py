"""WIR105 — CRUD REST des seuils de marge (NTCPQ6) et paliers d'approbation
de remise (NTCPQ7/8), sans passer par le Django admin.

Couvre :
* un responsable crée un seuil de marge par famille (company posée serveur) ;
* un responsable crée un palier d'approbation de remise, et ce palier est bien
  résolu par ``services.resoudre_regle_remise`` (déclenche NTCPQ7/8) ;
* validation des bornes (max ≥ min) ;
* isolation société en lecture ;
* écriture refusée à un rôle normal.
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.cpq import services
from apps.cpq.models import RegleApprobationRemise, SeuilMargeFamille
from apps.stock.models import Categorie
from authentication.models import CustomUser
from testkit.factories import CompanyFactory, UserFactory

SEUILS = '/api/django/cpq/seuils-marge/'
REGLES = '/api/django/cpq/regles-approbation-remise/'


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestParametresCpqCrud(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.admin = UserFactory(
            company=self.company, role_legacy=CustomUser.ROLE_RESPONSABLE)
        self.normal = UserFactory(
            company=self.company, role_legacy=CustomUser.ROLE_NORMAL)
        self.categorie = Categorie.objects.create(
            company=self.company, nom='Onduleurs')

    def test_creer_seuil_marge(self):
        resp = auth(self.admin).post(SEUILS, {
            'categorie': self.categorie.id,
            'marge_min_pct': '15.00',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        seuil = SeuilMargeFamille.objects.get(id=resp.data['id'])
        self.assertEqual(seuil.company_id, self.company.id)
        self.assertEqual(seuil.marge_min_pct, Decimal('15.00'))

    def test_creer_palier_declenche_resolution(self):
        resp = auth(self.admin).post(REGLES, {
            'libelle': 'Remise profonde',
            'remise_min_pct': '20.00',
            'remise_max_pct': '100.00',
            'niveau_approbation': 'administrateur',
            'nombre_approbateurs': 2,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        regle = RegleApprobationRemise.objects.get(id=resp.data['id'])
        self.assertEqual(regle.company_id, self.company.id)
        # NTCPQ7 — le palier créé via l'API est bien résolu pour une remise de 25 %.
        resolue = services.resoudre_regle_remise(
            company=self.company, remise=Decimal('25'))
        self.assertEqual(resolue, regle)

    def test_bornes_incoherentes_refusees(self):
        resp = auth(self.admin).post(REGLES, {
            'remise_min_pct': '50.00',
            'remise_max_pct': '10.00',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_lecture_scope_societe(self):
        other = CompanyFactory()
        SeuilMargeFamille.objects.create(
            company=other,
            categorie=Categorie.objects.create(company=other, nom='X'),
            marge_min_pct=Decimal('10'))
        resp = auth(self.admin).get(SEUILS)
        self.assertEqual(resp.status_code, 200, resp.data)
        results = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        self.assertEqual(len(results), 0)

    def test_role_normal_ne_peut_pas_ecrire(self):
        resp = auth(self.normal).post(REGLES, {
            'remise_min_pct': '5.00', 'remise_max_pct': '10.00',
        }, format='json')
        self.assertEqual(resp.status_code, 403, resp.data)
