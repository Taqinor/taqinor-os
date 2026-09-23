"""CALX287 — le tarif PPA est EXIGÉ, jamais supposé.

Ce qui est prouvé ici :

* appel sans ``ppa_tariff`` ⇒ résultat ``None`` (``schedule``, ``investor``,
  ``client``, ``summary``) et un ``motif`` qui NOMME le champ ;
* appel avec 0,90 saisi ⇒ résultat NUMÉRIQUEMENT identique à celui d'avant
  la tâche (garde de non-régression : :data:`AVANT`, capturé sur le commit
  CALX286 avec le même appel) ;
* ``DEFAULT_PPA_TARIFF`` n'est plus défini dans ``solar_design`` ;
* la seule provenance admise est le tarif de rachat réglé par la société
  (CALX276) : chaîné de bout en bout, il alimente le modèle.

Fonctions pures : aucune base.

Run :
    python manage.py test apps.ventes.tests.test_calx287_ppa_tarif_saisi -v2
"""
import json
import unittest
from types import SimpleNamespace

from apps.parametres import tariff
from apps.ventes import solar_design as sd

PARAMETRES = dict(
    annual_production_kwh=20000.0, grid_tariff=1.40, ppa_escalation=0.02,
    grid_escalation=0.0, term_years=5, capex=50000.0, annual_om=1000.0,
    om_escalation=0.02, degradation_rate=0.005, year1_degradation=0.02,
    discount_rate=0.05)

#: Sortie capturée AVANT CALX287 (commit CALX286), ``ppa_tariff=0.90``.
AVANT = json.loads(r'''{
 "client": {
  "grid_tariff_year1": 1.4,
  "net_benefit": 44967.03,
  "ppa_tariff_year1": 0.9,
  "savings_last_year": 8180.23,
  "savings_year1": 9800.0,
  "total_discounted_savings": 39107.61,
  "total_savings": 44967.03
 },
 "investor": {
  "capex": 50000.0,
  "discounted_payback_year": 4,
  "irr": 0.208703,
  "net_after_capex": 35663.78,
  "npv": 24071.16,
  "payback_year": 3,
  "total_discounted_net": 74071.16,
  "total_net": 85663.78,
  "total_om": 5204.04,
  "total_revenue": 90867.82
 },
 "schedule": [
  {
   "client_cumulative_savings": 9800.0,
   "client_discounted_savings": 9333.33,
   "client_savings": 9800.0,
   "grid_tariff_year": 1.4,
   "investor_discounted_net": 15847.62,
   "investor_net": 16640.0,
   "investor_om": 1000.0,
   "investor_revenue": 17640.0,
   "ppa_tariff_year": 0.9,
   "production_factor": 0.98,
   "production_kwh": 19600.0,
   "year": 1
  },
  {
   "client_cumulative_savings": 19199.96,
   "client_discounted_savings": 8526.04,
   "client_savings": 9399.96,
   "grid_tariff_year": 1.4,
   "investor_discounted_net": 15313.23,
   "investor_net": 16882.84,
   "investor_om": 1020.0,
   "investor_revenue": 17902.84,
   "ppa_tariff_year": 0.918,
   "production_factor": 0.9751,
   "production_kwh": 19502.0,
   "year": 2
  },
  {
   "client_cumulative_savings": 28196.66,
   "client_discounted_savings": 7771.69,
   "client_savings": 8996.7,
   "grid_tariff_year": 1.4,
   "investor_discounted_net": 14796.84,
   "investor_net": 17129.19,
   "investor_om": 1040.4,
   "investor_revenue": 18169.59,
   "ppa_tariff_year": 0.9364,
   "production_factor": 0.970225,
   "production_kwh": 19404.49,
   "year": 3
  },
  {
   "client_cumulative_savings": 36786.8,
   "client_discounted_savings": 7067.13,
   "client_savings": 8590.14,
   "grid_tariff_year": 1.4,
   "investor_discounted_net": 14297.83,
   "investor_net": 17379.11,
   "investor_om": 1061.21,
   "investor_revenue": 18440.32,
   "ppa_tariff_year": 0.9551,
   "production_factor": 0.965373,
   "production_kwh": 19307.47,
   "year": 4
  },
  {
   "client_cumulative_savings": 44967.03,
   "client_discounted_savings": 6409.42,
   "client_savings": 8180.23,
   "grid_tariff_year": 1.4,
   "investor_discounted_net": 13815.64,
   "investor_net": 17632.64,
   "investor_om": 1082.43,
   "investor_revenue": 18715.08,
   "ppa_tariff_year": 0.9742,
   "production_factor": 0.960547,
   "production_kwh": 19210.93,
   "year": 5
  }
 ],
 "summary": {
  "annual_om_year1": 1000.0,
  "degradation_rate": 0.005,
  "discount_rate": 0.05,
  "grid_escalation": 0.0,
  "om_escalation": 0.02,
  "ppa_escalation": 0.02,
  "ppa_tariff": 0.9,
  "production_year1": 20000.0,
  "term_years": 5,
  "total_production_kwh": 97024.89,
  "year1_degradation": 0.02
 },
 "warnings": []
}''')


class TarifPpaSaisiTest(unittest.TestCase):
    def test_sans_tarif_ppa_resultat_none_et_motif_nommant_le_champ(self):
        res = sd.ppa_model(**PARAMETRES)
        for bloc in ('schedule', 'investor', 'client', 'summary'):
            self.assertIsNone(res[bloc], bloc)
        self.assertIn('ppa_tariff', res['motif'])
        self.assertEqual(res['motif'], sd.MOTIF_TARIF_PPA_ABSENT)
        self.assertEqual([o['cle'] for o in res['omissions']],
                         ['ppa_tariff'])

    def test_tarif_illisible_traite_comme_absent(self):
        res = sd.ppa_model(ppa_tariff='abc', **PARAMETRES)
        self.assertIsNone(res['investor'])
        self.assertIn('ppa_tariff', res['motif'])

    def test_avec_0_90_saisi_identique_a_avant(self):
        res = sd.ppa_model(ppa_tariff=0.90, **PARAMETRES)
        for bloc in ('schedule', 'investor', 'client', 'summary', 'warnings'):
            self.assertEqual(res[bloc], AVANT[bloc], bloc)
        self.assertIsNone(res['motif'])

    def test_constante_de_tarif_ppa_supprimee(self):
        self.assertFalse(hasattr(sd, 'DEFAULT_PPA_TARIFF'))

    def test_seule_provenance_le_tarif_de_rachat_de_la_societe(self):
        reglages = SimpleNamespace(
            mecanisme_compensation='surplus', report_periode=None,
            plafond_annuel_kwh=None, ratio_compensation=None,
            surplus_prix_kwh_ttc='0.90')
        meca = tariff.mecanisme_depuis_reglages(reglages)
        res = sd.ppa_model(ppa_tariff=meca['tarif_rachat_mad_kwh'],
                           **PARAMETRES)
        self.assertEqual(res['summary']['ppa_tariff'], 0.9)
        self.assertEqual(res['investor'], AVANT['investor'])
        # Tarif de rachat non saisi (0, le défaut) ⇒ aucun tarif PPA.
        vierge = tariff.mecanisme_depuis_reglages(SimpleNamespace(
            mecanisme_compensation='surplus', report_periode=None,
            plafond_annuel_kwh=None, ratio_compensation=None,
            surplus_prix_kwh_ttc=0))
        res = sd.ppa_model(ppa_tariff=vierge['tarif_rachat_mad_kwh'],
                           **PARAMETRES)
        self.assertIsNone(res['investor'])
