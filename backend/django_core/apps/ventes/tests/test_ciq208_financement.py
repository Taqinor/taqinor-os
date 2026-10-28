"""CIQ208 — ``economie_ci`` (5/6) : financement construit UNIQUEMENT depuis
l'offre ÉCRITE d'un prêteur ou d'un bailleur, aucun taux inventé (D-CIQ-15).

SimpleTestCase : aucune base.
"""
import json

from django.test import SimpleTestCase

from apps.ventes import economie as eco_mod
from apps.ventes import economie_ci as eco


def _base(tva='oui'):
    return eco.base_economique(
        tva, investissement={'ht': 900000.0, 'ttc': 1080000.0},
        economie_annee1={'total_mad': 246350.0, 'total_mad_ttc': 295620.0})


def _offre(**surcharges):
    offre = {'nature': 'credit', 'preteur': 'Prêteur Exemple',
             'reference_offre': 'OFF-EXEMPLE-01', 'date_offre': '2026-09-15',
             'montant_finance_mad': 720000.0, 'apport_mad': 180000.0,
             'duree_mois': 84, 'echeance_mad': 12000.0, 'base_echeance': 'ht',
             'frais_mad': None, 'taux_annuel_pct': None,
             'valeur_residuelle_mad': None, 'source': 'offre écrite'}
    offre.update(surcharges)
    return offre


class OffreEcriteTest(SimpleTestCase):
    def test_credit_taux_ecrit_84_mois_egal_tableau_pret(self):
        res = eco.financement_ci(_offre(taux_annuel_pct=6.5), _base(),
                                 mode_installation='industriel')
        attendu = eco_mod.tableau_pret(
            principal_mad=720000.0, taux_annuel_pct=6.5, duree_mois=84,
            type_pret='annuite')['mensualite_mad']
        self.assertEqual(res['echeance_mad'], attendu)
        self.assertEqual(res['duree_mois'], 84)
        self.assertEqual(res['economie_mensuelle_moyenne_mad'],
                         round(246350.0 / 12, 2))
        self.assertEqual(res['ecart_mensuel_mad'],
                         round(round(246350.0 / 12, 2) - attendu, 2))

    def test_offre_sans_taux_echeance_tapee_aucun_taux(self):
        res = eco.financement_ci(_offre(), _base(),
                                 mode_installation='commercial')
        self.assertEqual(res['echeance_mad'], 12000.0)
        self.assertNotIn('taux_annuel_pct', res)
        self.assertNotIn('taux', json.dumps(res))
        self.assertEqual(
            res['libelle_client'],
            'Offre de crédit de Prêteur Exemple du 15/09/2026 '
            '(réf. OFF-EXEMPLE-01)')
        self.assertEqual(set(res), {
            'libelle_client', 'echeance_mad', 'economie_mensuelle_moyenne_mad',
            'ecart_mensuel_mad', 'duree_mois', 'source', 'flux_offre',
            'retour_offre_ans', 'apport_mad', 'frais_mad'})

    def test_offre_sans_source_refusee(self):
        with self.assertRaises(eco.SaisieEconomieCiInvalide) as ctx:
            eco.financement_ci(_offre(source=''), _base(),
                               mode_installation='industriel')
        self.assertEqual(ctx.exception.champ, 'offre_financement.source')

    def test_base_differente_refusee(self):
        with self.assertRaises(eco.SaisieEconomieCiInvalide) as ctx:
            eco.financement_ci(_offre(base_echeance='ttc'), _base('oui'),
                               mode_installation='industriel')
        self.assertEqual(ctx.exception.champ,
                         'offre_financement.base_echeance')

    def test_apport_porte_ou_omission_nommee(self):
        # CEC15 : apport, frais et valeur résiduelle saisis entrent dans le flux.
        avec = eco.financement_ci(_offre(), _base(),
                                  mode_installation='industriel')
        sans = eco.financement_ci(_offre(apport_mad=None), _base(),
                                  mode_installation='industriel')
        self.assertEqual(avec['flux_offre'][0]['flux_mad'], -180000.0)
        self.assertEqual(sans['flux_offre'][0]['flux_mad'], 0.0)
        self.assertEqual(
            round(sans['flux_offre'][0]['flux_mad']
                  - avec['flux_offre'][0]['flux_mad'], 2), 180000.0)
        plein = eco.financement_ci(
            _offre(frais_mad=5000.0, valeur_residuelle_mad=20000.0), _base(),
            mode_installation='industriel')
        self.assertEqual(plein['flux_offre'][0]['flux_mad'], -185000.0)
        self.assertEqual(plein['flux_offre'][-1]['flux_mad'],
                         avec['flux_offre'][-1]['flux_mad'] - 20000.0)
        self.assertEqual(len(avec['flux_offre']), 8)  # an 0 + 7 ans (84 mois)
        self.assertGreater(avec['retour_offre_ans'], 0)
        # CEC15 (affichage) : apport et frais servis tels que saisis.
        self.assertEqual((avec['apport_mad'], avec['frais_mad']),
                         (180000.0, 0.0))
        self.assertEqual((plein['apport_mad'], plein['frais_mad']),
                         (180000.0, 5000.0))
        self.assertEqual(sans['apport_mad'], 0.0)

    def test_base_deux_prend_la_base_de_l_echeance(self):
        res = eco.financement_ci(_offre(base_echeance='ttc'),
                                 _base('inconnu'),
                                 mode_installation='industriel')
        self.assertEqual(res['economie_mensuelle_moyenne_mad'],
                         round(295620.0 / 12, 2))

    def test_preteur_nomme_seulement_avec_la_reference(self):
        res = eco.financement_ci(_offre(reference_offre=''), _base(),
                                 mode_installation='industriel')
        self.assertEqual(res['libelle_client'], 'Offre de crédit')
        self.assertNotIn('Prêteur Exemple', json.dumps(res, ensure_ascii=False))


class SaisiesCec14Test(SimpleTestCase):
    def test_cec14_infini_refuse_nomme_jamais_500(self):
        for surcharge in ({'duree_mois': float('inf')},
                          {'echeance_mad': float('inf')},
                          {'montant_finance_mad': float('nan'),
                           'taux_annuel_pct': 6.0},
                          {'taux_annuel_pct': 1e300}):
            with self.assertRaises(eco.SaisieEconomieCiInvalide,
                                   msg=str(surcharge)):
                eco.financement_ci(_offre(**surcharge), _base(),
                                   mode_installation='industriel')

    def test_cec14_montant_nul_nomme_le_champ_de_l_ecran(self):
        with self.assertRaises(eco.SaisieEconomieCiInvalide) as ctx:
            eco.financement_ci(_offre(montant_finance_mad=0,
                                      taux_annuel_pct=6.0), _base(),
                               mode_installation='industriel')
        self.assertEqual(ctx.exception.champ,
                         'offre_financement.montant_finance_mad')


class CreditBailTest(SimpleTestCase):
    def test_reglage_faux_aucun_credit_bail(self):
        res = eco.financement_ci(_offre(nature='credit_bail'), _base(),
                                 mode_installation='industriel',
                                 mention_credit_bail_autorisee=False)
        texte = json.dumps(res, ensure_ascii=False).lower()
        self.assertNotIn('crédit-bail', texte)
        self.assertNotIn('credit_bail', texte)
        self.assertTrue(res['libelle_client'].startswith(
            'Offre de financement'))

    def test_reglage_vrai_credit_bail_nomme(self):
        res = eco.financement_ci(_offre(nature='credit_bail'), _base(),
                                 mode_installation='industriel',
                                 mention_credit_bail_autorisee=True)
        self.assertTrue(res['libelle_client'].startswith(
            'Offre de crédit-bail'))


class Pv80Test(SimpleTestCase):
    def test_residentiel_aucun_financement(self):
        self.assertIsNone(eco.financement_ci(
            _offre(), _base(), mode_installation='residentiel'))

    def test_sans_offre_aucun_financement(self):
        self.assertIsNone(eco.financement_ci(
            None, _base(), mode_installation='industriel'))
