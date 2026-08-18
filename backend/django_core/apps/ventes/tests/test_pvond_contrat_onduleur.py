# -*- coding: utf-8 -*-
"""PVOND — contrat de données onduleur + garde batterie PILOTÉ PAR LA DONNÉE.

Trois choses sont verrouillées ici, et chacune remplace une approximation :

1. **La plage de tension batterie est une DONNÉE**, pas un sous-entendu. Elle
   se lit sur une ligne marquée de la fiche produit (« Plage batterie : 40-60 V »
   / « aucune »), là où le dépôt loge déjà « Modèle confirmé fondateur : … »,
   parce que ``FicheTechnique`` n'a aucun champ pour elle.
2. **Une batterie s'accroche à un onduleur par les CHIFFRES** — sa tension
   nominale entre dans la plage de l'onduleur — et non parce que son nom ne dit
   pas « haute tension ». Le mot-clé reste un REPLI, exercé ici, pour qu'aucun
   catalogue non renseigné ne régresse.
3. **Un onduleur incomplet est NOMMÉ.** Le verrou de complétude rend la liste
   exacte des variables manquantes, en français — c'est ce que le générateur
   affiche pour le griser, comme « prix à renseigner ».

Run :
    DB_NAME=erp_ventes python manage.py test \
        apps.ventes.tests.test_pvond_contrat_onduleur -v 2
"""
from decimal import Decimal

from django.test import TestCase

from apps.stock.models import FicheTechnique, Produit
from apps.stock.selectors import (
    CLES_CONTRAT_ONDULEUR, onduleur_specs_manquantes, plage_batterie_onduleur,
    specs_solaire_produit,
)
from apps.ventes import services
from authentication.models import Company

#: Fiche ONDULEUR complète au sens du contrat (hors plage batterie/garantie,
#: qui vivent sur le produit).
FICHE_ONDULEUR_COMPLETE = {
    'type_fiche': 'onduleur',
    'ond_n_mppt': 2,
    'ond_mppt_v_min': Decimal('200.0'),
    'ond_mppt_v_max': Decimal('650.0'),
    'ond_v_max_abs': Decimal('800.0'),
    'ond_i_max_mppt_a': Decimal('26.0'),
    'ond_ac_kw': Decimal('10'),
    'ond_phases': 3,
    'ond_rendement_euro_pct': Decimal('97.0'),
}


class PvOndBase(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Taqinor PVOND')

    def _produit(self, nom, sku, prix='10000', description='',
                 garantie='Garantie constructeur 10 ans'):
        return Produit.objects.create(
            company=self.company, nom=nom, sku=sku,
            prix_achat=Decimal('1'), prix_vente=Decimal(prix),
            quantite_stock=10, description=description, garantie=garantie)

    def _onduleur(self, nom, sku, *, plage='40-60 V', fiche=None, prix='10000'):
        """Onduleur du catalogue, avec sa ligne marquée de plage batterie."""
        description = 'Onduleur hybride de test'
        if plage is not None:
            description += f'\nPlage batterie : {plage}'
        produit = self._produit(nom, sku, prix=prix, description=description)
        valeurs = dict(FICHE_ONDULEUR_COMPLETE)
        if fiche is not None:
            valeurs.update(fiche)
        FicheTechnique.objects.create(
            company=self.company, produit=produit, **valeurs)
        produit.refresh_from_db()
        return produit

    def _batterie(self, nom, sku, *, v_nominal=Decimal('51.2'), prix='16000'):
        produit = self._produit(nom, sku, prix=prix)
        if v_nominal is not None:
            FicheTechnique.objects.create(
                company=self.company, produit=produit, type_fiche='batterie',
                bat_kwh_nominal=Decimal('5.12'), bat_v_nominal=v_nominal)
        produit.refresh_from_db()
        return produit


class LectureDeLaPlageBatterieTests(PvOndBase):
    def test_une_fenetre_declaree_est_lue(self):
        onduleur = self._onduleur('Onduleur hybride Deye 10kW Triphasé',
                                  'PVOND-LV', plage='40-60 V')
        self.assertEqual(plage_batterie_onduleur(onduleur), (40.0, 60.0))

    def test_aucune_est_une_valeur_pleine_pas_une_absence(self):
        """« aucune » DÉCLARE un onduleur réseau : le contrat est satisfait,
        et aucune batterie ne s'y accroche."""
        onduleur = self._onduleur('Onduleur réseau Huawei 10kW Triphasé',
                                  'PVOND-RES', plage='aucune (onduleur réseau)')
        self.assertEqual(plage_batterie_onduleur(onduleur), (0.0, 0.0))
        self.assertNotIn('plage de tension batterie (V)',
                         onduleur_specs_manquantes(onduleur))

    def test_rien_de_declare_vaut_donnee_manquante(self):
        onduleur = self._onduleur('Onduleur hybride Sans Fiche 8kW',
                                  'PVOND-VIDE', plage=None)
        self.assertIsNone(plage_batterie_onduleur(onduleur))
        self.assertIn('plage de tension batterie (V)',
                      onduleur_specs_manquantes(onduleur))


class VerrouDeCompletudeTests(PvOndBase):
    def test_un_onduleur_complet_ne_manque_de_rien(self):
        onduleur = self._onduleur('Onduleur hybride Deye 10kW Triphasé',
                                  'PVOND-OK')
        self.assertEqual(onduleur_specs_manquantes(onduleur), [])
        self.assertEqual(specs_solaire_produit(onduleur)['manquantes'], [])

    def test_chaque_variable_absente_est_nommee_en_francais(self):
        onduleur = self._onduleur(
            'Onduleur hybride Deye 15kW Triphasé', 'PVOND-KO',
            fiche={'ond_i_max_mppt_a': None, 'ond_rendement_euro_pct': None})
        manquantes = onduleur_specs_manquantes(onduleur)
        self.assertIn('courant maxi par MPPT (A)', manquantes)
        self.assertIn('rendement européen (%)', manquantes)
        self.assertNotIn('puissance AC (kW)', manquantes)

    def test_une_garantie_absente_manque_aussi(self):
        onduleur = self._onduleur('Onduleur hybride Deye 8kW', 'PVOND-NOGAR')
        Produit.objects.filter(pk=onduleur.pk).update(garantie='')
        onduleur.refresh_from_db()
        self.assertIn('garantie constructeur',
                      onduleur_specs_manquantes(onduleur))

    def test_un_produit_qui_n_est_pas_un_onduleur_n_est_pas_concerne(self):
        batterie = self._batterie('Batterie Dyness 5 kWh', 'PVOND-BAT5')
        self.assertEqual(onduleur_specs_manquantes(batterie), [])

    def test_le_contrat_expose_ses_dix_variables(self):
        """Le contrat est la LISTE de ce qu'il faut saisir pour ajouter un
        onduleur : il doit rester lisible d'un coup d'œil."""
        self.assertEqual(len(CLES_CONTRAT_ONDULEUR), 10)
        self.assertIn('plage_batterie_v', CLES_CONTRAT_ONDULEUR)
        self.assertIn('garantie', CLES_CONTRAT_ONDULEUR)


class GardeBatterieDataDrivenTests(PvOndBase):
    def test_une_batterie_dans_la_fenetre_est_retenue(self):
        onduleur = self._onduleur('Onduleur hybride Deye 10kW Triphasé',
                                  'PVOND-LV2', plage='40-60 V')
        batterie = self._batterie('Batterie Dyness 5 kWh', 'PVOND-B1',
                                  v_nominal=Decimal('51.2'))
        self.assertEqual(
            services._pick_batterie(self.company, onduleur=onduleur), batterie)

    def test_une_batterie_hors_fenetre_est_refusee_meme_bien_nommee(self):
        """LE point du garde data-driven : une batterie 204,8 V dont le nom ne
        dit RIEN de sa tension était auto-choisie hier sur un onduleur 48 V —
        un appairage électriquement impossible que le mot-clé ne voyait pas."""
        onduleur = self._onduleur('Onduleur hybride Deye 10kW Triphasé',
                                  'PVOND-LV3', plage='40-60 V')
        self._batterie('Batterie LFP 16 kWh rack', 'PVOND-B2',
                       v_nominal=Decimal('204.8'), prix='100')
        self.assertIsNone(
            services._pick_batterie(self.company, onduleur=onduleur))

    def test_une_batterie_haute_tension_EST_retenue_sur_un_onduleur_HV(self):
        """L'autre moitié du gain : le mot-clé interdisait l'appairage
        LÉGITIME batterie HV ↔ onduleur HV. La donnée l'autorise."""
        onduleur = self._onduleur('Onduleur hybride Deye 20kW Triphasé',
                                  'PVOND-HV', plage='160-700 V')
        batterie = self._batterie('Batterie Dyness haute tension — 16 kWh',
                                  'PVOND-BHV', v_nominal=Decimal('204.8'))
        self.assertEqual(
            services._pick_batterie(self.company, onduleur=onduleur), batterie)

    def test_un_onduleur_reseau_n_accepte_aucune_batterie(self):
        onduleur = self._onduleur('Onduleur réseau Huawei 10kW Triphasé',
                                  'PVOND-RES2', plage='aucune (onduleur réseau)')
        self._batterie('Batterie Dyness 5 kWh', 'PVOND-B3')
        self.assertIsNone(
            services._pick_batterie(self.company, onduleur=onduleur))


class RepliMotCleTests(PvOndBase):
    """Sans donnée, le comportement doit être byte-identique à PVG4."""

    def test_sans_plage_declaree_le_mot_cle_reprend_la_main(self):
        onduleur = self._onduleur('Onduleur hybride Deye 10kW Triphasé',
                                  'PVOND-NOPL', plage=None)
        self._batterie('Batterie Dyness haute tension — 16 kWh',
                       'PVOND-BHV2', v_nominal=None, prix='100')
        basse = self._batterie('Batterie Dyness 5 kWh', 'PVOND-B4',
                               v_nominal=None)
        self.assertEqual(
            services._pick_batterie(self.company, onduleur=onduleur), basse)

    def test_sans_onduleur_du_tout_le_mot_cle_reprend_la_main(self):
        self._batterie('Batterie Dyness haute tension — 16 kWh',
                       'PVOND-BHV3', v_nominal=None, prix='100')
        basse = self._batterie('Batterie Dyness 5 kWh', 'PVOND-B5',
                               v_nominal=None)
        self.assertEqual(services._pick_batterie(self.company), basse)

    def test_une_batterie_sans_fiche_est_EXCLUE_sous_un_onduleur_a_plage(self):
        """RÈGLE CORRIGÉE (fondateur 2026-08-18) : le repli mot-clé ne
        s'applique QUE quand L'ONDULEUR ne déclare aucune plage.

        L'ancienne règle faisait l'inverse de sa promesse sur le catalogue
        réel : sous un onduleur 160-700 V elle ÉCARTAIT les Dyness 5/10 kWh
        (51,2 V, correctement documentées) et ACCEPTAIT « Batterie Lithium
        5 kWh » et « Batterie Gel 2.2 kWh » — deux références sans AUCUNE fiche
        technique, l'une en 48 V, l'autre en plomb-gel 12 V. Dès qu'une plage
        est déclarée, seule une tension MESURÉE prouve la compatibilité."""
        onduleur = self._onduleur('Onduleur hybride Deye 10kW Triphasé',
                                  'PVOND-LV4', plage='40-60 V')
        self._batterie('Batterie Dyness 5 kWh', 'PVOND-B6', v_nominal=None)
        self._batterie('Batterie Dyness haute tension — 16 kWh',
                       'PVOND-BHV4', v_nominal=None, prix='100')
        self.assertIsNone(
            services._pick_batterie(self.company, onduleur=onduleur))

    def test_une_tension_nulle_est_une_donnee_INVALIDE_pas_un_repli(self):
        """``bat_v_nominal = 0`` n'est pas « pas de donnée » : c'est une donnée
        fausse. Elle ne doit pas ouvrir la porte au mot-clé (miroir exact du
        garde JS ``tension <= 0``)."""
        onduleur = self._onduleur('Onduleur hybride Deye 10kW Triphasé',
                                  'PVOND-LV5', plage='40-60 V')
        self._batterie('Batterie Dyness 5 kWh', 'PVOND-B7',
                       v_nominal=Decimal('0'))
        self.assertIsNone(
            services._pick_batterie(self.company, onduleur=onduleur))

    def test_une_batterie_generique_du_catalogue_reel_ne_passe_plus(self):
        """Les deux références RÉELLES qui passaient : BAT-GEL-22 (plomb-gel
        12 V) et BAT-LIT-5 (48 V), toutes deux sans FicheTechnique."""
        onduleur = self._onduleur('Onduleur hybride Deye 15kW Triphasé',
                                  'PVOND-HV2', plage='160-700 V')
        self._batterie('Batterie Gel 2.2 kWh', 'BAT-GEL-22', v_nominal=None,
                       prix='5000')
        self._batterie('Batterie Lithium 5 kWh', 'BAT-LIT-5', v_nominal=None,
                       prix='15500')
        self.assertIsNone(
            services._pick_batterie(self.company, onduleur=onduleur))


class CompositionResidentielleTests(PvOndBase):
    def test_un_onduleur_HV_ne_compose_pas_de_batterie_48V(self):
        """L'incompatibilité métier signalée au fondateur (Deye SG01HP3 +
        Dyness 51,2 V) est désormais tranchée par les CHIFFRES."""
        self._onduleur('Onduleur hybride Deye 10kW Triphasé', 'PVOND-COMP-HV',
                       plage='160-700 V')
        self._batterie('Batterie Dyness 5 kWh', 'PVOND-COMP-B5')
        self._batterie('Batterie Dyness 10 kWh', 'PVOND-COMP-B10',
                       prix='30000')
        self._produit('Panneau Jinko 550W', 'PVOND-COMP-PAN', prix='1100')

        catalogue = services.catalogue_de_la_societe(self.company)
        lignes = services.composition_residentielle(
            catalogue, kwc=10, panel_watt=550, avec_batterie=True)

        self.assertFalse(
            [ligne for ligne in lignes if 'Batterie' in ligne.designation],
            'une batterie 48 V a été composée sous un onduleur haute tension')

    def test_un_onduleur_48V_compose_ses_batteries_comme_avant(self):
        self._onduleur('Onduleur hybride Deye 10kW Triphasé', 'PVOND-COMP-LV',
                       plage='40-60 V')
        self._batterie('Batterie Dyness 5 kWh', 'PVOND-COMP-B5B')
        self._batterie('Batterie Dyness 10 kWh', 'PVOND-COMP-B10B',
                       prix='30000')
        self._produit('Panneau Jinko 550W', 'PVOND-COMP-PANB', prix='1100')

        catalogue = services.catalogue_de_la_societe(self.company)
        lignes = services.composition_residentielle(
            catalogue, kwc=10, panel_watt=550, avec_batterie=True)

        batteries = [ligne for ligne in lignes
                     if 'Batterie' in ligne.designation]
        self.assertTrue(batteries)

    def test_un_vivier_VIDE_avertit_au_lieu_de_se_taire(self):
        """Le devis partait « avec batterie » et SANS aucune ligne batterie,
        sans que personne ne l'apprenne. La composition le DIT désormais, sur
        le canal que l'appelant lui fournit."""
        self._onduleur('Onduleur hybride Deye 15kW Triphasé', 'PVOND-VID-OND',
                       plage='160-700 V')
        self._batterie('Batterie Gel 2.2 kWh', 'PVOND-VID-GEL',
                       v_nominal=None, prix='5000')
        self._produit('Panneau Jinko 550W', 'PVOND-VID-PAN', prix='1100')

        catalogue = services.catalogue_de_la_societe(self.company)
        avertissements = []
        lignes = services.composition_residentielle(
            catalogue, kwc=15, panel_watt=550, avec_batterie=True,
            avertissements=avertissements)

        self.assertFalse([li for li in lignes if 'Batterie' in li.designation])
        self.assertEqual(len(avertissements), 1)
        self.assertIn('Aucune batterie compatible tarifée',
                      avertissements[0])
        # La plage de l'onduleur est NOMMÉE : le commercial sait quoi chercher.
        self.assertIn('160-700 V', avertissements[0])

    def test_aucun_avertissement_quand_la_batterie_est_bien_composee(self):
        self._onduleur('Onduleur hybride Deye 10kW Triphasé', 'PVOND-VID-OK',
                       plage='40-60 V')
        self._batterie('Batterie Dyness 5 kWh', 'PVOND-VID-B5')
        self._produit('Panneau Jinko 550W', 'PVOND-VID-PAN2', prix='1100')

        catalogue = services.catalogue_de_la_societe(self.company)
        avertissements = []
        services.composition_residentielle(
            catalogue, kwc=5, panel_watt=550, avec_batterie=True,
            avertissements=avertissements)

        self.assertEqual(avertissements, [])

    def test_sans_batterie_demandee_aucun_avertissement(self):
        """Un devis réseau ne lit jamais le vivier : rien à signaler."""
        self._onduleur('Onduleur réseau Huawei 10kW Triphasé', 'PVOND-VID-RES',
                       plage='aucune (onduleur réseau)')
        self._produit('Panneau Jinko 550W', 'PVOND-VID-PAN3', prix='1100')

        catalogue = services.catalogue_de_la_societe(self.company)
        avertissements = []
        services.composition_residentielle(
            catalogue, kwc=10, panel_watt=550, avec_batterie=False,
            avertissements=avertissements)

        self.assertEqual(avertissements, [])


class VerrouDeCompletudeBackendTests(PvOndBase):
    """PVOND — LA COUTURE : l'écran et le backend écartent LE MÊME onduleur.

    ``onduleur_specs_manquantes`` n'avait aucun appelant hors tests/sérialiseur :
    ``solar.js`` filtrait, ``composition_residentielle`` et ``_pick_product``
    non. Deux moitiés de la même auto-composition pouvaient donc retenir deux
    onduleurs différents pour la même demande — deux prix pour un seul devis,
    selon le bouton utilisé."""

    def test_un_onduleur_INCOMPLET_passe_derriere_un_complet(self):
        # Le 10 kW est INCOMPLET (il lui manque le courant maxi par MPPT) et
        # serait choisi le premier au seuil de 8 kWc ; le 20 kW est complet.
        self._onduleur('Onduleur hybride Deye 10kW Triphasé', 'PVOND-VC-KO',
                       plage='40-60 V',
                       fiche={'ond_i_max_mppt_a': None}, prix='36000')
        self._onduleur('Onduleur hybride Deye 20kW Triphasé', 'PVOND-VC-OK',
                       plage='40-60 V', prix='48000')
        self._batterie('Batterie Dyness 5 kWh', 'PVOND-VC-B5')
        self._produit('Panneau Jinko 550W', 'PVOND-VC-PAN', prix='1100')

        catalogue = services.catalogue_de_la_societe(self.company)
        lignes = services.composition_residentielle(
            catalogue, kwc=10, panel_watt=550, avec_batterie=True)

        onduleurs = [li.designation for li in lignes
                     if 'Onduleur' in li.designation]
        self.assertEqual(onduleurs, ['Onduleur hybride Deye 20kW Triphasé'])

    def test_pick_product_ecarte_lui_aussi_l_onduleur_incomplet(self):
        """Même verrou sur l'autre moitié du backend (resync / pont 3D)."""
        self._onduleur('Onduleur hybride Deye 10kW Triphasé', 'PVOND-VC2-KO',
                       plage='40-60 V',
                       fiche={'ond_rendement_euro_pct': None}, prix='1000')
        complet = self._onduleur('Onduleur hybride Deye 20kW Triphasé',
                                 'PVOND-VC2-OK', plage='40-60 V', prix='48000')

        retenu = services._pick_product(
            self.company, services._is_hybrid_inverter)

        self.assertEqual(retenu, complet)

    def test_un_catalogue_SANS_aucune_fiche_reste_chiffrable(self):
        """MULTI-TENANT : une société qui n'a saisi aucune fiche technique ne
        devient pas « non chiffrable » du jour au lendemain — le verrou trie
        entre candidats, il ne vide jamais la table."""
        nu = self._produit('Onduleur hybride Générique 10kW', 'PVOND-VC3-NU',
                           prix='20000')

        self.assertEqual(
            services._pick_product(self.company,
                                   services._is_hybrid_inverter), nu)
