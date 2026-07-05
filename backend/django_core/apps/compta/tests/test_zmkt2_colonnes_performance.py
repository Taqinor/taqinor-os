"""ZMKT2 — Colonnes de performance + Group By + favoris sur la liste des
campagnes.

Couvre : la liste affiche les %-colonnes triables, le regroupement par
statut/canal fonctionne, tests serializer (taux corrects, division par
zéro = 0).
"""
from django.test import TestCase

from authentication.models import Company

from apps.compta.models import Campagne, EnvoiCampagne
from apps.compta.serializers import CampagneSerializer


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class ColonnesPerformanceTests(TestCase):
    def setUp(self):
        self.co = make_company('zmkt2', 'ZMKT2')

    def test_taux_ouverture_correct(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.EMAIL,
            nb_envois=10, nb_ouvertures=3)
        data = CampagneSerializer(camp).data
        self.assertEqual(data['taux_ouverture_pct'], 30.0)

    def test_taux_clic_correct(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C2', canal=Campagne.Canal.EMAIL,
            nb_envois=20, nb_clics=5)
        data = CampagneSerializer(camp).data
        self.assertEqual(data['taux_clic_pct'], 25.0)

    def test_division_par_zero_donne_zero(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C3', canal=Campagne.Canal.EMAIL)
        data = CampagneSerializer(camp).data
        self.assertEqual(data['taux_ouverture_pct'], 0.0)
        self.assertEqual(data['taux_clic_pct'], 0.0)
        self.assertEqual(data['taux_delivre_pct'], 0.0)
        self.assertEqual(data['taux_desinscription_pct'], 0.0)

    def test_taux_desinscription_correct(self):
        camp = Campagne.objects.create(
            company=self.co, nom='C4', canal=Campagne.Canal.EMAIL,
            nb_envois=4)
        EnvoiCampagne.objects.create(
            company=self.co, campagne=camp, destinataire='a@x.ma',
            statut=EnvoiCampagne.Statut.DESINSCRIT)
        data = CampagneSerializer(camp).data
        self.assertEqual(data['taux_desinscription_pct'], 25.0)

    def test_groupby_statut_endpoint(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken

        User = get_user_model()
        Campagne.objects.create(
            company=self.co, nom='B1', canal=Campagne.Canal.EMAIL,
            statut=Campagne.Statut.BROUILLON)
        Campagne.objects.create(
            company=self.co, nom='E1', canal=Campagne.Canal.EMAIL,
            statut=Campagne.Statut.ENVOYEE)
        user = User.objects.create_user(
            username='zmkt2-user', password='x', company=self.co,
            role_legacy='responsable')
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        resp = api.get('/api/django/compta/campagnes/?groupby=statut')
        self.assertEqual(resp.status_code, 200, resp.content)
        statuts = [c['statut'] for c in resp.json()['results']]
        self.assertEqual(statuts, sorted(statuts))
