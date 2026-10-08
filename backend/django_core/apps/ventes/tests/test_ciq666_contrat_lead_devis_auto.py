# -*- coding: utf-8 -*-
"""CIQ666 — le devis automatique C&I lit le CONTRAT d'électricité déclaré au
lead (décision fondateur 08/10/2026) : la grille ONEE de CE contrat est
résolue (aucun mock de ``tarif_applicable``), au lieu du refus
« Tarif non déclaré et contrat d'électricité inconnu » (``tarif_omis``).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_ciq666_contrat_lead_devis_auto"
"""
from decimal import Decimal

from apps.ventes import tarif_ci
from apps.ventes.domain import etude_ci
from apps.ventes.models import Devis
from apps.ventes.services import AutoDevisError, build_devis_auto
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
                          tension_raccordement=None, raccordement=None,
                          categorie_commerciale=None, type_toiture=None,
                          contrat_electricite='bt_patente')
        devis = self._auto_reel(lead)
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)
        self.assertGreater(devis.lignes.count(), 0)

    def test_bt_sans_contrat_refuse_tarif_omis(self):
        lead = self._lead(conso_mensuelle_kwh=Decimal('6000'))
        avant = Devis.objects.filter(company=self.co).count()
        with self.assertRaises(AutoDevisError) as ctx:
            self._auto_reel(lead)
        self.assertEqual(ctx.exception.field, 'tarif_declare')
        self.assertIn("contrat d'électricité inconnu", ctx.exception.message)
        self.assertEqual(Devis.objects.filter(company=self.co).count(), avant)

    def test_ne_sait_pas_refuse_aussi(self):
        lead = self._lead(conso_mensuelle_kwh=Decimal('6000'),
                          contrat_electricite='ne_sait_pas')
        with self.assertRaises(AutoDevisError) as ctx:
            self._auto_reel(lead)
        self.assertEqual(ctx.exception.field, 'tarif_declare')


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
