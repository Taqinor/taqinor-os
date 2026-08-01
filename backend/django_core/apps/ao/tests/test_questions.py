"""AOF25 — ``SerieQuestions`` + ``QuestionAO`` : le workflow Q/R chiffré.

Constat MESURÉ : trois séries de questions sur images annotées ont fait passer
un site réel de 512 → 522 → 562 → 618 modules posables. Poser les BONNES
questions est donc une opération productive.

D'où la règle produit gravée testée ici : **une question ne se pose QUE si sa
réponse change le compte.** Une question sans impact chiffré est REFUSÉE, avec
le motif — sinon la série devient un questionnaire administratif où les vraies
questions se noient.

Et une décision tranchée doit APPLIQUER quelque chose : l'objet lié est mis à
jour (obstacle écarté/confirmé, cote requalifiée) et les variantes de
calepinage dépendantes basculent ``PERIME``.

Run :
    python manage.py test apps.ao.tests.test_questions -v2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ao import services
from apps.ao.models import (
    AppelOffre, BatimentAO, ChaineCotes, ObstacleAO, QuestionAO,
    SerieQuestions, ToitureAO,
)
from apps.roles.models import DIRECTEUR_PERMISSIONS, Role
from authentication.models import Company

User = get_user_model()

URL_QUESTIONS = '/api/django/ao/questions/'
URL_SERIES = '/api/django/ao/series-questions/'


class BaseQuestions(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF25 Co', slug='aof25-co')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-25-1', objet='Questions')
        batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=self.ao, code='A')
        self.toiture = ToitureAO.objects.create(
            company=self.company, batiment=batiment)
        self.serie = SerieQuestions.objects.create(
            company=self.company, appel_offre=self.ao, numero=2,
            date_envoi=datetime.date(2026, 7, 25),
            canal=SerieQuestions.Canal.EMAIL, destinataire='Maîtrise d\'œuvre')

    def _question(self, **kwargs):
        kwargs.setdefault('texte', 'Cette souche existe-t-elle réellement ?')
        kwargs.setdefault('impact_min_modules', 4)
        kwargs.setdefault('impact_max_modules', 12)
        return QuestionAO.objects.create(
            company=self.company, serie=self.serie, **kwargs)


class TestImpactChiffreObligatoire(BaseQuestions):
    def test_question_avec_impact_acceptee(self):
        self._question(repere='D').clean()

    def test_question_sans_impact_refusee(self):
        question = QuestionAO(
            company=self.company, serie=self.serie, repere='X',
            texte='Question molle')
        with self.assertRaises(ValidationError) as ctx:
            question.clean()
        message = ' '.join(ctx.exception.message_dict['impact_min_modules'])
        self.assertIn('change le compte', message)

    def test_un_seul_bord_de_fourchette_suffit(self):
        self._question(repere='E', impact_min_modules=None,
                       impact_max_modules=8).clean()

    def test_impact_cumule_de_la_serie(self):
        self._question(repere='A', impact_min_modules=4,
                       impact_max_modules=12)
        self._question(repere='B', impact_min_modules=6,
                       impact_max_modules=6)
        self.assertEqual(self.serie.impact_total_modules,
                         {'min': 10, 'max': 18})


class TestTrancherApplique(BaseQuestions):
    def test_ecarter_l_obstacle_lie(self):
        obstacle = ObstacleAO.objects.create(
            company=self.company, toiture=self.toiture, repere='D',
            nature=ObstacleAO.Nature.SOUCHE,
            provenance=ObstacleAO.Provenance.DEVINE)
        question = self._question(repere='D', obstacle=obstacle)
        services.trancher_question(
            question, decision='Souche inexistante — supprimée du relevé',
            action='ecarter_obstacle')
        obstacle.refresh_from_db()
        question.refresh_from_db()
        self.assertEqual(obstacle.provenance, ObstacleAO.Provenance.ECARTE)
        self.assertFalse(obstacle.actif)
        self.assertEqual(question.statut, QuestionAO.Statut.TRANCHEE)
        self.assertIsNotNone(question.date_decision)

    def test_confirmer_l_obstacle_lie(self):
        obstacle = ObstacleAO.objects.create(
            company=self.company, toiture=self.toiture, repere='F',
            nature=ObstacleAO.Nature.MURET,
            provenance=ObstacleAO.Provenance.PLAN)
        question = self._question(repere='F', obstacle=obstacle)
        services.trancher_question(
            question, decision='Muret confirmé sur site',
            action='confirmer_obstacle',
            provenance=ObstacleAO.Provenance.MESURE)
        obstacle.refresh_from_db()
        self.assertEqual(obstacle.provenance, ObstacleAO.Provenance.MESURE)
        self.assertTrue(obstacle.engageable)
        self.assertEqual(obstacle.degagement_m, Decimal('0.30'))

    def test_requalifier_les_cotes_de_la_chaine_liee(self):
        chaine = ChaineCotes.objects.create(
            company=self.company, toiture=self.toiture, libelle='Pignon',
            mesure_totale_m=Decimal('20.000'),
            segments=[
                {'libelle': 'P1', 'valeur_m': 12.0, 'statut': 'A_CONFIRMER'},
                {'libelle': 'P2', 'valeur_m': 8.0, 'statut': 'A_CONFIRMER'},
            ])
        services.recalculer_chaine(chaine)
        question = self._question(repere='G', chaine=chaine)
        services.trancher_question(
            question, decision='Cotes confirmées au décamètre',
            action='requalifier_cote', statut_cote='MESURE')
        chaine.refresh_from_db()
        self.assertEqual(
            {s['statut'] for s in chaine.segments}, {'MESURE'})
        self.assertEqual(chaine.cotes_a_confirmer, [])

    def test_action_sans_objet_lie_refusee(self):
        question = self._question(repere='H')
        with self.assertRaises(ValidationError) as ctx:
            services.trancher_question(
                question, decision='X', action='ecarter_obstacle')
        self.assertIn('obstacle', ctx.exception.message_dict)

    def test_action_inconnue_refusee(self):
        question = self._question(repere='I')
        with self.assertRaises(ValidationError) as ctx:
            services.trancher_question(
                question, decision='X', action='faire_le_cafe')
        self.assertIn('action', ctx.exception.message_dict)

    def test_action_aucune_tranche_sans_rien_modifier(self):
        obstacle = ObstacleAO.objects.create(
            company=self.company, toiture=self.toiture, repere='J',
            nature=ObstacleAO.Nature.MURET,
            provenance=ObstacleAO.Provenance.PLAN)
        question = self._question(repere='J', obstacle=obstacle)
        services.trancher_question(
            question, decision='Sans effet sur le calepinage', action='aucune')
        obstacle.refresh_from_db()
        question.refresh_from_db()
        self.assertEqual(obstacle.provenance, ObstacleAO.Provenance.PLAN)
        self.assertEqual(question.statut, QuestionAO.Statut.TRANCHEE)

    def test_decision_journalisee_au_chatter(self):
        from apps.records.services import chatter_qs

        question = self._question(repere='K')
        services.trancher_question(
            question, decision='Décision consignée', action='aucune')
        entrees = [
            e for e in chatter_qs(self.ao, company=self.company)
            if e.field == 'question'
        ]
        self.assertEqual(len(entrees), 1)
        self.assertIn('Impact prévisionnel', entrees[0].body)

    def test_peremption_des_variantes_ne_casse_rien_sans_modele(self):
        """``perimer_variantes_de_toiture`` est résolue PARESSEUSEMENT.

        Elle doit renvoyer un entier — 0 tant qu'aucune variante n'existe pour
        la toiture — sans jamais lever, que ``VarianteCalepinage`` soit déjà
        déployée ou non.
        """
        self.assertEqual(
            services.perimer_variantes_de_toiture(self.toiture.id), 0)


class TestApiQuestions(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF25 API', slug='aof25-api')
        role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='aof25_dir', password='x', company=self.company,
            role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-25-API', objet='API')
        batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=self.ao, code='A')
        self.toiture = ToitureAO.objects.create(
            company=self.company, batiment=batiment)
        self.serie = SerieQuestions.objects.create(
            company=self.company, appel_offre=self.ao, numero=1)

    def test_creation_scopee(self):
        r = self.api.post(URL_QUESTIONS, {
            'serie': self.serie.id, 'repere': 'A',
            'texte': 'Le grand rectangle est-il NÉANT ?',
            'impact_min_modules': 8, 'impact_max_modules': 8,
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(
            QuestionAO.objects.get(id=r.data['id']).company_id,
            self.company.id)
        self.assertTrue(r.data['a_un_impact_chiffre'])

    def test_question_sans_impact_refusee_avec_motif(self):
        r = self.api.post(URL_QUESTIONS, {
            'serie': self.serie.id, 'repere': 'B', 'texte': 'Question molle',
        }, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('impact_min_modules', r.data)
        self.assertIn('change le compte',
                      ' '.join(r.data['impact_min_modules']))

    def test_action_trancher(self):
        obstacle = ObstacleAO.objects.create(
            company=self.company, toiture=self.toiture, repere='D',
            nature=ObstacleAO.Nature.SOUCHE,
            provenance=ObstacleAO.Provenance.DEVINE)
        question = QuestionAO.objects.create(
            company=self.company, serie=self.serie, repere='D',
            texte='Souche réelle ?', impact_min_modules=4,
            impact_max_modules=4, obstacle=obstacle)
        r = self.api.post(f'{URL_QUESTIONS}{question.id}/trancher/', {
            'decision': 'Souche inexistante', 'action': 'ecarter_obstacle',
        }, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['statut'], 'tranchee')
        self.assertEqual(r.data['variantes_perimees'], 0)
        obstacle.refresh_from_db()
        self.assertEqual(obstacle.provenance, ObstacleAO.Provenance.ECARTE)

    def test_trancher_sans_decision_refuse(self):
        question = QuestionAO.objects.create(
            company=self.company, serie=self.serie, repere='E',
            texte='X', impact_min_modules=1)
        r = self.api.post(f'{URL_QUESTIONS}{question.id}/trancher/', {},
                          format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('decision', r.data)

    def test_serie_expose_ses_questions_et_son_impact(self):
        QuestionAO.objects.create(
            company=self.company, serie=self.serie, repere='A', texte='Q1',
            impact_min_modules=4, impact_max_modules=12)
        r = self.api.get(f'{URL_SERIES}{self.serie.id}/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(len(r.data['questions']), 1)
        self.assertEqual(r.data['impact_total_modules'],
                         {'min': 4, 'max': 12})

    def test_filtre_par_appel_offre(self):
        QuestionAO.objects.create(
            company=self.company, serie=self.serie, repere='A', texte='Q1',
            impact_min_modules=1)
        r = self.api.get(URL_QUESTIONS, {'appel_offre': self.ao.id})
        self.assertEqual(r.status_code, 200, r.data)
        lignes = r.data['results'] if isinstance(r.data, dict) \
            and 'results' in r.data else r.data
        self.assertEqual(len(lignes), 1)

    def test_isolation_multi_societe(self):
        autre = Company.objects.create(nom='AOF25 X', slug='aof25-x')
        ao = AppelOffre.objects.create(
            company=autre, reference='AO-25-X', objet='X')
        serie = SerieQuestions.objects.create(
            company=autre, appel_offre=ao, numero=1)
        QuestionAO.objects.create(
            company=autre, serie=serie, texte='X', impact_min_modules=1)
        r = self.api.get(URL_QUESTIONS)
        self.assertEqual(r.status_code, 200, r.data)
        lignes = r.data['results'] if isinstance(r.data, dict) \
            and 'results' in r.data else r.data
        self.assertEqual(lignes, [])
