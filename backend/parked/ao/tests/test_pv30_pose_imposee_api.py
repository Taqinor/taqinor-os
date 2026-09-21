"""PV30 — les deux paramètres de POSE traversent l'API, SANS nouvel endpoint.

Le moteur sait depuis PV29/PV52 poser un plan IMPOSÉ par l'utilisateur et
rejouer une phase FORCÉE. Rien de tout cela n'était atteignable depuis l'API :
``calepinage_io.parametres_vers_document`` recopiait treize clés du preset et
laissait tomber ces deux-là en silence. Une fonctionnalité qu'aucun appel ne
peut déclencher n'existe pas.

Ce que ce module VERROUILLE :

  1. **Aucun endpoint nouveau.** ``calculer`` / ``lancer`` portent déjà un
     champ ``params`` opaque (``JSONField``) : les deux paramètres passent par
     là. La liste des routes de calepinage est figée par un test.
  2. **Le plan imposé ressort NON OPTIMAL et le dit.** La preuve porte
     exactement ``impose_utilisateur`` (vocabulaire VERROUILLÉ d'AOF44),
     ``optimal`` est faux et l'écart au DP est chiffré — un plan choisi à la
     main ne peut jamais se réclamer d'un « optimum prouvé ».
  3. **La phase forcée atteint vraiment le moteur.** Deux phases différentes
     donnent deux empreintes d'entrée différentes : le paramètre est DANS les
     ``Parametres`` hachés, pas seulement dans le corps de la requête.
  4. **Une saisie fautive rend un 400 NOMMÉ, jamais un 500.** Le noyau refuse
     déjà en français, mais avec SON exception : la couture la retraduit.
  5. **La persistance reste celle qui existe** — ``lancer(persister, role)`` —
     et la garde d'AOF28 refuse de publier un plan imposé sous l'optimum.

Run :
    python manage.py test apps.ao.tests.test_pv30_pose_imposee_api -v2
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ao import calepinage_io
from apps.ao.calepinage_tasks import calculer_calepinage
from apps.ao.models import (
    AppelOffre, BatimentAO, KitCalepinage, ToitureAO, VarianteCalepinage,
)
from apps.roles.models import DIRECTEUR_PERMISSIONS, Role
from authentication.models import Company
from core.calepinage.types import MethodePreuve, ModePose

User = get_user_model()

CALCULER = '/api/django/ao/calepinage/calculer/'
LANCER = '/api/django/ao/calepinage/lancer/'

CODE_KIT = 'AO-TABLE-PORTRAIT'

#: Preset de base — le même que celui de l'API historique (AOF61).
PARAMS = {
    'rive_laterale_m': 0.35,
    'rive_extremite_m': 0.35,
    'allee_min_m': 0.60,
    'degagements_par_provenance_m': {'MESURE': 0.30, 'DEVINE': 0.50},
    'kits_autorises': [CODE_KIT],
    'pas_recherche_m': 0.01,
}

#: Deux rangées posées à la main, largement espacées : le DP en placerait
#: davantage sur cette toiture — c'est précisément ce qu'on veut PROUVER
#: (un plan imposé n'est pas un optimum).
RANGEES_IMPOSEES = [[0.35, CODE_KIT], [6.50, CODE_KIT]]


class TacheImmediate:
    """Substitut de la tâche Celery : ``.delay()`` exécute tout de suite."""

    def __init__(self):
        self.appels = []

    def delay(self, **kwargs):
        self.appels.append(kwargs)
        return calculer_calepinage(**kwargs)


class BasePv30(TestCase):
    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(nom='PV30 Co', slug='pv30-co')
        role = Role.objects.create(company=self.company, nom='Directeur',
                                   permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='pv30_dir', password='x', company=self.company,
            role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-30-1', objet='Pose imposée')
        self.batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=self.ao, code='C')
        self.toiture = ToitureAO.objects.create(
            company=self.company, batiment=self.batiment, code_document='05H',
            # 30 × 18 m : la bande transversale utile (0,35 → 17,65) héberge
            # 3 rangées de 4,70 m + 2 allées de 0,60 m et laisse ~2,00 m de
            # JEU — de quoi forcer une phase sans que le kit soit écarté.
            contour_local_m=[[0, 0], [30, 0], [30, 18], [0, 18]],
            parametres_calepinage=dict(PARAMS))
        self.kit = KitCalepinage.objects.create(
            company=self.company, code=CODE_KIT,
            libelle='Table dos-à-dos portrait', modules_par_kit=2,
            pas_rangee_m=Decimal('1.134'), longueur_pente_m=Decimal('2.382'),
            faitage_m=Decimal('0.098'), puissance_module_w=625,
            inclinaison_deg=Decimal('15.00'))
        self.kit.appliquer_emprise()
        self.kit.save()

    def _params(self, **surcharges):
        return dict(PARAMS, **surcharges)

    def _calculer(self, **surcharges):
        return self.api.post(
            CALCULER,
            {'toiture': self.toiture.pk, 'params': self._params(**surcharges)},
            format='json')


class AucunNouvelEndpoint(BasePv30):
    """Le mode imposé réutilise les routes existantes — il n'en crée aucune."""

    def test_les_routes_de_calepinage_sont_exactement_celles_d_aof61(self):
        from apps.ao import calepinage_urls

        noms = {motif.name for motif in calepinage_urls.urlpatterns
                if getattr(motif, 'name', None)}
        self.assertEqual(noms, {'ao-calepinage-calculer',
                                'ao-calepinage-lancer',
                                'ao-calepinage-resultat'})
        actions = {route.name for route in calepinage_urls.router.urls}
        self.assertNotIn('ao-calepinage-variante-imposer-rangees', actions)


class LePlanImposeTraverseCalculer(BasePv30):
    """POST ``calculer`` en mode imposé -> le plan FOURNI, situé face au DP."""

    def _impose(self):
        return self._calculer(
            mode_pose=ModePose.RANGEES_IMPOSEES_UTILISATEUR.value,
            rangees_imposees=[list(r) for r in RANGEES_IMPOSEES])

    def test_la_preuve_porte_exactement_impose_utilisateur(self):
        reponse = self._impose()
        self.assertEqual(reponse.status_code, 200, reponse.data)
        preuve = reponse.data['preuve']
        self.assertEqual(preuve['methode'],
                         MethodePreuve.IMPOSE_UTILISATEUR.value)
        self.assertEqual(preuve['methode'], 'impose_utilisateur')
        self.assertFalse(preuve['methode_exacte'])
        self.assertFalse(preuve['optimal'])

    def test_le_plan_pose_est_celui_qui_a_ete_impose(self):
        reponse = self._impose()
        rangees = reponse.data['rangees']
        self.assertEqual(len(rangees), len(RANGEES_IMPOSEES))
        positions = [round(r['y0'], 2) for r in rangees]
        self.assertEqual(positions, [0.35, 6.50])
        self.assertEqual({r['kit'] for r in rangees}, {CODE_KIT})
        self.assertGreater(reponse.data['total_modules'], 0)

    def test_l_ecart_a_l_optimum_est_chiffre_et_positif(self):
        """Le DP place plus de rangées : l'écart doit être VU, pas tu."""
        reponse = self._impose()
        plan = reponse.data['plans'][0]
        self.assertGreater(plan['ecart_a_l_optimum'], 0)
        preuve = reponse.data['preuve']
        self.assertGreater(preuve['total_optimal'], preuve['total_retenu'])

    def test_le_mode_libre_reste_l_optimum_prouve(self):
        """Contre-épreuve : sans le mode imposé, rien ne change."""
        reponse = self._calculer()
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['preuve']['methode'],
                         MethodePreuve.DP_EXACT_1CM.value)
        self.assertTrue(reponse.data['preuve']['optimal'])


class LaPhaseForceeAtteintLeMoteur(BasePv30):
    """PV52 — la phase forcée entre dans les ``Parametres``, donc dans le hash."""

    def _phase(self, valeur):
        return self._calculer(
            mode_pose=ModePose.RANGEES_UNIFORMES_PHASE.value,
            phase_forcee_m=valeur)

    def test_le_document_porte_la_phase_forcee(self):
        document = calepinage_io.document_entree(
            self.toiture, params=self._params(phase_forcee_m=0.25))
        self.assertEqual(document['parametres']['phase_forcee_m'], 0.25)

    def test_la_phase_est_omise_quand_elle_n_est_pas_demandee(self):
        """Absente, elle ne doit pas apparaître : l'empreinte ne bouge pas."""
        document = calepinage_io.document_entree(self.toiture)
        self.assertNotIn('phase_forcee_m', document['parametres'])
        self.assertNotIn('rangees_imposees', document['parametres'])

    def test_deux_phases_donnent_deux_empreintes(self):
        une = self._phase(0.10)
        deux = self._phase(0.30)
        self.assertEqual(une.status_code, 200, une.data)
        self.assertEqual(deux.status_code, 200, deux.data)
        self.assertNotEqual(une.data['hash_entree'], deux.data['hash_entree'])
        for reponse in (une, deux):
            self.assertEqual(reponse.data['preuve']['methode'],
                             MethodePreuve.HEURISTIQUE_BORNEE.value)

    def test_la_phase_forcee_cale_la_premiere_rangee(self):
        reponse = self._phase(0.30)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        rangees = reponse.data['rangees']
        self.assertTrue(rangees)
        # ymin utile = 0 + rive latérale 0,35 ; la phase s'y AJOUTE.
        self.assertAlmostEqual(rangees[0]['y0'], 0.65, places=2)


class LesSaisiesFautivesRendent400(BasePv30):
    """Le noyau refuse en français ; la couture le retraduit en 400 nommé."""

    def test_mode_impose_sans_rangees(self):
        reponse = self._calculer(
            mode_pose=ModePose.RANGEES_IMPOSEES_UTILISATEUR.value)
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('entree', reponse.data)
        self.assertIn('rangees_imposees', str(reponse.data['entree']))

    def test_un_kit_non_autorise_dans_une_rangee_imposee(self):
        reponse = self._calculer(
            mode_pose=ModePose.RANGEES_IMPOSEES_UTILISATEUR.value,
            rangees_imposees=[[0.35, 'KIT-INEXISTANT']])
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('KIT-INEXISTANT', str(reponse.data['entree']))

    def test_une_rangee_qui_n_est_pas_un_couple(self):
        reponse = self._calculer(
            mode_pose=ModePose.RANGEES_IMPOSEES_UTILISATEUR.value,
            rangees_imposees=[[0.35]])
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('entree', reponse.data)

    def test_une_position_qui_n_est_pas_un_nombre(self):
        reponse = self._calculer(
            mode_pose=ModePose.RANGEES_IMPOSEES_UTILISATEUR.value,
            rangees_imposees=[['en haut', CODE_KIT]])
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('entree', reponse.data)

    def test_une_phase_forcee_qui_n_est_pas_un_nombre(self):
        reponse = self._calculer(
            mode_pose=ModePose.RANGEES_UNIFORMES_PHASE.value,
            phase_forcee_m='beaucoup')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('entree', reponse.data)

    def test_une_phase_forcee_hors_du_jeu_possible(self):
        """Refus du NOYAU, retraduit : jamais un 500 sur une faute de saisie."""
        reponse = self._calculer(
            mode_pose=ModePose.RANGEES_UNIFORMES_PHASE.value,
            phase_forcee_m=99.0)
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('entree', reponse.data)


class LaPersistanceResteCelleQuiExiste(BasePv30):
    """``lancer(persister, role)`` — aucune seconde surface d'écriture."""

    def test_une_alternative_imposee_est_persistee_mais_pas_publiable(self):
        tache = TacheImmediate()
        with patch('apps.ao.calepinage_views.calculer_calepinage', tache):
            reponse = self.api.post(LANCER, {
                'toiture': self.toiture.pk,
                'params': self._params(
                    mode_pose=ModePose.RANGEES_IMPOSEES_UTILISATEUR.value,
                    rangees_imposees=[list(r) for r in RANGEES_IMPOSEES]),
                'persister': True,
                'role': VarianteCalepinage.Role.ALTERNATIVE,
                'nom': 'Pose imposée par le dessinateur',
            }, format='json')
        self.assertEqual(reponse.status_code, 202, reponse.data)
        variante = VarianteCalepinage.objects.get(company=self.company)
        self.assertEqual(variante.role, VarianteCalepinage.Role.ALTERNATIVE)
        self.assertEqual(variante.preuve['methode'], 'impose_utilisateur')
        # AOF28 — un plan sous l'optimum n'est JAMAIS publiable.
        self.assertEqual(variante.statut, VarianteCalepinage.Statut.CALCULEE)
        self.assertIn("optimum", variante.justification.lower())
        self.assertIn(
            'inférieur',
            '\n'.join(variante.raisons_de_non_publiabilite()).lower())
