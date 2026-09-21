"""AUD615 — la liste des appels d'offres ne coûte plus une requête par bâtiment.

``AppelOffreSerializer`` publie deux agrégats CALCULÉS —
``surface_toitures_m2`` et ``engagement_modules_batiments`` — qui itèrent
``self.batiments.all()`` puis, par bâtiment, ``batiment.toitures.all()``. Sur
``GET /appels-offres/``, sans préchargement, cela faisait deux niveaux de N+1
sur CHAQUE ligne de la liste, alors que le même fichier applique déjà un
garde-fou à ``synthese_calepinage`` pour exactement cette raison.

Le test ne fige AUCUN nombre de requêtes : il compare le coût d'une liste de 1
AO à celui d'une liste de 3 AO multi-bâtiments. Un nombre épinglé se serait
périmé au premier `select_related` ajouté ailleurs ; l'INVARIANCE, elle, est ce
qui est réellement promis.

Run :
    python manage.py test apps.ao.tests.test_aud615_liste_ao_sans_n_plus_1 -v2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ao.models import AppelOffre, BatimentAO, ToitureAO
from apps.ao.permissions import AO_VOIR
from apps.roles.models import Role
from authentication.models import Company

User = get_user_model()

URL = '/api/django/ao/appels-offres/'


class TestListeSansNPlus1(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AUD615 Co',
                                              slug='aud615-co')
        role = Role.objects.create(company=self.company, nom='AUD615 lecture',
                                   permissions=[AO_VOIR])
        self.user = User.objects.create_user(
            username='aud615', password='x', company=self.company, role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _affaire(self, suffixe, *, batiments=3, toitures=2):
        ao = AppelOffre.objects.create(
            company=self.company, reference=f'AO-615-{suffixe}',
            objet='Centrale PV')
        for index in range(batiments):
            batiment = BatimentAO.objects.create(
                company=self.company, appel_offre=ao, code=f'B{index}',
                designation=f'Bâtiment {index}', engagement_modules=100)
            for _ in range(toitures):
                ToitureAO.objects.create(
                    company=self.company, batiment=batiment, forme='rectangle',
                    surface_m2=Decimal('250.000'))
        return ao

    def _requetes_de_la_liste(self):
        with CaptureQueriesContext(connection) as capture:
            reponse = self.api.get(URL)
            self.assertEqual(reponse.status_code, 200, reponse.data)
        return len(capture.captured_queries), reponse

    def test_le_cout_ne_croit_pas_avec_le_nombre_d_affaires(self):
        self._affaire('A')
        cout_1, _ = self._requetes_de_la_liste()
        self._affaire('B')
        self._affaire('C')
        cout_3, reponse = self._requetes_de_la_liste()
        self.assertEqual(reponse.data['count'], 3)
        self.assertEqual(
            cout_3, cout_1,
            'La liste des AO coûte plus cher à 3 affaires qu\'à 1 : les '
            'agrégats de bâtiments/toitures repartent en N+1.')

    def test_les_deux_agregats_restent_JUSTES(self):
        """Le préchargement ne doit rien changer aux valeurs publiées."""
        self._affaire('D', batiments=3, toitures=2)
        _cout, reponse = self._requetes_de_la_liste()
        ligne = reponse.data['results'][0]
        # 3 bâtiments × 2 toitures × 250,000 m²
        self.assertEqual(Decimal(str(ligne['surface_toitures_m2'])),
                         Decimal('1500.000'))
        # 3 bâtiments × 100 modules engagés
        self.assertEqual(ligne['engagement_modules_batiments'], 300)

    def test_le_prefetch_est_declare_sur_le_queryset(self):
        """Garde de non-régression : le préchargement est le correctif."""
        from apps.ao.views import AppelOffreViewSet

        recherches = {
            getattr(lookup, 'prefetch_through', lookup)
            for lookup in AppelOffreViewSet.queryset._prefetch_related_lookups
        }
        self.assertIn('batiments__toitures', recherches)
