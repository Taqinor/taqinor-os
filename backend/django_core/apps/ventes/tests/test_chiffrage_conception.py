"""ACAL992 — la porte unique ``chiffrer_conception`` (contrat
``contract_samples/chiffrage_conception.json``, ACAL991).

Nouveau fichier car : la porte est neuve et aucun module de test ne couvre un
chiffrage hors rendu. SimpleTestCase : les lectures (devis, lead, rendu,
simulation du calepinage) sont des doublures ; le moteur horaire et
``base_depuis_servi`` sont RÉELS.
"""
import json
from pathlib import Path
from types import SimpleNamespace as N
from unittest import mock

from django.test import SimpleTestCase

from apps.ventes import services
from apps.ventes.domain import chiffrage_conception as cc
from apps.ventes.domain.entrees import EntreesMoteur
from apps.ventes.etude_horaire import calculer_etude_horaire
from apps.ventes.horaire.public import production_annuelle_pour_kwc

CONTRAT = json.loads((Path(__file__).resolve().parents[1] / 'contract_samples'
                      / 'chiffrage_conception.json').read_text(encoding='utf-8'))
SOCIETE = N(id=7)
#: Rendu ``build_quote_data`` d'un devis à production SAISIE et économie
#: imposée : la porte le recopie, elle ne recalcule rien.
RENDU = {'puissance_kwc': 71.0, 'prod_kwh': 98576, 'eco_s_ann': 7420, 'eco_a_ann': 9100,
         'autoconso_sans': 0.62, 'autoconso_avec': 0.81, 'recommended': 'Sans batterie',
         'savings_estimated': False}
SERVI = {'perime': False, 'pertes_et_ombrage_inclus': True, 'kwh_kwc_annuel': 1500.0,
         'kwh_kwc_mensuel': [125.0] * 12, 'kwc_simule': 5.0}
LAYOUT = {'result': {'kwc': 5.0, 'panels': 10}}


def _calepinage(devis=None, lead_id=3):
    return N(pk=1, devis=devis, devis_id=getattr(devis, 'pk', None), lead_id=lead_id,
             roof_layout=LAYOUT)


def _entrees(conso=(300.0,) * 12):
    return EntreesMoteur(company=SOCIETE, mode='residentiel', etude_params={},
                         conso_kwh_mensuelles=list(conso) if conso else None,
                         source_conso='factures', ville='Casablanca')


class ChiffrerConceptionTest(SimpleTestCase):
    def _chiffrer(self, calepinage, lead=N(type_installation=None)):
        with mock.patch('apps.crm.selectors.get_company_lead', return_value=lead):
            return services.chiffrer_conception(calepinage=calepinage, company=SOCIETE)

    def test_devis_lie_porte_egale_rendu_sans_recalcul(self):
        """Production saisie et économie imposée comprises ; mutant :
        recalculer le devis par le moteur ⇒ ``calculer_etude_horaire`` appelé."""
        devis = N(pk=4, company_id=7, mode_installation='residentiel', regles_calcul=15,
                  etude_params={'production_source': 'saisie'})
        with mock.patch('apps.ventes.quote_engine.builder.build_quote_data',
                        return_value=dict(RENDU)) as rendu, \
                mock.patch('apps.ventes.horaire.productible_pose.base_de_production', return_value=None), \
                mock.patch('apps.ventes.etude_horaire.calculer_etude_horaire') as moteur:
            bloc = self._chiffrer(_calepinage(devis))
        rendu.assert_called_once_with(devis, {'pdf_mode': 'full'})
        moteur.assert_not_called()
        self.assertEqual(set(bloc), set(CONTRAT['exemple']))
        self.assertEqual(bloc['production_annuelle_kwh'],
                         {'valeur': 98576, 'unite': 'kWh/an', 'source': 'devis', 'etat': 'servi'})
        self.assertEqual((bloc['economie_annee1_mad']['valeur'], bloc['economie_annee1_mad']['option']),
                         (7420, 'sans_batterie'))
        self.assertEqual((bloc['kwc']['valeur'], bloc['autoconsommation_pct']['valeur'], bloc['regles_calcul']),
                         (71.0, 62.0, 15))
        with mock.patch('apps.ventes.quote_engine.builder.build_quote_data',
                        return_value=dict(RENDU, recommended='Avec batterie')), \
                mock.patch('apps.ventes.horaire.productible_pose.base_de_production', return_value={'x': 1}):
            avec = self._chiffrer(_calepinage(N(**dict(vars(devis), etude_params={}))))
        self.assertEqual((avec['economie_annee1_mad']['valeur'], avec['economie_annee1_mad']['option']),
                         (9100, 'avec_batterie'))
        self.assertEqual(avec['production_annuelle_kwh']['source'], cc.SOURCE_POSE)

    def test_sans_devis_regles_15_base_de_la_pose(self):
        with mock.patch('apps.ventes.domain.entrees.entrees_depuis_lead', return_value=_entrees()), \
                mock.patch('apps.ventes.domain.regles_calcul.regles_au_moins', return_value=True), \
                mock.patch('apps.calepinage.selectors_devis.productible_pose_du_calepinage',
                           return_value=SERVI):
            bloc = self._chiffrer(_calepinage())
        attendu = calculer_etude_horaire(
            kwc=5.0, conso_kwh_mensuelles=[300.0] * 12, ville='Casablanca', tranches=None,
            charges_fixes_mad=None, source_conso='factures',
            base_production={'kwh_kwc_annuel': 1500.0, 'kwh_kwc_mensuel': [125.0] * 12,
                             'pertes_incluses': True, 'source': cc.SOURCE_POSE})['annuel']
        self.assertEqual(bloc['production_annuelle_kwh']['valeur'], attendu['production_kwh'])
        self.assertAlmostEqual(bloc['production_annuelle_kwh']['valeur'], 7500, delta=1)
        self.assertEqual(bloc['production_annuelle_kwh']['source'], cc.SOURCE_POSE)
        self.assertEqual(bloc['economie_annee1_mad']['valeur'], attendu['economie_sans_mad'])
        self.assertEqual(bloc['kwc'], {'valeur': 5.0, 'unite': 'kWc', 'source': 'lead', 'etat': 'servi'})

    def test_sans_facture_economie_omise(self):
        """D-ACAL-40 : base servie ⇒ production seule ; sans base ⇒ rien de chiffré."""
        with mock.patch('apps.ventes.domain.entrees.entrees_depuis_lead', return_value=_entrees(None)), \
                mock.patch('apps.ventes.domain.regles_calcul.regles_au_moins', return_value=True), \
                mock.patch('apps.calepinage.selectors_devis.productible_pose_du_calepinage',
                           return_value=SERVI):
            bloc = self._chiffrer(_calepinage())
        self.assertEqual(set(bloc), set(CONTRAT['exemple_sans_facture']))
        self.assertEqual(bloc['production_annuelle_kwh']['valeur'], production_annuelle_pour_kwc(
            5.0, base_production={'kwh_kwc_annuel': 1500.0, 'kwh_kwc_mensuel': [125.0] * 12,
                                  'pertes_incluses': True, 'source': cc.SOURCE_POSE}))
        self.assertEqual(bloc['economie_annee1_mad'], CONTRAT['exemple_sans_facture']['economie_annee1_mad'])
        self.assertEqual(bloc['omissions'], CONTRAT['exemple_sans_facture']['omissions'])
        with mock.patch('apps.ventes.domain.entrees.entrees_depuis_lead', return_value=_entrees(None)), \
                mock.patch('apps.ventes.domain.regles_calcul.regles_au_moins', return_value=False):
            ville = self._chiffrer(_calepinage())
        self.assertEqual(ville['production_annuelle_kwh']['etat'], 'omis')
        self.assertIsNone(ville['economie_annee1_mad']['option'])

    def test_ci_relaie_etudier_ci(self):
        etude = {'taille': {'retenue_kwc': 120.0}, 'bilan': {'production_kwh': 182400, 'taux_autoconso': 0.81},
                 'economie_ci': {'statut': 'calcule', 'economie_annee1': {'total_mad': 168000}}}
        lead = N(type_installation='industriel')
        with mock.patch('apps.ventes.domain.etude_ci.etudier_ci', return_value=etude) as ci:
            bloc = self._chiffrer(_calepinage(), lead=lead)
        ci.assert_called_once_with(SOCIETE, {'mode': 'industriel', 'taille_explicite_kwc': 5.0}, lead=lead)
        self.assertEqual(bloc['marche'], 'industriel')
        self.assertEqual([bloc[c]['valeur'] for c in cc.UNITES], [120.0, 182400, 168000, 81.0])

    def test_agricole_non_servi(self):
        bloc = self._chiffrer(_calepinage(), lead=N(type_installation='agricole'))
        attendu = dict(CONTRAT['exemple_agricole'], regles_calcul=bloc['regles_calcul'])
        self.assertEqual(bloc, attendu)

    def test_sans_lead_non_servi_et_echec_indisponible(self):
        sans = self._chiffrer(_calepinage(lead_id=None), lead=None)
        self.assertEqual({sans[c]['etat'] for c in cc.UNITES}, {'non_servi'})
        self.assertEqual(sans['omissions'][0]['motif'], cc.MOTIF_SANS_LEAD)
        devis = N(pk=4, company_id=7, mode_installation='residentiel', regles_calcul=14, etude_params={})
        with mock.patch('apps.ventes.quote_engine.builder.build_quote_data', side_effect=RuntimeError('panne')):
            echec = self._chiffrer(_calepinage(devis))
        self.assertEqual({echec[c]['etat'] for c in cc.UNITES}, {'indisponible'})
        self.assertEqual(echec['omissions'][0]['motif'], cc.MOTIF_ECHEC)
