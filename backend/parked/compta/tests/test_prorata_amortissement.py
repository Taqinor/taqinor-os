"""Tests XACC32 — Prorata temporis sur la 1re annuité d'amortissement linéaire.

Couvre : une immobilisation mise en service en juillet a une 1re dotation à
6/12 et un cumul final = base amortissable ; une immo SANS date de mise en
service garde le plan actuel byte-identique ; les plans avec dotations
postées ne sont jamais régénérés ; le dégressif garde sa règle actuelle.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.compta import services
from apps.compta.models import Immobilisation

from authentication.models import Company


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_immo(company, **kwargs):
    defaults = dict(
        libelle='Machine',
        categorie=Immobilisation.Categorie.MATERIEL,
        cout=Decimal('120000'),
        taux_tva=Decimal('20.00'),
        date_acquisition=date(2026, 1, 1),
    )
    defaults.update(kwargs)
    return Immobilisation.objects.create(company=company, **defaults)


class ProrataLineaireTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc32-svc', 'XACC32 Svc')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)

    def test_mise_en_service_juillet_premiere_dotation_6_12(self):
        immo = make_immo(
            self.co, cout=Decimal('120000'),
            date_acquisition=date(2026, 1, 1),
            date_mise_en_service=date(2026, 7, 1))
        plan = services.generer_plan_amortissement(
            immo, mode='lineaire', duree_annees=5, date_debut=date(2026, 1, 1))
        dotations = list(plan.dotations.order_by('annee'))
        self.assertEqual(len(dotations), 5)
        # Annuité pleine = 120000/5 = 24000 ; 1re année = 24000 × 6/12 = 12000.
        self.assertEqual(dotations[0].montant, Decimal('12000.00'))
        # Cumul final = base amortissable exactement.
        self.assertEqual(dotations[-1].cumul, Decimal('120000.00'))
        total = sum((d.montant for d in dotations), Decimal('0'))
        self.assertEqual(total, Decimal('120000.00'))

    def test_sans_mise_en_service_plan_inchange(self):
        immo = make_immo(
            self.co, cout=Decimal('100000'),
            date_acquisition=date(2026, 1, 1), date_mise_en_service=None)
        plan = services.generer_plan_amortissement(
            immo, mode='lineaire', duree_annees=5, date_debut=date(2026, 1, 1))
        dotations = list(plan.dotations.order_by('annee'))
        # Années pleines : 100000/5 = 20000 chacune (comportement historique).
        for dot in dotations:
            self.assertEqual(dot.montant, Decimal('20000.00'))

    def test_dotations_postees_non_regenerees(self):
        immo = make_immo(
            self.co, cout=Decimal('120000'),
            date_acquisition=date(2026, 1, 1),
            date_mise_en_service=date(2026, 7, 1))
        plan = services.generer_plan_amortissement(
            immo, mode='lineaire', duree_annees=5, date_debut=date(2026, 1, 1))
        premiere = plan.dotations.get(annee=2026)
        services.poster_dotation(premiere, user=None)
        premiere.refresh_from_db()
        montant_poste = premiere.montant
        self.assertTrue(premiere.posted)
        # Régénération avec un changement de mise en service ne doit PAS
        # toucher la dotation déjà postée.
        immo.date_mise_en_service = date(2026, 10, 1)
        immo.save(update_fields=['date_mise_en_service'])
        services.generer_plan_amortissement(
            immo, mode='lineaire', duree_annees=5, date_debut=date(2026, 1, 1))
        premiere.refresh_from_db()
        self.assertEqual(premiere.montant, montant_poste)

    def test_degressif_garde_sa_regle_actuelle(self):
        immo = make_immo(
            self.co, cout=Decimal('100000'),
            date_acquisition=date(2026, 1, 1),
            date_mise_en_service=date(2026, 7, 1))
        plan = services.generer_plan_amortissement(
            immo, mode='degressif', duree_annees=5, date_debut=date(2026, 1, 1))
        dotations = list(plan.dotations.order_by('annee'))
        total = sum((d.montant for d in dotations), Decimal('0'))
        self.assertEqual(total, Decimal('100000.00'))
        # Le dégressif n'applique aucun prorata : 1re annuité > linéaire simple
        # (100000/5 = 20000) — comportement inchangé par XACC32.
        self.assertGreater(dotations[0].montant, Decimal('20000.00'))

    def test_date_mise_en_service_effective_property(self):
        immo = make_immo(
            self.co, date_acquisition=date(2026, 3, 15),
            date_mise_en_service=None)
        self.assertEqual(
            immo.date_mise_en_service_effective, date(2026, 3, 15))
        immo.date_mise_en_service = date(2026, 9, 1)
        self.assertEqual(
            immo.date_mise_en_service_effective, date(2026, 9, 1))
