# -*- coding: utf-8 -*-
"""QJR33 (29/08/2026) — ``services.cible_depuis_lignes`` cesse de mélanger le
COMPTE d'une option et le WATTAGE de l'autre.

LE DÉFAUT. Depuis CTX3D, quatre des cinq grandeurs rendues (``panneaux``,
``scenario``, ``batterie``, et donc ``kwc``) se lisaient sur le panier de
l'option demandée — mais la ligne DOMINANTE, celle qui porte ``panel_watt``,
était encore cherchée dans TOUTES les lignes panneau du devis. Sur un devis
« Les deux » à DEUX modèles de panneau (8 × 710 Wc pour l'option « sans »,
10 × 440 Wc pour l'option « avec »), le ``kwc`` rendu mariait le compte d'une
option au wattage de l'autre — et ce kWc partait tel quel dans le contrat 3D
(PV17).

NOTE DE PÉRIMÈTRE : cette fonction sera DÉPLACÉE telle quelle vers
``domain/lignes.py`` (QJR73). Ce module épingle son COMPORTEMENT, pas son
adresse — il suivra le déplacement sans changer une assertion.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_qjr_cible_depuis_lignes"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.services import cible_depuis_lignes
from authentication.models import Company

User = get_user_model()


class _CibleBase(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='qjr33-co', defaults={'nom': 'QJR33 Co'})
        self.client_obj = Client.objects.create(
            company=self.company, nom='Cible', prenom='QJR33',
            telephone='+212600000094')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-QJR33-0001',
            client=self.client_obj, statut=Devis.Statut.BROUILLON,
            taux_tva=Decimal('20.00'),
            mode_installation=Devis.ModeInstallation.RESIDENTIEL,
            etude_params={})

    def _produit(self, nom, prix='1000'):
        """UN produit par NOM : deux lignes variantées du même modèle doivent
        partager le même produit (sinon la règle d'identité L-2OPT verrait
        deux modèles là où il n'y en a qu'un)."""
        produit = Produit.objects.filter(company=self.company, nom=nom).first()
        if produit is None:
            produit = Produit.objects.create(
                company=self.company, nom=nom, prix_vente=Decimal(prix),
                quantite_stock=100)
        return produit

    def _ligne(self, nom, *, quantite, variante='', prix='1000'):
        return LigneDevis.objects.create(
            devis=self.devis, produit=self._produit(nom, prix),
            designation=nom,
            quantite=Decimal(str(quantite)), prix_unitaire=Decimal(prix),
            remise=Decimal('0'), variante=variante)


class DeuxModelesDeuxOptionsTests(_CibleBase):
    """LE cas du défaut : deux options, DEUX modèles de panneau."""

    def setUp(self):
        super().setUp()
        # Option « sans » : 8 panneaux de 710 Wc (la ligne la PLUS GROSSE en
        # wattage, mais pas en quantité).
        self._ligne('Panneau Canadian Solar 710W', quantite=8,
                    variante='sans')
        self._ligne('Onduleur réseau Huawei 5kW Monophasé', quantite=1,
                    variante='sans', prix='9000')
        # Option « avec » : 10 panneaux de 440 Wc — la ligne la plus grosse EN
        # QUANTITÉ, donc la « dominante » que l'ancien code retenait pour les
        # DEUX options.
        self._ligne('Panneau Jinko 440W', quantite=10, variante='avec')
        self._ligne('Onduleur hybride Deye 5kW Monophasé', quantite=1,
                    variante='avec', prix='12000')
        self._ligne('Batterie Dyness 10 kWh', quantite=1, variante='avec',
                    prix='30000')

    def test_l_option_sans_est_coherente_compte_x_wattage_de_SA_variante(self):
        """ROUGE avant QJR33 : 8 panneaux × 710 Wc = 5,68 kWc était rendu avec
        ``panel_watt`` = 440 (la dominante de l'AUTRE option) — soit 3,52 kWc,
        ou l'inverse selon la ligne retenue. Les deux nombres devaient
        s'accorder, ils ne le faisaient pas."""
        cible = cible_depuis_lignes(self.devis, 'sans')
        self.assertEqual(cible['panneaux'], 8)
        self.assertEqual(cible['panel_watt'], 710)
        self.assertAlmostEqual(cible['kwc'], 5.68, places=3)
        self.assertAlmostEqual(
            cible['kwc'],
            round(cible['panneaux'] * cible['panel_watt'] / 1000.0, 3),
            places=6)

    def test_l_option_avec_est_coherente_compte_x_wattage_de_SA_variante(self):
        cible = cible_depuis_lignes(self.devis, 'avec')
        self.assertEqual(cible['panneaux'], 10)
        self.assertEqual(cible['panel_watt'], 440)
        self.assertAlmostEqual(cible['kwc'], 4.40, places=3)
        self.assertAlmostEqual(
            cible['kwc'],
            round(cible['panneaux'] * cible['panel_watt'] / 1000.0, 3),
            places=6)

    def test_les_deux_options_ne_rendent_pas_le_meme_wattage(self):
        """La preuve directe du mélange : avant QJR33 les deux vues
        partageaient la MÊME ligne dominante, donc le MÊME wattage."""
        sans = cible_depuis_lignes(self.devis, 'sans')
        avec = cible_depuis_lignes(self.devis, 'avec')
        self.assertNotEqual(sans['panel_watt'], avec['panel_watt'])
        self.assertNotEqual(sans['kwc'], avec['kwc'])

    def test_le_scenario_et_la_batterie_restent_ceux_de_l_option(self):
        """Non-régression CTX3D — les cinq grandeurs décrivent LA MÊME
        installation."""
        sans = cible_depuis_lignes(self.devis, 'sans')
        avec = cible_depuis_lignes(self.devis, 'avec')
        self.assertEqual(sans['scenario'], 'reseau')
        self.assertFalse(sans['batterie'])
        self.assertEqual(avec['scenario'], 'avec_batterie')
        self.assertTrue(avec['batterie'])

    def test_l_avertissement_deux_modeles_nomme_la_ligne_de_l_option(self):
        sans = cible_depuis_lignes(self.devis, 'sans')
        avec = cible_depuis_lignes(self.devis, 'avec')
        self.assertTrue(any('modèles de panneau' in m
                            for m in sans['avertissements']))
        self.assertTrue(any('Canadian Solar 710W' in m
                            for m in sans['avertissements']))
        self.assertTrue(any('Jinko 440W' in m
                            for m in avec['avertissements']))


class UnSeulModeleTests(_CibleBase):
    """Non-régression : deux options mais UN SEUL modèle de panneau (le cas
    courant) — seul le COMPTE diffère, jamais le wattage."""

    def setUp(self):
        super().setUp()
        self._ligne('Panneau Jinko 550W', quantite=8, variante='sans')
        self._ligne('Panneau Jinko 550W', quantite=10, variante='avec')

    def test_le_wattage_est_le_meme_et_le_compte_diffère(self):
        sans = cible_depuis_lignes(self.devis, 'sans')
        avec = cible_depuis_lignes(self.devis, 'avec')
        self.assertEqual(sans['panel_watt'], 550)
        self.assertEqual(avec['panel_watt'], 550)
        self.assertEqual(sans['panneaux'], 8)
        self.assertEqual(avec['panneaux'], 10)
        self.assertAlmostEqual(sans['kwc'], 4.4, places=3)
        self.assertAlmostEqual(avec['kwc'], 5.5, places=3)

    def test_aucun_avertissement_deux_modeles_sur_un_seul_modele(self):
        """Deux lignes VARIANTÉES du même modèle sont UN modèle (L-2OPT) —
        la règle d'identité ne compte pas la variante."""
        for variante in ('sans', 'avec'):
            cible = cible_depuis_lignes(self.devis, variante)
            self.assertFalse(
                [m for m in cible['avertissements']
                 if 'modèles de panneau' in m], msg=variante)


class DevisNonVarianteTests(_CibleBase):
    """Le chemin d'hier — aucune ligne variantée : les deux vues sont
    identiques, à l'octet."""

    def setUp(self):
        super().setUp()
        self._ligne('Panneau Jinko 550W', quantite=12)
        self._ligne('Onduleur réseau Huawei 5kW Monophasé', quantite=1,
                    prix='9000')

    def test_les_deux_vues_sont_identiques(self):
        self.assertEqual(cible_depuis_lignes(self.devis, 'sans'),
                         cible_depuis_lignes(self.devis, 'avec'))

    def test_le_compte_et_le_wattage_viennent_des_memes_lignes(self):
        cible = cible_depuis_lignes(self.devis)
        self.assertEqual(cible['panneaux'], 12)
        self.assertEqual(cible['panel_watt'], 550)
        self.assertAlmostEqual(cible['kwc'], 6.6, places=3)
        self.assertEqual(cible['scenario'], 'reseau')


class OptionSansLignePanneauTests(_CibleBase):
    """Cas dégénéré : une option ne porte AUCUNE ligne panneau. On ne nomme
    alors aucune ligne dominante plutôt que d'en emprunter une à l'autre
    option (et surtout : on ne plante pas)."""

    def setUp(self):
        super().setUp()
        self._ligne('Panneau Canadian Solar 710W', quantite=8,
                    variante='sans')
        self._ligne('Panneau Jinko 440W', quantite=10, variante='sans')
        self._ligne('Batterie Dyness 10 kWh', quantite=1, variante='avec',
                    prix='30000')

    def test_l_option_vide_rend_zero_sans_lever(self):
        cible = cible_depuis_lignes(self.devis, 'avec')
        self.assertEqual(cible['panneaux'], 0)
        self.assertEqual(cible['kwc'], 0.0)
        self.assertTrue(cible['batterie'])
        # Aucun message ne nomme une ligne : il n'y en a pas dans ce panier.
        self.assertFalse([m for m in cible['avertissements']
                          if 'modèles de panneau' in m])
