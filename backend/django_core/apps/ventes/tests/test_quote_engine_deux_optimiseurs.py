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
        self.assertIn('<div class="c1-kpi-v">5,68 · 6,39'
                      '<span class="c1-u">&nbsp;kWc</span></div>', html)
        self.assertIn('<div class="c1-kpi-l">Puissance (sans · avec) · '
                      '8 · 9 panneaux × 710 W</div>', html)
        # Plus aucune vignette mono-valeur portant le kWc de l'option AVEC.
        self.assertNotIn('<div class="c1-kpi-l">Puissance · 9 panneaux '
                         '× 710 W</div>', html)

    def test_la_vignette_legacy_porte_les_deux_valeurs(self):
        html = F.html_legacy(**DIVERGENCE_RENDU)
        self.assertIn('5,68&#160;&#183;&#160;6,39&nbsp;kWc', html)
        self.assertIn('8 &#183; 9 panneaux (sans &#183; avec) '
                      '&#215; 710&nbsp;W', html)

    def test_sans_divergence_la_vignette_est_celle_d_hier(self):
        html = F.html_residentiel()
        self.assertIn('<div class="c1-kpi-v">5,68'
                      '<span class="c1-u">&nbsp;kWc</span></div>', html)
        self.assertIn('<div class="c1-kpi-l">Puissance · 8 panneaux '
                      '× 710 W</div>', html)
        self.assertNotIn('(sans · avec)', html)


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

    def test_la_branche_sans_affiche_la_production_de_ses_8_panneaux(self):
        html = F.html_onepage(onepage_branche="sans", **self.BRANCHES)
        self.assertEqual(self._prod(html), "8065")
        # …et la puissance de la même branche (garde L-2OPT, déjà en place).
        self.assertIn("5.68 kWc", html)
        self.assertNotIn("6.39 kWc", html)

    def test_la_branche_avec_affiche_la_production_de_ses_9_panneaux(self):
        html = F.html_onepage(onepage_branche="avec", **self.BRANCHES)
        self.assertEqual(self._prod(html), "9070")
        self.assertIn("6.39 kWc", html)

    def test_sans_divergence_la_une_page_ne_recale_rien(self):
        d = F.donnees_legacy()
        html = F.html_onepage(onepage_branche="sans")
        self.assertEqual(self._prod(html), str(d["prod_kwh"]))
