"""Tests FG200 — Cockpit RH (effectifs & coûts).

Couvre :
* Agrégation : effectif total (hors sortis), répartitions par statut/contrat/
  département, pyramide d'ancienneté, turnover 12 mois, alertes.
* Masse salariale GATED : omise pour un responsable sans ``salaires_voir``.
* Isolation multi-société + permission (rôle normal 403).
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh.models import Departement, DossierEmploye

User = get_user_model()

URL = '/api/django/rh/cockpit/'


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


class CockpitRhTests(TestCase):
    def setUp(self):
        self.co_a = make_company('ck-a', 'A')
        self.co_b = make_company('ck-b', 'B')
        self.user_a = make_user(self.co_a, 'ck-user-a')
        self.user_b = make_user(self.co_b, 'ck-user-b')
        self.today = timezone.localdate()
        self.dep = Departement.objects.create(company=self.co_a, nom='Atelier')

    def _emp(self, matricule, **extra):
        return DossierEmploye.objects.create(
            company=self.co_a, matricule=matricule, nom='N', prenom='P',
            **extra)

    def test_effectif_et_repartitions(self):
        self._emp('E1', statut=DossierEmploye.Statut.ACTIF,
                  type_contrat=DossierEmploye.TypeContrat.CDI,
                  departement=self.dep,
                  date_embauche=self.today - timedelta(days=200))
        self._emp('E2', statut=DossierEmploye.Statut.ACTIF,
                  type_contrat=DossierEmploye.TypeContrat.CDD,
                  date_embauche=self.today - timedelta(days=4000))
        # Un sorti ne compte pas dans l'effectif.
        self._emp('E3', statut=DossierEmploye.Statut.SORTI,
                  date_sortie=self.today - timedelta(days=10))
        resp = auth(self.user_a).get(URL)
        self.assertEqual(resp.status_code, 200, resp.data)
        data = resp.data
        self.assertEqual(data['effectif_total'], 2)
        self.assertEqual(data['par_contrat'].get('cdi'), 1)
        self.assertEqual(data['par_contrat'].get('cdd'), 1)
        self.assertEqual(data['par_statut'].get('sorti'), 1)
        # Pyramide : un <1 an, un 10+.
        self.assertEqual(data['pyramide_anciennete']['<1'], 1)
        self.assertEqual(data['pyramide_anciennete']['10+'], 1)
        # Département : Atelier effectif 1.
        ateliers = [d for d in data['par_departement']
                    if d['nom'] == 'Atelier']
        self.assertEqual(ateliers[0]['effectif'], 1)

    def test_turnover_et_alertes(self):
        # CDD échéant dans 10 jours → alerte.
        self._emp('E1', type_contrat=DossierEmploye.TypeContrat.CDD,
                  contrat_date_fin=self.today + timedelta(days=10))
        # Une sortie récente → turnover sorties.
        self._emp('E2', statut=DossierEmploye.Statut.SORTI,
                  date_sortie=self.today - timedelta(days=30))
        resp = auth(self.user_a).get(URL)
        self.assertEqual(resp.data['alertes']['cdd_a_echeance'], 1)
        self.assertEqual(resp.data['turnover']['sorties_12m'], 1)

    def test_masse_salariale_gated_omise(self):
        self._emp('E1')
        resp = auth(self.user_a).get(URL)
        # Un responsable sans ``salaires_voir`` ne reçoit pas la masse.
        self.assertNotIn('masse_salariale_mensuelle', resp.data)

    def test_isolation(self):
        self._emp('E1')
        resp = auth(self.user_b).get(URL)
        self.assertEqual(resp.data['effectif_total'], 0)

    def test_role_normal_refuse(self):
        normal = make_user(self.co_a, 'ck-normal', role='normal')
        self.assertEqual(auth(normal).get(URL).status_code, 403)
