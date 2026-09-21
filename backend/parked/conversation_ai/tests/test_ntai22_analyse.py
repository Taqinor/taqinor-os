"""NTAI22 — Tests de l'analyse d'un appel (objections / next-steps / sentiment).

Couvre :
  * ``POST appels/<id>/analyser/`` renvoie l'analyse structurée + les relances
    PROPOSÉES, sans rien écrire dans le CRM (``confirme: false``) ;
  * la garde NTAI4 : tout élément NON ancré dans le transcript est écarté ;
  * le sentiment est ramené à une valeur fermée, une sortie non-JSON ne casse
    rien et n'invente rien ;
  * sans clé LLM → 503 douce ; sans transcript → 400 ;
  * ``creer-relances/`` (confirmation explicite) crée les activités sur le lead
    et RIEN d'autre ; isolation société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Lead
from apps.records.models import Activity
from core.ai.providers import AIResult, LLMProvider
from core.ai.registry import register_provider

from ..models import AppelCommercial
from ..services import (AnalyseIndisponible, analyser_appel,
                        ancre_dans_transcript, proposer_relances)

User = get_user_model()

TRANSCRIPT = (
    "Bonjour, le prix des batteries me semble trop élevé pour mon budget. "
    "Je vous rappelle lundi après avoir parlé à mon associé. "
    "L'onduleur hybride m'intéresse."
)

REPONSE_JSON = (
    '{"objections": ["le prix des batteries est trop élevé", '
    '"délai de livraison en Chine"], '
    '"next_steps": ["rappeler lundi"], '
    '"produits": ["onduleur hybride"], '
    '"sentiment": "neutre"}'
)


class FauxLLM(LLMProvider):
    """LLM factice : ACTIF, local, aucun appel réseau."""

    key = 'faux_llm_ntai22'
    label = 'LLM de test'
    reponse = REPONSE_JSON

    def is_configured(self):
        return True

    def complete(self, *, prompt, system=None, max_tokens=512):
        return AIResult(ok=True, configured=True, provider=self.key,
                        data={'text': type(self).reponse})


class FauxLLMTexteLibre(FauxLLM):
    key = 'faux_llm_libre_ntai22'
    reponse = "Je pense que le client hésite."


register_provider(FauxLLM)
register_provider(FauxLLMTexteLibre)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntai22AncrageTests(TestCase):
    """Garde NTAI4 : ce qui n'est pas dans le transcript n'existe pas."""

    def test_element_ancre(self):
        self.assertTrue(
            ancre_dans_transcript('le prix des batteries', TRANSCRIPT))

    def test_element_invente_ecarte(self):
        self.assertFalse(
            ancre_dans_transcript('délai de livraison en Chine', TRANSCRIPT))

    def test_element_vide_ou_mots_vides(self):
        self.assertFalse(ancre_dans_transcript('', TRANSCRIPT))
        self.assertFalse(ancre_dans_transcript('le la les', TRANSCRIPT))


class Ntai22AnalyseTests(TestCase):
    def setUp(self):
        self.co = make_company('ntai22a', 'NTAI22 A')
        self.lead = Lead.objects.create(company=self.co, nom='Prospect')
        self.appel = AppelCommercial.objects.create(
            company=self.co, lead=self.lead, transcript=TRANSCRIPT,
            statut=AppelCommercial.STATUT_TRANSCRIT)

    def test_sans_cle_llm_503_doux(self):
        with self.assertRaises(AnalyseIndisponible) as ctx:
            analyser_appel(self.appel)
        self.assertFalse(ctx.exception.configured)

    def test_sans_transcript_400(self):
        appel = AppelCommercial.objects.create(company=self.co)
        with self.assertRaises(AnalyseIndisponible) as ctx:
            analyser_appel(appel)
        self.assertTrue(ctx.exception.configured)

    @override_settings(AI_PROVIDERS={'llm': 'faux_llm_ntai22'})
    def test_analyse_structuree_et_ancree(self):
        analyse = analyser_appel(self.appel)
        # L'objection RÉELLE est gardée, l'objection INVENTÉE est écartée.
        self.assertEqual(analyse['objections'],
                         ['le prix des batteries est trop élevé'])
        self.assertEqual(analyse['next_steps'], ['rappeler lundi'])
        self.assertEqual(analyse['produits'], ['onduleur hybride'])
        self.assertEqual(analyse['sentiment'], 'neutre')

        self.appel.refresh_from_db()
        self.assertEqual(self.appel.sentiment, 'neutre')
        self.assertEqual(self.appel.analyse_json['next_steps'],
                         ['rappeler lundi'])
        self.assertIsNotNone(self.appel.analyse_le)

    @override_settings(AI_PROVIDERS={'llm': 'faux_llm_libre_ntai22'})
    def test_sortie_non_json_n_invente_rien(self):
        analyse = analyser_appel(self.appel)
        self.assertEqual(analyse['objections'], [])
        self.assertEqual(analyse['next_steps'], [])
        self.assertEqual(analyse['sentiment'], 'neutre')

    @override_settings(AI_PROVIDERS={'llm': 'faux_llm_ntai22'})
    def test_analyse_n_ecrit_rien_dans_le_crm(self):
        avant = Activity.objects.count()
        analyse = analyser_appel(self.appel)
        self.assertEqual(Activity.objects.count(), avant)
        propositions = proposer_relances(self.appel, analyse)
        self.assertEqual(len(propositions), 1)
        self.assertEqual(propositions[0]['resume'], 'rappeler lundi')
        # Proposer n'écrit RIEN : aucune activité n'est apparue.
        self.assertEqual(Activity.objects.count(), avant)

    def test_aucune_relance_sans_lead(self):
        appel = AppelCommercial.objects.create(company=self.co)
        self.assertEqual(
            proposer_relances(appel, {'next_steps': ['rappeler lundi']}), [])


class Ntai22EndpointTests(TestCase):
    def setUp(self):
        self.co = make_company('ntai22b', 'NTAI22 B')
        self.user = User.objects.create_user(
            username='ntai22b', password='x', company=self.co)
        self.lead = Lead.objects.create(company=self.co, nom='Prospect')
        self.appel = AppelCommercial.objects.create(
            company=self.co, lead=self.lead, transcript=TRANSCRIPT,
            statut=AppelCommercial.STATUT_TRANSCRIT)
        self.api = auth(self.user)
        self.base = f'/api/django/conversation_ai/appels/{self.appel.id}/'

    def test_analyser_sans_cle_renvoie_503(self):
        rep = self.api.post(f'{self.base}analyser/', {}, format='json')
        self.assertEqual(rep.status_code, 503)

    @override_settings(AI_PROVIDERS={'llm': 'faux_llm_ntai22'})
    def test_analyser_propose_sans_ecrire(self):
        avant = Activity.objects.count()
        rep = self.api.post(f'{self.base}analyser/', {}, format='json')
        self.assertEqual(rep.status_code, 200, rep.data)
        self.assertFalse(rep.data['confirme'])
        self.assertEqual(len(rep.data['relances_proposees']), 1)
        self.assertEqual(Activity.objects.count(), avant)

    def test_creer_relances_exige_une_charge(self):
        avant = Activity.objects.count()
        rep = self.api.post(f'{self.base}creer-relances/', {}, format='json')
        self.assertEqual(rep.status_code, 400)
        self.assertEqual(Activity.objects.count(), avant)

    def test_creer_relances_confirme(self):
        rep = self.api.post(
            f'{self.base}creer-relances/',
            {'relances': [{'resume': 'rappeler lundi', 'delai_jours': 2}]},
            format='json')
        self.assertEqual(rep.status_code, 201, rep.data)
        self.assertTrue(rep.data['confirme'])
        activite = Activity.objects.get(summary='rappeler lundi')
        self.assertEqual(activite.company_id, self.co.id)
        self.assertEqual(activite.object_id, self.lead.id)
        self.assertEqual(activite.content_type.model, 'lead')
        self.assertEqual(activite.summary, 'rappeler lundi')
        self.assertEqual(activite.assigned_to_id, self.user.id)

    def test_appel_d_une_autre_societe_invisible(self):
        autre = make_company('ntai22c', 'NTAI22 C')
        appel_autre = AppelCommercial.objects.create(
            company=autre, transcript=TRANSCRIPT)
        rep = self.api.post(
            f'/api/django/conversation_ai/appels/{appel_autre.id}/analyser/',
            {}, format='json')
        self.assertEqual(rep.status_code, 404)
