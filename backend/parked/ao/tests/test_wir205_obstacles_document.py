"""WIR205 — un obstacle saisi dans l'atelier ARRIVE au moteur de calepinage.

L'atelier toiture gardait obstacles et chaînes de cotes en mémoire d'écran :
le calepinage tournait donc sur une toiture SANS obstacle, et le compte publié
était plausible — la pire forme de panne. Les écritures existent désormais
(`ObstacleAOViewSet`, `ChaineCotesViewSet`) ; ce module verrouille le maillon
qui prouve que la persistance SERT à quelque chose : l'obstacle créé par l'API
ressort dans `calepinage_io.obstacles_vers_document`.

Il verrouille aussi les deux gestes que l'atelier vient de câbler :

  * ÉCARTER retire l'obstacle du document (``actif=False``) SANS perdre sa
    géométrie — c'est ce qui rend la décision chiffrable et le retour arrière
    possible ;
  * RÉINTÉGRER le remet dans le document, à l'identique.

Et la COMPENSATION au prorata d'une chaîne : la forme exacte que l'écran
consomme (`{residu_m, applique, segments:[{index, libelle, valeur_m,
valeur_proposee_m, delta_m}]}`), et le fait qu'elle n'APPLIQUE rien.

Run :
    python manage.py test apps.ao.tests.test_wir205_obstacles_document -v2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ao import calepinage_io, services
from apps.ao.models import AppelOffre, BatimentAO, ChaineCotes, ToitureAO
from apps.roles.models import DIRECTEUR_PERMISSIONS, Role
from authentication.models import Company

User = get_user_model()

URL_OBSTACLES = '/api/django/ao/obstacles/'
URL_CHAINES = '/api/django/ao/chaines-cotes/'


class BaseWir205(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='WIR205 Co', slug='wir205-co')
        role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='wir205_dir', password='x', company=self.company,
            role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-205', objet='Atelier')
        batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=self.ao, code='A')
        self.toiture = ToitureAO.objects.create(
            company=self.company, batiment=batiment,
            contour_local_m=[[0, 0], [20, 0], [20, 12], [0, 12]])

    def _creer_obstacle(self, **extra):
        corps = {
            'toiture': self.toiture.id, 'repere': 'A', 'nature': 'edicule',
            'provenance': 'MESURE',
            'rect_x0_m': '2.000', 'rect_x1_m': '4.000',
            'rect_y0_m': '3.000', 'rect_y1_m': '5.000',
        }
        corps.update(extra)
        resp = self.api.post(URL_OBSTACLES, corps, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        return resp.data

    @staticmethod
    def _reperes(toiture):
        return [o['repere']
                for o in calepinage_io.obstacles_vers_document(toiture)]


class ObstacleAtelierVersDocumentTests(BaseWir205):
    """La chaîne complète : écriture d'atelier → document du moteur."""

    def test_obstacle_cree_par_l_api_entre_dans_le_document(self):
        self._creer_obstacle()
        document = calepinage_io.obstacles_vers_document(self.toiture)
        self.assertEqual(len(document), 1, document)
        entree = document[0]
        self.assertEqual(entree['repere'], 'A')
        self.assertEqual(entree['x0'], 2.0)
        self.assertEqual(entree['x1'], 4.0)
        self.assertEqual(entree['y0'], 3.0)
        self.assertEqual(entree['y1'], 5.0)
        # Le dégagement transmis est celui DÉRIVÉ par le serveur (AOF22 :
        # max(nature, provenance) — 0,60 pour un édicule mesuré), jamais une
        # valeur devinée par l'appelant.
        self.assertEqual(entree['degagement_m'], 0.60)

    def test_ecarter_sort_l_obstacle_du_document_sans_perdre_sa_geometrie(self):
        obstacle = self._creer_obstacle()
        self.assertEqual(self._reperes(self.toiture), ['A'])

        resp = self.api.post(
            f'{URL_OBSTACLES}{obstacle["id"]}/ecarter/',
            {'motif': 'Édicule déposé au lot couverture'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['est_ecarte'])
        self.assertFalse(resp.data['actif'])
        self.assertEqual(
            resp.data['decision'], 'Édicule déposé au lot couverture')
        # La géométrie reste EN BASE : le retour arrière est un one-liner et
        # la marche de décomposition reste chiffrable.
        self.assertEqual(resp.data['rect_x0_m'], '2.000')

        self.assertEqual(self._reperes(self.toiture), [])

    def test_reintegrer_remet_l_obstacle_dans_le_document(self):
        obstacle = self._creer_obstacle()
        self.api.post(
            f'{URL_OBSTACLES}{obstacle["id"]}/ecarter/',
            {'motif': 'À confirmer'}, format='json')
        self.assertEqual(self._reperes(self.toiture), [])

        resp = self.api.post(
            f'{URL_OBSTACLES}{obstacle["id"]}/reintegrer/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['est_ecarte'])
        self.assertTrue(resp.data['actif'])
        self.assertEqual(self._reperes(self.toiture), ['A'])


class CompensationProrataApiTests(BaseWir205):
    """La compensation est une PROPOSITION servie par le serveur."""

    def _chaine(self):
        chaine = ChaineCotes.objects.create(
            company=self.company, toiture=self.toiture,
            libelle='Développé arc', axe=ChaineCotes.Axe.X,
            segments=[
                {'libelle': 'T1', 'valeur_m': 22.6, 'statut': 'MESURE'},
                {'libelle': 'T2', 'valeur_m': 22.75, 'statut': 'MESURE'},
                {'libelle': 'T3', 'valeur_m': 22.4, 'statut': 'MESURE'},
            ],
            mesure_globale_m=Decimal('68.050'),
            tolerance_m=Decimal('0.250'))
        # Le résidu doit être PERSISTÉ : `proposer_compensation_prorata` le lit
        # depuis la donnée, il ne le recalcule pas à la volée.
        services.recalculer_chaine(chaine)
        return chaine

    def test_compensation_sert_la_forme_que_l_ecran_consomme(self):
        chaine = self._chaine()
        resp = self.api.get(f'{URL_CHAINES}{chaine.id}/compensation/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('residu_m', resp.data)
        self.assertFalse(resp.data['applique'])
        segments = resp.data['segments']
        self.assertEqual(len(segments), 3)
        for attendu, segment in enumerate(segments):
            self.assertEqual(segment['index'], attendu)
            for cle in ('libelle', 'valeur_m', 'valeur_proposee_m', 'delta_m'):
                self.assertIn(cle, segment)

    def test_compensation_n_applique_rien(self):
        """Elle PROPOSE : les segments en base ne bougent pas d'un millimètre."""
        chaine = self._chaine()
        avant = list(chaine.segments)
        self.api.get(f'{URL_CHAINES}{chaine.id}/compensation/')
        chaine.refresh_from_db()
        self.assertEqual(chaine.segments, avant)
