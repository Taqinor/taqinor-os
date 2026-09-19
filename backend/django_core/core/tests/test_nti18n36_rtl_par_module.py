"""Tests NTI18N36 — granularité RTL par module.

Acceptance criteria couverte : activer ``rtl_pret=true`` sur le module CRM
seul bascule le CRM en RTL sans affecter Stock.
"""
from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from core import rtl
from core.models import ModuleToggle


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class LocaleRtlTests(SimpleTestCase):
    """Unités PURES : reconnaître une langue de droite à gauche."""

    def test_langues_rtl(self):
        for locale in ['ar', 'AR', 'ar-MA', 'ar_ma', ' ar ', 'he', 'fa', 'ur']:
            self.assertTrue(rtl.locale_est_rtl(locale), locale)

    def test_langues_ltr(self):
        for locale in ['fr', 'fr-MA', 'en', '', None, 'es']:
            self.assertFalse(rtl.locale_est_rtl(locale), locale)

    def test_direction_ltr_ignore_le_drapeau_module(self):
        # Langue LTR : pas même besoin de connaître la société.
        resultat = rtl.direction_module(None, 'crm', 'fr')
        self.assertEqual(resultat['direction'], rtl.DIRECTION_LTR)
        self.assertFalse(resultat['force_ltr'])
        self.assertEqual(resultat['note'], '')


class DirectionParModuleTests(TestCase):

    def setUp(self):
        self.company = make_company('nti18n36-co', 'NTI18N36 Co')
        # Le CRM est migré, le stock ne l'est pas encore.
        ModuleToggle.objects.create(
            company=self.company, module='crm', actif=True, rtl_pret=True)
        ModuleToggle.objects.create(
            company=self.company, module='stock', actif=True, rtl_pret=False)

    def test_crm_bascule_en_rtl_sans_affecter_stock(self):
        crm = rtl.direction_module(self.company, 'crm', 'ar')
        self.assertEqual(crm['direction'], rtl.DIRECTION_RTL)
        self.assertFalse(crm['force_ltr'])
        self.assertEqual(crm['note'], '')

        stock = rtl.direction_module(self.company, 'stock', 'ar')
        self.assertEqual(stock['direction'], rtl.DIRECTION_LTR)
        self.assertTrue(stock['force_ltr'])
        self.assertEqual(stock['note'], rtl.NOTE_MIGRATION_EN_COURS)

    def test_module_sans_ligne_reste_en_ltr(self):
        sans_ligne = rtl.direction_module(self.company, 'flotte', 'ar')
        self.assertEqual(sans_ligne['direction'], rtl.DIRECTION_LTR)
        self.assertTrue(sans_ligne['force_ltr'])
        self.assertFalse(rtl.module_rtl_pret(self.company, 'flotte'))

    def test_le_drapeau_est_scope_par_societe(self):
        voisine = make_company('nti18n36-voisine', 'NTI18N36 Voisine')
        self.assertFalse(rtl.module_rtl_pret(voisine, 'crm'))
        self.assertEqual(
            rtl.direction_module(voisine, 'crm', 'ar')['direction'],
            rtl.DIRECTION_LTR)

    def test_liste_groupee_des_modules_prets(self):
        self.assertEqual(rtl.modules_rtl_prets(self.company), {'crm'})
        self.assertEqual(rtl.modules_rtl_prets(None), set())

    def test_defaut_du_champ_est_faux(self):
        """Comportement inchangé : un module créé sans rien dire reste LTR."""
        toggle = ModuleToggle.objects.create(
            company=self.company, module='sav', actif=True)
        self.assertFalse(toggle.rtl_pret)
        self.assertEqual(
            rtl.direction_module(self.company, 'sav', 'ar')['direction'],
            rtl.DIRECTION_LTR)

    def test_rtl_pret_est_independant_de_actif(self):
        """Un module éteint peut être déclaré prêt : ce sont deux axes."""
        ModuleToggle.objects.create(
            company=self.company, module='litiges', actif=False,
            rtl_pret=True)
        self.assertTrue(rtl.module_rtl_pret(self.company, 'litiges'))
        self.assertIn('litiges', rtl.modules_rtl_prets(self.company))
