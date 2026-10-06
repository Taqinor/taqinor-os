# -*- coding: utf-8 -*-
"""CIQ120 — devis automatique commercial / industriel par le serveur.

``build_devis_auto`` accepte commercial et industriel (origine « auto ») :
``etudier_ci`` → taille retenue → composition du moteur → devis brouillon →
étude v2 écrite une fois. PVGIS simulé (table vendorisée de Casablanca).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_ciq120_devis_auto_ci"
"""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Lead
from apps.stock.models import FicheTechnique, Produit
from apps.ventes import tarif_ci
from apps.ventes.domain import etude_ci
from apps.ventes.models import Devis
from apps.ventes.services import AutoDevisError, build_devis_auto
from apps.ventes.tests.test_ciq118_etude_ci_preview import _production_casablanca
from authentication.models import Company

User = get_user_model()


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.co = Company.objects.get_or_create(
            slug='ciq120-co', defaults={'nom': 'CIQ120 Co'})[0]
        cls.panneau = Produit.objects.create(
            company=cls.co, nom='Panneau 710W', prix_vente=Decimal('1272.73'),
            prix_achat=Decimal('800'))
        FicheTechnique.objects.create(
            company=cls.co, produit=cls.panneau, type_fiche='module',
            pmax_wc=Decimal('710'), vmp_v=Decimal('40'), voc_v=Decimal('48'),
            isc_a=Decimal('18'), imp_a=Decimal('17'))
        cls.onduleur = Produit.objects.create(
            company=cls.co, nom='Onduleur réseau Huawei 50kW Triphasé',
            prix_vente=Decimal('45833.33'), prix_achat=Decimal('30000'),
            role_devis='onduleur_reseau', garantie='10 ans constructeur')
        FicheTechnique.objects.create(
            company=cls.co, produit=cls.onduleur, type_fiche='onduleur',
            ond_ac_kw=Decimal('50'), ond_phases=3, ond_n_mppt=4,
            ond_mppt_v_min=Decimal('200'), ond_mppt_v_max=Decimal('1000'),
            ond_v_max_abs=Decimal('1100'), ond_i_max_mppt_a=Decimal('30'),
            ond_rendement_euro_pct=Decimal('98.4'))
        cls.structure = Produit.objects.create(
            company=cls.co, nom='Structure bac acier C&I', prix_vente=Decimal('300'),
            prix_achat=Decimal('150'), role_ci='structure_ci', type_pose='bac_acier')

    def setUp(self):
        patcher = mock.patch.object(etude_ci, 'lire_production',
                                    side_effect=_production_casablanca)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.user = User.objects.create_user(
            username='ciq120_user', password='x', role_legacy='responsable',
            company=self.co)

    def _lead(self, **kw):
        kw.setdefault('type_installation', 'commercial')
        kw.setdefault('ville', 'Casablanca')
        kw.setdefault('categorie_commerciale', 'bureau')
        kw.setdefault('tension_raccordement', 'bt')
        kw.setdefault('raccordement', 'triphase')
        kw.setdefault('type_toiture', 'bac_acier')
        return Lead.objects.create(company=self.co, nom='Pro CIQ120', **kw)

    def _auto(self, lead):
        # Le lead ne porte aucune colonne « contrat d'électricité » : sans tarif
        # sourcé, aucune économie n'est chiffrée. Le test fixe la grille
        # officielle (BT patenté, MT général) — jamais un prix plat.
        with mock.patch.object(tarif_ci, 'tarif_applicable', side_effect=_tarif_grille):
            return build_devis_auto(lead=lead, user=self.user, company=self.co)


_TARIF_APPLICABLE = tarif_ci.tarif_applicable


def _tarif_grille(tarif_declare, *, tension=None, millesime=2026):
    contrat = 'mt_general' if tension == 'mt' else 'bt_patente'
    return _TARIF_APPLICABLE({'contrat': contrat}, tension=tension, millesime=millesime)


class DevisAutoCITests(_Base):
    def test_lead_commercial_complet_devis_brouillon(self):
        lead = self._lead(conso_mensuelle_kwh=Decimal('6000'))
        devis = self._auto(lead)
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)
        self.assertEqual(devis.mode_installation, 'commercial')
        produits = set(devis.lignes.values_list('produit_id', flat=True))
        self.assertIn(self.panneau.id, produits)
        self.assertIn(self.onduleur.id, produits)
        self.assertIn(self.structure.id, produits)
        noms = ' '.join(devis.lignes.values_list('designation', flat=True)).lower()
        self.assertNotIn('hybride', noms)
        self.assertNotIn('batterie', noms)
        etude = devis.etude_params['etude_ci']
        for cle in ('entrees_resolues', 'profil_charge', 'production', 'taille',
                    'bilan', 'alertes', 'hypotheses', 'version', 'empreinte'):
            self.assertIn(cle, etude)
        self.assertIn('production_figee', devis.etude_params)

    def test_lead_mt_tension_stockee(self):
        lead = self._lead(conso_mensuelle_kwh=Decimal('20000'), type_installation='industriel',
                          tension_raccordement='mt', categorie_commerciale=None,
                          jours_ouverture=[1, 2, 3, 4, 5, 6], heure_debut=7, heure_fin=19)
        devis = self._auto(lead)
        self.assertEqual(devis.etude_params['tension'], 'mt')

    def test_lead_sans_consommation_422_nomme_le_champ(self):
        lead = self._lead()
        avant = Devis.objects.filter(company=self.co).count()
        with self.assertRaises(AutoDevisError) as ctx:
            self._auto(lead)
        self.assertEqual(ctx.exception.field, 'conso_mensuelle_kwh')
        self.assertEqual(Devis.objects.filter(company=self.co).count(), avant)

    def test_structure_sans_prix_422_prix_a_renseigner(self):
        Produit.objects.filter(pk=self.structure.pk).update(prix_vente=0)
        lead = self._lead(conso_mensuelle_kwh=Decimal('6000'))
        with self.assertRaises(AutoDevisError) as ctx:
            self._auto(lead)
        self.assertIn('Prix à renseigner', ctx.exception.message)
        self.assertEqual(ctx.exception.field, 'composition')

    def test_type_du_lead_inchange(self):
        lead = self._lead(conso_mensuelle_kwh=Decimal('6000'))
        self._auto(lead)
        lead.refresh_from_db()
        self.assertEqual(lead.type_installation, 'commercial')

    def test_tunnel_refuse_pour_le_ci(self):
        lead = self._lead(conso_mensuelle_kwh=Decimal('6000'))
        with self.assertRaises(AutoDevisError) as ctx:
            build_devis_auto(lead=lead, user=self.user, company=self.co, origine='tunnel')
        self.assertEqual(ctx.exception.field, 'type_installation')

    def test_agricole_tunnel_toujours_refuse(self):
        # AGR124 — l'agricole est ouvert au bouton (origine « auto ») ; le
        # tunnel du site, lui, reste refusé.
        lead = self._lead(type_installation='agricole', conso_mensuelle_kwh=Decimal('6000'))
        with self.assertRaises(AutoDevisError) as ctx:
            build_devis_auto(lead=lead, user=self.user, company=self.co,
                             origine='tunnel')
        self.assertEqual(ctx.exception.field, 'type_installation')
