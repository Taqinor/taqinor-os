"""Tests XPAI14 — Indemnités journalières CNSS (maladie/maternité).

Couvre : un bulletin avec 10 jours d'arrêt CNSS déduit les jours (comme une
absence non rémunérée) et ne cotise pas sur la fraction non travaillée,
``arrets_cnss_periode``/``attestation_salaire_ij_cnss`` agrègent les arrêts
de la période, et le PDF attestation de salaire IJ CNSS est généré.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie import builders
from apps.paie.models import ElementVariable, PeriodePaie, ProfilPaie
from apps.paie.services import (
    arrets_cnss_periode,
    attestation_salaire_ij_cnss,
    calculer_bulletin,
    calculer_salaire_base_periode,
    ensure_defaults,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


def make_setup(slug):
    co = make_company(slug)
    ensure_defaults(co)
    dossier = DossierEmploye.objects.create(
        company=co, matricule='X1', nom='Test', prenom='Arret')
    profil = ProfilPaie.objects.create(
        company=co, employe=dossier,
        type_remuneration=ProfilPaie.TYPE_MENSUEL,
        salaire_base=Decimal('26000'),  # 1000/jour sur 26 jours
        jours_travail_mensuel=26, affilie_cnss=True, affilie_amo=True)
    periode = PeriodePaie.objects.create(company=co, annee=2026, mois=6)
    return co, profil, periode


class ArretCnssBulletinTests(TestCase):
    def setUp(self):
        self.co, self.profil, self.periode = make_setup('arret-bulletin')

    def test_10_jours_arret_deduit_jours_et_cnss(self):
        ElementVariable.objects.create(
            company=self.co, periode=self.periode, profil=self.profil,
            type=ElementVariable.TYPE_ABSENCE, quantite=Decimal('10'),
            remunere=False,
            categorie_absence=ElementVariable.ABSENCE_MALADIE_CNSS)
        # Proration : 26000 × (26-10)/26 = 16000.
        base = calculer_salaire_base_periode(self.profil, self.periode)
        self.assertEqual(base, Decimal('16000.00'))
        res = calculer_bulletin(self.profil, self.periode)
        # La cotisation CNSS est calculée sur le brut RÉDUIT (16000), pas
        # sur le plein salaire (26000) — pas de cotisation sur l'indemnité
        # CNSS elle-même (versée par la CNSS, hors paie).
        self.assertLess(res['brut'], Decimal('26000.00'))
        self.assertGreater(res['cnss_salariale'], Decimal('0'))

    def test_arret_maternite_egalement_neutralise(self):
        ElementVariable.objects.create(
            company=self.co, periode=self.periode, profil=self.profil,
            type=ElementVariable.TYPE_ABSENCE, quantite=Decimal('5'),
            remunere=False,
            categorie_absence=ElementVariable.ABSENCE_MATERNITE_CNSS)
        base = calculer_salaire_base_periode(self.profil, self.periode)
        self.assertEqual(base, Decimal('21000.00'))  # 26000*(26-5)/26


class ArretsCnssPeriodeTests(TestCase):
    def setUp(self):
        self.co, self.profil, self.periode = make_setup('arret-periode')

    def test_liste_arrets_cnss_seulement(self):
        ElementVariable.objects.create(
            company=self.co, periode=self.periode, profil=self.profil,
            type=ElementVariable.TYPE_ABSENCE, quantite=Decimal('3'),
            categorie_absence=ElementVariable.ABSENCE_MALADIE_CNSS)
        ElementVariable.objects.create(
            company=self.co, periode=self.periode, profil=self.profil,
            type=ElementVariable.TYPE_ABSENCE, quantite=Decimal('2'),
            categorie_absence=ElementVariable.ABSENCE_AUCUNE)
        arrets = arrets_cnss_periode(self.profil, self.periode)
        self.assertEqual(len(arrets), 1)
        self.assertEqual(arrets[0]['jours'], Decimal('3'))

    def test_attestation_agrege_jours_et_categorie(self):
        ElementVariable.objects.create(
            company=self.co, periode=self.periode, profil=self.profil,
            type=ElementVariable.TYPE_ABSENCE, quantite=Decimal('10'),
            categorie_absence=ElementVariable.ABSENCE_MALADIE_CNSS)
        ctx = attestation_salaire_ij_cnss(self.profil, self.periode)
        self.assertEqual(ctx['jours_arret'], Decimal('10'))
        self.assertEqual(ctx['type_arret_libelle'], 'arrêt maladie')
        self.assertEqual(ctx['brut_reference'], Decimal('26000.00'))

    def test_aucun_arret_jours_zero(self):
        ctx = attestation_salaire_ij_cnss(self.profil, self.periode)
        self.assertEqual(ctx['jours_arret'], Decimal('0'))


class AttestationIjCnssPdfTests(TestCase):
    def setUp(self):
        self.co, self.profil, self.periode = make_setup('arret-pdf')
        ElementVariable.objects.create(
            company=self.co, periode=self.periode, profil=self.profil,
            type=ElementVariable.TYPE_ABSENCE, quantite=Decimal('7'),
            categorie_absence=ElementVariable.ABSENCE_MALADIE_CNSS)

    def test_html_genere_sans_erreur(self):
        arret_cnss = attestation_salaire_ij_cnss(self.profil, self.periode)
        html = builders.render_attestation_html(
            builders.TYPE_ATTESTATION_IJ_CNSS, self.profil,
            arret_cnss=arret_cnss)
        self.assertIn('IJ CNSS', html)
        self.assertIn('7', html)

    def test_type_dans_attestation_types(self):
        self.assertIn(
            builders.TYPE_ATTESTATION_IJ_CNSS, builders.ATTESTATION_TYPES)
