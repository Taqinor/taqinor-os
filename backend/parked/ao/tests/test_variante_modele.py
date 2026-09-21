"""AOF28 — ``VarianteCalepinage`` : le modèle PIVOT (role + parent + preuve).

Variante retenue, alternative comparée, sensibilité défavorable et marche de
l'échelle de décomposition sont le MÊME objet : ``role`` + ``parent``. Trois
tables jumelles auraient triplé chaque évolution du moteur.

Le cœur du test est la PREUVE. On ne peut écrire « capacité prouvée optimale »
à un maître d'ouvrage que si la donnée le démontre : trois causes de refus sont
vérifiées une par une, plus l'unicité en base de la variante retenue.

Run :
    python manage.py test apps.ao.tests.test_variante_modele -v2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.utils import IntegrityError
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ao import services
from apps.ao.models import (
    AppelOffre, BatimentAO, ObstacleAO, ToitureAO, VarianteCalepinage,
)
from apps.roles.models import DIRECTEUR_PERMISSIONS, Role
from authentication.models import Company

User = get_user_model()

URL = '/api/django/ao/variantes-calepinage/'

PREUVE_OK = {
    'total_retenu': 314,
    'total_optimal': 314,
    'methode': 'balayage exhaustif',
    'pas_cm': 1,
    'nb_optima': 3,
    'marge_troncon_min': 0.05,
    'marge_bande_min': 0.12,
    'controles': ['rives', 'allées', 'dégagements'],
}


class TestRolesEtStatuts(SimpleTestCase):
    def test_les_quatre_roles(self):
        valeurs = {v for v, _ in VarianteCalepinage.Role.choices}
        self.assertEqual(valeurs, {'RETENUE', 'ALTERNATIVE', 'SENSIBILITE',
                                   'MARCHE'})

    def test_les_seuils_de_preuve(self):
        self.assertEqual(VarianteCalepinage.MARGE_TRONCON_MIN_M,
                         Decimal('0.02'))
        self.assertEqual(VarianteCalepinage.MARGE_BANDE_MIN_M,
                         Decimal('0.04'))


class BaseVariante(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF28 Co', slug='aof28-co')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-28-1', objet='Variantes')
        batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=self.ao, code='C')
        self.toiture = ToitureAO.objects.create(
            company=self.company, batiment=batiment, code_document='05H')

    def _variante(self, **kwargs):
        base = {
            'nom': 'Retenue', 'role': VarianteCalepinage.Role.RETENUE,
            'preuve': dict(PREUVE_OK),
            'resultat': {'total_modules': 314, 'kwc': 196.25,
                         'rangees': [{'x0': 0.0, 'kit': 'AO-TABLE-PORTRAIT',
                                      'modules': 14}]},
        }
        base.update(kwargs)
        return VarianteCalepinage.objects.create(
            company=self.company, toiture=self.toiture, appel_offre=self.ao,
            **base)


class TestPivotRoleParent(BaseVariante):
    def test_une_alternative_pend_a_sa_retenue(self):
        retenue = self._variante()
        alternative = self._variante(
            nom='Allée 1,94 m', role=VarianteCalepinage.Role.ALTERNATIVE,
            parent=retenue)
        self.assertEqual(alternative.parent_id, retenue.id)
        self.assertEqual(list(retenue.enfants.all()), [alternative])

    def test_l_ecran_de_comparaison_est_une_requete(self):
        retenue = self._variante()
        self._variante(nom='Alt', role=VarianteCalepinage.Role.ALTERNATIVE,
                       parent=retenue)
        self._variante(nom='Sens', role=VarianteCalepinage.Role.SENSIBILITE,
                       parent=retenue)
        self._variante(nom='Marche G', role=VarianteCalepinage.Role.MARCHE,
                       parent=retenue)
        self.assertEqual(
            VarianteCalepinage.objects.filter(toiture=self.toiture).count(), 4)

    def test_agregats_lus_dans_le_resultat(self):
        variante = self._variante()
        self.assertEqual(variante.total_modules, 314)
        self.assertEqual(variante.puissance_kwc, 196.25)


class TestUniciteDeLaRetenue(BaseVariante):
    def test_une_seule_retenue_par_toiture(self):
        self._variante(est_retenue=True)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._variante(nom='Seconde', est_retenue=True)

    def test_le_service_bascule_proprement(self):
        premiere = self._variante(est_retenue=True)
        seconde = self._variante(nom='Seconde')
        services.retenir_variante(seconde)
        premiere.refresh_from_db()
        seconde.refresh_from_db()
        self.assertFalse(premiere.est_retenue)
        self.assertTrue(seconde.est_retenue)

    def test_deux_toitures_ont_chacune_leur_retenue(self):
        autre_toiture = ToitureAO.objects.create(
            company=self.company, batiment=self.toiture.batiment,
            code_document='06H')
        self._variante(est_retenue=True)
        VarianteCalepinage.objects.create(
            company=self.company, toiture=autre_toiture, appel_offre=self.ao,
            nom='Retenue 06H', est_retenue=True)
        self.assertEqual(
            VarianteCalepinage.objects.filter(est_retenue=True).count(), 2)


class TestPreuveEstUnePorte(BaseVariante):
    """Les TROIS causes de refus, une par une."""

    def test_publiable_quand_la_preuve_tient(self):
        variante = self._variante()
        self.assertEqual(variante.raisons_de_non_publiabilite(), [])
        services.publier_variante(variante)
        variante.refresh_from_db()
        self.assertEqual(variante.statut, VarianteCalepinage.Statut.PUBLIABLE)

    def test_refus_si_le_retenu_est_sous_l_optimum(self):
        preuve = dict(PREUVE_OK, total_retenu=300, total_optimal=314)
        variante = self._variante(preuve=preuve)
        with self.assertRaises(ValidationError) as ctx:
            services.publier_variante(variante)
        message = ' '.join(ctx.exception.message_dict['preuve'])
        self.assertIn("inférieur à l'optimum", message)
        variante.refresh_from_db()
        self.assertNotEqual(variante.statut,
                            VarianteCalepinage.Statut.PUBLIABLE)

    def test_refus_si_la_marge_de_troncon_est_trop_faible(self):
        variante = self._variante(
            preuve=dict(PREUVE_OK, marge_troncon_min=0.01))
        with self.assertRaises(ValidationError) as ctx:
            services.publier_variante(variante)
        self.assertIn('tronçon',
                      ' '.join(ctx.exception.message_dict['preuve']))

    def test_refus_si_la_marge_de_bande_est_trop_faible(self):
        variante = self._variante(
            preuve=dict(PREUVE_OK, marge_bande_min=0.03))
        with self.assertRaises(ValidationError) as ctx:
            services.publier_variante(variante)
        self.assertIn('bande', ' '.join(ctx.exception.message_dict['preuve']))

    def test_refus_si_un_obstacle_non_mesure_est_actif(self):
        ObstacleAO.objects.create(
            company=self.company, toiture=self.toiture, repere='D',
            nature=ObstacleAO.Nature.SOUCHE,
            provenance=ObstacleAO.Provenance.DEVINE)
        variante = self._variante()
        with self.assertRaises(ValidationError) as ctx:
            services.publier_variante(variante)
        message = ' '.join(ctx.exception.message_dict['preuve'])
        self.assertIn('NON MESURÉS', message)
        self.assertIn('D', message)

    def test_un_obstacle_ecarte_ne_bloque_plus(self):
        obstacle = ObstacleAO.objects.create(
            company=self.company, toiture=self.toiture, repere='D',
            nature=ObstacleAO.Nature.SOUCHE,
            provenance=ObstacleAO.Provenance.DEVINE)
        services.ecarter_obstacle(obstacle, motif='Souche inventée')
        variante = self._variante()
        self.assertEqual(variante.raisons_de_non_publiabilite(), [])

    def test_refus_si_la_preuve_est_incomplete(self):
        variante = self._variante(preuve={})
        with self.assertRaises(ValidationError) as ctx:
            services.publier_variante(variante)
        self.assertIn('incomplète',
                      ' '.join(ctx.exception.message_dict['preuve']))


class TestPeremptionParLesQuestions(BaseVariante):
    def test_trancher_une_question_perime_les_variantes(self):
        from apps.ao.models import QuestionAO, SerieQuestions

        variante = self._variante(statut=VarianteCalepinage.Statut.CALCULEE)
        obstacle = ObstacleAO.objects.create(
            company=self.company, toiture=self.toiture, repere='D',
            nature=ObstacleAO.Nature.SOUCHE,
            provenance=ObstacleAO.Provenance.DEVINE)
        serie = SerieQuestions.objects.create(
            company=self.company, appel_offre=self.ao, numero=1)
        question = QuestionAO.objects.create(
            company=self.company, serie=serie, repere='D',
            texte='Souche réelle ?', impact_min_modules=4, obstacle=obstacle)
        _, perimees = services.trancher_question(
            question, decision='Souche inexistante',
            action='ecarter_obstacle')
        self.assertEqual(perimees, 1)
        variante.refresh_from_db()
        self.assertEqual(variante.statut, VarianteCalepinage.Statut.PERIME)


class TestApiVariantes(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF28 API', slug='aof28-api')
        role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='aof28_dir', password='x', company=self.company,
            role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-28-API', objet='API')
        batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=self.ao, code='C')
        self.toiture = ToitureAO.objects.create(
            company=self.company, batiment=batiment)

    def _creer(self, **kwargs):
        base = {'nom': 'Retenue', 'preuve': dict(PREUVE_OK),
                'resultat': {'total_modules': 314, 'kwc': 196.25}}
        base.update(kwargs)
        return VarianteCalepinage.objects.create(
            company=self.company, toiture=self.toiture, appel_offre=self.ao,
            **base)

    def test_publier_ok(self):
        variante = self._creer()
        r = self.api.post(f'{URL}{variante.id}/publier/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['statut'], 'publiable')
        self.assertEqual(r.data['raisons_de_non_publiabilite'], [])

    def test_publier_refuse_avec_motifs_francais(self):
        variante = self._creer(
            preuve=dict(PREUVE_OK, total_retenu=300, total_optimal=314))
        r = self.api.post(f'{URL}{variante.id}/publier/', {}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn("inférieur à l'optimum", ' '.join(r.data['preuve']))

    def test_action_retenir(self):
        premiere = self._creer(est_retenue=True)
        seconde = self._creer(nom='Seconde')
        r = self.api.post(f'{URL}{seconde.id}/retenir/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        premiere.refresh_from_db()
        self.assertFalse(premiere.est_retenue)

    def test_filtre_par_role_et_par_toiture(self):
        self._creer()
        self._creer(nom='Alt', role=VarianteCalepinage.Role.ALTERNATIVE)
        r = self.api.get(URL, {'toiture': self.toiture.id,
                               'role': 'ALTERNATIVE'})
        self.assertEqual(r.status_code, 200, r.data)
        lignes = r.data['results'] if isinstance(r.data, dict) \
            and 'results' in r.data else r.data
        self.assertEqual(len(lignes), 1)

    def test_isolation_multi_societe(self):
        autre = Company.objects.create(nom='AOF28 X', slug='aof28-x')
        ao = AppelOffre.objects.create(
            company=autre, reference='AO-28-X', objet='X')
        batiment = BatimentAO.objects.create(
            company=autre, appel_offre=ao, code='X')
        toiture = ToitureAO.objects.create(company=autre, batiment=batiment)
        VarianteCalepinage.objects.create(
            company=autre, toiture=toiture, appel_offre=ao, nom='X')
        r = self.api.get(URL)
        self.assertEqual(r.status_code, 200, r.data)
        lignes = r.data['results'] if isinstance(r.data, dict) \
            and 'results' in r.data else r.data
        self.assertEqual(lignes, [])
