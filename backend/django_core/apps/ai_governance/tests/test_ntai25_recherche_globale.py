"""NTAI25 — Tests de la recherche sémantique GLOBALE avec citations.

Couvre :
  * la réponse CITE des fiches RÉELLES (couple ``app.model#id`` cliquable) ;
  * garde NTAI4 : une citation absente des résultats est RETIRÉE de la réponse
    et rapportée — jamais un lien mort ;
  * sans clé LLM, l'endpoint dégrade sur la recherche par mots-clés existante
    (l'utilisateur obtient toujours ses fiches) ;
  * l'index étant scopé société, la recherche ne peut pas voir un autre tenant ;
  * question vide → 400 ; aucune écriture nulle part.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Lead
from core.ai.providers import AIResult, LLMProvider
from core.ai.registry import register_provider

from ..services import filtrer_citations, recherche_globale

User = get_user_model()

URL = '/api/django/ai/recherche-globale/'


class FauxLLMCitations(LLMProvider):
    """LLM factice qui cite UNE fiche réelle ET UNE fiche inventée."""

    key = 'faux_llm_ntai25'
    label = 'LLM de test (citations)'
    gabarit = ('Le lead ALPHA est à Casablanca [crm.lead#{id}]. '
               'Voir aussi [ventes.devis#99999].')

    def is_configured(self):
        return True

    def complete(self, *, prompt, system=None, max_tokens=512):
        import re

        match = re.search(r'\[crm\.lead#(\d+)\]', prompt)
        identifiant = match.group(1) if match else '0'
        return AIResult(
            ok=True, configured=True, provider=self.key,
            data={'text': type(self).gabarit.format(id=identifiant)})


register_provider(FauxLLMCitations)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntai25FiltreCitationsTests(TestCase):
    """Garde NTAI4, testée sans base : une citation hors résultats disparaît."""

    RESULTATS = [{'content_type': 'crm.lead', 'object_id': 7,
                  'titre': 'ALPHA', 'extrait': 'Casablanca',
                  'module': 'crm', 'route': None, 'score': None}]

    def test_citation_connue_conservee(self):
        texte, utilisees, ecartees = filtrer_citations(
            'ALPHA est à Casablanca [crm.lead#7].', self.RESULTATS)
        self.assertIn('[crm.lead#7]', texte)
        self.assertEqual(len(utilisees), 1)
        self.assertEqual(ecartees, [])

    def test_citation_inventee_retiree(self):
        texte, utilisees, ecartees = filtrer_citations(
            'Voir [ventes.devis#99999] et [crm.lead#7].', self.RESULTATS)
        self.assertNotIn('99999', texte)
        self.assertIn('[crm.lead#7]', texte)
        self.assertEqual(ecartees, ['ventes.devis#99999'])
        self.assertEqual(len(utilisees), 1)


@override_settings(AI_SEMANTIC_INDEX_ENABLED=True)
class Ntai25RechercheTests(TestCase):
    def setUp(self):
        self.co = make_company('ntai25a', 'NTAI25 A')
        self.user = User.objects.create_user(
            username='ntai25a', password='x', company=self.co)
        self.lead = Lead.objects.create(
            company=self.co, nom='ALPHA', societe='STE ALPHA',
            ville='Casablanca')
        self.api = auth(self.user)

    def test_repli_recherche_sans_cle_llm(self):
        resultat = recherche_globale(company=self.co, question='Casablanca')
        self.assertEqual(resultat['source'], 'recherche')
        self.assertEqual(len(resultat['citations']), 1)
        self.assertEqual(resultat['citations'][0]['content_type'], 'crm.lead')
        self.assertEqual(resultat['citations'][0]['object_id'], self.lead.pk)

    @override_settings(AI_PROVIDERS={'llm': 'faux_llm_ntai25'})
    def test_reponse_citee_et_citation_inventee_ecartee(self):
        resultat = recherche_globale(company=self.co, question='Casablanca')
        self.assertEqual(resultat['source'], 'llm')
        self.assertIn(f'[crm.lead#{self.lead.pk}]', resultat['reponse'])
        # La fiche inventée par le modèle n'atteint jamais l'utilisateur.
        self.assertNotIn('99999', resultat['reponse'])
        self.assertEqual(resultat['citations_ecartees'], ['ventes.devis#99999'])
        self.assertEqual(len(resultat['citations']), 1)
        self.assertEqual(resultat['citations'][0]['object_id'], self.lead.pk)

    def test_aucun_resultat_ne_ment_pas(self):
        resultat = recherche_globale(company=self.co, question='zzzzintrouvable')
        self.assertEqual(resultat['citations'], [])
        self.assertIn('Aucune fiche', resultat['reponse'])

    def test_jamais_cross_tenant(self):
        autre = make_company('ntai25b', 'NTAI25 B')
        Lead.objects.create(company=autre, nom='GAMMA', ville='Casablanca')
        resultat = recherche_globale(company=self.co, question='Casablanca')
        identifiants = {c['object_id'] for c in resultat['citations']}
        self.assertEqual(identifiants, {self.lead.pk})

    def test_endpoint_question_requise(self):
        rep = self.api.post(URL, {'question': '  '}, format='json')
        self.assertEqual(rep.status_code, 400)

    def test_endpoint_renvoie_les_citations(self):
        rep = self.api.post(URL, {'question': 'Casablanca'}, format='json')
        self.assertEqual(rep.status_code, 200, rep.data)
        self.assertEqual(rep.data['citations'][0]['content_type'], 'crm.lead')
        self.assertEqual(rep.data['citations'][0]['object_id'], self.lead.pk)

    def test_endpoint_exige_une_authentification(self):
        rep = APIClient().post(URL, {'question': 'Casablanca'}, format='json')
        self.assertIn(rep.status_code, (401, 403))
