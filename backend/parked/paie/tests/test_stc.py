"""Tests XPAI1 — Solde de tout compte (STC).

Couvre :
* le barème art. 53 (chaque tranche d'ancienneté) ;
* l'exonération IR de l'indemnité de licenciement (sous/au-dessus du
  plafond) ;
* la génération du bulletin STC (immuabilité une fois validé, avances
  soldées) ;
* l'isolation tenant.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import AvanceSalarie, BulletinPaie, PeriodePaie, ProfilPaie
from apps.paie.services import (
    ensure_defaults,
    exoneration_ir_indemnite_licenciement,
    generer_bulletin_stc,
    indemnite_licenciement_art53,
    indemnite_preavis,
    parametre_en_vigueur,
    valider_bulletin,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


class BaremeArt53Tests(TestCase):
    """Chaque tranche du barème légal de licenciement (96/144/192/240 h)."""

    def test_tranche_1_moins_de_5_ans(self):
        # 3 ans x 96h x taux horaire 50 = 14400
        montant = indemnite_licenciement_art53(Decimal('3'), Decimal('50'))
        self.assertEqual(montant, Decimal('14400.00'))

    def test_tranche_2_6_a_10_ans(self):
        # 5 ans x 96h + 3 ans x 144h = 480 + 432 = 912h x 50 = 45600
        montant = indemnite_licenciement_art53(Decimal('8'), Decimal('50'))
        self.assertEqual(montant, Decimal('45600.00'))

    def test_tranche_3_11_a_15_ans(self):
        # 5x96 + 5x144 + 2x192 = 480+720+384=1584h x 50 = 79200
        montant = indemnite_licenciement_art53(Decimal('12'), Decimal('50'))
        self.assertEqual(montant, Decimal('79200.00'))

    def test_tranche_4_plus_de_15_ans(self):
        # 5x96 + 5x144 + 5x192 + 5x240 = 480+720+960+1200=3360h x 50 = 168000
        montant = indemnite_licenciement_art53(Decimal('20'), Decimal('50'))
        self.assertEqual(montant, Decimal('168000.00'))

    def test_anciennete_nulle(self):
        self.assertEqual(
            indemnite_licenciement_art53(Decimal('0'), Decimal('50')),
            Decimal('0.00'))

    def test_taux_horaire_nul(self):
        self.assertEqual(
            indemnite_licenciement_art53(Decimal('10'), Decimal('0')),
            Decimal('0.00'))


class ExonerationIRTests(TestCase):
    def setUp(self):
        self.co = make_company('stc-ir')
        ensure_defaults(self.co)
        self.parametre = parametre_en_vigueur(self.co, date(2026, 6, 1))

    def test_sous_le_plafond_totalement_exoneree(self):
        exoneree, imposable = exoneration_ir_indemnite_licenciement(
            Decimal('500000'), self.parametre)
        self.assertEqual(exoneree, Decimal('500000.00'))
        self.assertEqual(imposable, Decimal('0.00'))

    def test_au_dessus_du_plafond_excedent_imposable(self):
        exoneree, imposable = exoneration_ir_indemnite_licenciement(
            Decimal('1200000'), self.parametre)
        self.assertEqual(exoneree, Decimal('1000000.00'))
        self.assertEqual(imposable, Decimal('200000.00'))
        self.assertEqual(exoneree + imposable, Decimal('1200000.00'))

    def test_indemnite_nulle(self):
        exoneree, imposable = exoneration_ir_indemnite_licenciement(
            Decimal('0'), self.parametre)
        self.assertEqual(exoneree, Decimal('0.00'))
        self.assertEqual(imposable, Decimal('0.00'))

    def test_sans_parametre_defaut_1000000(self):
        exoneree, imposable = exoneration_ir_indemnite_licenciement(
            Decimal('1100000'), None)
        self.assertEqual(exoneree, Decimal('1000000.00'))
        self.assertEqual(imposable, Decimal('100000.00'))


class IndemnitePreavisTests(TestCase):
    def test_un_mois_par_defaut(self):
        self.assertEqual(
            indemnite_preavis(Decimal('10000')), Decimal('10000.00'))

    def test_deux_mois(self):
        self.assertEqual(
            indemnite_preavis(Decimal('10000'), mois_preavis=2),
            Decimal('20000.00'))

    def test_zero_mois_aucune_indemnite(self):
        self.assertEqual(
            indemnite_preavis(Decimal('10000'), mois_preavis=0),
            Decimal('0.00'))


class GenererBulletinSTCTests(TestCase):
    def setUp(self):
        self.co = make_company('stc-gen')
        ensure_defaults(self.co)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def _profil(self, mat='S1', date_embauche=date(2015, 1, 1)):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule=mat, nom='Nom' + mat, prenom='P',
            date_embauche=date_embauche,
            date_sortie=date(2026, 6, 15),
            motif_sortie=DossierEmploye.MotifSortie.LICENCIEMENT)
        return ProfilPaie.objects.create(
            company=self.co, employe=dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('8000'),
            affilie_cnss=True, affilie_amo=True)

    def test_cree_bulletin_stc_brouillon(self):
        profil = self._profil()
        bulletin = generer_bulletin_stc(profil, self.periode)
        self.assertEqual(bulletin.type_bulletin, BulletinPaie.TYPE_STC)
        self.assertEqual(bulletin.statut, BulletinPaie.STATUT_BROUILLON)
        self.assertGreater(bulletin.net_a_payer, Decimal('0'))
        # Motif repris du dossier RH (motif de sortie) quand non fourni.
        self.assertEqual(bulletin.motif, DossierEmploye.MotifSortie.LICENCIEMENT)

    def test_lignes_indemnites_presentes(self):
        profil = self._profil()
        bulletin = generer_bulletin_stc(profil, self.periode)
        codes = set(bulletin.lignes.values_list('code', flat=True))
        self.assertIn('STC_LICENCIEMENT', codes)

    def test_avances_soldees_a_la_validation(self):
        profil = self._profil()
        AvanceSalarie.objects.create(
            company=self.co, profil=profil,
            type=AvanceSalarie.TYPE_AVANCE,
            montant_total=Decimal('1000'), montant_echeance=Decimal('1000'),
            nombre_echeances=1, date_debut=date(2026, 1, 1))
        bulletin = generer_bulletin_stc(profil, self.periode)
        valider_bulletin(bulletin)
        avance = AvanceSalarie.objects.get(profil=profil)
        self.assertEqual(avance.montant_rembourse, Decimal('1000.00'))
        self.assertTrue(avance.soldee)

    def test_immuable_une_fois_valide(self):
        profil = self._profil()
        bulletin = generer_bulletin_stc(profil, self.periode)
        valider_bulletin(bulletin)
        bulletin.refresh_from_db()
        self.assertEqual(bulletin.statut, BulletinPaie.STATUT_VALIDE)
        with self.assertRaises(BulletinPaie.BulletinVerrouille):
            generer_bulletin_stc(profil, self.periode)

    def test_periode_cloturee_refuse(self):
        profil = self._profil()
        self.periode.statut = PeriodePaie.STATUT_CLOTUREE
        self.periode.save(update_fields=['statut'])
        with self.assertRaises(BulletinPaie.BulletinVerrouille):
            generer_bulletin_stc(profil, self.periode)

    def test_isolation_tenant(self):
        co_b = make_company('stc-gen-b')
        ensure_defaults(co_b)
        periode_b = PeriodePaie.objects.create(
            company=co_b, annee=2026, mois=6)
        profil_a = self._profil()
        with self.assertRaises(ValueError):
            generer_bulletin_stc(profil_a, periode_b)
