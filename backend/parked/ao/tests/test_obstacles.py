"""AOF22 — ``ObstacleAO`` : provenance de premier rang, dégagement dérivé.

Constat mesuré qui justifie tout ce modèle : deux emprises venues du PLAN et
jamais relevées coûtaient 12 modules sur la seule aile en L, et quatre
« souches » avaient été purement INVENTÉES faute de photo lisible.

Invariants verrouillés :
  1. le dégagement = max(défaut de la NATURE, défaut de la PROVENANCE), et la
     règle appliquée est ÉCRITE dans la donnée (pas dans un commentaire) ;
  2. il est recalculé à TOUT changement de provenance, SAUF surcharge — et une
     surcharge sans motif est refusée ;
  3. ``engageable`` dépend de la provenance : seul ce qui a été RELEVÉ engage ;
  4. un obstacle mesuré n'est JAMAIS supprimé — il passe ``ECARTE`` en
     CONSERVANT sa géométrie, et ``?provenance=ECARTE`` le retrouve.

Run :
    python manage.py test apps.ao.tests.test_obstacles -v2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ao import services
from apps.ao.models import AppelOffre, BatimentAO, ObstacleAO, ToitureAO
from apps.roles.models import DIRECTEUR_PERMISSIONS, Role
from authentication.models import Company

User = get_user_model()

URL = '/api/django/ao/obstacles/'
P = ObstacleAO.Provenance
N = ObstacleAO.Nature


class TestCatalogueObstacle(SimpleTestCase):
    def test_treize_natures(self):
        self.assertEqual(len(N.choices), 13)

    def test_six_provenances(self):
        valeurs = {v for v, _ in P.choices}
        self.assertEqual(valeurs, {
            'MESURE', 'MESURE_DOUTEUX', 'PLAN', 'DEVINE', 'DECLARE_CLIENT',
            'ECARTE'})

    def test_bareme_de_degagement_par_provenance(self):
        table = ObstacleAO.DEGAGEMENT_PAR_PROVENANCE
        self.assertEqual(table[P.MESURE], Decimal('0.30'))
        self.assertEqual(table[P.MESURE_DOUTEUX], Decimal('0.50'))
        self.assertEqual(table[P.PLAN], Decimal('0.50'))
        self.assertEqual(table[P.DEVINE], Decimal('0.50'))
        self.assertEqual(table[P.DECLARE_CLIENT], Decimal('0.30'))

    def test_seules_les_provenances_relevees_engagent(self):
        self.assertEqual(
            set(ObstacleAO.PROVENANCES_ENGAGEABLES),
            {P.MESURE, P.MESURE_DOUTEUX})


class TestReglesDeDegagement(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF22 Co', slug='aof22-co')
        ao = AppelOffre.objects.create(
            company=self.company, reference='AO-22-1', objet='Obstacles')
        batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=ao, code='C')
        self.toiture = ToitureAO.objects.create(
            company=self.company, batiment=batiment)

    def _obstacle(self, **kwargs):
        kwargs.setdefault('nature', N.MURET)
        kwargs.setdefault('provenance', P.MESURE)
        obstacle = ObstacleAO(
            company=self.company, toiture=self.toiture, **kwargs)
        obstacle.appliquer_degagement()
        obstacle.save()
        return obstacle

    def test_provenance_gagne_quand_elle_est_plus_exigeante(self):
        obstacle = self._obstacle(nature=N.MURET, provenance=P.PLAN)
        self.assertEqual(obstacle.degagement_m, Decimal('0.50'))
        self.assertIn('provenance', obstacle.regle_degagement)

    def test_nature_gagne_quand_elle_est_plus_exigeante(self):
        obstacle = self._obstacle(
            nature=N.EXUTOIRE_FUMEE, provenance=P.MESURE)
        self.assertEqual(obstacle.degagement_m, Decimal('1.00'))
        self.assertIn('nature', obstacle.regle_degagement)

    def test_la_regle_appliquee_est_ecrite_dans_la_donnee(self):
        obstacle = self._obstacle(nature=N.EDICULE, provenance=P.DEVINE)
        self.assertEqual(obstacle.degagement_m, Decimal('0.60'))
        self.assertIn('Édicule', obstacle.regle_degagement)
        self.assertIn('Deviné', obstacle.regle_degagement)

    def test_recalcul_a_tout_changement_de_provenance(self):
        obstacle = self._obstacle(nature=N.MURET, provenance=P.MESURE)
        self.assertEqual(obstacle.degagement_m, Decimal('0.30'))
        services.requalifier_provenance(obstacle, P.DEVINE)
        obstacle.refresh_from_db()
        self.assertEqual(obstacle.degagement_m, Decimal('0.50'))

    def test_surcharge_motivee_fige_la_valeur(self):
        obstacle = self._obstacle(nature=N.MURET, provenance=P.MESURE)
        obstacle.degagement_surcharge = True
        obstacle.motif_surcharge = 'Accès pompiers imposé par le site'
        obstacle.degagement_m = Decimal('1.50')
        obstacle.appliquer_degagement()
        self.assertEqual(obstacle.degagement_m, Decimal('1.50'))
        self.assertIn('surcharge', obstacle.regle_degagement)
        self.assertIn('pompiers', obstacle.regle_degagement)

    def test_surcharge_sans_motif_refusee(self):
        obstacle = self._obstacle()
        obstacle.degagement_surcharge = True
        with self.assertRaises(ValidationError) as ctx:
            obstacle.clean()
        self.assertIn('motif_surcharge', ctx.exception.message_dict)


class TestEngageable(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF22 En', slug='aof22-en')
        ao = AppelOffre.objects.create(
            company=self.company, reference='AO-22-E', objet='Engageable')
        batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=ao, code='A')
        self.toiture = ToitureAO.objects.create(
            company=self.company, batiment=batiment)

    def _obstacle(self, provenance, actif=True):
        return ObstacleAO.objects.create(
            company=self.company, toiture=self.toiture, nature=N.SOUCHE,
            provenance=provenance, actif=actif)

    def test_par_provenance(self):
        attendu = {
            P.MESURE: True, P.MESURE_DOUTEUX: True, P.PLAN: False,
            P.DEVINE: False, P.DECLARE_CLIENT: False, P.ECARTE: False,
        }
        for provenance, engageable in attendu.items():
            obstacle = self._obstacle(provenance)
            self.assertEqual(obstacle.engageable, engageable, provenance)

    def test_un_obstacle_inactif_n_engage_rien(self):
        obstacle = self._obstacle(P.MESURE, actif=False)
        self.assertFalse(obstacle.engageable)


class TestEcartementSansSuppression(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF22 Ec', slug='aof22-ec')
        ao = AppelOffre.objects.create(
            company=self.company, reference='AO-22-EC', objet='Écart')
        batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=ao, code='B')
        self.toiture = ToitureAO.objects.create(
            company=self.company, batiment=batiment)
        self.obstacle = ObstacleAO.objects.create(
            company=self.company, toiture=self.toiture, repere='D',
            nature=N.SOUCHE, provenance=P.DEVINE,
            rect_x0_m=Decimal('2.000'), rect_x1_m=Decimal('3.000'),
            rect_y0_m=Decimal('1.000'), rect_y1_m=Decimal('2.000'))

    def test_ecarter_conserve_la_geometrie(self):
        services.ecarter_obstacle(
            self.obstacle, motif='Souche inventée — aucune photo la montrant')
        self.obstacle.refresh_from_db()
        self.assertEqual(self.obstacle.provenance, P.ECARTE)
        self.assertFalse(self.obstacle.actif)
        self.assertEqual(self.obstacle.rect_x0_m, Decimal('2.000'))
        self.assertEqual(self.obstacle.rect_y1_m, Decimal('2.000'))
        self.assertIn('inventée', self.obstacle.decision)

    def test_retour_arriere_est_un_one_liner(self):
        services.ecarter_obstacle(self.obstacle, motif='Écarté')
        services.reintegrer_obstacle(self.obstacle, P.MESURE)
        self.obstacle.refresh_from_db()
        self.assertEqual(self.obstacle.provenance, P.MESURE)
        self.assertTrue(self.obstacle.actif)
        self.assertEqual(self.obstacle.degagement_m, Decimal('0.50'))

    def test_ecarte_reste_interrogeable(self):
        services.ecarter_obstacle(self.obstacle, motif='Écarté')
        ecartes = ObstacleAO.objects.filter(
            company=self.company, provenance=P.ECARTE)
        self.assertEqual([o.pk for o in ecartes], [self.obstacle.pk])

    def test_ecartement_journalise_au_chatter_du_dossier(self):
        from apps.records.services import chatter_qs

        appel_offre = self.toiture.batiment.appel_offre
        services.ecarter_obstacle(self.obstacle, motif='Écarté')
        entrees = list(chatter_qs(appel_offre, company=self.company))
        self.assertEqual(len(entrees), 1)
        self.assertEqual(entrees[0].field, 'provenance')


class TestApiObstacles(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF22 API', slug='aof22-api')
        role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='aof22_dir', password='x', company=self.company,
            role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-22-API', objet='API')
        batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=self.ao, code='A')
        self.toiture = ToitureAO.objects.create(
            company=self.company, batiment=batiment)

    def _lignes(self, resp):
        data = resp.data
        return data['results'] if isinstance(data, dict) and 'results' in data \
            else data

    def test_creation_applique_la_regle(self):
        r = self.api.post(URL, {
            'toiture': self.toiture.id, 'repere': 'A', 'nature': 'edicule',
            'provenance': 'PLAN',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        obstacle = ObstacleAO.objects.get(id=r.data['id'])
        self.assertEqual(obstacle.degagement_m, Decimal('0.60'))
        self.assertTrue(obstacle.regle_degagement)
        self.assertFalse(r.data['engageable'])

    def test_surcharge_sans_motif_refusee_par_l_api(self):
        r = self.api.post(URL, {
            'toiture': self.toiture.id, 'nature': 'muret',
            'degagement_surcharge': True, 'degagement_m': '1.50',
        }, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('motif_surcharge', r.data)

    def test_action_ecarter_puis_filtre_ecarte(self):
        obstacle = ObstacleAO.objects.create(
            company=self.company, toiture=self.toiture, repere='D',
            nature=N.SOUCHE, provenance=P.DEVINE,
            rect_x0_m=Decimal('2.000'), rect_x1_m=Decimal('3.000'))
        r = self.api.post(f'{URL}{obstacle.id}/ecarter/',
                          {'motif': 'Souche inventée'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        r2 = self.api.get(URL, {'provenance': 'ECARTE'})
        self.assertEqual(r2.status_code, 200, r2.data)
        lignes = self._lignes(r2)
        self.assertEqual(len(lignes), 1)
        # La GÉOMÉTRIE est bien renvoyée avec l'écarté (sinon la marche de
        # l'échelle de décomposition serait irreproductible).
        self.assertEqual(lignes[0]['rect_x0_m'], '2.000')
        self.assertTrue(lignes[0]['est_ecarte'])

    def test_ecarter_sans_motif_refuse(self):
        obstacle = ObstacleAO.objects.create(
            company=self.company, toiture=self.toiture, nature=N.SOUCHE)
        r = self.api.post(f'{URL}{obstacle.id}/ecarter/', {}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('motif', r.data)

    def test_filtre_par_appel_offre(self):
        ObstacleAO.objects.create(
            company=self.company, toiture=self.toiture, nature=N.MURET)
        r = self.api.get(URL, {'appel_offre': self.ao.id})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(len(self._lignes(r)), 1)

    def test_isolation_multi_societe(self):
        autre = Company.objects.create(nom='AOF22 X', slug='aof22-x')
        ao = AppelOffre.objects.create(
            company=autre, reference='AO-22-X', objet='X')
        batiment = BatimentAO.objects.create(
            company=autre, appel_offre=ao, code='X')
        toiture = ToitureAO.objects.create(company=autre, batiment=batiment)
        ObstacleAO.objects.create(
            company=autre, toiture=toiture, nature=N.MURET)
        r = self.api.get(URL)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(self._lignes(r), [])
