"""XSAV22 — Déflection KB sur le portail client (côté apps.kb).

Couvre : ``suggestions_portail`` ne renvoie que les articles PUBLIÉS ET
flagués ``visible_portail`` (jamais un brouillon, jamais un article non
flagué même publié), scoping multi-société, et
``enregistrer_consultation_portail`` incrémente le compteur DÉDIÉ (distinct
de ``vues``) et no-op proprement si l'article n'appartient pas à la société
ou n'est pas ``visible_portail``.
"""
from django.test import TestCase

from authentication.models import Company

from apps.kb.models import KbArticle
from apps.kb.selectors import consultations_portail_total, suggestions_portail
from apps.kb.services import enregistrer_consultation_portail


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class SuggestionsPortailTests(TestCase):

    def setUp(self):
        self.co = make_company('xsav22-a', 'XSAV22 A')
        self.visible = KbArticle.objects.create(
            company=self.co, titre='Onduleur qui clignote rouge',
            corps="Vérifier le code d'erreur sur l'écran.",
            statut=KbArticle.Statut.PUBLIE, visible_portail=True)
        self.non_flague = KbArticle.objects.create(
            company=self.co, titre='Onduleur en panne totale',
            corps='Diagnostic interne.',
            statut=KbArticle.Statut.PUBLIE, visible_portail=False)
        self.brouillon = KbArticle.objects.create(
            company=self.co, titre='Onduleur — brouillon interne',
            corps='Pas prêt.',
            statut=KbArticle.Statut.BROUILLON, visible_portail=True)

    def test_only_published_and_flagged_articles_suggested(self):
        result = suggestions_portail(self.co, 'onduleur')
        ids = {r['id'] for r in result}
        self.assertEqual(ids, {self.visible.id})

    def test_empty_query_returns_nothing(self):
        self.assertEqual(suggestions_portail(self.co, ''), [])
        self.assertEqual(suggestions_portail(self.co, '   '), [])

    def test_multi_tenant_isolation(self):
        other = make_company('xsav22-b', 'XSAV22 B')
        result = suggestions_portail(other, 'onduleur')
        self.assertEqual(result, [])


class ConsultationTrackingTests(TestCase):

    def setUp(self):
        self.co = make_company('xsav22-c', 'XSAV22 C')
        self.article = KbArticle.objects.create(
            company=self.co, titre='Coupure disjoncteur',
            statut=KbArticle.Statut.PUBLIE, visible_portail=True)

    def test_records_consultation_and_is_distinct_from_vues(self):
        ok = enregistrer_consultation_portail(self.co, self.article.id)
        self.assertTrue(ok)
        self.article.refresh_from_db()
        self.assertEqual(self.article.consultations_portail_ticket, 1)
        self.assertEqual(self.article.vues, 0)
        self.assertEqual(consultations_portail_total(self.co), 1)

    def test_noop_for_other_company(self):
        other = make_company('xsav22-d', 'XSAV22 D')
        ok = enregistrer_consultation_portail(other, self.article.id)
        self.assertFalse(ok)
        self.article.refresh_from_db()
        self.assertEqual(self.article.consultations_portail_ticket, 0)

    def test_noop_when_not_visible_portail(self):
        hidden = KbArticle.objects.create(
            company=self.co, titre='Interne seulement',
            statut=KbArticle.Statut.PUBLIE, visible_portail=False)
        ok = enregistrer_consultation_portail(self.co, hidden.id)
        self.assertFalse(ok)
