"""XSAV22 — Ratio de déflection KB (côté apps.sav, rapport service).

``ratio_deflection_kb`` lit UNIQUEMENT via ``apps.kb.selectors`` et
``apps.portail.selectors`` (jamais leurs modèles). Couvre : ratio correct
avec consultations ET tickets, zéro division par zéro, isolation
multi-société.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_xsav22_ratio_deflection -v 2
"""
from django.test import TestCase

from authentication.models import Company

from apps.kb.models import KbArticle
from apps.kb.services import enregistrer_consultation_portail
from apps.portail.models import DemandeTicketPortail
from apps.sav.selectors import ratio_deflection_kb


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class RatioDeflectionKbTests(TestCase):

    def setUp(self):
        self.co = make_company('xsav22-ratio', 'XSAV22 Ratio')

    def test_zero_activity_returns_zero_ratio_no_division_error(self):
        result = ratio_deflection_kb(self.co)
        self.assertEqual(
            result, {'consultations_kb': 0, 'tickets_crees': 0, 'ratio': 0.0})

    def test_ratio_computed_from_consultations_and_tickets(self):
        article = KbArticle.objects.create(
            company=self.co, titre='Panne courante',
            statut=KbArticle.Statut.PUBLIE, visible_portail=True)
        enregistrer_consultation_portail(self.co, article.id)
        enregistrer_consultation_portail(self.co, article.id)
        enregistrer_consultation_portail(self.co, article.id)
        DemandeTicketPortail.objects.create(
            company=self.co, client_id=1, sujet='Panne')

        result = ratio_deflection_kb(self.co)
        self.assertEqual(result['consultations_kb'], 3)
        self.assertEqual(result['tickets_crees'], 1)
        self.assertEqual(result['ratio'], 0.75)

    def test_multi_tenant_isolation(self):
        other = make_company('xsav22-ratio-b', 'XSAV22 Ratio B')
        article = KbArticle.objects.create(
            company=other, titre='Autre société',
            statut=KbArticle.Statut.PUBLIE, visible_portail=True)
        enregistrer_consultation_portail(other, article.id)
        DemandeTicketPortail.objects.create(
            company=other, client_id=2, sujet='Autre')

        result = ratio_deflection_kb(self.co)
        self.assertEqual(
            result, {'consultations_kb': 0, 'tickets_crees': 0, 'ratio': 0.0})
