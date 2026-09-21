"""Tests XPAI3 — Mutuelle / prévoyance / assurance groupe.

Couvre : lignes salariale + patronale sur le bulletin d'un profil adhérent,
la baisse de l'IR quand le régime est déductible, l'absence d'effet pour un
profil non adhérent, et l'isolation tenant.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import AdhesionMutuelle, PeriodePaie, ProfilPaie, RegimeMutuelle
from apps.paie.services import (
    calculer_bulletin,
    ensure_defaults,
    mutuelle_du_profil,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class MutuelleDuProfilTests(TestCase):
    def setUp(self):
        self.co = make_company('mut-helper')
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='M1', nom='Nom', prenom='P')
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'))

    def test_sans_adhesion_zero(self):
        sal, pat, deductible = mutuelle_du_profil(self.profil, Decimal('10000'))
        self.assertEqual(sal, Decimal('0.00'))
        self.assertEqual(pat, Decimal('0.00'))
        self.assertFalse(deductible)

    def test_mode_pourcentage(self):
        regime = RegimeMutuelle.objects.create(
            company=self.co, libelle='Mutuelle standard',
            mode=RegimeMutuelle.MODE_POURCENTAGE,
            part_salariale=Decimal('2'), part_patronale=Decimal('3'))
        AdhesionMutuelle.objects.create(
            company=self.co, profil=self.profil, regime=regime,
            date_debut='2026-01-01')
        self.profil.refresh_from_db()
        sal, pat, deductible = mutuelle_du_profil(self.profil, Decimal('10000'))
        self.assertEqual(sal, Decimal('200.00'))
        self.assertEqual(pat, Decimal('300.00'))
        self.assertTrue(deductible)

    def test_mode_fixe(self):
        regime = RegimeMutuelle.objects.create(
            company=self.co, libelle='Mutuelle forfait',
            mode=RegimeMutuelle.MODE_FIXE,
            part_salariale=Decimal('150'), part_patronale=Decimal('250'))
        AdhesionMutuelle.objects.create(
            company=self.co, profil=self.profil, regime=regime,
            date_debut='2026-01-01')
        self.profil.refresh_from_db()
        sal, pat, _ = mutuelle_du_profil(self.profil, Decimal('10000'))
        self.assertEqual(sal, Decimal('150.00'))
        self.assertEqual(pat, Decimal('250.00'))


class MutuelleBulletinTests(TestCase):
    def setUp(self):
        self.co = make_company('mut-bulletin')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='M2', nom='Nom', prenom='P')
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('12000'),
            affilie_cnss=True, affilie_amo=True)

    def test_lignes_mutuelle_sur_bulletin(self):
        regime = RegimeMutuelle.objects.create(
            company=self.co, libelle='Mutuelle groupe',
            mode=RegimeMutuelle.MODE_POURCENTAGE,
            part_salariale=Decimal('2'), part_patronale=Decimal('3'),
            deductible_net_imposable=True)
        AdhesionMutuelle.objects.create(
            company=self.co, profil=self.profil, regime=regime,
            date_debut='2026-01-01')
        self.profil.refresh_from_db()
        resultat = calculer_bulletin(self.profil, self.periode)
        codes = {ligne['code'] for ligne in resultat['lignes']}
        self.assertIn('MUTUELLE_SAL', codes)
        self.assertIn('MUTUELLE_PAT', codes)
        self.assertGreater(resultat['mutuelle_salariale'], Decimal('0'))
        self.assertGreater(resultat['mutuelle_patronale'], Decimal('0'))

    def test_ir_baisse_quand_deductible(self):
        base = calculer_bulletin(self.profil, self.periode)
        regime = RegimeMutuelle.objects.create(
            company=self.co, libelle='Mutuelle déductible',
            mode=RegimeMutuelle.MODE_POURCENTAGE,
            part_salariale=Decimal('5'), part_patronale=Decimal('5'),
            deductible_net_imposable=True)
        AdhesionMutuelle.objects.create(
            company=self.co, profil=self.profil, regime=regime,
            date_debut='2026-01-01')
        self.profil.refresh_from_db()
        avec_mutuelle = calculer_bulletin(self.profil, self.periode)
        self.assertLessEqual(avec_mutuelle['ir'], base['ir'])
        self.assertLess(
            avec_mutuelle['net_imposable'], base['net_imposable'])

    def test_non_deductible_ne_change_pas_net_imposable(self):
        base = calculer_bulletin(self.profil, self.periode)
        regime = RegimeMutuelle.objects.create(
            company=self.co, libelle='Mutuelle non déductible',
            mode=RegimeMutuelle.MODE_POURCENTAGE,
            part_salariale=Decimal('5'), part_patronale=Decimal('5'),
            deductible_net_imposable=False)
        AdhesionMutuelle.objects.create(
            company=self.co, profil=self.profil, regime=regime,
            date_debut='2026-01-01')
        self.profil.refresh_from_db()
        avec_mutuelle = calculer_bulletin(self.profil, self.periode)
        self.assertEqual(
            avec_mutuelle['net_imposable'], base['net_imposable'])

    def test_charges_patronales_incluent_mutuelle(self):
        base = calculer_bulletin(self.profil, self.periode)
        regime = RegimeMutuelle.objects.create(
            company=self.co, libelle='Mutuelle charge',
            mode=RegimeMutuelle.MODE_FIXE,
            part_salariale=Decimal('100'), part_patronale=Decimal('200'))
        AdhesionMutuelle.objects.create(
            company=self.co, profil=self.profil, regime=regime,
            date_debut='2026-01-01')
        self.profil.refresh_from_db()
        avec_mutuelle = calculer_bulletin(self.profil, self.periode)
        self.assertEqual(
            avec_mutuelle['charges_patronales'],
            base['charges_patronales'] + Decimal('200.00'))


class MutuelleApiIsolationTests(TestCase):
    def test_isolation_tenant(self):
        co_a = make_company('mut-api-a')
        co_b = make_company('mut-api-b')
        RegimeMutuelle.objects.create(
            company=co_a, libelle='Régime A',
            part_salariale=Decimal('2'), part_patronale=Decimal('3'))
        self.assertEqual(
            RegimeMutuelle.objects.filter(company=co_b).count(), 0)
        self.assertEqual(
            RegimeMutuelle.objects.filter(company=co_a).count(), 1)
