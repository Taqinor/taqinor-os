"""CALX276 — mécanisme de compensation du surplus, typé et saisi.

Ce qui est prouvé ici :

* société vierge ⇒ mécanisme ``None`` et économie de surplus ``None`` +
  motif (comportement d'aujourd'hui : ``surplus_injecte_compense = False``) ;
* ``net_metering_report`` avec ``report_periode = 12`` ⇒ le crédit d'un
  mois excédentaire est consommé le mois suivant, et le solde de fin de
  période est publié ;
* ``injection_totale`` ⇒ zéro autoconsommation valorisée, toute la
  production vendue au tarif de rachat SAISI ;
* sans tarif de rachat saisi ⇒ « omis : aucun tarif d'injection publié,
  aucun tarif saisi par la société » — jamais 0,04 $/kWh ni aucun défaut ;
* ``net_metering_report`` sans ``report_periode`` ⇒ refus nommant le champ.

Run :
    python manage.py test apps.parametres.tests_calx276_mecanisme_compensation
"""
import unittest
from types import SimpleNamespace

from django.test import TestCase

from apps.parametres import tariff
from apps.ventes import solar_design as sd


def _reglages(**champs):
    base = {'mecanisme_compensation': '', 'report_periode': None,
            'plafond_annuel_kwh': None, 'ratio_compensation': None,
            'surplus_prix_kwh_ttc': 0}
    base.update(champs)
    return SimpleNamespace(**base)


class MecanismeServicePurTest(unittest.TestCase):
    def test_societe_vierge_surplus_omis_avec_motif(self):
        self.assertIsNone(tariff.mecanisme_depuis_reglages(_reglages()))
        res = sd.compensation_surplus(
            mecanisme=None, injection_kwh_mois=[100] * 12,
            import_kwh_mois=[50] * 12)
        self.assertIsNone(res['mecanisme'])
        self.assertIsNone(res['economie_surplus_mad'])
        self.assertIn('mecanisme_compensation', res['motif'])

    def test_net_metering_report_credit_consomme_le_mois_suivant(self):
        # Janvier : 100 injectés, 20 soutirés ⇒ 80 kWh de crédit reporté.
        # Février : rien injecté, 50 soutirés ⇒ 50 kWh pris sur le crédit.
        injection = [100, 0] + [0] * 10
        soutirage = [20, 50] + [0] * 10
        res = sd.compensation_surplus(
            mecanisme='net_metering_report', injection_kwh_mois=injection,
            import_kwh_mois=soutirage, report_periode=12,
            tarif_import_mad_kwh=1.0)
        janvier, fevrier = res['mois'][0], res['mois'][1]
        self.assertEqual(janvier['credit_reporte_kwh'], 80.0)
        self.assertEqual(fevrier['credit_entrant_kwh'], 80.0)
        self.assertEqual(fevrier['credit_consomme_kwh'], 50.0)
        self.assertEqual(fevrier['credit_reporte_kwh'], 30.0)
        # Solde de fin de période (12 mois) publié : les 30 kWh restants.
        self.assertEqual(len(res['soldes_fin_periode']), 1)
        self.assertEqual(res['solde_fin_periode_kwh'], 30.0)
        self.assertEqual(res['soldes_fin_periode'][0]['fin_mois'], 12)
        # Économie = 70 kWh compensés × 1,00 MAD/kWh fourni.
        self.assertEqual(res['compense_kwh'], 70.0)
        self.assertEqual(res['economie_surplus_mad'], 70.0)
        # Aucun tarif de rachat saisi : la valeur du solde est omise.
        self.assertIsNone(res['soldes_fin_periode'][0]['valeur_mad'])

    def test_report_remis_a_zero_a_la_fin_de_chaque_periode(self):
        res = sd.compensation_surplus(
            mecanisme='net_metering_report',
            injection_kwh_mois=[100, 0, 0, 0], import_kwh_mois=[0, 0, 30, 0],
            report_periode=2, tarif_import_mad_kwh=1.0)
        # Période 1 (mois 1-2) close avec 100 kWh ; mois 3 repart de zéro.
        self.assertEqual(res['soldes_fin_periode'][0]['solde_kwh'], 100.0)
        self.assertEqual(res['mois'][2]['credit_entrant_kwh'], 0.0)
        self.assertEqual(res['compense_kwh'], 0.0)

    def test_injection_totale_tout_le_produit_au_tarif_saisi(self):
        res = sd.compensation_surplus(
            mecanisme='injection_totale', production_kwh_mois=[500] * 12,
            injection_kwh_mois=[200] * 12, tarif_rachat_mad_kwh=0.60)
        self.assertFalse(res['autoconsommation_valorisee'])
        self.assertEqual(res['autoconsommation_valorisee_kwh'], 0.0)
        self.assertEqual(res['vendu_kwh'], 6000.0)
        self.assertEqual(res['vente_mad'], 3600.0)
        self.assertEqual(res['economie_surplus_mad'], 3600.0)

    def test_sans_tarif_de_rachat_vente_omise_jamais_un_defaut(self):
        res = sd.compensation_surplus(
            mecanisme='surplus', injection_kwh_mois=[200] * 12)
        self.assertEqual(res['vendu_kwh'], 2400.0)
        self.assertIsNone(res['vente_mad'])
        self.assertIsNone(res['economie_surplus_mad'])
        self.assertEqual(res['motif'], tariff.MOTIF_TARIF_RACHAT_ABSENT)
        self.assertIn("aucun tarif d'injection publié", res['motif'])

    def test_tarif_de_rachat_nul_vaut_non_saisi(self):
        meca = tariff.mecanisme_depuis_reglages(
            _reglages(mecanisme_compensation='surplus'))
        self.assertIsNone(meca['tarif_rachat_mad_kwh'])
        meca = tariff.mecanisme_depuis_reglages(_reglages(
            mecanisme_compensation='surplus', surplus_prix_kwh_ttc='0.55'))
        self.assertEqual(meca['tarif_rachat_mad_kwh'], 0.55)

    def test_ratio_non_saisi_publie_comme_hypothese(self):
        res = sd.compensation_surplus(
            mecanisme='surplus', injection_kwh_mois=[10],
            tarif_rachat_mad_kwh=1.0)
        self.assertTrue(any(h['cle'] == 'ratio_compensation' and h['source']
                            for h in res['hypotheses']))


class MecanismeValidationPurTest(unittest.TestCase):
    def test_net_metering_sans_report_periode_refuse_en_le_nommant(self):
        erreurs = tariff.erreurs_compensation(
            'net_metering_report', None, None, None)
        self.assertIn('report_periode', erreurs)
        self.assertIn('report_periode', erreurs['report_periode'])

    def test_mecanisme_inconnu_refuse(self):
        erreurs = tariff.erreurs_compensation('troc', None, None, None)
        self.assertIn('mecanisme_compensation', erreurs)

    def test_ratio_hors_zero_un_refuse(self):
        erreurs = tariff.erreurs_compensation('surplus', None, None, '1.5')
        self.assertIn('ratio_compensation', erreurs)

    def test_point_d_entree_unique_relaie(self):
        erreurs = tariff.erreurs_reglages_tarif(_reglages(
            mecanisme_compensation='net_metering_report', tou_heures=None,
            tou_tarifs=None, tou_source='', tou_date_source=None))
        self.assertIn('report_periode', erreurs)

    def test_choix_du_modele_verrouilles_sur_le_service(self):
        # Les clés du modèle (lues dans la migration, sans Django) sont
        # EXACTEMENT celles du service.
        import importlib
        migration = importlib.import_module(
            'apps.parametres.migrations.0098_calx276_mecanisme_compensation')
        operation = [op for op in migration.Migration.operations
                     if op.name == 'mecanisme_compensation'][0]
        cles = tuple(cle for cle, _ in operation.field.choices)
        self.assertEqual(cles, tariff.MECANISMES_COMPENSATION)


class MecanismeOrmTest(TestCase):
    def setUp(self):
        from authentication.models import Company
        self.company, _ = Company.objects.get_or_create(
            slug='calx276-co', defaults={'nom': 'CALX276 Co'})

    def test_societe_vierge_mecanisme_none_et_surplus_omis(self):
        from apps.parametres.models_tariff import TariffSettings
        reglages = TariffSettings.get(company=self.company)
        self.assertEqual(reglages.mecanisme_compensation, '')
        self.assertFalse(reglages.surplus_injecte_compense)
        self.assertIsNone(tariff.mecanisme_depuis_reglages(reglages))
        res = sd.compensation_surplus(mecanisme=None)
        self.assertIsNone(res['economie_surplus_mad'])
        self.assertTrue(res['motif'])

    def test_net_metering_sans_report_refuse_par_le_modele(self):
        from django.core.exceptions import ValidationError
        from apps.parametres.models_tariff import TariffSettings
        reglages = TariffSettings.get(company=self.company)
        reglages.mecanisme_compensation = 'net_metering_report'
        with self.assertRaises(ValidationError) as ctx:
            reglages.full_clean()
        self.assertIn('report_periode', ctx.exception.message_dict)

    def test_choix_du_modele_identiques_au_service(self):
        from apps.parametres.models_tariff import TariffSettings
        cles = tuple(c for c, _ in
                     TariffSettings.MECANISMES_COMPENSATION_CHOICES)
        self.assertEqual(cles, tariff.MECANISMES_COMPENSATION)
