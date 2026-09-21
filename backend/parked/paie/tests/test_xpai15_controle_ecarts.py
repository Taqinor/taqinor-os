"""Tests XPAI15 — Contrôle des écarts avant validation (M vs M-1).

Couvre : ``controle_ecarts`` détecte les salariés manquants/nouveaux, un net
qui double (variation > seuil, avertissement jamais blocage), les HS
anormales, et respecte le seuil paramétrable.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import ElementVariable, PeriodePaie, ProfilPaie
from apps.paie.services import controle_ecarts, ensure_defaults, \
    generer_bulletin, valider_bulletin
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class ControleEcartsTests(TestCase):
    def setUp(self):
        self.co = make_company('xpai15-ecarts')
        ensure_defaults(self.co)
        self.periode_prec = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=5)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def _profil(self, mat, salaire=Decimal('10000')):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule=mat, nom='Nom' + mat, prenom='P')
        return ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=salaire, affilie_cnss=True, affilie_amo=True)

    def _bulletin(self, profil, periode, valider=True):
        b = generer_bulletin(profil, periode)
        if valider:
            valider_bulletin(b)
        return b

    def test_salarie_manquant(self):
        p1 = self._profil('A1')
        self._bulletin(p1, self.periode_prec)
        # Aucun bulletin ce mois-ci pour p1.
        rapport = controle_ecarts(self.periode)
        ids = [item['profil_id'] for item in rapport['salaries_manquants']]
        self.assertIn(p1.id, ids)

    def test_salarie_nouveau(self):
        p1 = self._profil('B1')
        self._bulletin(p1, self.periode, valider=False)
        rapport = controle_ecarts(self.periode)
        ids = [item['profil_id'] for item in rapport['salaries_nouveaux']]
        self.assertIn(p1.id, ids)

    def test_net_qui_double_signale(self):
        p1 = self._profil('C1', salaire=Decimal('10000'))
        self._bulletin(p1, self.periode_prec)
        p1.salaire_base = Decimal('20000')
        p1.save()
        self._bulletin(p1, self.periode, valider=False)
        rapport = controle_ecarts(self.periode)
        ids = [item['profil_id'] for item in rapport['variations_net']]
        self.assertIn(p1.id, ids)

    def test_variation_sous_seuil_non_signalee(self):
        p1 = self._profil('D1', salaire=Decimal('10000'))
        self._bulletin(p1, self.periode_prec)
        p1.salaire_base = Decimal('10100')  # variation minime
        p1.save()
        self._bulletin(p1, self.periode, valider=False)
        rapport = controle_ecarts(self.periode)
        ids = [item['profil_id'] for item in rapport['variations_net']]
        self.assertNotIn(p1.id, ids)

    def test_seuil_paramétrable(self):
        p1 = self._profil('E1', salaire=Decimal('10000'))
        self._bulletin(p1, self.periode_prec)
        p1.salaire_base = Decimal('11000')  # +10%
        p1.save()
        self._bulletin(p1, self.periode, valider=False)
        # Seuil bas (5%) -> signalé.
        rapport_bas = controle_ecarts(self.periode, seuil_pct=Decimal('5'))
        ids_bas = [item['profil_id'] for item in rapport_bas['variations_net']]
        self.assertIn(p1.id, ids_bas)
        # Seuil haut (50%) -> pas signalé.
        rapport_haut = controle_ecarts(self.periode, seuil_pct=Decimal('50'))
        ids_haut = [
            item['profil_id'] for item in rapport_haut['variations_net']]
        self.assertNotIn(p1.id, ids_haut)

    def test_hs_anormales(self):
        p1 = self._profil('F1')
        ElementVariable.objects.create(
            company=self.co, periode=self.periode_prec, profil=p1,
            type=ElementVariable.TYPE_HS, quantite=Decimal('5'))
        self._bulletin(p1, self.periode_prec)
        ElementVariable.objects.create(
            company=self.co, periode=self.periode, profil=p1,
            type=ElementVariable.TYPE_HS, quantite=Decimal('20'))
        self._bulletin(p1, self.periode, valider=False)
        rapport = controle_ecarts(self.periode)
        ids = [item['profil_id'] for item in rapport['hs_anormales']]
        self.assertIn(p1.id, ids)

    def test_hs_normales_non_signalees(self):
        p1 = self._profil('G1')
        ElementVariable.objects.create(
            company=self.co, periode=self.periode_prec, profil=p1,
            type=ElementVariable.TYPE_HS, quantite=Decimal('5'))
        self._bulletin(p1, self.periode_prec)
        ElementVariable.objects.create(
            company=self.co, periode=self.periode, profil=p1,
            type=ElementVariable.TYPE_HS, quantite=Decimal('6'))
        self._bulletin(p1, self.periode, valider=False)
        rapport = controle_ecarts(self.periode)
        ids = [item['profil_id'] for item in rapport['hs_anormales']]
        self.assertNotIn(p1.id, ids)

    def test_pas_de_periode_precedente(self):
        periode_isolee = PeriodePaie.objects.create(
            company=self.co, annee=2020, mois=1)
        p1 = self._profil('H1')
        self._bulletin(p1, periode_isolee, valider=False)
        rapport = controle_ecarts(periode_isolee)
        self.assertEqual(rapport['salaries_manquants'], [])
        ids = [item['profil_id'] for item in rapport['salaries_nouveaux']]
        self.assertIn(p1.id, ids)

    def test_isolation_tenant(self):
        autre = make_company('xpai15-ecarts-autre')
        ensure_defaults(autre)
        periode_autre = PeriodePaie.objects.create(
            company=autre, annee=2026, mois=6)
        rapport = controle_ecarts(periode_autre)
        self.assertEqual(rapport['salaries_manquants'], [])
        self.assertEqual(rapport['salaries_nouveaux'], [])
