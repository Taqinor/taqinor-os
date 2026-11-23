# -*- coding: utf-8 -*-
"""CIQ666 — le devis automatique C&I lit le CONTRAT d'électricité déclaré au
lead (décision fondateur 08/10/2026) : la grille ONEE de CE contrat est
résolue (aucun mock de ``tarif_applicable``). ADEV125 (D-ACAL-92, 23/11/2026) —
sans contrat déclaré, le tarif basse tension est SUPPOSÉ (dit, estimation) au
lieu du refus « Tarif non déclaré et contrat d'électricité inconnu ».

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_ciq666_contrat_lead_devis_auto"
"""
from decimal import Decimal

from apps.ventes import tarif_ci
from apps.ventes.domain import etude_ci
from apps.ventes.models import Devis
from apps.ventes.services import build_devis_auto
from apps.ventes.tests.test_ciq120_devis_auto_ci import _Base


class DevisAutoContratDuLead(_Base):
    def _auto_reel(self, lead):
        return build_devis_auto(lead=lead, user=self.user, company=self.co)

    def test_bt_commercial_avec_contrat_declare_brouillon(self):
        lead = self._lead(conso_mensuelle_kwh=Decimal('6000'),
                          contrat_electricite='bt_patente')
        devis = self._auto_reel(lead)
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)
        self.assertTrue(devis.lignes.filter(produit=self.panneau).exists())
        # Le contrat déclaré est recopié dans l'étude du devis (tarif_declare).
        self.assertEqual(devis.etude_params['tarif_declare'],
                         {'contrat': 'bt_patente'})

    def test_lead_du_e2e_ciq127_avec_contrat(self):
        # Même lead que frontend/e2e/devis-ci-serveur.spec.js (CIQ127) :
        # kWh mensuel, taille souhaitée, jours et heures, contrat déclaré.
        lead = self._lead(conso_mensuelle_kwh=Decimal('12000'),
                          taille_souhaitee_kwc=Decimal('20'),
                          jours_ouverture=[1, 2, 3, 4, 5, 6],
                          heure_debut=8, heure_fin=18,
                          tension_raccordement=None,
                          # ADEV89 — la phase du site est un prérequis du
                          # devis automatique (le lead e2e la déclare aussi).
                          raccordement='triphase',
                          categorie_commerciale=None, type_toiture=None,
                          contrat_electricite='bt_patente')
        devis = self._auto_reel(lead)
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)
        self.assertGreater(devis.lignes.count(), 0)

    def _suppose(self, lead, contrat):
        """ADEV125 (D-ACAL-92) — le devis part au tarif BT supposé, dit avec le
        champ de la fiche, marqué estimation, jamais figé au devis."""
        journal = {}
        devis = build_devis_auto(lead=lead, user=self.user, company=self.co,
                                 journal_auto=journal)
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)
        self.assertNotIn('tarif_declare', devis.etude_params)
        etude = devis.etude_params['etude_ci']
        resolu = etude['entrees_resolues']['tarif_declare']
        self.assertEqual(resolu['valeur'], {'contrat': contrat})
        self.assertEqual(resolu['provenance']['origine'], 'estimation')
        hyp = {h['cle']: h for h in etude['hypotheses']}
        self.assertEqual((hyp['contrat_electricite']['valeur'],
                          hyp['contrat_electricite']['statut']), (contrat, 'estimation'))
        self.assertIsNotNone(etude['economie_ci'])
        dites = [a for a in journal['alertes'] if a['champ_lead'] == 'contrat_electricite']
        self.assertEqual(len(dites), 1, journal['alertes'])
        self.assertIn('basse tension', dites[0]['message'])
        self.assertIn('estimation', dites[0]['message'])
        # Relu : le rafraîchisseur re-suppose — même étude, même hypothèse.
        devis.refresh_from_db()
        self.assertEqual(etude_ci.rafraichir_etude_ci_devis(devis, force=True)['hypotheses'],
                         etude['hypotheses'])
        return etude

    def test_adev125_bt_sans_contrat_tarif_bt_suppose_dit_et_estimation(self):
        lead = self._lead(conso_mensuelle_kwh=Decimal('6000'))
        self._suppose(lead, 'bt_patente')
        apercu = etude_ci.etudier_ci(self.co, {'mode': 'commercial'}, lead=lead)
        self.assertTrue(apercu['sous_reserve_visite']['valeur'])

    def test_adev125_facture_mad_seule_et_ne_sait_pas_aboutissent(self):
        # Le cas mesuré en production : une facture en dirhams et une catégorie.
        self._suppose(self._lead(facture_hiver=Decimal('3500')), 'bt_patente')
        self._suppose(self._lead(conso_mensuelle_kwh=Decimal('6000'),
                                 contrat_electricite='ne_sait_pas'), 'bt_patente')

    def test_adev125_industriel_force_motrice_mt_et_domestique_jamais_supposes(self):
        res = etude_ci.resoudre_entrees({}, lead=self._lead(type_installation='industriel'))
        from apps.ventes.domain.suppositions_ci import supposer_entrees
        self.assertEqual(supposer_entrees(res, 'industriel')[0]['valeur'], 'bt_force_motrice')
        # Rien n'est supposé contre une déclaration (MT, contrat domestique).
        for kw in ({'tension_raccordement': 'mt'}, {'contrat_electricite': 'bt_domestique'}):
            res = etude_ci.resoudre_entrees({}, lead=self._lead(**kw))
            self.assertEqual(supposer_entrees(res, 'commercial'), [], kw)


class TarifSaisiSansContrat(_Base):
    """Un tarif du devis saisi SANS contrat garde celui du lead."""

    def test_contrat_du_lead_herite(self):
        lead = self._lead(conso_mensuelle_kwh=Decimal('6000'),
                          contrat_electricite='bt_force_motrice',
                          option_tarifaire_bt='bi_horaire')
        res = etude_ci.resoudre_entrees(
            {'tarif_declare': {'contrat': None, 'base_tarifs': 'ttc'}},
            lead=lead)
        td = res.valeur('tarif_declare')
        self.assertEqual(td['contrat'], 'bt_force_motrice')
        self.assertTrue(td['option_bi_horaire'])
        self.assertEqual(tarif_ci.tarif_applicable(td, tension='bt')['origine'],
                         tarif_ci.ORIGINE_GRILLE)

    def test_contrat_du_devis_prime(self):
        lead = self._lead(contrat_electricite='bt_force_motrice')
        res = etude_ci.resoudre_entrees(
            {'tarif_declare': {'contrat': 'bt_patente'}}, lead=lead)
        self.assertEqual(res.valeur('tarif_declare'), {'contrat': 'bt_patente'})
