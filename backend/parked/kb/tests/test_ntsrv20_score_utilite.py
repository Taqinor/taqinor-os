"""NTSRV20 — Score d'utilité d'article KCS.

Critère d'acceptation testé : cocher « a résolu » sur un ticket incrémente
le compteur du bon article, visible dans la liste KB triée par utilité.
"""
from django.test import TestCase

from authentication.models import Company
from apps.kb.models import KbArticle


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class TestScoreUtiliteKcs(TestCase):
    def setUp(self):
        self.company = make_company('ntsrv20-co', 'NTSRV20 Co')
        self.article = KbArticle.objects.create(
            company=self.company, titre='Panne onduleur',
            statut=KbArticle.Statut.PUBLIE)

    def test_defaut_zero_comportement_historique_inchange(self):
        self.assertEqual(self.article.nb_vues_depuis_ticket, 0)
        self.assertEqual(self.article.nb_resolutions_attribuees, 0)

    def test_incrementer_vue_depuis_ticket(self):
        nouvelle_valeur = self.article.incrementer_vue_depuis_ticket()
        self.assertEqual(nouvelle_valeur, 1)
        self.article.refresh_from_db()
        self.assertEqual(self.article.nb_vues_depuis_ticket, 1)
        self.article.incrementer_vue_depuis_ticket()
        self.article.refresh_from_db()
        self.assertEqual(self.article.nb_vues_depuis_ticket, 2)

    def test_incrementer_resolution_marque_le_bon_article(self):
        autre = KbArticle.objects.create(
            company=self.company, titre='Autre article',
            statut=KbArticle.Statut.PUBLIE)
        self.article.incrementer_resolution()
        self.article.refresh_from_db()
        autre.refresh_from_db()
        self.assertEqual(self.article.nb_resolutions_attribuees, 1)
        self.assertEqual(autre.nb_resolutions_attribuees, 0)

    def test_tri_par_utilite_place_larticle_le_plus_resolu_en_tete(self):
        peu_utile = KbArticle.objects.create(
            company=self.company, titre='Article peu utile',
            statut=KbArticle.Statut.PUBLIE)
        self.article.incrementer_resolution()
        self.article.incrementer_resolution()
        self.article.incrementer_resolution()
        classement = list(
            KbArticle.objects.filter(company=self.company)
            .order_by('-nb_resolutions_attribuees', 'id')
            .values_list('id', flat=True))
        self.assertEqual(classement[0], self.article.id)
        self.assertIn(peu_utile.id, classement)
