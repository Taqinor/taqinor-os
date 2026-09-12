"""Tests NTPAY8 — Barèmes & paramètres versionnés PAR PAYS.

Couvre : deux pays actifs ont chacun leur barème/plafonds, sélectionnés selon
``profil.pays`` ; le comportement MONO-PAYS marocain reste identique (jeux sans
pays servis aux profils sans pays comme aux profils MA) ; un pays étranger ne
retombe JAMAIS sur le barème marocain ; le seed accepte un pays ; l'isolation
société tient.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.paie.models import (
    BaremeIR, ParametrePaie, PaysPaie, PeriodePaie, ProfilPaie, TrancheIR,
)
from apps.paie.services import (
    bareme_en_vigueur,
    calculer_bulletin,
    ensure_defaults,
    ensure_pays_paie_standard,
    parametre_en_vigueur,
)
from apps.rh.models import DossierEmploye


def make_company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    return company


class ResolutionParPaysTests(TestCase):
    def setUp(self):
        self.co = make_company('ntpay8')
        ensure_defaults(self.co)                 # jeu MAROCAIN sans pays
        ensure_pays_paie_standard(self.co)
        self.pays_ma = PaysPaie.objects.get(
            company=self.co, code_iso=PaysPaie.CODE_MA)
        self.pays_fr = PaysPaie.objects.create(
            company=self.co, code_iso=PaysPaie.CODE_FR, libelle='France',
            devise='EUR', moteur='FR')
        self.jour = date(2026, 6, 1)

    def _jeu_fr(self):
        """Jeu FR au 1ᵉʳ janvier 2026 — mêmes DATES que le jeu marocain."""
        parametre = ParametrePaie.objects.create(
            company=self.co, pays=self.pays_fr, date_effet=date(2026, 1, 1),
            plafond_cnss=Decimal('3925'))
        bareme = BaremeIR.objects.create(
            company=self.co, pays=self.pays_fr, libelle='Barème FR 2026',
            date_effet=date(2026, 1, 1))
        TrancheIR.objects.create(
            company=self.co, bareme=bareme, borne_min=Decimal('0'),
            borne_max=None, taux=Decimal('11'), somme_a_deduire=Decimal('0'),
            ordre=1)
        return parametre, bareme

    def test_deux_pays_ont_chacun_leur_jeu_a_la_meme_date(self):
        parametre_fr, bareme_fr = self._jeu_fr()
        # Le jeu marocain (sans pays) et le jeu FR coexistent à la MÊME date.
        self.assertEqual(
            ParametrePaie.objects.filter(
                company=self.co, date_effet=date(2026, 1, 1)).count(), 2)

        self.assertEqual(
            parametre_en_vigueur(self.co, self.jour, pays=self.pays_fr).pk,
            parametre_fr.pk)
        self.assertEqual(
            bareme_en_vigueur(self.co, self.jour, pays=self.pays_fr).pk,
            bareme_fr.pk)
        # Côté marocain : le jeu SANS pays, jamais celui de la France.
        parametre_ma = parametre_en_vigueur(
            self.co, self.jour, pays=self.pays_ma)
        self.assertIsNone(parametre_ma.pays_id)
        self.assertEqual(parametre_ma.plafond_cnss, Decimal('6000.00'))

    def test_appel_historique_sans_pays_ignore_le_jeu_etranger(self):
        self._jeu_fr()
        parametre = parametre_en_vigueur(self.co, self.jour)
        self.assertIsNone(parametre.pays_id)
        self.assertEqual(parametre.plafond_cnss, Decimal('6000.00'))
        self.assertIsNone(bareme_en_vigueur(self.co, self.jour).pays_id)

    def test_pays_etranger_sans_jeu_ne_retombe_pas_sur_le_maroc(self):
        pays_sn = PaysPaie.objects.create(
            company=self.co, code_iso=PaysPaie.CODE_SN, libelle='Sénégal',
            devise='XOF')
        self.assertIsNone(
            parametre_en_vigueur(self.co, self.jour, pays=pays_sn))
        self.assertIsNone(bareme_en_vigueur(self.co, self.jour, pays=pays_sn))

    def test_seed_accepte_un_pays(self):
        created = ensure_defaults(self.co, pays=self.pays_ma)
        self.assertEqual(created['parametre'], 1)
        self.assertEqual(created['bareme'], 1)
        # Idempotent sur la même clé (société, pays, date).
        self.assertEqual(
            ensure_defaults(self.co, pays=self.pays_ma)['parametre'], 0)
        # Le jeu SANS pays est intact (clé différente).
        self.assertTrue(
            ParametrePaie.objects.filter(
                company=self.co, pays__isnull=True).exists())

    def test_isolation_societe(self):
        autre = make_company('ntpay8-autre')
        ensure_defaults(autre)
        ensure_pays_paie_standard(autre)
        pays_autre = PaysPaie.objects.get(company=autre)
        self._jeu_fr()
        self.assertEqual(
            parametre_en_vigueur(autre, self.jour, pays=pays_autre).company_id,
            autre.id)


class NonRegressionMonoPaysTests(TestCase):
    """Le comportement MAROCAIN mono-pays est identique, au centime."""

    def setUp(self):
        self.co = make_company('ntpay8-mono')
        ensure_defaults(self.co)
        ensure_pays_paie_standard(self.co)
        self.pays_ma = PaysPaie.objects.get(
            company=self.co, code_iso=PaysPaie.CODE_MA)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)

    def _profil(self, matricule, pays=None):
        dossier = DossierEmploye.objects.create(
            company=self.co, matricule=matricule, nom='N' + matricule,
            prenom='P')
        return ProfilPaie.objects.create(
            company=self.co, employe=dossier, pays=pays,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('12500'),
            affilie_cnss=True, affilie_amo=True)

    def test_profil_sans_pays_et_profil_ma_donnent_le_meme_bulletin(self):
        sans = calculer_bulletin(self._profil('M1'), self.periode)
        avec = calculer_bulletin(self._profil('M2', self.pays_ma),
                                 self.periode)
        for champ in ('brut', 'cnss_salariale', 'amo_salariale', 'ir',
                      'net_a_payer', 'charges_patronales'):
            self.assertEqual(sans[champ], avec[champ], champ)
        self.assertGreater(sans['ir'], 0)
