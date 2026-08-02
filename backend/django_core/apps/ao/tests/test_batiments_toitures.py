"""AOF18 — ``BatimentAO`` + ``ToitureAO`` : la géométrie du projet.

Quatre promesses verrouillées ici :
  1. un polygone qui SE CROISE est refusé (sinon les rangées de modules
     sortiraient du bâtiment) ;
  2. un arc SANS rayon ni largeur est refusé (il n'est pas développable) ;
  3. les agrégats du projet sont CALCULÉS (somme des toitures), jamais
     recopiés dans une colonne qui deviendrait fausse au premier ajout ;
  4. la surface d'une toiture est recalculée depuis le contour à chaque
     écriture — jamais saisie.

Run :
    python manage.py test apps.ao.tests.test_batiments_toitures -v2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ao.models import (
    AppelOffre, BatimentAO, ToitureAO, aire_polygone_m2, polygone_est_simple,
)
from apps.roles.models import DIRECTEUR_PERMISSIONS, Role
from authentication.models import Company

User = get_user_model()

URL_TOITURES = '/api/django/ao/toitures/'
URL_BATIMENTS = '/api/django/ao/batiments/'

CARRE_10 = [[0, 0], [10, 0], [10, 10], [0, 10]]
NOEUD_PAPILLON = [[0, 0], [10, 10], [10, 0], [0, 10]]


class TestGeometriePure(SimpleTestCase):
    def test_carre_est_simple(self):
        self.assertTrue(polygone_est_simple(CARRE_10))

    def test_contour_ferme_explicitement_reste_simple(self):
        self.assertTrue(polygone_est_simple(CARRE_10 + [[0, 0]]))

    def test_noeud_papillon_refuse(self):
        self.assertFalse(polygone_est_simple(NOEUD_PAPILLON))

    def test_moins_de_trois_sommets_refuse(self):
        self.assertFalse(polygone_est_simple([[0, 0], [1, 1]]))
        self.assertFalse(polygone_est_simple([]))

    def test_sommets_dupliques_refuses(self):
        self.assertFalse(polygone_est_simple([[0, 0], [5, 0], [0, 0], [5, 5]]))

    def test_aire_du_carre(self):
        self.assertAlmostEqual(aire_polygone_m2(CARRE_10), 100.0)

    def test_aire_d_une_forme_en_l(self):
        forme_l = [[0, 0], [10, 0], [10, 4], [4, 4], [4, 10], [0, 10]]
        self.assertAlmostEqual(aire_polygone_m2(forme_l), 64.0)

    def test_aire_nulle_sans_contour(self):
        self.assertEqual(aire_polygone_m2([]), 0.0)


class TestValidationToiture(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF18 Co', slug='aof18-co')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-18-1', objet='Géométrie')
        self.batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=self.ao, code='A',
            designation='Bâtiment A')

    def _toiture(self, **kwargs):
        return ToitureAO(
            company=self.company, batiment=self.batiment, **kwargs)

    def test_polygone_simple_accepte(self):
        self._toiture(forme=ToitureAO.Forme.POLYGONE,
                      contour_local_m=CARRE_10).clean()

    def test_polygone_qui_se_croise_refuse(self):
        with self.assertRaises(ValidationError) as ctx:
            self._toiture(forme=ToitureAO.Forme.POLYGONE,
                          contour_local_m=NOEUD_PAPILLON).clean()
        self.assertIn('contour_local_m', ctx.exception.message_dict)

    def test_arc_sans_rayon_ni_largeur_refuse(self):
        with self.assertRaises(ValidationError) as ctx:
            self._toiture(forme=ToitureAO.Forme.ARC).clean()
        self.assertIn('rayon_ext_m', ctx.exception.message_dict)

    def test_arc_avec_rayon_seul_refuse(self):
        with self.assertRaises(ValidationError):
            self._toiture(forme=ToitureAO.Forme.ARC,
                          rayon_ext_m=Decimal('42.000')).clean()

    def test_arc_complet_accepte(self):
        self._toiture(forme=ToitureAO.Forme.ARC,
                      rayon_ext_m=Decimal('42.000'),
                      largeur_m=Decimal('12.500')).clean()

    def test_recalcul_de_surface(self):
        toiture = self._toiture(forme=ToitureAO.Forme.RECTANGLE,
                                contour_local_m=CARRE_10)
        toiture.recalculer_surface()
        self.assertEqual(toiture.surface_m2, Decimal('100.000'))


class TestAgregationProjet(TestCase):
    """Les agrégats sont CALCULÉS — jamais recopiés."""

    def setUp(self):
        self.company = Company.objects.create(nom='AOF18 Ag', slug='aof18-ag')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-18-AG', objet='Agrégats')
        self.a = BatimentAO.objects.create(
            company=self.company, appel_offre=self.ao, code='A',
            engagement_modules=178)
        self.b = BatimentAO.objects.create(
            company=self.company, appel_offre=self.ao, code='B',
            engagement_modules=126)

    def _toiture(self, batiment, contour):
        toiture = ToitureAO(
            company=self.company, batiment=batiment,
            forme=ToitureAO.Forme.POLYGONE, contour_local_m=contour)
        toiture.recalculer_surface()
        toiture.save()
        return toiture

    def test_somme_des_surfaces(self):
        self._toiture(self.a, CARRE_10)
        self._toiture(self.b, [[0, 0], [20, 0], [20, 10], [0, 10]])
        self.assertEqual(self.a.surface_toitures_m2, Decimal('100.000'))
        self.assertEqual(self.ao.surface_toitures_m2, Decimal('300.000'))

    def test_l_agregat_suit_un_ajout(self):
        self._toiture(self.a, CARRE_10)
        avant = self.ao.surface_toitures_m2
        self._toiture(self.a, CARRE_10)
        self.assertEqual(self.ao.surface_toitures_m2, avant * 2)

    def test_somme_des_engagements_batiments(self):
        self.assertEqual(self.ao.engagement_modules_batiments, 304)

    def test_engagement_global_reste_distinct_de_la_somme(self):
        """L'écart entre l'annonce et la somme signale un bâtiment oublié."""
        self.ao.engagement_modules = 314
        self.ao.save(update_fields=['engagement_modules'])
        self.assertNotEqual(self.ao.engagement_modules,
                            self.ao.engagement_modules_batiments)


class TestApiToitures(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF18 API', slug='aof18-api')
        role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='aof18_dir', password='x', company=self.company,
            role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-18-API', objet='API')
        self.batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=self.ao, code='C')

    def test_creation_calcule_la_surface(self):
        r = self.api.post(URL_TOITURES, {
            'batiment': self.batiment.id, 'code_document': '05H',
            'forme': 'polygone', 'contour_local_m': CARRE_10,
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        toiture = ToitureAO.objects.get(id=r.data['id'])
        self.assertEqual(toiture.surface_m2, Decimal('100.000'))
        self.assertEqual(toiture.company_id, self.company.id)

    def test_api_refuse_un_polygone_qui_se_croise(self):
        r = self.api.post(URL_TOITURES, {
            'batiment': self.batiment.id, 'forme': 'polygone',
            'contour_local_m': NOEUD_PAPILLON,
        }, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('contour_local_m', r.data)

    def test_api_refuse_un_arc_incomplet(self):
        r = self.api.post(URL_TOITURES, {
            'batiment': self.batiment.id, 'forme': 'arc',
        }, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('rayon_ext_m', r.data)

    def test_modification_recalcule_la_surface(self):
        r = self.api.post(URL_TOITURES, {
            'batiment': self.batiment.id, 'forme': 'polygone',
            'contour_local_m': CARRE_10,
        }, format='json')
        toiture_id = r.data['id']
        r2 = self.api.patch(f'{URL_TOITURES}{toiture_id}/', {
            'contour_local_m': [[0, 0], [20, 0], [20, 10], [0, 10]],
        }, format='json')
        self.assertEqual(r2.status_code, 200, r2.data)
        toiture = ToitureAO.objects.get(id=toiture_id)
        self.assertEqual(toiture.surface_m2, Decimal('200.000'))

    def test_filtre_par_appel_offre(self):
        ToitureAO.objects.create(
            company=self.company, batiment=self.batiment, forme='rectangle')
        r = self.api.get(URL_TOITURES, {'appel_offre': self.ao.id})
        self.assertEqual(r.status_code, 200, r.data)
        lignes = r.data['results'] if isinstance(r.data, dict) \
            and 'results' in r.data else r.data
        self.assertEqual(len(lignes), 1)

    def test_batiment_expose_ses_toitures_et_sa_surface(self):
        ToitureAO.objects.create(
            company=self.company, batiment=self.batiment, forme='polygone',
            contour_local_m=CARRE_10, surface_m2=Decimal('100.000'))
        r = self.api.get(f'{URL_BATIMENTS}{self.batiment.id}/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(len(r.data['toitures']), 1)
        self.assertEqual(r.data['surface_toitures_m2'], '100.000')
