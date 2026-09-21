"""Tests XPAI5 — État des charges sociales + rapprochement paie↔GL.

Couvre : ``etat_des_charges`` consolide CNSS+AMO/IR/CIMR (parts salariale ET
patronale) sur une période, ``rapprochement_paie_gl`` prouve que les totaux du
livre de paie égalent l'écriture postée par ``journal_de_paie`` (écart = 0 sur
une période saine), et détecte un écart quand le GL diverge (ex. écriture non
postée).
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import PeriodePaie, ProfilPaie
from apps.paie.services import (
    ensure_defaults,
    etat_des_charges,
    generer_bulletin,
    journal_de_paie,
    rapprochement_paie_gl,
    valider_bulletin,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class EtatDesChargesTests(TestCase):
    def setUp(self):
        self.co = make_company('xpai5-etat')
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

    def test_organismes_consolides(self):
        self._bulletin_valide('A1')
        etat = etat_des_charges(self.periode)
        codes = {o['code'] for o in etat['organismes']}
        self.assertEqual(codes, {'cnss_amo', 'ir', 'cimr'})
        cnss_org = next(o for o in etat['organismes'] if o['code'] == 'cnss_amo')
        self.assertGreater(cnss_org['salarial'], 0)
        self.assertGreater(cnss_org['patronal'], 0)
        self.assertEqual(
            cnss_org['total'], cnss_org['salarial'] + cnss_org['patronal'])

    def test_total_general_somme_organismes(self):
        self._bulletin_valide('A2')
        etat = etat_des_charges(self.periode)
        somme = sum((o['total'] for o in etat['organismes']), Decimal('0.00'))
        self.assertEqual(etat['total_general'], somme)

    def test_vide_sans_bulletin(self):
        etat = etat_des_charges(self.periode)
        self.assertEqual(etat['total_general'], Decimal('0.00'))


class RapprochementPaieGlTests(TestCase):
    def setUp(self):
        self.co = make_company('xpai5-gl')
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

    def test_ecart_zero_apres_journal_de_paie(self):
        self._bulletin_valide('B1')
        ecriture = journal_de_paie(self.periode)
        self.assertIsNotNone(ecriture)
        rap = rapprochement_paie_gl(self.periode)
        self.assertTrue(rap['coherent'])
        self.assertEqual(rap['ecart_total'], Decimal('0.00'))
        for ligne in rap['lignes']:
            self.assertEqual(ligne['ecart'], Decimal('0.00'))

    def test_ecart_detecte_sans_ecriture_postee(self):
        # Bulletin validé mais journal_de_paie jamais appelé -> le GL est
        # vide : le rapprochement doit SIGNALER l'écart (pas un skip).
        self._bulletin_valide('B2')
        rap = rapprochement_paie_gl(self.periode)
        self.assertFalse(rap['coherent'])
        self.assertNotEqual(rap['ecart_total'], Decimal('0.00'))

    def test_isolation_tenant(self):
        self._bulletin_valide('B3')
        journal_de_paie(self.periode)
        autre = make_company('xpai5-gl-autre')
        ensure_defaults(autre)
        periode_autre = PeriodePaie.objects.create(
            company=autre, annee=2026, mois=6)
        rap_autre = rapprochement_paie_gl(periode_autre)
        # Aucune donnée dans l'autre société -> tout à zéro, cohérent.
        self.assertTrue(rap_autre['coherent'])
        self.assertEqual(rap_autre['ecart_total'], Decimal('0.00'))
