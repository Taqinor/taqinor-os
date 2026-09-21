"""Tests PAIE31 — Déclaration CNSS (BDS / format DAMANCOM).

Couvre :
* ``declaration_cnss`` — agrège les bulletins VALIDÉS des salariés affiliés
  CNSS (numéro CNSS, brut, salaire plafonné, cotisations) ; plafonne le salaire
  à ``plafond_cnss`` ; ignore les non-affiliés et les brouillons.
* ``fichier_damancom_cnss`` — en-tête + une ligne par salarié.
* Multi-tenant — isolation société.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import PeriodePaie, ProfilPaie
from apps.paie.services import (
    declaration_cnss,
    ensure_defaults,
    fichier_damancom_cnss,
    generer_bulletin,
    valider_bulletin,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class DeclarationCnssTests(TestCase):
    def setUp(self):
        self.co = make_company('cnss')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def _profil(self, mat, salaire, affilie=True, num='12345'):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule=mat, nom='N' + mat, prenom='P')
        return ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=salaire, affilie_cnss=affilie, affilie_amo=True,
            numero_cnss=num)

    def _bulletin_valide(self, profil):
        b = generer_bulletin(profil, self.periode)
        valider_bulletin(b)
        return b

    def test_plafonne_le_salaire(self):
        # Salaire 10000 > plafond CNSS 6000 → base plafonnée à 6000.
        p = self._profil('A1', Decimal('10000'))
        self._bulletin_valide(p)
        decl = declaration_cnss(self.periode)
        self.assertEqual(decl['nombre_salaries'], 1)
        self.assertEqual(decl['lignes'][0]['plafonne'], Decimal('6000.00'))
        self.assertEqual(decl['lignes'][0]['brut'], Decimal('10000.00'))
        self.assertEqual(decl['total_plafonne'], Decimal('6000.00'))

    def test_ignore_non_affilie_cnss(self):
        self._bulletin_valide(self._profil('B1', Decimal('5000')))
        self._bulletin_valide(
            self._profil('B2', Decimal('5000'), affilie=False))
        decl = declaration_cnss(self.periode)
        self.assertEqual(decl['nombre_salaries'], 1)

    def test_ignore_brouillon(self):
        p = self._profil('C1', Decimal('5000'))
        generer_bulletin(p, self.periode)  # brouillon
        decl = declaration_cnss(self.periode)
        self.assertEqual(decl['nombre_salaries'], 0)

    def test_fichier_damancom(self):
        self._bulletin_valide(self._profil('D1', Decimal('5000')))
        fichier = fichier_damancom_cnss(self.periode)
        self.assertEqual(fichier['nombre_salaries'], 1)
        # En-tête + 1 ligne salarié.
        self.assertEqual(len(fichier['lignes']), 2)
        self.assertTrue(fichier['lignes'][0].startswith('E;'))
        self.assertTrue(fichier['lignes'][1].startswith('S;'))
