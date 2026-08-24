# -*- coding: utf-8 -*-
"""L-2OPT — la resynchronisation 3D ne RÉTRÉCIT plus un devis « Les deux ».

L'INCIDENT, sur donnée réelle (DEV-202608-0023, production). Le devis naît
« Les deux (Sans + Avec) » (U2) : il porte un onduleur RÉSEAU (option « sans »),
un onduleur HYBRIDE et une BATTERIE (option « avec »), et son
``etude_params['scenario']`` le DÉCLARE — c'est cette déclaration que le moteur
PDF lit pour rendre la comparaison (PV86/QF6). Puis quelqu'un enregistre le
calepinage 3D, et la resynchronisation :

  * voyait dans l'onduleur réseau l'« intrus » de l'artefact deux-onduleurs
    (PVHEAL) et le SUPPRIMAIT ;
  * supprimait la batterie dès que le layout ne « voulait » pas de batterie ;
  * réécrivait le scénario avec un libellé MONO (``_scenario_stocke`` ne sait
    rendre que « Sans batterie » / « Avec batterie »).

Le moteur relisait alors une déclaration mono : ``nb_options`` retombait à 1,
``sans_items`` se vidait, et la page publique du client ne montrait plus qu'une
seule option — celle que le commercial n'avait jamais choisie seule.

Ces tests verrouillent la préservation, ET son témoin négatif : sur un devis
MONO « Avec batterie », l'artefact deux-onduleurs est toujours assaini comme
avant.

Run :
    DB_NAME=erp_ventes python manage.py test \\
        apps.ventes.tests.test_resync_les_deux -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis
from apps.ventes.services import (SCENARIO_AVEC_BATTERIE, SCENARIO_LES_DEUX)

# Fixtures PARTAGÉES avec le module PV18 : mêmes désignations catalogue (c'est
# par elles que le classifieur range les produits), même client authentifié,
# même fabrique de layout. On importe des FONCTIONS et des CONSTANTES seulement
# — jamais une classe ``TestCase``, qui serait alors collectée deux fois.
from apps.ventes.tests.test_pv18_sync_layout import (
    BAREMES_FORFAIT, CATALOGUE_KIT, CLES_REPONSE, auth_client, layout,
    make_company)

User = get_user_model()

RESEAU = 'Onduleur réseau Huawei 5kW'
HYBRIDE = 'Onduleur hybride Deye 5kW'
BATTERIE = 'Batterie Dyness 5 kWh'
PANNEAU = 'Panneau Jinko 550W'


class _BaseDeuxOptions(TestCase):
    """Catalogue COMPLET + fabriques de devis à deux options."""

    def setUp(self):
        self.company = make_company('l2opt-co')
        self.user = User.objects.create_user(
            username='l2optuser', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth_client(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client L-2OPT')
        self.produits = {}
        for nom, sku, prix in CATALOGUE_KIT:
            fixe, par_panneau = BAREMES_FORFAIT.get(sku, (None, None))
            self.produits[nom] = Produit.objects.create(
                company=self.company, nom=nom, sku='L2OPT-%s' % sku,
                prix_vente=Decimal(prix), prix_achat=Decimal('1'),
                quantite_stock=500,
                prix_fixe_ht=None if fixe is None else Decimal(fixe),
                prix_par_panneau_ht=(None if par_panneau is None
                                     else Decimal(par_panneau)))
        self.compteur = 0

    def _devis(self, *, scenario_stocke, reseau=True, hybride=True,
               batterie=True, panneaux=12):
        """Le devis « Les deux » tel que la création (U2) le compose."""
        self.compteur += 1
        devis = Devis.objects.create(
            company=self.company, reference='DEV-L2OPT-%s' % self.compteur,
            client=self.client_obj, statut=Devis.Statut.BROUILLON,
            created_by=self.user,
            etude_params={'scenario': scenario_stocke})
        devis.lignes.create(
            produit=self.produits[PANNEAU], designation=PANNEAU,
            quantite=Decimal(str(panneaux)), prix_unitaire=Decimal('1100'),
            remise=Decimal('0'), ordre=1)
        ordre = 1
        for actif, nom, prix in ((reseau, RESEAU, '14000'),
                                 (hybride, HYBRIDE, '17000'),
                                 (batterie, BATTERIE, '16000')):
            if not actif:
                continue
            ordre += 1
            devis.lignes.create(
                produit=self.produits[nom], designation=nom,
                quantite=Decimal('1'), prix_unitaire=Decimal(prix),
                remise=Decimal('0'), ordre=ordre)
        return devis

    def _post(self, devis, corps):
        return self.api.post(
            '/api/django/ventes/devis/%s/sync-layout/' % devis.id,
            corps, format='json')

    def _designations(self, devis):
        return set(devis.lignes.values_list('designation', flat=True))


class TestResyncPreserveLesDeux(_BaseDeuxOptions):
    """Un devis NÉ « Les deux » sort de la resynchro toujours à deux options."""

    def test_les_trois_lignes_survivent_a_un_layout_avec_batterie(self):
        devis = self._devis(scenario_stocke=SCENARIO_LES_DEUX)
        resp = self._post(devis, layout(panels=16, kwc=8.8,
                                        scenario='avec_batterie'))
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(set(resp.data), CLES_REPONSE)
        designations = self._designations(devis)
        self.assertIn(RESEAU, designations)
        self.assertIn(HYBRIDE, designations)
        self.assertIn(BATTERIE, designations)
        devis.refresh_from_db()
        self.assertEqual(devis.etude_params['scenario'], SCENARIO_LES_DEUX)

    def test_le_layout_sans_batterie_ne_retire_pas_la_batterie(self):
        """La batterie EST l'option « avec » : un layout « réseau » ne la
        supprime pas d'un devis qui propose les deux."""
        devis = self._devis(scenario_stocke=SCENARIO_LES_DEUX)
        resp = self._post(devis, layout(panels=16, kwc=8.8,
                                        scenario='reseau'))
        self.assertEqual(resp.status_code, 200, resp.content)
        designations = self._designations(devis)
        self.assertIn(BATTERIE, designations)
        self.assertIn(RESEAU, designations)
        self.assertIn(HYBRIDE, designations)
        devis.refresh_from_db()
        self.assertEqual(devis.etude_params['scenario'], SCENARIO_LES_DEUX)

    def test_aucun_avertissement_deux_onduleurs(self):
        """Les DEUX onduleurs sont légitimes ici : rien à signaler."""
        devis = self._devis(scenario_stocke=SCENARIO_LES_DEUX)
        resp = self._post(devis, layout(panels=16, kwc=8.8,
                                        scenario='avec_batterie'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            [a for a in resp.data['avertissements'] if 'onduleur' in a.lower()],
            [])

    def test_la_reponse_dit_les_deux(self):
        devis = self._devis(scenario_stocke=SCENARIO_LES_DEUX)
        resp = self._post(devis, layout(panels=16, kwc=8.8,
                                        scenario='avec_batterie'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['scenario'], 'les_deux')
        self.assertTrue(resp.data['batterie'])

    def test_le_moteur_rend_toujours_deux_options(self):
        """La preuve par le moteur : c'est LUI que la page publique lit."""
        from apps.ventes.quote_engine.builder import build_quote_data

        devis = self._devis(scenario_stocke=SCENARIO_LES_DEUX)
        self._post(devis, layout(panels=16, kwc=8.8, scenario='avec_batterie'))
        devis.refresh_from_db()

        data = build_quote_data(devis)
        self.assertEqual(data['nb_options'], 2)
        self.assertEqual(data['scenario'], SCENARIO_LES_DEUX)
        self.assertTrue(data['sans_items'])
        self.assertGreater(data['total_sans'], 0)
        self.assertGreater(data['total_avec'], 0)

    def test_les_prix_negocies_des_deux_onduleurs_sont_intacts(self):
        devis = self._devis(scenario_stocke=SCENARIO_LES_DEUX)
        devis.lignes.filter(designation=RESEAU).update(
            prix_unitaire=Decimal('11900'))
        self._post(devis, layout(panels=16, kwc=8.8, scenario='avec_batterie'))
        reseau = devis.lignes.get(designation=RESEAU)
        self.assertEqual(reseau.prix_unitaire, Decimal('11900.00'))
        hybride = devis.lignes.get(designation=HYBRIDE)
        self.assertEqual(hybride.prix_unitaire, Decimal('17000.00'))


class TestResyncCompleteLOnduleurManquant(_BaseDeuxOptions):
    """Un devis deux-options AMPUTÉ d'un onduleur est COMPLÉTÉ, pas permuté."""

    def test_le_reseau_manquant_est_re_ajoute_au_prix_catalogue(self):
        """DEV-202608-0023 rejoué : hybride + batterie, réseau disparu."""
        devis = self._devis(scenario_stocke=SCENARIO_LES_DEUX, reseau=False)
        resp = self._post(devis, layout(panels=16, kwc=8.8,
                                        scenario='avec_batterie'))
        self.assertEqual(resp.status_code, 200, resp.content)
        reseau = devis.lignes.get(designation=RESEAU)
        self.assertEqual(reseau.produit_id, self.produits[RESEAU].id)
        self.assertEqual(reseau.prix_unitaire, Decimal('14000.00'))
        self.assertEqual(reseau.remise, Decimal('0.00'))
        # L'hybride n'a PAS été permuté : il est toujours là, intact.
        hybride = devis.lignes.get(designation=HYBRIDE)
        self.assertEqual(hybride.prix_unitaire, Decimal('17000.00'))
        devis.refresh_from_db()
        self.assertEqual(devis.etude_params['scenario'], SCENARIO_LES_DEUX)

    def test_l_hybride_manquant_est_re_ajoute_quand_la_batterie_est_la(self):
        devis = self._devis(scenario_stocke=SCENARIO_LES_DEUX, hybride=False)
        resp = self._post(devis, layout(panels=16, kwc=8.8,
                                        scenario='avec_batterie'))
        self.assertEqual(resp.status_code, 200, resp.content)
        hybride = devis.lignes.get(designation=HYBRIDE)
        self.assertEqual(hybride.produit_id, self.produits[HYBRIDE].id)
        self.assertEqual(hybride.prix_unitaire, Decimal('17000.00'))
        # Le réseau n'a PAS été permuté en hybride : les deux coexistent.
        self.assertTrue(devis.lignes.filter(designation=RESEAU).exists())
        devis.refresh_from_db()
        self.assertEqual(devis.etude_params['scenario'], SCENARIO_LES_DEUX)

    def test_sans_reseau_tarife_on_previent_au_lieu_de_mentir(self):
        Produit.objects.filter(pk=self.produits[RESEAU].pk).update(
            is_archived=True)
        devis = self._devis(scenario_stocke=SCENARIO_LES_DEUX, reseau=False)
        resp = self._post(devis, layout(panels=16, kwc=8.8,
                                        scenario='avec_batterie'))
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertFalse(devis.lignes.filter(designation=RESEAU).exists())
        self.assertTrue(
            any('réseau' in a and 'deux options' in a
                for a in resp.data['avertissements']),
            resp.data['avertissements'])
        # Le scénario stocké ne PROMET pas une option que les lignes ne
        # peuvent pas servir : il dégrade honnêtement.
        devis.refresh_from_db()
        self.assertEqual(devis.etude_params['scenario'],
                         SCENARIO_AVEC_BATTERIE)


class TestTemoinNegatifDevisMono(_BaseDeuxOptions):
    """Le devis MONO « Avec batterie » garde EXACTEMENT l'ancien comportement."""

    def test_l_intrus_reseau_au_prix_catalogue_est_toujours_retire(self):
        devis = self._devis(scenario_stocke=SCENARIO_AVEC_BATTERIE)
        resp = self._post(devis, layout(panels=16, kwc=8.8,
                                        scenario='avec_batterie'))
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertFalse(devis.lignes.filter(designation=RESEAU).exists())
        self.assertTrue(devis.lignes.filter(designation=HYBRIDE).exists())
        self.assertTrue(devis.lignes.filter(designation=BATTERIE).exists())
        devis.refresh_from_db()
        self.assertEqual(devis.etude_params['scenario'],
                         SCENARIO_AVEC_BATTERIE)
        self.assertEqual(resp.data['scenario'], 'avec_batterie')

    def test_un_devis_sans_scenario_stocke_reste_assaini(self):
        """Aucune déclaration = artefact deux-onduleurs, comme avant."""
        devis = self._devis(scenario_stocke=None)
        resp = self._post(devis, layout(panels=16, kwc=8.8,
                                        scenario='avec_batterie'))
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertFalse(devis.lignes.filter(designation=RESEAU).exists())
        devis.refresh_from_db()
        self.assertEqual(devis.etude_params['scenario'],
                         SCENARIO_AVEC_BATTERIE)

    def test_la_batterie_sort_toujours_d_un_devis_mono(self):
        devis = self._devis(scenario_stocke=SCENARIO_AVEC_BATTERIE,
                            reseau=False)
        resp = self._post(devis, layout(panels=16, kwc=8.8,
                                        scenario='reseau'))
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertFalse(devis.lignes.filter(designation=BATTERIE).exists())
