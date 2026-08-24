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

from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

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

    def _etude_params(self, **extra):
        return {**DEUX_OPTIONS,
                'factures_mensuelles_reelles': list(FACTURES_REELLES),
                **extra}

    def _devis_divergent(self, reference='DEV-L2OPT-DIV'):
        return self._devis(self.DIVERGENT, reference, self._etude_params())

    def _devis_legacy(self, reference='DEV-L2OPT-LEG'):
        return self._devis(self.LEGACY, reference, self._etude_params())


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
        # Deux options → la une-page facture l'option 1 (« sans »).
        self.assertEqual(data['onepage_branche'], 'sans')
        html, doc = self._render_legacy(data)
        self.assertEqual(
            len(doc.pages), 1,
            f'le format une page doit rendre 1 page, {len(doc.pages)} rendues')
        self.assertIn('15.62 kWc', html)     # kWc de la branche facturée
        self.assertNotIn('18.46 kWc', html)  # jamais ceux de l'autre option

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
            # « rachat » apparaît dans les mentions tarifaires ANRE.
            for marqueur in ('9876', '9 876', '9 876', '9&#8239;876'):
                self.assertNotIn(marqueur, html.lower())
