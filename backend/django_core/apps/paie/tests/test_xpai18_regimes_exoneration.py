"""Tests XPAI18 — Régimes stagiaire / ANAPEC / TAHFIZ (exonération IR).

Couvre : un stagiaire dans la fenêtre paie 0 IR sous le plafond, l'excédent
au-delà du plafond reste imposé, l'expiration de la fenêtre réintègre le
profil au régime normal (et notifie best-effort), et le montant exonéré est
tracé sur le bulletin (visible dans l'état IR 9421).
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import PeriodePaie, ProfilPaie
from apps.paie.services import (
    ensure_defaults, etat_ir_9421, expirer_regimes_echus, generer_bulletin,
    montant_exonere_regime_profil, regime_actif_a_la_date, valider_bulletin,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class RegimeActifTests(TestCase):
    def setUp(self):
        self.co = make_company('xpai18-actif')
        ensure_defaults(self.co)
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='S1', nom='Stag', prenom='I')

    def _profil(self, **kwargs):
        return ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('5000'), affilie_cnss=True, affilie_amo=True,
            **kwargs)

    def test_regime_aucun_jamais_actif(self):
        profil = self._profil()
        self.assertFalse(regime_actif_a_la_date(profil, date(2026, 6, 1)))

    def test_regime_actif_dans_la_fenetre(self):
        profil = self._profil(
            regime_exoneration=ProfilPaie.REGIME_STAGIAIRE,
            regime_date_debut=date(2026, 1, 1),
            regime_date_fin=date(2026, 12, 31))
        self.assertTrue(regime_actif_a_la_date(profil, date(2026, 6, 15)))

    def test_regime_expire_hors_fenetre(self):
        profil = self._profil(
            regime_exoneration=ProfilPaie.REGIME_STAGIAIRE,
            regime_date_debut=date(2025, 1, 1),
            regime_date_fin=date(2025, 12, 31))
        self.assertFalse(regime_actif_a_la_date(profil, date(2026, 6, 1)))

    def test_regime_pas_encore_demarre(self):
        profil = self._profil(
            regime_exoneration=ProfilPaie.REGIME_ANAPEC,
            regime_date_debut=date(2027, 1, 1))
        self.assertFalse(regime_actif_a_la_date(profil, date(2026, 6, 1)))


class MontantExonereTests(TestCase):
    def setUp(self):
        self.co = make_company('xpai18-montant')
        ensure_defaults(self.co)
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='S2', nom='Stag', prenom='II')

    def test_sous_plafond_tout_exonere(self):
        profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('4000'),
            regime_exoneration=ProfilPaie.REGIME_STAGIAIRE,
            regime_date_debut=date(2026, 1, 1),
            regime_date_fin=date(2026, 12, 31),
            regime_plafond_mensuel=Decimal('6000'))
        exonere = montant_exonere_regime_profil(
            profil, date(2026, 6, 1), Decimal('4000'))
        self.assertEqual(exonere, Decimal('4000.00'))

    def test_au_dela_plafond_excedent_reste(self):
        profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('9000'),
            regime_exoneration=ProfilPaie.REGIME_STAGIAIRE,
            regime_date_debut=date(2026, 1, 1),
            regime_date_fin=date(2026, 12, 31),
            regime_plafond_mensuel=Decimal('6000'))
        exonere = montant_exonere_regime_profil(
            profil, date(2026, 6, 1), Decimal('9000'))
        self.assertEqual(exonere, Decimal('6000.00'))


class BulletinAvecRegimeTests(TestCase):
    def setUp(self):
        self.co = make_company('xpai18-bulletin')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='S3', nom='Stag', prenom='III')

    def test_stagiaire_sous_plafond_zero_ir(self):
        profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('4000'), affilie_cnss=True, affilie_amo=True,
            regime_exoneration=ProfilPaie.REGIME_STAGIAIRE,
            regime_date_debut=date(2026, 1, 1),
            regime_date_fin=date(2026, 12, 31),
            regime_plafond_mensuel=Decimal('6000'))
        bulletin = generer_bulletin(profil, self.periode)
        self.assertEqual(bulletin.ir, Decimal('0.00'))
        self.assertGreater(bulletin.montant_exonere_regime, Decimal('0'))

    def test_regime_normal_paye_ir_normalement(self):
        profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('12000'), affilie_cnss=True, affilie_amo=True)
        bulletin = generer_bulletin(profil, self.periode)
        self.assertGreater(bulletin.ir, Decimal('0'))
        self.assertEqual(bulletin.montant_exonere_regime, Decimal('0.00'))

    def test_excedent_au_dela_plafond_impose(self):
        dossier2 = DossierEmploye.objects.create(
            company=self.co, matricule='S4', nom='Stag', prenom='IV')
        profil_normal = ProfilPaie.objects.create(
            company=self.co, employe=dossier2,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('12000'), affilie_cnss=True, affilie_amo=True)
        bulletin_normal = generer_bulletin(profil_normal, self.periode)

        dossier3 = DossierEmploye.objects.create(
            company=self.co, matricule='S5', nom='Stag', prenom='V')
        profil_regime = ProfilPaie.objects.create(
            company=self.co, employe=dossier3,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('12000'), affilie_cnss=True, affilie_amo=True,
            regime_exoneration=ProfilPaie.REGIME_TAHFIZ,
            regime_date_debut=date(2026, 1, 1),
            regime_date_fin=date(2026, 12, 31),
            regime_plafond_mensuel=Decimal('6000'))
        bulletin_regime = generer_bulletin(profil_regime, self.periode)
        # L'IR du régime (excédent seulement imposé) doit être STRICTEMENT
        # inférieur à celui du même salaire sans régime.
        self.assertLess(bulletin_regime.ir, bulletin_normal.ir)
        self.assertGreater(bulletin_regime.ir, Decimal('0'))

    def test_9421_expose_montant_exonere(self):
        profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('4000'), affilie_cnss=True, affilie_amo=True,
            regime_exoneration=ProfilPaie.REGIME_STAGIAIRE,
            regime_date_debut=date(2026, 1, 1),
            regime_date_fin=date(2026, 12, 31))
        bulletin = generer_bulletin(profil, self.periode)
        valider_bulletin(bulletin)
        etat = etat_ir_9421(self.periode)
        self.assertEqual(len(etat['lignes']), 1)
        self.assertGreater(
            etat['lignes'][0]['montant_exonere_regime'], Decimal('0'))
        self.assertGreater(etat['total_exonere_regime'], Decimal('0'))


class ExpirerRegimesEchusTests(TestCase):
    def setUp(self):
        self.co = make_company('xpai18-expiration')
        ensure_defaults(self.co)
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='S6', nom='Stag', prenom='VI')

    def test_bascule_profil_expire(self):
        profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('4000'),
            regime_exoneration=ProfilPaie.REGIME_STAGIAIRE,
            regime_date_debut=date(2024, 1, 1),
            regime_date_fin=date(2024, 12, 31))
        bascules = expirer_regimes_echus(self.co, today=date(2026, 1, 1))
        self.assertEqual(len(bascules), 1)
        profil.refresh_from_db()
        self.assertEqual(profil.regime_exoneration, ProfilPaie.REGIME_AUCUN)

    def test_ne_touche_pas_profil_dans_la_fenetre(self):
        profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('4000'),
            regime_exoneration=ProfilPaie.REGIME_ANAPEC,
            regime_date_debut=date(2026, 1, 1),
            regime_date_fin=date(2026, 12, 31))
        bascules = expirer_regimes_echus(self.co, today=date(2026, 6, 1))
        self.assertEqual(len(bascules), 0)
        profil.refresh_from_db()
        self.assertEqual(profil.regime_exoneration, ProfilPaie.REGIME_ANAPEC)

    def test_idempotent_ne_reprend_pas_profil_deja_normal(self):
        ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('4000'),
            regime_exoneration=ProfilPaie.REGIME_STAGIAIRE,
            regime_date_debut=date(2024, 1, 1),
            regime_date_fin=date(2024, 12, 31))
        expirer_regimes_echus(self.co, today=date(2026, 1, 1))
        bascules2 = expirer_regimes_echus(self.co, today=date(2026, 1, 1))
        self.assertEqual(len(bascules2), 0)
