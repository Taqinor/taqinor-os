"""Tests PAIE33 — Livre de paie + journal de paie → écritures (via compta).

Couvre :
* ``livre_de_paie`` — registre récapitulatif des bulletins VALIDÉS + totaux.
* ``journal_de_paie`` — crée UNE écriture comptable ÉQUILIBRÉE via
  ``compta.services`` (cross-app par la couche services, jamais les models) ;
  None si aucun bulletin validé.
* Multi-tenant — isolation société.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import PeriodePaie, ProfilPaie
from apps.paie.services import (
    ensure_defaults,
    generer_bulletin,
    journal_de_paie,
    livre_de_paie,
    valider_bulletin,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class JournalPaieTests(TestCase):
    def setUp(self):
        self.co = make_company('jp')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def _bulletin_valide(self, mat, salaire=Decimal('10000')):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule=mat, nom='N' + mat, prenom='P')
        profil = ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=salaire, affilie_cnss=True, affilie_amo=True)
        b = generer_bulletin(profil, self.periode)
        valider_bulletin(b)
        return b

    def test_livre_de_paie(self):
        b1 = self._bulletin_valide('A1')
        b2 = self._bulletin_valide('A2')
        livre = livre_de_paie(self.periode)
        self.assertEqual(livre['nombre_salaries'], 2)
        self.assertEqual(livre['totaux']['brut'], b1.brut + b2.brut)
        self.assertEqual(
            livre['totaux']['net_a_payer'], b1.net_a_payer + b2.net_a_payer)

    def test_journal_de_paie_ecriture_equilibree(self):
        self._bulletin_valide('B1')
        ecriture = journal_de_paie(self.periode)
        self.assertIsNotNone(ecriture)
        # L'écriture est équilibrée : Σ débit = Σ crédit.
        lignes = list(ecriture.lignes.all())
        debit = sum((lig.debit for lig in lignes), Decimal('0'))
        credit = sum((lig.credit for lig in lignes), Decimal('0'))
        self.assertEqual(debit, credit)
        self.assertGreater(debit, Decimal('0'))
        self.assertEqual(ecriture.company, self.co)
        self.assertEqual(ecriture.reference, 'PAIE-2026-06')

    def test_journal_de_paie_sans_bulletin(self):
        # Aucun bulletin validé → rien à comptabiliser.
        self.assertIsNone(journal_de_paie(self.periode))

    # ── DC21 — aucun numéro de compte écrit en dur : tout passe par le
    #          référentiel `compta.CompteComptable` (plan comptable unique). ──

    def test_journal_resout_les_comptes_du_referentiel(self):
        """Chaque ligne de l'écriture porte un FK `CompteComptable` réel.

        DC21 : la paie ne stocke jamais un numéro de compte en dur ; elle
        RÉSOUT chaque compte d'imputation par ``compta.services.get_compte``
        contre le plan comptable canonique. On vérifie qu'aucune ligne ne porte
        un compte « inventé » hors référentiel.
        """
        from apps.compta.models import CompteComptable

        self._bulletin_valide('C1')
        ecriture = journal_de_paie(self.periode)
        self.assertIsNotNone(ecriture)
        comptes_referentiel = set(
            CompteComptable.objects
            .filter(company=self.co)
            .values_list('id', flat=True))
        lignes = list(ecriture.lignes.all())
        self.assertGreater(len(lignes), 0)
        for ligne in lignes:
            # Le compte est un FK réel (jamais None / jamais une chaîne brute).
            self.assertIsNotNone(ligne.compte_id)
            self.assertIn(ligne.compte_id, comptes_referentiel)
            self.assertEqual(ligne.compte.company_id, self.co.id)

    def test_comptes_paie_existent_dans_le_plan(self):
        """Tous les comptes d'imputation paie sont des numéros du référentiel.

        Garantit que les clés ``_COMPTE_*`` sont de simples NUMÉROS résolus
        contre le plan comptable (semé au besoin), pas des comptes ad-hoc.
        """
        from apps.compta.services import get_compte
        from apps.paie import services as paie_services

        numeros = [
            paie_services._COMPTE_REMUNERATION,
            paie_services._COMPTE_CHARGES_SOCIALES,
            paie_services._COMPTE_CNSS,
            paie_services._COMPTE_IR,
            paie_services._COMPTE_CIMR,
            paie_services._COMPTE_NET,
        ]
        # Déclenche le seed idempotent via une écriture, puis vérifie.
        self._bulletin_valide('D1')
        journal_de_paie(self.periode)
        for num in numeros:
            self.assertIsNotNone(
                get_compte(self.co, num),
                f'Compte {num} absent du plan comptable (référentiel DC21).')
