"""Tests XACC16 — Amortissements dérogatoires (double plan comptable / fiscal).

Couvre : une immo en dégressif fiscal / linéaire comptable poste chaque année
la différence exacte (Σ des dérogatoires = 0 sur la vie totale), l'absence de
plan fiscal laisse le comportement FG119 intact, et le posting GL équilibré
(dotation 65941/1351, reprise 1351/7594) est idempotent.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company

from apps.compta import services
from apps.compta.models import (
    DotationDerogatoire, Immobilisation, LigneEcriture, PlanAmortissement,
)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_immo(company, **kwargs):
    defaults = dict(
        libelle='Machine industrielle',
        categorie=Immobilisation.Categorie.MATERIEL,
        cout=Decimal('100000'),
        taux_tva=Decimal('20.00'),
        date_acquisition=date(2026, 1, 1),
    )
    defaults.update(kwargs)
    return Immobilisation.objects.create(company=company, **defaults)


class PlanFiscalTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc16-svc', 'XACC16 Svc')
        self.immo = make_immo(self.co)
        self.plan_compt = services.generer_plan_amortissement(
            self.immo, mode=PlanAmortissement.Mode.LINEAIRE, duree_annees=5,
            base_amortissable=Decimal('100000'), date_debut=date(2026, 1, 1))

    def test_somme_derogatoires_nulle_sur_vie_totale(self):
        plan_fiscal = services.creer_plan_amortissement_fiscal(
            self.plan_compt, mode=PlanAmortissement.Mode.DEGRESSIF,
            duree_annees=5)
        dotations = services.generer_dotations_derogatoires(plan_fiscal)
        total = sum((d.difference for d in dotations), Decimal('0'))
        self.assertEqual(total, Decimal('0.00'))

    def test_difference_exacte_annee_1_degressif_gt_lineaire(self):
        plan_fiscal = services.creer_plan_amortissement_fiscal(
            self.plan_compt, mode=PlanAmortissement.Mode.DEGRESSIF,
            duree_annees=5)
        dotations = services.generer_dotations_derogatoires(plan_fiscal)
        annee1 = [d for d in dotations if d.annee == 2026][0]
        # Dégressif > linéaire en début de vie => différence positive.
        self.assertGreater(annee1.difference, Decimal('0'))
        self.assertEqual(
            annee1.difference,
            (annee1.dotation_fiscale - annee1.dotation_comptable))

    def test_absence_plan_fiscal_comportement_intact(self):
        # Aucun plan fiscal créé pour cette immo : la relation reverse échoue,
        # le plan comptable seul (FG119) reste utilisable normalement.
        self.assertFalse(
            hasattr(self.plan_compt, 'plan_fiscal')
            and PlanAmortissement.objects.filter(
                id=self.plan_compt.id, plan_fiscal__isnull=False).exists())
        self.assertEqual(self.plan_compt.duree_annees, 5)


class PosterDotationDerogatoireTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc16-post', 'XACC16 Post')
        self.immo = make_immo(self.co)
        self.plan_compt = services.generer_plan_amortissement(
            self.immo, mode=PlanAmortissement.Mode.LINEAIRE, duree_annees=5,
            base_amortissable=Decimal('100000'), date_debut=date(2026, 1, 1))
        self.plan_fiscal = services.creer_plan_amortissement_fiscal(
            self.plan_compt, mode=PlanAmortissement.Mode.DEGRESSIF,
            duree_annees=5)
        self.dotations = services.generer_dotations_derogatoires(self.plan_fiscal)

    def test_poster_dotation_positive_ecriture_equilibree(self):
        annee1 = [d for d in self.dotations if d.annee == 2026][0]
        ecriture = services.poster_dotation_derogatoire(annee1)
        lignes = LigneEcriture.objects.filter(ecriture=ecriture)
        debit = sum((line.debit for line in lignes), Decimal('0'))
        credit = sum((line.credit for line in lignes), Decimal('0'))
        self.assertEqual(debit, credit)
        numeros = {line.compte.numero for line in lignes}
        self.assertIn('65941', numeros)
        self.assertIn('1351', numeros)

    def test_poster_reprise_fin_de_vie_ecriture_inverse(self):
        derniere = sorted(self.dotations, key=lambda d: d.annee)[-1]
        self.assertLess(derniere.difference, Decimal('0'))
        ecriture = services.poster_dotation_derogatoire(derniere)
        numeros = {
            line.compte.numero
            for line in LigneEcriture.objects.filter(ecriture=ecriture)}
        self.assertIn('1351', numeros)
        self.assertIn('7594', numeros)

    def test_poster_idempotent(self):
        annee1 = [d for d in self.dotations if d.annee == 2026][0]
        ec1 = services.poster_dotation_derogatoire(annee1)
        annee1.refresh_from_db()
        ec2 = services.poster_dotation_derogatoire(annee1)
        self.assertEqual(ec1.id, ec2.id)

    def test_regeneration_ne_touche_pas_dotation_postee(self):
        annee1 = [d for d in self.dotations if d.annee == 2026][0]
        services.poster_dotation_derogatoire(annee1)
        montant_avant = annee1.difference
        # Regénère : la dotation postée doit rester inchangée.
        services.generer_dotations_derogatoires(self.plan_fiscal)
        annee1.refresh_from_db()
        self.assertEqual(annee1.difference, montant_avant)
        self.assertTrue(annee1.posted)

    def test_isolation_multi_societe(self):
        co_b = make_company('xacc16-b', 'XACC16 B')
        self.assertEqual(
            DotationDerogatoire.objects.filter(company=co_b).count(), 0)
