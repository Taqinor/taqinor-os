"""CALX274 — tranches horaires et tarifs SAISIS par la société, avec source et date.

Ce qui est prouvé ici :

* société sans saisie ⇒ ``tou_pour()`` rend ``None`` ; et
  ``net_metering_savings(..., tranche_tariffs=None)`` rend ``economie is None``
  avec un ``motif`` qui NOMME le réglage (jamais les anciens 1,45 / 1,15 /
  0,85 « à CONFIRMER ») ;
* tarifs saisis sans ``tou_source`` ⇒ refus nommant ``tou_source`` (le
  validateur pur ET ``TariffSettings.full_clean``) ; sans date ⇒ refus
  nommant ``tou_date_source`` ; une tranche employée sans tarif ⇒ refus
  nommant ``tou_tarifs.<tranche>`` ;
* société ayant saisi ⇒ l'économie est calculée avec SES valeurs ;
* ``DEFAULT_TRANCHE_TARIFFS`` n'existe plus dans ``solar_design``.

Deux familles de tests : ``*Pur*`` (``unittest``, sans base — exécutables
partout) et ``*Orm*`` (``django.test.TestCase``, CI).

Run :
    python manage.py test apps.parametres.tests_calx274_tarifs_tou -v2
"""
import datetime
import unittest
from types import SimpleNamespace

from django.test import TestCase

from apps.parametres import tariff
from apps.ventes import solar_design as sd

#: Découpage 24 h d'EXEMPLE (saisie de test, jamais un défaut du code).
HEURES = (['creuse'] * 7 + ['pleine'] * 11 + ['pointe'] * 4
          + ['pleine', 'creuse'])
#: Tarifs d'EXEMPLE saisis par une société de test (MAD/kWh).
TARIFS = {'pointe': '2.00', 'pleine': '1.00', 'creuse': '0.50'}
SOURCE = 'Facture SRM de test n° 1 (jeu d’essai)'
DATE = datetime.date(2026, 5, 8)


def _reglages(**champs):
    base = {'tou_heures': None, 'tou_tarifs': None, 'tou_source': '',
            'tou_date_source': None}
    base.update(champs)
    return SimpleNamespace(**base)


class TouValidationPurTest(unittest.TestCase):
    def test_rien_de_saisi_aucune_erreur(self):
        self.assertEqual(tariff.erreurs_tou(None, None, '', None), {})

    def test_tarifs_sans_source_refuses_en_nommant_tou_source(self):
        erreurs = tariff.erreurs_tou(HEURES, TARIFS, '', DATE)
        self.assertIn('tou_source', erreurs)
        self.assertIn('tou_source', erreurs['tou_source'])

    def test_tarifs_sans_date_refuses_en_nommant_tou_date_source(self):
        erreurs = tariff.erreurs_tou(HEURES, TARIFS, SOURCE, None)
        self.assertIn('tou_date_source', erreurs)
        self.assertIn('tou_date_source', erreurs['tou_date_source'])

    def test_tranche_employee_sans_tarif_nommee(self):
        tarifs = {'pointe': 2, 'pleine': 1}  # « creuse » manque
        erreurs = tariff.erreurs_tou(HEURES, tarifs, SOURCE, DATE)
        self.assertIn('tou_tarifs.creuse', erreurs['tou_tarifs'])

    def test_heures_de_longueur_fausse_refusees(self):
        erreurs = tariff.erreurs_tou(HEURES[:23], TARIFS, SOURCE, DATE)
        self.assertIn('tou_heures', erreurs)

    def test_tarif_negatif_refuse(self):
        erreurs = tariff.erreurs_tou(
            HEURES, {**TARIFS, 'pointe': '-1'}, SOURCE, DATE)
        self.assertIn('tou_tarifs.pointe', erreurs['tou_tarifs'])

    def test_point_d_entree_unique_relaie_le_refus(self):
        erreurs = tariff.erreurs_reglages_tarif(
            _reglages(tou_heures=HEURES, tou_tarifs=TARIFS))
        self.assertIn('tou_source', erreurs)


class TouResolutionPurTest(unittest.TestCase):
    def test_reglages_vierges_rendent_none(self):
        self.assertIsNone(tariff.tou_depuis_reglages(_reglages()))
        self.assertIsNone(tariff.tou_depuis_reglages(None))

    def test_sans_source_ou_sans_date_rend_none(self):
        self.assertIsNone(tariff.tou_depuis_reglages(_reglages(
            tou_heures=HEURES, tou_tarifs=TARIFS, tou_date_source=DATE)))
        self.assertIsNone(tariff.tou_depuis_reglages(_reglages(
            tou_heures=HEURES, tou_tarifs=TARIFS, tou_source=SOURCE)))

    def test_grille_complete_rendue_avec_sa_provenance(self):
        tou = tariff.tou_depuis_reglages(_reglages(
            tou_heures=HEURES, tou_tarifs=TARIFS, tou_source=SOURCE,
            tou_date_source=DATE))
        self.assertEqual(tou['heures'], HEURES)
        self.assertEqual(tou['tarifs'],
                         {'pointe': 2.0, 'pleine': 1.0, 'creuse': 0.5})
        self.assertEqual(tou['source'], SOURCE)
        self.assertEqual(tou['date_source'], '2026-05-08')


class EconomieHorairePurTest(unittest.TestCase):
    INJ = [0.0] * 24
    IMP = [0.0] * 24

    def setUp(self):
        self.inj = list(self.INJ)
        self.imp = list(self.IMP)
        self.inj[19] = 4.0   # 19 h — pointe dans HEURES
        self.imp[19] = 4.0

    def test_sans_tarifs_economie_omise_avec_motif_nommant_le_reglage(self):
        res = sd.net_metering_savings(
            injected_curve=self.inj, import_curve=self.imp,
            days_per_year=1, tranche_tariffs=None)
        self.assertIsNone(res['economie'])
        self.assertIsNone(res['annual_savings_mad'])
        self.assertIn('tou_tarifs', res['motif'])
        self.assertIn('Tarification', res['motif'])
        self.assertTrue(any(o['cle'] == 'tranche_tariffs'
                            for o in res['omissions']))
        # Aucun tarif publié pour la tranche : jamais un 1,45 supposé.
        self.assertIsNone(res['tranches']['pointe']['tariff'])

    def test_societe_ayant_saisi_economie_calculee_avec_ses_valeurs(self):
        tou = tariff.tou_depuis_reglages(_reglages(
            tou_heures=HEURES, tou_tarifs=TARIFS, tou_source=SOURCE,
            tou_date_source=DATE))
        res = sd.net_metering_savings(
            injected_curve=self.inj, import_curve=self.imp, days_per_year=1,
            hour_tranches=tou['heures'], tranche_tariffs=tou['tarifs'])
        # 4 kWh compensés en pointe × 2,00 MAD/kWh saisis = 8,00 MAD.
        self.assertEqual(res['economie'], 8.0)
        self.assertIsNone(res['motif'])
        self.assertEqual(res['tranches']['pointe']['tariff'], 2.0)
        self.assertEqual(res['hypotheses'], [])

    def test_tranche_compensee_sans_tarif_omise_en_la_nommant(self):
        res = sd.net_metering_savings(
            injected_curve=self.inj, import_curve=self.imp, days_per_year=1,
            hour_tranches=HEURES, tranche_tariffs={'pleine': 1.0})
        self.assertIsNone(res['economie'])
        self.assertIn('tou_tarifs.pointe', res['motif'])

    def test_compensation_desactivee_reste_nulle_par_le_regime(self):
        res = sd.net_metering_savings(
            injected_curve=self.inj, import_curve=self.imp, days_per_year=1,
            surplus_injecte_compense=False)
        self.assertEqual(res['economie'], 0.0)

    def test_plus_aucun_tarif_par_defaut_dans_le_module(self):
        self.assertFalse(hasattr(sd, 'DEFAULT_TRANCHE_TARIFFS'))


class TouPourOrmTest(TestCase):
    """``apps.parametres.selectors.tou_pour`` sur la vraie table (CI)."""

    def setUp(self):
        from authentication.models import Company
        self.company, _ = Company.objects.get_or_create(
            slug='calx274-co', defaults={'nom': 'CALX274 Co'})

    def test_societe_sans_reglage_ni_saisie_rend_none(self):
        from apps.parametres.models_tariff import TariffSettings
        from apps.parametres.selectors import tou_pour
        self.assertIsNone(tou_pour(self.company))
        # Le sélecteur ne crée rien (lecture pure).
        self.assertFalse(
            TariffSettings.objects.filter(company=self.company).exists())
        TariffSettings.get(company=self.company)
        self.assertIsNone(tou_pour(self.company))
        self.assertIsNone(tou_pour(None))

    def test_tarifs_sans_source_refuses_par_le_modele(self):
        from django.core.exceptions import ValidationError
        from apps.parametres.models_tariff import TariffSettings
        reglages = TariffSettings.get(company=self.company)
        reglages.tou_heures = HEURES
        reglages.tou_tarifs = TARIFS
        reglages.tou_date_source = DATE
        with self.assertRaises(ValidationError) as ctx:
            reglages.full_clean()
        self.assertIn('tou_source', ctx.exception.message_dict)

    def test_societe_ayant_saisi_rend_ses_valeurs(self):
        from apps.parametres.models_tariff import TariffSettings
        from apps.parametres.selectors import tou_pour
        reglages = TariffSettings.get(company=self.company)
        reglages.tou_heures = HEURES
        reglages.tou_tarifs = TARIFS
        reglages.tou_source = SOURCE
        reglages.tou_date_source = DATE
        reglages.full_clean()
        reglages.save()
        tou = tou_pour(self.company)
        self.assertEqual(tou['tarifs']['pointe'], 2.0)
        self.assertEqual(tou['date_source'], '2026-05-08')
        inj = [0.0] * 24
        inj[19] = 4.0
        res = sd.net_metering_savings(
            injected_curve=inj, import_curve=inj, days_per_year=1,
            hour_tranches=tou['heures'], tranche_tariffs=tou['tarifs'])
        self.assertEqual(res['economie'], 8.0)
