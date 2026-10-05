# -*- coding: utf-8 -*-
"""ACAL165 (C-ACAL-061) — l'étude électrique du devis lit les températures,
longueurs et régime du calepinage LIÉ.

Avant : −5 / 70 °C, 30 / 15 m et TT forfaitaires pour TOUT devis, même lié à
un calepinage d'Ifrane (TMY −9,89 °C) dont l'onglet Verdict dimensionnait à
d'autres bornes. Désormais : surcharge explicite du devis d'abord, puis le
calepinage lié (mêmes températures que son Verdict, longueurs et régime
SAISIS), les forfaits seulement sans l'un ni l'autre ; la provenance est
publiée (``source_entree``). Une étude rangée d'un devis ENVOYÉ n'est jamais
recalculée par la seule arrivée de la source : seul un calcul VOLONTAIRE
(surcharges POSTées, lignes modifiées) l'adopte.

Devis, lignes, fiches techniques et Calepinage RÉELS en base ; fournisseur TMY
INJECTÉ (``enregistrer_fournisseur_temperatures``, aucun réseau) — la source
n'est pas mockée.

Test-du-test : ignorer le calepinage dans ``construire_entree_et_source`` ⇒
``test_temperatures_du_calepinage_quand_lie`` échoue ; recalculer l'envoyé ⇒
``test_envoye_non_recalcule`` échoue.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_acal_etude_electrique_calepinage"
"""
from decimal import Decimal

from django.test import TestCase

from apps.calepinage.models import Calepinage
from apps.calepinage.services.electrique import (
    CLE_ENTREE, enregistrer_fournisseur_temperatures,
)
from apps.crm.models import Client
from apps.stock.models import FicheTechnique, Produit
from apps.ventes import electrical_service as es
from apps.ventes.models import Devis, LigneDevis
from authentication.models import Company
from core.electrique.types import TEMP_CHAUD_DEFAUT_C, TEMP_FROID_DEFAUT_C

#: Site d'Ifrane (TMY PVGIS) — les extrêmes de l'audit.
IFRANE = {'lat': 33.5333, 'lng': -5.1}
#: Chaud de CELLULE (ACAL164) : 33,53 + (45 − 20) × 1000 / 800.
CHAUD_CELLULE_IFRANE = 64.78


def _tmy_ifrane(lat, lon):
    return {'temperature_min_c': -9.89, 'temperature_max_c': 33.53,
            'base': 'PVGIS-SARAH3', 'fenetre_annees': '2005-2023'}


class EntreeDuDevis(TestCase):

    def setUp(self):
        precedent = enregistrer_fournisseur_temperatures(_tmy_ifrane)
        self.addCleanup(enregistrer_fournisseur_temperatures, precedent)
        self.company = Company.objects.create(nom='ACAL165',
                                              slug='acal165-co')
        self.crm_client = Client.objects.create(
            company=self.company, nom='Client ACAL165',
            email='acal165@example.com')
        self.n = 0

    def _devis(self):
        self.n += 1
        devis = Devis.objects.create(
            company=self.company, reference='DV-ACAL165-%d' % self.n,
            client=self.crm_client,
            roof_layout={'_pans_geometry': [
                {'label': 'Sud', 'nb_panneaux': 20, 'azimut_deg': 180,
                 'inclinaison_deg': 20}]},
            layout_hash='h-acal165-%d' % self.n)
        panneau = Produit.objects.create(
            company=self.company, nom='Panneau PV 550W mono',
            sku='ACAL165-PV-%d' % self.n, prix_vente=Decimal('1200'),
            prix_achat=Decimal('900'), quantite_stock=100)
        onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur réseau 10kW triphasé',
            sku='ACAL165-OND-%d' % self.n, prix_vente=Decimal('15000'),
            prix_achat=Decimal('11000'), quantite_stock=10)
        FicheTechnique.objects.create(
            company=self.company, produit=panneau, type_fiche='module',
            pmax_wc=Decimal('550.00'), voc_v=Decimal('49.90'),
            isc_a=Decimal('14.02'), vmp_v=Decimal('41.80'),
            imp_a=Decimal('13.16'), noct_c=Decimal('45.0'),
            temp_coeff_voc_pct_c=Decimal('-0.270'),
            temp_coeff_pmax_pct_c=Decimal('-0.350'))
        FicheTechnique.objects.create(
            company=self.company, produit=onduleur, type_fiche='onduleur',
            ond_ac_kw=Decimal('10.00'), ond_phases=3, ond_n_mppt=2,
            ond_mppt_v_min=Decimal('200.0'), ond_mppt_v_max=Decimal('950.0'),
            ond_v_max_abs=Decimal('1100.0'),
            ond_i_max_mppt_a=Decimal('26.0'),
            ond_rendement_euro_pct=Decimal('98.0'), ond_bat_aucune=True)
        LigneDevis.objects.create(
            devis=devis, produit=panneau, designation='Panneau PV 550W mono',
            quantite=20, prix_unitaire=Decimal('1200'))
        LigneDevis.objects.create(
            devis=devis, produit=onduleur,
            designation='Onduleur réseau 10kW triphasé',
            quantite=1, prix_unitaire=Decimal('15000'))
        self.panneau = panneau
        return devis

    def _lier_calepinage(self, devis):
        return Calepinage.objects.create(
            company=self.company, devis=devis, titre='Ifrane',
            roof_layout={'pin': IFRANE, 'zones': []},
            # Module DÉSIGNÉ sur le calepinage (D-ACAL-10, provenance
            # explicite) : sa fiche porte le NOCT du chaud de cellule.
            resultat={CLE_ENTREE: {'module_produit': self.panneau.pk,
                                   'dc_m': 22.0, 'ac_m': 8.0,
                                   'regime': 'TN'}})

    def test_temperatures_du_calepinage_quand_lie(self):
        devis = self._devis()
        self._lier_calepinage(devis)
        entree, source, lie = es.construire_entree_et_source(devis)
        self.assertTrue(lie)
        self.assertEqual(entree.temp_froid_c, -9.89)
        self.assertAlmostEqual(entree.temp_chaud_c, CHAUD_CELLULE_IFRANE,
                               places=2)
        self.assertEqual(entree.dc_m, 22.0)
        self.assertEqual(entree.ac_m, 8.0)
        self.assertEqual(entree.regime, 'TN')
        self.assertEqual(source, {'temperatures': 'calepinage',
                                  'longueurs': 'calepinage',
                                  'regime': 'calepinage'})
        design = es.build_electrical_design(devis)
        self.assertEqual(design['source_entree'], source)
        self.assertEqual(design['parametres']['dc_m'], 22.0)
        self.assertEqual(design['parametres']['regime'], 'TN')
        # Persistance : l'étude rangée porte la provenance.
        devis.refresh_from_db()
        self.assertEqual(devis.electrical_design['source_entree'], source)

    def test_surcharge_du_devis_gagne(self):
        devis = self._devis()
        self._lier_calepinage(devis)
        entree, source, _lie = es.construire_entree_et_source(
            devis, {'temp_froid_c': -2.0, 'temp_chaud_c': 60.0,
                    'dc_m': 40.0, 'regime': 'TT'})
        self.assertEqual(entree.temp_froid_c, -2.0)
        self.assertEqual(entree.temp_chaud_c, 60.0)
        self.assertEqual(entree.dc_m, 40.0)
        self.assertEqual(entree.regime, 'TT')
        self.assertEqual(source, {'temperatures': 'surcharge',
                                  'longueurs': 'surcharge',
                                  'regime': 'surcharge'})

    def test_sans_calepinage_inchange(self):
        devis = self._devis()
        entree, source, lie = es.construire_entree_et_source(devis)
        self.assertFalse(lie)
        self.assertEqual(entree, es.construire_entree_et_source(
            devis, avec_calepinage=False)[0])
        self.assertEqual(entree.temp_froid_c, TEMP_FROID_DEFAUT_C)
        self.assertEqual(entree.temp_chaud_c, TEMP_CHAUD_DEFAUT_C)
        self.assertEqual(entree.dc_m, es.DC_M_PAR_DEFAUT)
        self.assertEqual(entree.ac_m, es.AC_M_DEFAUT)
        self.assertEqual(entree.regime, 'TT')
        self.assertEqual(source, es.SOURCE_ENTREE_DEFAUT)
        es.build_electrical_design(devis)
        devis.refresh_from_db()
        # L'empreinte d'un devis sans calepinage est celle d'avant ACAL165.
        self.assertEqual(devis.electrical_design_hash,
                         es.empreinte_entree(devis, entree))

    def test_envoye_non_recalcule(self):
        devis = self._devis()
        # L'étude d'AVANT : rangée sans calepinage (forfaits), puis envoyée.
        avant = es.build_electrical_design(devis)
        devis.statut = Devis.Statut.ENVOYE
        devis.save(update_fields=['statut'])
        devis.refresh_from_db()
        hash_avant = devis.electrical_design_hash
        self._lier_calepinage(devis)

        # Passif (lecture, rafraîchissement d'enregistrement) : rien ne bouge.
        self.assertEqual(es.build_electrical_design(devis), avant)
        es.rafraichir_conception_electrique_devis(devis)
        devis.refresh_from_db()
        self.assertEqual(devis.electrical_design_hash, hash_avant)
        self.assertEqual(devis.electrical_design['parametres']['dc_m'],
                         es.DC_M_PAR_DEFAUT)

        # Calcul VOLONTAIRE (surcharges POSTées) : la source calepinage joue.
        recalcule = es.build_electrical_design(devis, overrides={})
        self.assertEqual(recalcule['source_entree']['temperatures'],
                         'calepinage')
        devis.refresh_from_db()
        self.assertNotEqual(devis.electrical_design_hash, hash_avant)
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
