"""Tests XPAI10 — Télédéclaration CIMR (fichier préétabli).

Couvre : ``declaration_cimr`` liste les affiliés (taux, base, parts) avec
totaux = lignes bulletins CIMR, détecte les nouveaux affiliés et les
changements de salaire par rapport au mois précédent, et
``fichier_cimr`` exporte le format CSV documenté.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import PeriodePaie, ProfilPaie
from apps.paie.services import (
    declaration_cimr,
    ensure_defaults,
    fichier_cimr,
    generer_bulletin,
    valider_bulletin,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class DeclarationCimrTests(TestCase):
    def setUp(self):
        self.co = make_company('xpai10-cimr')
        ensure_defaults(self.co)
        self.periode_prec = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=5)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def _employe(self, mat, affilie_cimr=True, taux=Decimal('6'),
                 salaire=Decimal('10000')):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule=mat, nom='Nom' + mat, prenom='P')
        return ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=salaire, affilie_cnss=True, affilie_amo=True,
            affilie_cimr=affilie_cimr, taux_cimr_salarial=taux)

    def _bulletin_valide(self, profil, periode):
        b = generer_bulletin(profil, periode)
        valider_bulletin(b)
        return b

    def test_liste_affilies_seulement(self):
        p_cimr = self._employe('A1', affilie_cimr=True)
        p_non = self._employe('A2', affilie_cimr=False)
        self._bulletin_valide(p_cimr, self.periode)
        self._bulletin_valide(p_non, self.periode)
        decl = declaration_cimr(self.periode)
        self.assertEqual(decl['nombre_affilies'], 1)

    def test_totaux_egaux_lignes(self):
        p1 = self._employe('B1')
        b1 = self._bulletin_valide(p1, self.periode)
        decl = declaration_cimr(self.periode)
        self.assertEqual(decl['total_base'], b1.brut)
        self.assertEqual(decl['total_cimr_salariale'], b1.cimr_salariale)

    def test_nouvel_affilie_sans_mois_precedent(self):
        p1 = self._employe('C1')
        self._bulletin_valide(p1, self.periode)
        decl = declaration_cimr(self.periode)
        self.assertTrue(decl['lignes'][0]['nouvel_affilie'])
        self.assertFalse(decl['lignes'][0]['changement_salaire'])

    def test_pas_nouvel_affilie_si_present_mois_precedent(self):
        p1 = self._employe('D1')
        self._bulletin_valide(p1, self.periode_prec)
        self._bulletin_valide(p1, self.periode)
        decl = declaration_cimr(self.periode)
        self.assertFalse(decl['lignes'][0]['nouvel_affilie'])

    def test_changement_salaire_detecte(self):
        p1 = self._employe('E1', salaire=Decimal('8000'))
        self._bulletin_valide(p1, self.periode_prec)
        p1.salaire_base = Decimal('9000')
        p1.save()
        self._bulletin_valide(p1, self.periode)
        decl = declaration_cimr(self.periode)
        self.assertTrue(decl['lignes'][0]['changement_salaire'])

    def test_sans_changement_salaire(self):
        p1 = self._employe('F1', salaire=Decimal('8000'))
        self._bulletin_valide(p1, self.periode_prec)
        self._bulletin_valide(p1, self.periode)
        decl = declaration_cimr(self.periode)
        self.assertFalse(decl['lignes'][0]['changement_salaire'])

    def test_fichier_cimr_export(self):
        p1 = self._employe('G1')
        self._bulletin_valide(p1, self.periode)
        fichier = fichier_cimr(self.periode)
        self.assertEqual(len(fichier['lignes']), 2)  # en-tête + 1 salarié
        self.assertTrue(fichier['lignes'][0].startswith('E;'))
        self.assertTrue(fichier['lignes'][1].startswith('S;'))

    def test_isolation_tenant(self):
        autre = make_company('xpai10-cimr-autre')
        ensure_defaults(autre)
        periode_autre = PeriodePaie.objects.create(
            company=autre, annee=2026, mois=6)
        decl = declaration_cimr(periode_autre)
        self.assertEqual(decl['nombre_affilies'], 0)
