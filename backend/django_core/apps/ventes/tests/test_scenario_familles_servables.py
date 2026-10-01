# -*- coding: utf-8 -*-
"""QJR607 — le scénario stocké et ``option_avec_servable`` dérivent de
``utils.options.familles_servables``.

Constat : ``scenario_servable(False, a_reseau=False, a_hybride=False,
a_batterie=True)`` rendait « Sans batterie » sur un site isolé (onduleur
autonome + batterie), et ``scenario_servable(True, a_reseau=True,
a_hybride=True, a_batterie=False)`` rendait « Sans batterie » sur un devis
BAT-DIFF (ordre fondateur du 17/09 : hybride face au réseau, batterie
différée) — alors que le builder lit ``familles_servables`` et sert deux
options. Une resynchro réduisait donc un BAT-DIFF « Les deux » à une option.

Run :
    python manage.py test apps.ventes.tests.test_scenario_familles_servables -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from apps.crm.models import Client, Lead
from apps.stock.models import Produit
from apps.ventes.domain.scenario import (
    SCENARIO_AVEC_BATTERIE, SCENARIO_LES_DEUX, SCENARIO_SANS_BATTERIE,
    scenario_servable)
from apps.ventes.models import Devis
from apps.ventes.tests.test_pv18_sync_layout import (
    BAREMES_FORFAIT, CATALOGUE_KIT, auth_client, layout, make_company)
from apps.ventes.utils.options import (
    deux_options_depuis_paniers, familles_servables)

User = get_user_model()

RESEAU = 'Onduleur réseau Huawei 5kW'
HYBRIDE = 'Onduleur hybride Deye 5kW'
BATTERIE = 'Batterie Dyness 5 kWh'
PANNEAU = 'Panneau Jinko 550W'
OFFGRID = 'Deye Off-Grid 6kW'


class TableDAccord(SimpleTestCase):
    """Le libellé stocké est la traduction de ``(sans_ok, avec_ok)``."""

    def test_les_cas_du_constat(self):
        self.assertEqual(
            scenario_servable(False, a_reseau=False, a_hybride=False,
                              a_batterie=True, a_offgrid=True),
            SCENARIO_AVEC_BATTERIE)
        self.assertEqual(
            scenario_servable(True, a_reseau=True, a_hybride=True,
                              a_batterie=False),
            SCENARIO_LES_DEUX)

    def test_accord_sur_toutes_les_combinaisons(self):
        for masque in range(32):
            reseau, hybride, offgrid, batterie, demande = (
                bool(masque & (1 << i)) for i in range(5))
            with self.subTest(reseau=reseau, hybride=hybride,
                              offgrid=offgrid, batterie=batterie,
                              demande=demande):
                sans_ok, avec_ok = familles_servables(
                    has_reseau=reseau, has_hybride=hybride,
                    has_offgrid=offgrid, has_batterie=batterie)
                libelle = scenario_servable(
                    demande, a_reseau=reseau, a_hybride=hybride,
                    a_batterie=batterie, a_offgrid=offgrid)
                deux = deux_options_depuis_paniers(
                    sans_ok, avec_ok, alternative_declaree=demande)
                self.assertEqual(libelle == SCENARIO_LES_DEUX, deux)
                if libelle == SCENARIO_AVEC_BATTERIE:
                    # « Avec batterie » exige une batterie RÉELLE.
                    self.assertTrue(avec_ok and batterie)


class _Base(TestCase):
    def setUp(self):
        self.company = make_company('qjr607-co')
        self.user = User.objects.create_user(
            username='qjr607user', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth_client(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client QJR607')
        self.produits = {}
        for nom, sku, prix in CATALOGUE_KIT + [(OFFGRID, 'Q607-OFF', '16000')]:
            fixe, par_panneau = BAREMES_FORFAIT.get(sku, (None, None))
            self.produits[nom] = Produit.objects.create(
                company=self.company, nom=nom, sku='Q607-%s' % sku,
                prix_vente=Decimal(prix), prix_achat=Decimal('1'),
                quantite_stock=500,
                prix_fixe_ht=None if fixe is None else Decimal(fixe),
                prix_par_panneau_ht=(None if par_panneau is None
                                     else Decimal(par_panneau)))

    def _devis(self, noms, scenario=None):
        devis = Devis.objects.create(
            company=self.company, reference='DEV-Q607-%d' % Devis.objects.count(),
            client=self.client_obj, statut=Devis.Statut.BROUILLON,
            created_by=self.user,
            etude_params={'scenario': scenario} if scenario else {})
        devis.lignes.create(
            produit=self.produits[PANNEAU], designation=PANNEAU,
            quantite=Decimal('12'), prix_unitaire=Decimal('1100'),
            remise=Decimal('0'), ordre=1)
        for ordre, nom in enumerate(noms, start=2):
            devis.lignes.create(
                produit=self.produits[nom], designation=nom,
                quantite=Decimal('1'),
                prix_unitaire=self.produits[nom].prix_vente,
                remise=Decimal('0'), ordre=ordre)
        return devis


class OptionAvecServableDelegue(_Base):
    def test_accord_avec_familles_servables(self):
        from apps.ventes.domain.lignes import option_avec_servable
        cas = {
            (RESEAU, HYBRIDE): True,          # BAT-DIFF
            (HYBRIDE,): False,                # Z1 : hybride seul
            (HYBRIDE, BATTERIE): True,
            (RESEAU, BATTERIE): False,
            (OFFGRID, BATTERIE): True,        # site isolé
            (OFFGRID,): False,
        }
        for noms, attendu in cas.items():
            with self.subTest(noms=noms):
                self.assertEqual(option_avec_servable(self._devis(noms)),
                                 attendu)


class SiteIsoleNaitAvecBatterie(_Base):
    def test_build_devis_auto_raccordement_aucun(self):
        lead = Lead.objects.create(
            company=self.company, nom='Isolé', email='q607@example.com',
            raccordement='aucun', taille_souhaitee_kwc=Decimal('5'))
        reponse = self.api.post('/api/django/ventes/devis/auto/',
                                {'lead': lead.id}, format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        devis = Devis.objects.get(pk=reponse.data['id'])
        self.assertEqual(devis.etude_params['scenario'],
                         SCENARIO_AVEC_BATTERIE)


class BatDiffResynchro(_Base):
    def test_les_deux_conserve_et_deux_options_rendues(self):
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = self._devis((RESEAU, HYBRIDE), scenario=SCENARIO_LES_DEUX)
        reponse = self.api.post(
            '/api/django/ventes/devis/%s/sync-layout/' % devis.id,
            layout(panels=16, kwc=8.8, scenario='reseau'), format='json')
        self.assertEqual(reponse.status_code, 200, reponse.content)
        devis.refresh_from_db()
        self.assertEqual(devis.etude_params['scenario'], SCENARIO_LES_DEUX)
        self.assertNotEqual(devis.etude_params['scenario'],
                            SCENARIO_SANS_BATTERIE)
        data = build_quote_data(devis)
        self.assertEqual(data['nb_options'], 2)
