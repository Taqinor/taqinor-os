"""Tests PAIE34 — PDF bulletin conforme + attestations (salaire/travail/domic.).

Couvre (au niveau HTML, indépendant de WeasyPrint) :
* ``render_bulletin_html`` — le bulletin reprend le salarié, la période, les
  lignes et le net à payer.
* ``render_attestation_html`` — chaque type d'attestation (salaire/travail/
  domiciliation) produit le bon titre + corps ; type inconnu → ValueError.
* ``_fmt`` — formatage des montants avec séparateur de milliers.
* Multi-tenant — les helpers ne lisent que des champs publics.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie import builders
from apps.paie.models import PeriodePaie, ProfilPaie
from apps.paie.services import (
    ensure_defaults,
    generer_bulletin,
    valider_bulletin,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class FormatTests(TestCase):
    def test_fmt_milliers(self):
        self.assertEqual(builders._fmt(Decimal('1234.5')), '1 234,50')
        self.assertEqual(builders._fmt(Decimal('0')), '0,00')
        self.assertEqual(builders._fmt(Decimal('-500')), '-500,00')


class BulletinHtmlTests(TestCase):
    def setUp(self):
        self.co = make_company('pdf')
        ensure_defaults(self.co)
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='PDF1', nom='Salarié', prenom='Test')
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'), rib='RIB123', banque='BMCE',
            numero_cnss='99887766', affilie_cnss=True, affilie_amo=True)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        self.bulletin = generer_bulletin(self.profil, self.periode)
        valider_bulletin(self.bulletin)

    def test_bulletin_html(self):
        html = builders.render_bulletin_html(self.bulletin)
        self.assertIn('Bulletin de paie', html)
        self.assertIn('Salarié Test', html)
        self.assertIn('juin 2026', html)
        self.assertIn('99887766', html)
        # Au moins la ligne Salaire de base.
        self.assertIn('Salaire de base', html)
        self.assertIn('Net à payer', html)

    def test_attestation_salaire(self):
        html = builders.render_attestation_html(
            builders.TYPE_SALAIRE, self.profil, bulletin=self.bulletin)
        self.assertIn('Attestation de salaire', html)
        self.assertIn('Salarié Test', html)

    def test_attestation_travail(self):
        html = builders.render_attestation_html(
            builders.TYPE_TRAVAIL, self.profil)
        self.assertIn('Attestation de travail', html)
        self.assertIn('fait', html)

    def test_attestation_domiciliation(self):
        html = builders.render_attestation_html(
            builders.TYPE_DOMICILIATION, self.profil)
        self.assertIn('domiciliation irrévocable', html.lower())
        self.assertIn('RIB123', html)
        self.assertIn('BMCE', html)

    def test_type_inconnu(self):
        with self.assertRaises(ValueError):
            builders.render_attestation_html('inconnu', self.profil)
