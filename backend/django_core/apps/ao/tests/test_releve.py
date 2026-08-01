"""AOF24 — ``ReleveAO`` : la visite contradictoire comme OBJET.

Sans cet objet, une cote ou un obstacle ne peut pas dire D'OÙ il vient, et le
cartouche d'une planche ne peut rien opposer au maître d'ouvrage.

Le test central est le DÉFAUT que ce lot rend détectable : **une cote orange
(``A_CONFIRMER``) absente de la liste « à confirmer à l'exécution » est un
défaut**. La liste est donc DÉRIVÉE de la donnée, jamais saisie.

Run :
    python manage.py test apps.ao.tests.test_releve -v2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ao import selectors, services
from apps.ao.models import (
    AppelOffre, BatimentAO, ChaineCotes, ObstacleAO, ReleveAO, ToitureAO,
)
from apps.roles.models import DIRECTEUR_PERMISSIONS, Role
from authentication.models import Company

User = get_user_model()

SEGMENTS = [
    {'libelle': 'A→B', 'valeur_m': 19.36, 'statut': 'MESURE'},
    {'libelle': 'B→C', 'valeur_m': 7.92, 'statut': 'MESURE'},
    {'libelle': 'C→D', 'valeur_m': 4.50, 'statut': 'MESURE'},
    {'libelle': 'D→E', 'valeur_m': 10.50, 'statut': 'MESURE'},
    {'libelle': 'E→F', 'valeur_m': 8.50, 'statut': 'PLAN_OU_DEDUIT'},
]


class BaseReleve(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF24 Co', slug='aof24-co')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-24-1', objet='Relevé')
        self.batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=self.ao, code='C')
        self.toiture = ToitureAO.objects.create(
            company=self.company, batiment=self.batiment)
        self.releve = ReleveAO.objects.create(
            company=self.company, appel_offre=self.ao,
            date_visite=datetime.date(2026, 7, 27), contradictoire=True,
            participants='Maître d\'ouvrage\nEntreprise')
        self.releve.toitures.add(self.toiture)


class TestReleveObjet(BaseReleve):
    def test_mention_de_cartouche(self):
        self.assertEqual(self.releve.mention_cartouche,
                         'base : relevé contradictoire du 27/07/2026')

    def test_mention_simple_quand_non_contradictoire(self):
        simple = ReleveAO.objects.create(
            company=self.company, appel_offre=self.ao,
            date_visite=datetime.date(2026, 7, 28))
        self.assertEqual(simple.mention_cartouche,
                         'base : relevé simple du 28/07/2026')

    def test_le_dossier_prend_le_releve_le_plus_recent(self):
        ReleveAO.objects.create(
            company=self.company, appel_offre=self.ao,
            date_visite=datetime.date(2026, 7, 30), contradictoire=True)
        self.assertEqual(selectors.mention_cartouche(self.ao),
                         'base : relevé contradictoire du 30/07/2026')

    def test_aucune_mention_sans_releve(self):
        vide = AppelOffre.objects.create(
            company=self.company, reference='AO-24-V', objet='Sans relevé')
        self.assertIsNone(selectors.mention_cartouche(vide))

    def test_toitures_couvertes(self):
        self.assertEqual(list(self.releve.toitures.all()), [self.toiture])
        self.assertEqual(list(self.toiture.releves.all()), [self.releve])


class TestTracabiliteDesSaisies(BaseReleve):
    """Un obstacle ou une cote référence TOUJOURS le relevé qui l'a produit."""

    def test_obstacle_reference_son_releve(self):
        obstacle = ObstacleAO.objects.create(
            company=self.company, toiture=self.toiture, releve=self.releve,
            repere='A', nature=ObstacleAO.Nature.SOUCHE)
        self.assertEqual(obstacle.releve_id, self.releve.id)
        self.assertEqual(list(self.releve.obstacles.all()), [obstacle])

    def test_chaine_reference_son_releve(self):
        chaine = ChaineCotes.objects.create(
            company=self.company, toiture=self.toiture, releve=self.releve,
            libelle='Façade sud', segments=[dict(s) for s in SEGMENTS],
            mesure_globale_m=Decimal('51.100'))
        self.assertEqual(chaine.releve_id, self.releve.id)
        self.assertEqual(list(self.releve.chaines_cotes.all()), [chaine])

    def test_un_obstacle_sans_releve_reste_possible(self):
        """Un obstacle LU SUR PLAN n'a pas de relevé — c'est le signal."""
        obstacle = ObstacleAO.objects.create(
            company=self.company, toiture=self.toiture,
            nature=ObstacleAO.Nature.MURET,
            provenance=ObstacleAO.Provenance.PLAN)
        self.assertIsNone(obstacle.releve_id)
        self.assertFalse(obstacle.engageable)


class TestPointsALever(BaseReleve):
    """La liste est DÉRIVÉE : une cote orange non listée est un DÉFAUT."""

    def test_une_cote_a_confirmer_apparait(self):
        chaine = ChaineCotes.objects.create(
            company=self.company, toiture=self.toiture, releve=self.releve,
            libelle='Façade sud', segments=[dict(s) for s in SEGMENTS],
            mesure_globale_m=Decimal('51.100'))
        services.recalculer_chaine(chaine)
        services.deduire_segment(chaine, 4)
        points = selectors.points_a_lever(self.ao)
        cotes = [p for p in points if p['type'] == 'cote']
        self.assertEqual(len(cotes), 1)
        self.assertIn('E→F', cotes[0]['reference'])
        self.assertIn('8.82', cotes[0]['detail'])
        self.assertIn('8.5', cotes[0]['detail'])

    def test_aucune_cote_orange_ne_manque(self):
        """Le DÉFAUT que ce test attrape : une orange hors de la liste."""
        chaine = ChaineCotes.objects.create(
            company=self.company, toiture=self.toiture, releve=self.releve,
            libelle='Pignon', mesure_globale_m=Decimal('20.000'),
            segments=[
                {'libelle': 'P1', 'valeur_m': 5.0, 'statut': 'A_CONFIRMER'},
                {'libelle': 'P2', 'valeur_m': 7.0, 'statut': 'A_CONFIRMER'},
                {'libelle': 'P3', 'valeur_m': 8.0, 'statut': 'MESURE'},
            ])
        services.recalculer_chaine(chaine)
        listees = {
            p['reference'] for p in selectors.points_a_lever(self.ao)
            if p['type'] == 'cote'
        }
        attendues = {
            f"{chaine.libelle} · {s['libelle']}"
            for s in chaine.segments if s['statut'] == 'A_CONFIRMER'
        }
        self.assertEqual(attendues - listees, set())
        self.assertEqual(len(listees), 2)

    def test_un_obstacle_non_engageable_apparait(self):
        ObstacleAO.objects.create(
            company=self.company, toiture=self.toiture, repere='D',
            nature=ObstacleAO.Nature.SOUCHE,
            provenance=ObstacleAO.Provenance.DEVINE)
        obstacles = [p for p in selectors.points_a_lever(self.ao)
                     if p['type'] == 'obstacle']
        self.assertEqual(len(obstacles), 1)
        self.assertEqual(obstacles[0]['reference'], 'D')
        self.assertIn('Deviné', obstacles[0]['detail'])

    def test_un_obstacle_mesure_n_apparait_pas(self):
        ObstacleAO.objects.create(
            company=self.company, toiture=self.toiture, repere='E',
            nature=ObstacleAO.Nature.SOUCHE,
            provenance=ObstacleAO.Provenance.MESURE)
        self.assertEqual(selectors.points_a_lever(self.ao), [])

    def test_un_obstacle_ecarte_n_apparait_pas(self):
        obstacle = ObstacleAO.objects.create(
            company=self.company, toiture=self.toiture, repere='F',
            nature=ObstacleAO.Nature.SOUCHE,
            provenance=ObstacleAO.Provenance.DEVINE)
        services.ecarter_obstacle(obstacle, motif='Souche inventée')
        self.assertEqual(selectors.points_a_lever(self.ao), [])

    def test_liste_stable_et_triee(self):
        ObstacleAO.objects.create(
            company=self.company, toiture=self.toiture, repere='Z',
            nature=ObstacleAO.Nature.SOUCHE,
            provenance=ObstacleAO.Provenance.PLAN)
        ObstacleAO.objects.create(
            company=self.company, toiture=self.toiture, repere='B',
            nature=ObstacleAO.Nature.MURET,
            provenance=ObstacleAO.Provenance.PLAN)
        premier = selectors.points_a_lever(self.ao)
        second = selectors.points_a_lever(self.ao)
        self.assertEqual(premier, second)
        self.assertEqual([p['reference'] for p in premier], ['B', 'Z'])

    def test_isolation_multi_societe(self):
        autre = Company.objects.create(nom='AOF24 X', slug='aof24-x')
        ao = AppelOffre.objects.create(
            company=autre, reference='AO-24-X', objet='X')
        batiment = BatimentAO.objects.create(
            company=autre, appel_offre=ao, code='X')
        toiture = ToitureAO.objects.create(company=autre, batiment=batiment)
        ObstacleAO.objects.create(
            company=autre, toiture=toiture, repere='X',
            nature=ObstacleAO.Nature.SOUCHE,
            provenance=ObstacleAO.Provenance.PLAN)
        self.assertEqual(selectors.points_a_lever(self.ao), [])


class TestApiReleve(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF24 API', slug='aof24-api')
        role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='aof24_dir', password='x', company=self.company,
            role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-24-API', objet='API')
        batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=self.ao, code='C')
        self.toiture = ToitureAO.objects.create(
            company=self.company, batiment=batiment)

    def test_creation_scopee_avec_mention(self):
        r = self.api.post('/api/django/ao/releves/', {
            'appel_offre': self.ao.id, 'date_visite': '2026-07-27',
            'contradictoire': True, 'toitures': [self.toiture.id],
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['mention_cartouche'],
                         'base : relevé contradictoire du 27/07/2026')
        self.assertEqual(
            ReleveAO.objects.get(id=r.data['id']).company_id, self.company.id)

    def test_endpoint_points_a_lever(self):
        ReleveAO.objects.create(
            company=self.company, appel_offre=self.ao,
            date_visite=datetime.date(2026, 7, 27), contradictoire=True)
        ObstacleAO.objects.create(
            company=self.company, toiture=self.toiture, repere='D',
            nature=ObstacleAO.Nature.SOUCHE,
            provenance=ObstacleAO.Provenance.DEVINE)
        r = self.api.get(
            f'/api/django/ao/appels-offres/{self.ao.id}/points-a-lever/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['mention_cartouche'],
                         'base : relevé contradictoire du 27/07/2026')
        self.assertEqual(len(r.data['points']), 1)
