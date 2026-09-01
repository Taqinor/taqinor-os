"""Moteur premium — chantier « DEUX OPTIMISEURS » (L-2OPT, 24/08/2026).

Les options « Sans batterie » et « Avec batterie » d'un devis résidentiel
peuvent porter des NOMBRES DE PANNEAUX DIFFÉRENTS (22 sans, 26 avec) : la
ligne panneau est dédoublée, chaque exemplaire portant sa variante
(``LigneDevis.variante`` : '' commun | 'sans' | 'avec').

Le champ modèle est ajouté par une AUTRE lane ; le moteur le lit par
``getattr(ligne, 'variante', '')``. Ces tests exercent donc le VRAI chemin de
répartition en remplaçant l'unique point de lecture
(``builder._variante_de_ligne``) — aucune dépendance à une migration qui
n'est pas encore sur ``main``, et le jour où elle y est, le même code passe
sans une ligne de changement.

Deux garanties, toujours ensemble :
  · le NEUF — deltas par quantité, deux jeux de scalaires, tableau comparatif,
    une-page calé sur SA branche (chacun de ces tests échoue sur ``main``) ;
  · l'ANCIEN — un devis sans variante est rendu au bit près (la page 2 est
    comparée à celle qu'aurait produite l'ancien découpage).

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_quote_engine_deux_optimiseurs -v 2
"""

import re
from decimal import Decimal
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, tag

from apps.ventes.tests import _moteur_fixtures as F
from apps.ventes.tests._quote_engine_common import (
    DEUX_OPTIONS, make_client, make_company, make_user,
)


# 12 factures RÉELLES : sans elles, ``residential.renderer._augment`` refuse le
# devis (M1 — plus aucune série proxy). Mêmes valeurs que les fixtures voisines.
FACTURES_REELLES = [1200, 1200, 1300, 1400, 1600, 1800,
                    1900, 1900, 1700, 1500, 1300, 1200]


def _legacy_split_items(sans_items, avec_items):
    """L'ANCIEN découpage de page 2, à l'octet : appartenance par DÉSIGNATION.

    Recopié tel qu'il était avant L-2OPT pour servir de témoin : sur un devis
    sans variante, le nouveau découpage (par désignation ET quantité) doit
    produire EXACTEMENT la même page.
    """
    avec_names = {it["designation"] for it in avec_items}
    sans_names = {it["designation"] for it in sans_items}
    common = sans_names & avec_names
    shared = [it for it in sans_items if it["designation"] in common]
    delta_sans = [it for it in sans_items
                  if it["designation"] not in avec_names]
    delta_avec = [it for it in avec_items
                  if it["designation"] not in sans_names]
    return shared, delta_sans, delta_avec


class _DevisVariantesMixin:
    """Fabrique de devis dont les lignes portent une variante déclarée."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        # Variantes par identifiant de ligne, consommées par le patch de
        # ``_variante_de_ligne`` (le champ modèle appartient à une autre lane).
        self.variantes = {}

    def _devis(self, lignes, reference, etude_params=None):
        """``lignes`` = [(désignation, quantité, prix HT, variante), …].

        Deux lignes peuvent partager la MÊME désignation (c'est tout l'objet du
        chantier) : chaque ligne reçoit donc son propre produit, au SKU unique.
        """
        from apps.stock.models import Produit
        from apps.ventes.models import Devis, LigneDevis

        devis = Devis.objects.create(
            company=self.company, reference=reference, client=self.client_obj,
            statut='brouillon', taux_tva=Decimal('20.00'),
            remise_globale=Decimal('0'), created_by=self.user,
            etude_params=etude_params,
        )
        for i, (desig, qty, pu, variante) in enumerate(lignes):
            produit = Produit.objects.create(
                company=self.company, nom=desig, sku=f'{reference}-L{i}',
                prix_vente=Decimal(pu), prix_achat=Decimal('1'),
                quantite_stock=100,
            )
            ligne = LigneDevis.objects.create(
                devis=devis, produit=produit, designation=desig,
                quantite=Decimal(qty), prix_unitaire=Decimal(pu),
                remise=Decimal('0'), taux_tva=None,
            )
            if variante:
                self.variantes[ligne.pk] = variante
        return devis

    def _build(self, devis, pdf_options=None):
        """``build_quote_data`` avec les variantes déclarées de la fixture."""
        from apps.ventes.quote_engine.builder import build_quote_data
        with patch('apps.ventes.quote_engine.builder._variante_de_ligne',
                   side_effect=lambda li: self.variantes.get(li.pk, '')):
            return build_quote_data(devis, pdf_options)

    # ── Fixtures ────────────────────────────────────────────────────────────
    # 22 panneaux sans batterie / 26 avec : LA MÊME désignation, deux
    # quantités, deux variantes.
    DIVERGENT = [
        ('Panneau Canadien Solar 710W', '22', '1272.73', 'sans'),
        ('Panneau Canadien Solar 710W', '26', '1272.73', 'avec'),
        ('Onduleur réseau Huawei 10kW Triphasé', '1', '16666.67', ''),
        ('Onduleur hybride Deye 10kW Triphasé', '1', '23333.33', ''),
        ('Batterie Dyness 10 kWh', '1', '25000', ''),
        ('Installation', '1', '5000', ''),
    ]
    # Devis à deux options SANS variante : tout l'existant.
    LEGACY = [
        ('Panneau Canadien Solar 710W', '14', '1272.73', ''),
        ('Onduleur réseau Huawei 10kW Triphasé', '1', '16666.67', ''),
        ('Onduleur hybride Deye 10kW Triphasé', '1', '23333.33', ''),
        ('Batterie Dyness 10 kWh', '1', '25000', ''),
        ('Installation', '1', '5000', ''),
    ]
    # TÉMOIN de la lane F1 : le MÊME devis, mais avec les 22 panneaux en ligne
    # COMMUNE (les deux options portent donc le même champ PV). Son option
    # « sans » a exactement la composition — et donc le total — de l'option
    # « sans » du devis DIVERGENT : ce que le moteur en dit (production,
    # économies, payback) doit être identique des deux côtés.
    EGAL_22 = [
        ('Panneau Canadien Solar 710W', '22', '1272.73', ''),
        ('Onduleur réseau Huawei 10kW Triphasé', '1', '16666.67', ''),
        ('Onduleur hybride Deye 10kW Triphasé', '1', '23333.33', ''),
        ('Batterie Dyness 10 kWh', '1', '25000', ''),
        ('Installation', '1', '5000', ''),
    ]

    def _etude_params(self, **extra):
        return {**DEUX_OPTIONS,
                'factures_mensuelles_reelles': list(FACTURES_REELLES),
                **extra}

    def _devis_divergent(self, reference='DEV-L2OPT-DIV'):
        return self._devis(self.DIVERGENT, reference, self._etude_params())

    def _devis_legacy(self, reference='DEV-L2OPT-LEG'):
        return self._devis(self.LEGACY, reference, self._etude_params())

    def _devis_egal_22(self, reference='DEV-L2OPT-EG22'):
        return self._devis(self.EGAL_22, reference, self._etude_params())


class TestDeuxOptimiseursBuilder(_DevisVariantesMixin, TestCase):
    """Le découpage et les scalaires par option, côté builder."""

    def test_la_variante_route_chaque_ligne_dans_son_option(self):
        data = self._build(self._devis_divergent())
        sans = [(it['designation'], it['quantite'])
                for it in data['sans_items']]
        avec = [(it['designation'], it['quantite'])
                for it in data['avec_items']]
        self.assertEqual(sans, [
            ('Panneau Canadien Solar 710W', 22.0),
            ('Onduleur réseau Huawei 10kW Triphasé', 1.0),
            ('Installation', 1.0),
        ])
        self.assertEqual(avec, [
            ('Panneau Canadien Solar 710W', 26.0),
            ('Onduleur hybride Deye 10kW Triphasé', 1.0),
            ('Batterie Dyness 10 kWh', 1.0),
            ('Installation', 1.0),
        ])

    def test_scalaires_par_option_et_repli_documente_sur_avec(self):
        data = self._build(self._devis_divergent())
        self.assertEqual(data['nb_panneaux_sans'], 22)
        self.assertEqual(data['nb_panneaux_avec'], 26)
        self.assertEqual(data['puissance_kwc_sans'], 15.62)
        self.assertEqual(data['puissance_kwc_avec'], 18.46)
        self.assertEqual(data['watt_par_panneau_sans'], 710)
        self.assertEqual(data['watt_par_panneau_avec'], 710)
        self.assertTrue(data['panneaux_divergents'])
        # Repli documenté : les clés legacy portent l'option AVEC — jamais la
        # SOMME des deux paniers (48 panneaux, le compte de personne).
        self.assertEqual(data['nb_panneaux'], 26)
        self.assertEqual(data['puissance_kwc'], 18.46)

    def test_chaque_option_totalise_ses_propres_lignes(self):
        data = self._build(self._devis_divergent())
        for cle_items, cle_totaux in (('sans_items', 'totaux_sans'),
                                      ('avec_items', 'totaux_avec')):
            attendu = round(sum(it['quantite'] * it['prix_unit_ht']
                                for it in data[cle_items]), 2)
            self.assertEqual(data[cle_totaux]['ht_brut'], attendu)
        # Deux paniers réellement distincts (l'option avec est la plus chère).
        self.assertGreater(data['totaux_avec']['ttc'],
                           data['totaux_sans']['ttc'])

    def test_un_devis_sans_variante_est_reparti_comme_avant(self):
        data = self._build(self._devis_legacy())
        self.assertEqual(
            [it['designation'] for it in data['sans_items']],
            ['Panneau Canadien Solar 710W',
             'Onduleur réseau Huawei 10kW Triphasé', 'Installation'])
        self.assertEqual(
            [it['designation'] for it in data['avec_items']],
            ['Panneau Canadien Solar 710W',
             'Onduleur hybride Deye 10kW Triphasé', 'Batterie Dyness 10 kWh',
             'Installation'])
        self.assertFalse(data['panneaux_divergents'])
        # Scalaire unique inchangé : 14 × 710 W.
        self.assertEqual(data['nb_panneaux'], 14)
        self.assertEqual(data['puissance_kwc'], 9.94)
        self.assertEqual(data['nb_panneaux_sans'], 14)
        self.assertEqual(data['nb_panneaux_avec'], 14)

    def test_une_variante_contredite_garde_sa_ligne_et_avertit_en_interne(self):
        """Ceinture-bretelles : une batterie déclarée « sans » reste dans son
        option (aucune ligne, aucun dirham ne s'évapore) et le vendeur est
        averti — l'avertissement est INTERNE, jamais rendu au client."""
        devis = self._devis([
            ('Panneau Canadien Solar 710W', '14', '1272.73', ''),
            ('Onduleur réseau Huawei 10kW Triphasé', '1', '16666.67', ''),
            ('Onduleur hybride Deye 10kW Triphasé', '1', '23333.33', ''),
            ('Batterie Dyness 10 kWh', '1', '25000', 'sans'),
            ('Installation', '1', '5000', ''),
        ], 'DEV-L2OPT-CONTRA', self._etude_params())
        data = self._build(devis)
        self.assertIn('Batterie Dyness 10 kWh',
                      [it['designation'] for it in data['sans_items']])
        self.assertTrue(any('variante déclarée incompatible' in a
                            for a in data['avertissements_internes']))
        # Le total du panier « sans » inclut bel et bien cette ligne.
        self.assertEqual(
            data['totaux_sans']['ht_brut'],
            round(sum(it['quantite'] * it['prix_unit_ht']
                      for it in data['sans_items']), 2))


class TestDeuxOptimiseursVarianteRendue(_DevisVariantesMixin, TestCase):
    """F1 (26/08/2026) — LE DOCUMENT RÉTRÉCI À UNE VARIANTE.

    Le trou qui a laissé passer le bug : AUCUN test ne construisait ce devis
    divergent avec ``variante_option``. Le PDF « Sans batterie » du lien public
    (``public_views.proposal_pdf`` → ``clean_pdf_options({'variante_option':
    'sans'})``) annonçait donc « 18,46 kWc · 26 panneaux » — les figures de
    l'option AVEC — au-dessus d'un tableau qui liste ses 22 panneaux.
    """

    def test_la_variante_sans_porte_les_scalaires_de_l_option_sans(self):
        data = self._build(self._devis_divergent('DEV-L2OPT-VSANS'),
                           {'variante_option': 'sans'})
        # Le document est bien rétréci à l'option 1.
        self.assertEqual(data['scenario'], 'Sans batterie')
        self.assertFalse(data['deux_options'])
        self.assertFalse(data['avec_ok'])
        # …et il porte SES figures, jamais celles de l'option qu'il ne rend pas.
        self.assertEqual(data['nb_panneaux'], 22)
        self.assertEqual(data['puissance_kwc'], 15.62)
        self.assertEqual(data['watt_par_panneau'], 710)
        # Les figures par option restent servies telles quelles (le contrat
        # L-2OPT ne bouge pas : c'est le scalaire legacy qui suit la variante).
        self.assertEqual(data['puissance_kwc_sans'], 15.62)
        self.assertEqual(data['puissance_kwc_avec'], 18.46)

    def test_la_variante_avec_porte_les_scalaires_de_l_option_avec(self):
        data = self._build(self._devis_divergent('DEV-L2OPT-VAVEC'),
                           {'variante_option': 'avec'})
        self.assertEqual(data['scenario'], 'Avec batterie')
        self.assertFalse(data['deux_options'])
        self.assertFalse(data['sans_ok'])
        self.assertEqual(data['nb_panneaux'], 26)
        self.assertEqual(data['puissance_kwc'], 18.46)

    def test_la_variante_les_deux_garde_le_document_complet(self):
        """Le document qui rend LES DEUX options garde le repli documenté
        (clés legacy = option AVEC) : la bande page 2 y affiche les deux."""
        data = self._build(self._devis_divergent('DEV-L2OPT-VDEUX'),
                           {'variante_option': 'les_deux'})
        self.assertTrue(data['deux_options'])
        self.assertEqual(data['nb_panneaux'], 26)
        self.assertEqual(data['puissance_kwc'], 18.46)

    def test_la_production_du_document_sans_est_celle_de_ses_22_panneaux(self):
        """La production DÉRIVE du kWc : elle suit donc la variante rendue."""
        sans = self._build(self._devis_divergent('DEV-L2OPT-VPRS'),
                           {'variante_option': 'sans'})
        avec = self._build(self._devis_divergent('DEV-L2OPT-VPRA'),
                           {'variante_option': 'avec'})
        self.assertLess(sans['prod_kwh'], avec['prod_kwh'])
        self.assertEqual(sans['prod_kwh'], sans['prod_kwh_sans'])
        self.assertEqual(avec['prod_kwh'], avec['prod_kwh_avec'])


class TestDeuxOptimiseursEconomiesParOption(_DevisVariantesMixin, TestCase):
    """F1 — LA CHAÎNE ÉCONOMIQUE SE CALCULE PAR OPTION.

    ``calculate_savings_roi`` dérive production, économies et payback d'UN seul
    kWc : appelée une fois avec le scalaire legacy (= option AVEC), elle
    chiffrait la colonne « Sans batterie » du comparatif sur 18,46 kWc.

    Le témoin est mécanique, jamais recalculé à la main : le devis EGAL_22 a
    EXACTEMENT la même option « sans » (22 panneaux, onduleur réseau,
    installation → même total, même onduleur, même batterie côté avec). Ce que
    le moteur dit de cette option doit donc être identique dans les deux devis.
    """

    def setUp(self):
        super().setUp()
        self.divergent = self._build(self._devis_divergent('DEV-L2OPT-ECO1'))
        self.temoin = self._build(self._devis_egal_22('DEV-L2OPT-ECO2'))

    def test_le_temoin_a_bien_la_meme_option_sans(self):
        """Sans cette garantie, les égalités ci-dessous ne prouveraient rien."""
        self.assertTrue(self.divergent['panneaux_divergents'])
        self.assertFalse(self.temoin['panneaux_divergents'])
        self.assertEqual(self.divergent['puissance_kwc_sans'],
                         self.temoin['puissance_kwc_sans'])
        self.assertEqual(self.divergent['totaux_sans']['ttc'],
                         self.temoin['totaux_sans']['ttc'])

    def test_les_economies_sans_batterie_sont_celles_de_son_champ_pv(self):
        self.assertEqual(self.divergent['eco_s_ann'], self.temoin['eco_s_ann'])
        self.assertEqual(self.divergent['eco_s_monthly'],
                         self.temoin['eco_s_monthly'])

    def test_le_payback_sans_batterie_est_celui_de_son_champ_pv(self):
        self.assertEqual(self.divergent['roi_s'], self.temoin['roi_s'])
        self.assertEqual(self.divergent['cashflow_sans'],
                         self.temoin['cashflow_sans'])
        self.assertEqual(self.divergent['net_gain_sans'],
                         self.temoin['net_gain_sans'])

    def test_l_option_avec_garde_son_propre_chiffrage(self):
        """Le témoin n'aplatit rien : l'option 2 du devis divergent porte
        26 panneaux, donc plus de production et plus d'économies."""
        self.assertGreater(self.divergent['prod_kwh_avec'],
                           self.divergent['prod_kwh_sans'])
        self.assertGreater(self.divergent['eco_a_ann'],
                           self.temoin['eco_a_ann'])
        # Le document complet met en avant l'option AVEC : ses figures globales
        # restent celles-là (repli documenté L-2OPT).
        self.assertEqual(self.divergent['prod_kwh'],
                         self.divergent['prod_kwh_avec'])

    def test_un_devis_non_divergent_ne_rejoue_aucun_calcul(self):
        """Économie de calcul ET garantie de non-régression : sans divergence,
        les deux options partagent la MÊME production dérivée."""
        self.assertEqual(self.temoin['prod_kwh_sans'],
                         self.temoin['prod_kwh_avec'])
        self.assertEqual(self.temoin['prod_kwh_sans'], self.temoin['prod_kwh'])


class TestQjr28ModeleDeclareParColonne(_DevisVariantesMixin, TestCase):
    """QJR28 — DEUX COLONNES, DEUX MOTEURS : LE DOCUMENT LE DIT.

    Le bloc d'étude horaire porte LA puissance pour laquelle il a été calculé
    et ``pricing`` le refuse (garde de fraîcheur) dès qu'une option ne fait
    plus cette puissance. Sur un devis divergent, la colonne « Sans batterie »
    retombait donc EN SILENCE sur le forfait « estimation » pendant que le
    document continuait de déclarer ``savings_model='horaire'`` et
    ``savings_estimated=False`` pour tout le tableau.
    """

    #: le bloc horaire décrit l'option AVEC : 26 × 710 W = 18,46 kWc.
    KWC_AVEC = 18.46
    #: la colonne SANS fait 22 × 710 W = 15,62 kWc — hors tolérance (2 %).

    def test_le_modele_declare_est_celui_employe_par_chaque_colonne(self):
        from apps.ventes.tests.test_cj2b_graphe_mensuel import bloc_horaire
        data = self._build(self._devis(
            self.DIVERGENT, 'DEV-QJR28-DIV',
            self._etude_params(etude_horaire=bloc_horaire(self.KWC_AVEC))))
        # TÉMOIN mécanique : le MÊME champ PV « sans » (22 panneaux), sans
        # aucun bloc horaire — donc chiffré par le moteur de repli.
        temoin = self._build(self._devis_egal_22('DEV-QJR28-T'))

        self.assertTrue(data['panneaux_divergents'])
        # l'option AVEC est celle que le bloc décrit : modèle horaire, déclaré
        self.assertEqual(data['savings_model'], 'horaire')
        self.assertEqual(data['savings_model_avec'], 'horaire')
        self.assertEqual(data['savings_estimated_avec'],
                         data['savings_estimated'])
        # la colonne SANS a bien été chiffrée par l'AUTRE moteur — preuve
        # mécanique : ses économies sont, au dirham près, celles du témoin.
        self.assertEqual(data['eco_s_ann'], temoin['eco_s_ann'])
        self.assertNotEqual(data['savings_model_sans'], 'horaire')
        self.assertEqual(data['savings_model_sans'], temoin['savings_model'])
        self.assertEqual(data['savings_estimated_sans'],
                         temoin['savings_estimated'])

    def test_un_devis_non_divergent_declare_un_seul_modele(self):
        """Tout l'existant : une seule dérivation ⇒ les trois clés portent la
        même valeur (aucune colonne chiffrée par un autre moteur)."""
        from apps.ventes.tests.test_cj2b_graphe_mensuel import bloc_horaire
        # LEGACY = 14 × 710 W = 9,94 kWc, la puissance du bloc.
        data = self._build(self._devis(
            self.LEGACY, 'DEV-QJR28-LEG',
            self._etude_params(etude_horaire=bloc_horaire(9.94))))
        self.assertFalse(data['panneaux_divergents'])
        self.assertEqual(data['savings_model'], 'horaire')
        self.assertEqual(data['savings_model_sans'], 'horaire')
        self.assertEqual(data['savings_model_avec'], 'horaire')
        self.assertEqual(data['savings_estimated_sans'],
                         data['savings_estimated'])
        self.assertEqual(data['savings_estimated_avec'],
                         data['savings_estimated'])


@tag('pdf')  # rendu page 2 via WeasyPrint — lourd → palier release-verify
class TestDeuxOptimiseursPage2(_DevisVariantesMixin, TestCase):
    """Page 2 du document résidentiel : deltas, bandeau, tableau comparatif."""

    def _page2(self, data):
        from apps.ventes.quote_engine.residential import render, renderer
        ctx = render.build_ctx(renderer._augment(data))
        from apps.ventes.quote_engine.residential import options
        return ctx, "".join(options.build_pages(ctx))

    def test_une_quantite_divergente_sort_du_commun(self):
        from apps.ventes.quote_engine.residential import options
        data = self._build(self._devis_divergent())
        shared, delta_sans, delta_avec = options._split_items(
            data['sans_items'], data['avec_items'])
        self.assertEqual([it['designation'] for it in shared],
                         ['Installation'])
        self.assertEqual(
            [(it['designation'], it['quantite']) for it in delta_sans],
            [('Panneau Canadien Solar 710W', 22.0),
             ('Onduleur réseau Huawei 10kW Triphasé', 1.0)])
        self.assertEqual(
            [(it['designation'], it['quantite']) for it in delta_avec],
            [('Panneau Canadien Solar 710W', 26.0),
             ('Onduleur hybride Deye 10kW Triphasé', 1.0),
             ('Batterie Dyness 10 kWh', 1.0)])

    def test_quantites_egales_restent_communes(self):
        from apps.ventes.quote_engine.residential import options
        data = self._build(self._devis_legacy())
        shared, delta_sans, delta_avec = options._split_items(
            data['sans_items'], data['avec_items'])
        self.assertEqual([it['designation'] for it in shared],
                         ['Panneau Canadien Solar 710W', 'Installation'])
        self.assertEqual([it['designation'] for it in delta_sans],
                         ['Onduleur réseau Huawei 10kW Triphasé'])
        self.assertEqual([it['designation'] for it in delta_avec],
                         ['Onduleur hybride Deye 10kW Triphasé',
                          'Batterie Dyness 10 kWh'])

    def test_le_tableau_comparatif_ne_montre_que_des_valeurs_reelles(self):
        data = self._build(self._devis_divergent())
        _, html = self._page2(data)
        # La classe seule vit aussi dans la feuille de style : on épingle la
        # BALISE, qui n'existe que lorsque le tableau est réellement rendu.
        self.assertIn('<table class="p2-cmp">', html)
        self.assertIn('22 × 710 W', html)
        self.assertIn('26 × 710 W', html)
        self.assertIn('15,62 kWc', html)
        self.assertIn('18,46 kWc', html)
        self.assertIn('10 kWh', html)          # capacité batterie réelle
        self.assertIn('Sans batterie</th>', html)
        self.assertIn('Avec batterie</th>', html)

    def test_le_bandeau_porte_les_deux_puissances(self):
        data = self._build(self._devis_divergent())
        _, html = self._page2(data)
        self.assertIn('15,62 · 18,46', html)
        self.assertIn('kWc installés (sans · avec)', html)
        self.assertIn('22 · 26', html)
        self.assertIn('panneaux (sans · avec) · 710 W', html)

    def test_sans_variante_la_page_2_est_celle_d_hier_au_bit_pres(self):
        """Le témoin : la MÊME page, rendue avec l'ANCIEN découpage."""
        from apps.ventes.quote_engine.residential import options
        data = self._build(self._devis_legacy())
        ctx, html_neuf = self._page2(data)
        with patch.object(options, '_split_items', _legacy_split_items):
            html_ancien = "".join(options.build_pages(ctx))
        self.assertEqual(html_neuf, html_ancien)
        # Et aucun élément neuf ne s'invite sur un devis sans variante.
        self.assertNotIn('<table class="p2-cmp">', html_neuf)
        self.assertNotIn('(sans · avec)', html_neuf)


@tag('pdf')  # rendus complets 3p/4p/onepage via WeasyPrint — lourds → release-verify
class TestDeuxOptimiseursFormats(_DevisVariantesMixin, TestCase):
    """Nombres de pages et intégrité des formats sur un devis divergent."""

    def _render_legacy(self, data):
        from weasyprint import HTML
        from apps.ventes.quote_engine import generate_devis_premium as G
        cap = {}
        orig = G._render_pdf_weasyprint
        G._render_pdf_weasyprint = lambda html, out: cap.update(html=html)
        try:
            G.generate_premium_pdf(data, '/tmp/_l2opt_test.pdf')
        finally:
            G._render_pdf_weasyprint = orig
        return cap['html'], HTML(string=cap['html']).render()

    def test_le_document_residentiel_tient_en_trois_pages(self):
        from weasyprint import HTML
        from apps.ventes.quote_engine.residential import render, renderer
        data = self._build(self._devis_divergent())
        html = render.build_html(renderer._augment(data))
        doc = HTML(string=html).render()
        self.assertEqual(
            len(doc.pages), 3,
            'le comparatif ne doit induire AUCUNE 4ᵉ page, '
            f'{len(doc.pages)} pages rendues')

    def test_une_page_chiffre_les_panneaux_de_sa_branche(self):
        devis = self._devis_divergent()
        data = self._build(devis, {'pdf_mode': 'onepage'})
        # LANE CHOIX-AVEC (fondateur, 25/08/2026) — un document qui ne peut
        # montrer qu'UNE option montre TOUJOURS l'option AVEC batterie quand
        # elle est servable (``deux_options`` implique ``avec_ok``) : la
        # une-page facture donc l'option 2 (« avec »), plus « sans » comme
        # avant M4/19-08.
        self.assertEqual(data['onepage_branche'], 'avec')
        html, doc = self._render_legacy(data)
        self.assertEqual(
            len(doc.pages), 1,
            f'le format une page doit rendre 1 page, {len(doc.pages)} rendues')
        self.assertIn('18.46 kWc', html)     # kWc de la branche facturée
        self.assertNotIn('15.62 kWc', html)  # jamais ceux de l'autre option

    def test_l_etude_ajoute_exactement_une_page(self):
        # Même recette que la garde d'étude existante (mode industriel + ces
        # données d'étude) : seules les lignes changent (variantes divergentes).
        devis = self._devis(self.DIVERGENT, 'DEV-L2OPT-ETU', {
            **DEUX_OPTIONS,
            'kwc': 9.94, 'production_annuelle': 12486,
            'conso_annuelle': 120000, 'taux_autoconso': 100,
            'taux_couverture': 10.4, 'economies_annuelles': 21851,
            'payback': 3.0, 'prix_kwc': 6543,
            'prod_mensuelle': [1040] * 12, 'conso_mensuelle': [10000] * 12,
        })
        devis.mode_installation = 'industriel'
        devis.save(update_fields=['mode_installation'])
        data = self._build(devis, {'include_etude': True})
        _, doc = self._render_legacy(data)
        self.assertEqual(len(doc.pages), 4)

    def test_aucun_prix_d_achat_dans_les_rendus_client(self):
        from apps.ventes.quote_engine.residential import render, renderer
        devis = self._devis_divergent('DEV-L2OPT-ACHAT')
        for ligne in devis.lignes.all():
            ligne.produit.prix_achat = Decimal('9876.54')
            ligne.produit.save(update_fields=['prix_achat'])
        rendus = [render.build_html(
            renderer._augment(self._build(devis)))]
        rendus.append(self._render_legacy(
            self._build(devis, {'pdf_mode': 'onepage'}))[0])
        for html in rendus:
            # Le prix d'achat dans TOUTES ses graphies de formatage. Le
            # mot « achat » seul ne serait pas un marqueur exploitable :
            # « rachat » apparaît dans les mentions tarifaires ANRE (F1 : les
            # classes SANS tag ``pdf`` de la lane suivent en fin de module).
            for marqueur in ('9876', '9 876', '9 876', '9&#8239;876'):
                self.assertNotIn(marqueur, html.lower())


# ── F1 (26/08/2026) — LES SURFACES CLIENT, SUR LE DOCUMENT RÉELLEMENT RENDU ──
# Aucune BD, aucun WeasyPrint (même doctrine que ``_moteur_fixtures`` : on
# cherche une chaîne dans le HTML EXACT qui part au rendu). Ces classes n'ont
# donc PAS le tag ``pdf`` — elles gatent la CI ordinaire, là où les trois
# classes ci-dessus sont réservées au palier release-verify.
#
# Divergence posée sur l'échantillon résidentiel EXACTEMENT comme le builder la
# pose : les clés legacy portent l'option AVEC (repli documenté L-2OPT), les
# clés par option disent la vérité de chaque côté.
DIVERGENCE_RENDU = {
    "panneaux_divergents": True,
    "puissance_kwc": 6.39, "nb_panneaux": 9, "watt_par_panneau": 710,
    "puissance_kwc_sans": 5.68, "puissance_kwc_avec": 6.39,
    "nb_panneaux_sans": 8, "nb_panneaux_avec": 9,
    "watt_par_panneau_sans": 710, "watt_par_panneau_avec": 710,
}


class TestPrixAuKwcParOption(SimpleTestCase):
    """F1 (a) — CHAQUE OPTION DIVISE SON TOTAL PAR SON PROPRE kWc.

    Le scalaire legacy porte l'option AVEC dès que les champs PV divergent : la
    carte « Option 1 — Sans batterie » divisait donc son total par le kWc de
    l'AUTRE option — le prix au kWc, seul chiffre qu'un client compare d'un
    devis à l'autre, sortait ~15 % trop bas.
    """

    def test_la_couverture_residentielle_divise_par_le_bon_kwc(self):
        from apps.ventes.quote_engine.residential.theme import fmt
        d = F.donnees_residentiel(**DIVERGENCE_RENDU)
        html = F.html_residentiel(**DIVERGENCE_RENDU)
        self.assertIn(f'soit {fmt(d["total_sans"] / 5.68)} MAD/kWc', html)
        self.assertNotIn(f'soit {fmt(d["total_sans"] / 6.39)} MAD/kWc', html)
        # L'option 2, elle, était déjà juste : elle le reste.
        self.assertIn(f'soit {fmt(d["total_avec"] / 6.39)} MAD/kWc', html)

    def test_la_page_1_legacy_divise_par_le_bon_kwc(self):
        from apps.ventes.quote_engine import generate_devis_premium as G
        d = F.donnees_legacy(**DIVERGENCE_RENDU)
        html = F.html_legacy(**DIVERGENCE_RENDU)
        self.assertIn(f'soit {G.fmt(d["total_sans"] / 5.68)}/kWc', html)
        self.assertNotIn(f'soit {G.fmt(d["total_sans"] / 6.39)}/kWc', html)
        self.assertIn(f'soit {G.fmt(d["total_avec"] / 6.39)}/kWc', html)

    def test_sans_divergence_le_prix_au_kwc_ne_bouge_pas(self):
        """Non-régression : tout l'existant passe par ce chemin."""
        from apps.ventes.quote_engine.residential.theme import fmt
        d = F.donnees_residentiel()
        html = F.html_residentiel()
        kwc = d["puissance_kwc"]
        self.assertIn(f'soit {fmt(d["total_sans"] / kwc)} MAD/kWc', html)
        self.assertIn(f'soit {fmt(d["total_avec"] / kwc)} MAD/kWc', html)


class TestVignettePuissanceDeuxValeurs(SimpleTestCase):
    """F1 (R1#3) — LA PAGE 1 ET LA PAGE 2 DISENT LA MÊME CHOSE.

    Sur un document qui rend LES DEUX options, la bande de la page 2 affiche
    honnêtement « sans · avec » pendant que la vignette de la page 1 annonçait
    un kWc unique (celui de l'option AVEC) : deux pages, deux vérités.
    """

    def test_la_vignette_de_couverture_porte_les_deux_valeurs(self):
        html = F.html_residentiel(**DIVERGENCE_RENDU)
        # Corps réduit à 13 pt : deux valeurs SANS agrandir la vignette (la
        # page 1 est pleine — une ligne de plus y coûterait une 4ᵉ page).
        self.assertIn('<div class="c1-kpi-v" style="font-size:13pt;">'
                      '5,68 · 6,39<span class="c1-u">&nbsp;kWc</span></div>',
                      html)
        self.assertIn('<div class="c1-kpi-l">Puissance sans · avec · '
                      '8 · 9 panneaux</div>', html)
        # Plus aucune vignette mono-valeur portant le kWc de l'option AVEC.
        self.assertNotIn('<div class="c1-kpi-l">Puissance · 9 panneaux '
                         '× 710 W</div>', html)

    def test_la_vignette_legacy_porte_les_deux_valeurs(self):
        html = F.html_legacy(**DIVERGENCE_RENDU)
        self.assertIn('5,68&#160;&#183;&#160;6,39&nbsp;kWc', html)
        self.assertIn('8 &#183; 9 panneaux (sans &#183; avec)', html)
        self.assertNotIn('9 panneaux &#215; 710&nbsp;W', html)

    def test_sans_divergence_la_vignette_est_celle_d_hier(self):
        html = F.html_residentiel()
        self.assertIn('<div class="c1-kpi-v">5,68'
                      '<span class="c1-u">&nbsp;kWc</span></div>', html)
        self.assertIn('<div class="c1-kpi-l">Puissance · 8 panneaux '
                      '× 710 W</div>', html)
        self.assertNotIn('(sans · avec)', html)
        self.assertNotIn('sans · avec', html)


class TestUnePageProductionDeSaBranche(SimpleTestCase):
    """F1 (d) — LA UNE-PAGE CHIFFRE LA PRODUCTION DE SA BRANCHE.

    Le bloc L-2OPT recalait puissance/panneaux/watt sur la branche facturée
    mais laissait « Production annuelle » sur le scalaire global : la vignette
    annonçait la production de l'AUTRE option juste à côté du kWc de celle-ci.
    """

    BRANCHES = dict(DIVERGENCE_RENDU, prod_kwh=9070,
                    prod_kwh_sans=8065, prod_kwh_avec=9070)

    @staticmethod
    def _prod(html):
        """Production RENDUE dans le résumé système, sans séparateurs."""
        i = html.find("Production annuelle")
        if i < 0:
            return None
        m = re.search(r">([\d   ]+) kWh/an<", html[i:i + 400])
        return re.sub(r"[^\d]", "", m.group(1)) if m else None

    # QJR145 (a) — LA PUISSANCE S'IMPRIME À LA FRANÇAISE : « 5,68 kWc », plus
    # jamais « 5.68 kWc ». Le formateur ``kwc_fr`` existait depuis l'origine
    # SANS aucun site d'appel ; QJR145 l'a branché sur les cinq impressions de
    # puissance du document, qui sortaient jusque-là le point décimal anglais.
    # Ces attentes suivent donc le rendu RÉEL (vérifié : la branche « sans » ne
    # rend qu'une seule chaîne kWc, « 5,68 kWc » ; la branche « avec »,
    # « 6,39 kWc »). 8 × 710 W = 5,68 kWc et 9 × 710 W = 6,39 kWc : ce sont des
    # PUISSANCES posées en dur dans ``BRANCHES``, jamais dérivées d'un
    # productible — le recalage QJR158 (d) du repli ne les touche pas.
    KWC_SANS = "5,68 kWc"      # 8 panneaux × 710 W
    KWC_AVEC = "6,39 kWc"      # 9 panneaux × 710 W

    def test_la_branche_sans_affiche_la_production_de_ses_8_panneaux(self):
        html = F.html_onepage(onepage_branche="sans", **self.BRANCHES)
        self.assertEqual(self._prod(html), "8065")
        # …et la puissance de la même branche (garde L-2OPT, déjà en place).
        # Le NÉGATIF doit porter la MÊME forme que le positif : avec l'ancien
        # « 6.39 kWc » il serait devenu vrai par accident (cette chaîne n'est
        # plus jamais rendue) et cesserait de garder quoi que ce soit.
        self.assertIn(self.KWC_SANS, html)
        self.assertNotIn(self.KWC_AVEC, html)

    def test_la_branche_avec_affiche_la_production_de_ses_9_panneaux(self):
        html = F.html_onepage(onepage_branche="avec", **self.BRANCHES)
        self.assertEqual(self._prod(html), "9070")
        self.assertIn(self.KWC_AVEC, html)
        self.assertNotIn(self.KWC_SANS, html)

    def test_sans_divergence_la_une_page_ne_recale_rien(self):
        d = F.donnees_legacy()
        html = F.html_onepage(onepage_branche="sans")
        self.assertEqual(self._prod(html), str(d["prod_kwh"]))


class TestVignetteProductionDeuxValeurs(SimpleTestCase):
    """PDFPROD (27/08/2026) — LA PRODUCTION AUSSI SE LIT PAR OPTION.

    Miroir exact de ``TestVignettePuissanceDeuxValeurs`` : la production DÉRIVE
    du kWc, elle diverge donc avec lui. Le builder publie les deux valeurs
    depuis F1 (``prod_kwh_sans`` / ``prod_kwh_avec``) mais deux surfaces
    lisaient encore le scalaire — la vignette « Production estimée » de la
    page 1 et la bande de specs de la page 2 — soit la production de la seule
    option AVEC, imprimée à côté d'une puissance écrite « sans · avec ».
    """

    # Le même échantillon divergent que les tests kWc, augmenté des deux
    # productions (dérivées des 8 et 9 panneaux, jamais inventées ici : ce sont
    # les valeurs déjà utilisées par ``TestUnePageProductionDeSaBranche``).
    DIVERGENCE_PROD = dict(DIVERGENCE_RENDU, prod_kwh=9070,
                           prod_kwh_sans=8065, prod_kwh_avec=9070)

    def test_la_vignette_de_couverture_porte_les_deux_productions(self):
        from apps.ventes.quote_engine.residential.theme import fmt
        html = F.html_residentiel(**self.DIVERGENCE_PROD)
        # Corps réduit à 12 pt : une production s'écrit sur 5 à 6 chiffres, la
        # paire doit tenir SANS élargir la vignette ni passer à la ligne.
        self.assertIn(
            f'<div class="c1-kpi-v" style="font-size:12pt;">{fmt(8065)} · '
            f'{fmt(9070)}<span class="c1-u">&nbsp;kWh/an</span></div>', html)
        self.assertIn('<div class="c1-kpi-l">Production estimée sans · avec'
                      '</div>', html)
        # Plus aucune vignette mono-valeur portant la production de l'AVEC.
        self.assertNotIn('<div class="c1-kpi-l">Production estimée</div>',
                         html)

    def test_la_bande_de_la_page_2_porte_les_deux_productions(self):
        from apps.ventes.quote_engine.residential.theme import fmt
        html = F.html_residentiel(**self.DIVERGENCE_PROD)
        self.assertIn(f'<span style="font-size:13pt;">{fmt(8065)} · '
                      f'{fmt(9070)}</span>', html)
        self.assertIn('kWh / an produits (sans · avec)', html)
        self.assertNotIn('<span class="p2-spec-l">kWh / an produits</span>',
                         html)

    def test_la_vignette_legacy_porte_les_deux_productions(self):
        """Le moteur legacy rend la MÊME page 1 quand le renderer résidentiel
        décline le devis : il portait le même scalaire unique."""
        html = F.html_legacy(**self.DIVERGENCE_PROD)
        # Le legacy groupe ses milliers avec U+00A0 (espace insécable),
        # jamais l'espace fine du thème résidentiel : la chaîne est écrite
        # en échappements pour rester lisible.
        self.assertIn('8 065&#160;&#183;&#160;9 070&nbsp;kWh', html)
        self.assertIn('&#233;nergie propre / an (sans &#183; avec)', html)
        self.assertNotIn('>&#233;nergie propre / an</div>', html)

    def test_une_production_saisie_identique_reste_une_seule_valeur(self):
        """Garde propre à la production : une production SAISIE dans l'étude
        vaut pour les deux options (le builder réaligne les deux clés). Les
        panneaux divergent, la production non — « 9 070 · 9 070 » n'aurait
        aucun sens : la vignette reste mono-valeur."""
        html = F.html_residentiel(**dict(self.DIVERGENCE_PROD,
                                         prod_kwh_sans=9070))
        self.assertIn('<div class="c1-kpi-l">Production estimée</div>', html)
        self.assertNotIn('Production estimée sans · avec', html)
        self.assertIn('<span class="p2-spec-l">kWh / an produits</span>', html)

    def test_sans_divergence_la_production_est_celle_d_hier(self):
        from apps.ventes.quote_engine.residential.theme import fmt
        d = F.donnees_residentiel()
        html = F.html_residentiel()
        self.assertIn(f'<div class="c1-kpi-v">{fmt(d["prod_kwh"])}'
                      '<span class="c1-u">&nbsp;kWh/an</span></div>', html)
        self.assertIn('<div class="c1-kpi-l">Production estimée</div>', html)
        self.assertIn('<span class="p2-spec-l">kWh / an produits</span>', html)
        self.assertNotIn('sans · avec', html)


# ── L-2OPTPDF (ORDRE FONDATEUR, 28/08/2026) — LA PAGE ÉQUIPEMENT NE SE ────────
# DÉDOUBLE PLUS. Sur un devis à deux options dont les nombres de panneaux
# divergent (DEV-202608-0040 : 15 sans / 14 avec), ``_split_items`` sortait
# panneaux + structures + socles du tableau commun et les REPOSAIT dans LES DEUX
# cartes « Spécifique à l'option N » : trois rôles écrits deux fois, une page 2
# gonflée, et un devis rendu sur 4 pages au lieu de 3.
#
# Chaque rôle divergent tient désormais sur UNE ligne à deux valeurs
# (« 15 · 14 »), et le tableau comparatif se lit sur deux colonnes : le devis
# divergent retrouve sa pagination normale.
#
# Fixtures PURES (aucune BD, aucun WeasyPrint) : on compte les ``<div
# class="page">`` du HTML EXACT qui part au rendu — une ``.page`` = une page A4
# composée par WeasyPrint (cf. ``render.build_html``).
def _items_divergents(nb_sans=15, nb_avec=14):
    """Composition réelle d'un devis divergent : panneaux, structures et socles
    changent de quantité d'une option à l'autre ; l'onduleur et la batterie
    n'existent que d'un côté."""
    pan = {"designation": "Panneau Canadien Solar 710W",
           "marque": "Canadian Solar", "prix_unit_ht": 1273.0, "taux_tva": 10}
    stru = {"designation": "Structure de fixation aluminium", "marque": "",
            "prix_unit_ht": 250.0, "taux_tva": 20}
    socle = {"designation": "Socle béton", "marque": "",
             "prix_unit_ht": 60.0, "taux_tva": 20}
    tab = {"designation": "Tableau De Protection AC/DC", "marque": "",
           "quantite": 1, "prix_unit_ht": 1250.0, "taux_tva": 20}
    inst = {"designation": "Installation", "marque": "", "quantite": 1,
            "prix_unit_ht": 4000.0, "taux_tva": 20}
    ond_r = {"designation": "Onduleur réseau Huawei 10kW Triphasé",
             "marque": "Huawei", "quantite": 1, "prix_unit_ht": 14000.0,
             "taux_tva": 20}
    ond_h = {"designation": "Onduleur hybride Deye 10kW Triphasé",
             "marque": "Deye", "quantite": 1, "prix_unit_ht": 19000.0,
             "taux_tva": 20}
    bat = {"designation": "Batterie Dyness 10 kWh", "marque": "Dyness",
           "quantite": 1, "prix_unit_ht": 22000.0, "taux_tva": 20}
    sans = [dict(pan, quantite=nb_sans), ond_r, tab,
            dict(stru, quantite=nb_sans), dict(socle, quantite=nb_sans * 2),
            inst]
    avec = [dict(pan, quantite=nb_avec), ond_h, bat, tab,
            dict(stru, quantite=nb_avec), dict(socle, quantite=nb_avec * 2),
            inst]
    return sans, avec


def _surcharges_divergentes(nb_sans=15, nb_avec=14):
    sans, avec = _items_divergents(nb_sans, nb_avec)
    return {
        "sans_items": sans, "avec_items": avec,
        "panneaux_divergents": True,
        "nb_panneaux_sans": nb_sans, "nb_panneaux_avec": nb_avec,
        "nb_panneaux": nb_avec,
        "puissance_kwc_sans": round(nb_sans * 0.71, 2),
        "puissance_kwc_avec": round(nb_avec * 0.71, 2),
        "puissance_kwc": round(nb_avec * 0.71, 2),
        "watt_par_panneau_sans": 710, "watt_par_panneau_avec": 710,
        "batterie_kwh_total": 10,
    }


def _surcharges_egales(nb=15):
    """Le TÉMOIN : la même composition, quantités IDENTIQUES des deux côtés."""
    s = _surcharges_divergentes(nb, nb)
    s["panneaux_divergents"] = False
    return s


class TestLignesDivergentesDeuxValeurs(SimpleTestCase):
    """L-2OPTPDF (a) — UN RÔLE DIVERGENT = UNE LIGNE, DEUX VALEURS."""

    def setUp(self):
        self.html = F.html_residentiel(**_surcharges_divergentes())

    def _cartes(self):
        cartes = re.findall(r'<div class="p2-dbody">.*?</ul>', self.html, re.S)
        self.assertEqual(len(cartes), 2)
        return cartes

    def test_le_panneau_ne_s_ecrit_qu_une_fois(self):
        """Le cœur de l'incident : la désignation apparaissait dans les DEUX
        cartes d'option. Elle vit maintenant dans le tableau, une seule fois."""
        for carte in self._cartes():
            self.assertNotIn('Panneau Canadien Solar 710W', carte)
            self.assertNotIn('Structure de fixation aluminium', carte)
            self.assertNotIn('Socle béton', carte)

    def test_la_ligne_porte_les_deux_quantites_et_les_deux_totaux(self):
        lignes = re.findall(r'<tr class="p2-tr-2v">.*?</tr>', self.html, re.S)
        self.assertEqual(len(lignes), 3)      # panneaux, structures, socles
        panneau = next(x for x in lignes if 'Panneau Canadien' in x)
        # Qté « 15 · 14 » …
        self.assertIn('<span class="p2-vs">15</span>', panneau)
        self.assertIn('<span class="p2-va">14</span>', panneau)
        # … P.U. unique (le prix ne change pas d'une option à l'autre) …
        from apps.ventes.quote_engine.residential.theme import fmt
        self.assertIn(f'<td class="p2-r">{fmt(1273.0)}</td>', panneau)
        # … et les DEUX totaux HT (15 × 1 273 et 14 × 1 273).
        self.assertIn(f'<span class="p2-vs">{fmt(15 * 1273.0)}</span>',
                      panneau)
        self.assertIn(f'<span class="p2-va">{fmt(14 * 1273.0)}</span>',
                      panneau)
        # La chaîne par ligne reste complète : TVA comprise.
        self.assertIn('>10%<', panneau)

    def test_les_deux_colonnes_sont_nommees(self):
        """Deux nombres côte à côte ne se devinent pas : la légende du tableau
        dit lequel est « sans » et lequel est « avec »."""
        self.assertIn('deux valeurs&nbsp;: <b>sans</b> &middot; '
                      '<b>avec</b> batterie', self.html)
        self.assertIn('Équipement des deux options', self.html)

    def test_le_vraiment_specifique_reste_dans_sa_carte(self):
        """Ce qui n'existe QUE d'un côté ne se compare pas : onduleur réseau
        contre onduleur hybride + batterie restent par option."""
        sans, avec = self._cartes()
        self.assertIn('Onduleur réseau Huawei 10kW Triphasé', sans)
        self.assertNotIn('Batterie Dyness 10 kWh', sans)
        self.assertIn('Onduleur hybride Deye 10kW Triphasé', avec)
        self.assertIn('Batterie Dyness 10 kWh', avec)


class TestPaginationDevisDivergent(SimpleTestCase):
    """L-2OPTPDF (b) — LE DEVIS DIVERGENT GARDE SES 3 PAGES.

    Le format 'full' résidentiel vaut 3 pages (couverture + installation +
    signature). Un devis divergent en faisait 4 : ses trois rôles dupliqués
    plus le tableau comparatif ne tenaient plus dans le budget de la page
    installation, qui se scindait en page équipement + page rentabilité.
    """

    def _pages(self, **surcharges):
        return F.html_residentiel(**surcharges).count('<div class="page">')

    def test_le_devis_divergent_tient_en_trois_pages(self):
        self.assertEqual(self._pages(**_surcharges_divergentes()), 3)

    def test_le_devis_a_quantites_egales_tient_toujours_en_trois_pages(self):
        """Non-régression : le témoin (même composition, 15 · 15) n'a jamais
        débordé et ne déborde toujours pas."""
        self.assertEqual(self._pages(**_surcharges_egales()), 3)

    def test_le_comparatif_de_synthese_est_intact(self):
        """La page reste compacte SANS rien retirer au comparatif : il se lit
        sur deux colonnes, chaque moitié gardant ses en-têtes."""
        html = F.html_residentiel(**_surcharges_divergentes())
        self.assertEqual(html.count('<div class="p2-cmp-grid">'), 1)
        self.assertEqual(html.count('<table class="p2-cmp">'), 2)
        self.assertEqual(html.count('<th>Sans batterie</th>'), 2)
        self.assertEqual(html.count('<th>Avec batterie</th>'), 2)
        for libelle in ('Panneaux', 'Puissance', 'Batteries', 'Prix TTC'):
            self.assertIn(f'<td class="p2-cmp-k">{libelle}</td>', html)


class TestNonDivergentInchangeAuBitPres(SimpleTestCase):
    """L-2OPTPDF (c) — QUANTITÉS ÉGALES ⇒ EXACTEMENT LE RENDU D'HIER.

    Aucune ligne appariée, aucune légende, aucun comparatif : le corps de la
    page 2 d'un devis non divergent ne bouge pas d'un octet (seule la feuille
    de style gagne des règles qui ne s'appliquent à rien ici).
    """

    def test_aucune_ligne_a_deux_valeurs(self):
        for surcharges in ({}, _surcharges_egales()):
            html = F.html_residentiel(**surcharges)
            # La BALISE, pas la classe seule : les deux vivent aussi dans la
            # feuille de style, qui part sur toutes les pages.
            self.assertNotIn('<tr class="p2-tr-2v">', html)
            self.assertNotIn('<span class="p2-lbl-leg">', html)
            self.assertNotIn('<div class="p2-cmp-grid">', html)
            self.assertIn('Équipement commun aux deux options', html)
            self.assertNotIn('Équipement des deux options', html)

    def test_le_tableau_commun_garde_toutes_ses_lignes(self):
        """Quantités égales ⇒ panneaux, structures et socles restent COMMUNS
        (une seule quantité, l'historique)."""
        html = F.html_residentiel(**_surcharges_egales())
        for designation in ('Structure de fixation aluminium', 'Socle béton'):
            self.assertEqual(html.count(designation), 1)

    def test_le_corps_de_la_page_2_est_celui_de_l_ancien_decoupage(self):
        """Témoin mécanique : la même page rendue en neutralisant
        l'appariement — les deux HTML doivent être identiques."""
        from apps.ventes.quote_engine.residential import (
            options, render, renderer,
        )
        data = renderer._augment(F.donnees_residentiel(**_surcharges_egales()))
        ctx = render.build_ctx(data)
        neuf = "".join(options.build_pages(ctx))
        with patch.object(options, '_pair_divergents',
                          lambda s, a: ([], s, a)):
            ancien = "".join(options.build_pages(ctx))
        self.assertEqual(neuf, ancien)


class TestQjr210ModeleDeclareParCarte(_DevisVariantesMixin, TestCase):
    """QJR210 (contre-visite du 30/08/2026) — LA MOITIÉ *RENDU* DE QJR28.

    QJR28 a bâti la moitié DONNÉES : sur un devis divergent, ``builder``
    enregistre le modèle d'économies EFFECTIF de chaque colonne
    (``savings_model_sans`` / ``savings_model_avec``) parce que la garde de
    fraîcheur de ``pricing`` fait retomber sur le forfait la colonne dont la
    puissance ne correspond plus au bloc horaire. Personne ne LISAIT ces clés :
    la page 1 étiquetait les DEUX cartes avec le modèle du DOCUMENT, et la
    ligne « Économies … / an » du comparatif de page 2 déclarait un mot unique
    pour deux colonnes chiffrées par deux moteurs.

    Rendu seulement : ``builder`` n'est pas touché (aucune donnée nouvelle —
    ces quatre clés sont publiées depuis QJR28).

    Classe volontairement NON taguée ``pdf`` : elle ne rend que du HTML (comme
    ``TestPageUnQrProposition``), donc elle garde le comportement dans le
    palier de CI courant plutôt que dans le seul palier release-verify.
    """

    #: le bloc horaire décrit l'option AVEC : 26 × 710 W = 18,46 kWc ; la
    #: colonne SANS fait 22 × 710 W = 15,62 kWc — hors tolérance, donc chiffrée
    #: par l'autre moteur.
    KWC_AVEC = 18.46

    def _data_divergent_horaire(self, reference):
        from apps.ventes.tests.test_cj2b_graphe_mensuel import bloc_horaire
        return self._build(self._devis(
            self.DIVERGENT, reference,
            self._etude_params(etude_horaire=bloc_horaire(self.KWC_AVEC))))

    def _cover(self, data):
        from apps.ventes.quote_engine.residential import (
            cover, render, renderer)
        return cover.build(render.build_ctx(renderer._augment(data)))

    def _page2(self, data):
        from apps.ventes.quote_engine.residential import (
            options, render, renderer)
        ctx = render.build_ctx(renderer._augment(data))
        return "".join(options.build_pages(ctx))

    @staticmethod
    def _libelles_cartes(html):
        """Le libellé de chaque carte d'option, DANS L'ORDRE DU DOCUMENT
        (Option 1 « Sans batterie », puis Option 2 « Avec batterie »)."""
        return re.findall(r'<div class="c1-opt-eco">(.*?) ≈', html)

    # ── page 1 : une carte, un modèle ───────────────────────────────────────
    def test_chaque_carte_porte_le_modele_de_son_option(self):
        data = self._data_divergent_horaire('DEV-QJR210-DIV')
        # Préalable (déjà épinglé par QJR28) : les deux colonnes ONT été
        # chiffrées par deux moteurs différents.
        self.assertEqual(data['savings_model_avec'], 'horaire')
        self.assertNotEqual(data['savings_model_sans'], 'horaire')

        libelles = self._libelles_cartes(self._cover(data))
        self.assertEqual(len(libelles), 2, libelles)
        self.assertNotEqual(
            libelles[0], libelles[1],
            "les deux cartes portaient le modèle du DOCUMENT")
        self.assertEqual(libelles, ['Économie estimée', 'Économie calculée'])

    def test_un_devis_a_un_seul_moteur_garde_le_meme_mot_des_deux_cotes(self):
        """Non-régression : quand les deux colonnes sont chiffrées par le même
        moteur (tout l'existant), les deux cartes portent le même mot."""
        from apps.ventes.tests.test_cj2b_graphe_mensuel import bloc_horaire
        # LEGACY = 14 × 710 W = 9,94 kWc, exactement la puissance du bloc.
        data = self._build(self._devis(
            self.LEGACY, 'DEV-QJR210-LEG',
            self._etude_params(etude_horaire=bloc_horaire(9.94))))
        self.assertEqual(data['savings_model_sans'],
                         data['savings_model_avec'])
        libelles = self._libelles_cartes(self._cover(data))
        self.assertEqual(libelles, ['Économie calculée', 'Économie calculée'])

    def test_sans_les_cles_l_etiquette_est_omise_jamais_devinee(self):
        """Dict d'appelant antérieur à QJR28 : le modèle de chaque colonne est
        inconnu — le mot disparaît, l'économie reste. Jamais le modèle du
        document réattribué à une carte qui ne l'a peut-être pas."""
        data = self._data_divergent_horaire('DEV-QJR210-NOKEY')
        self.assertEqual(data['savings_model'], 'horaire')   # le document, lui
        data.pop('savings_model_sans')
        data.pop('savings_model_avec')
        libelles = self._libelles_cartes(self._cover(data))
        self.assertEqual(libelles, ['Économie', 'Économie'])

    # ── page 2 : la ligne « Économies … / an » du comparatif ────────────────
    def test_le_comparatif_n_impose_pas_un_mot_a_deux_moteurs(self):
        data = self._data_divergent_horaire('DEV-QJR210-CMP')
        html = self._page2(data)
        self.assertIn('Économies / an', html)
        self.assertNotIn('Économies estimées / an', html)
        self.assertNotIn('Économies calculées / an', html)

    def test_le_comparatif_garde_son_mot_quand_les_deux_colonnes_concordent(self):
        """Le devis divergent SANS bloc horaire : un seul moteur pour les deux
        colonnes ⇒ le libellé garde son qualificatif (rendu d'aujourd'hui).
        Le mot attendu est LU dans les données, jamais recopié à la main."""
        data = self._build(self._devis_divergent('DEV-QJR210-CMP2'))
        self.assertEqual(data['savings_model_sans'],
                         data['savings_model_avec'])
        attendu = (' calculées' if data['savings_model_sans'] == 'horaire'
                   else ' estimées')
        self.assertIn(f'Économies{attendu} / an', self._page2(data))
