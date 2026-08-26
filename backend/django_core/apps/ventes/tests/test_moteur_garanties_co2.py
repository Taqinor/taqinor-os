"""M6/M8 — le renderer RÉSIDENTIEL n'invente aucun chiffre (audit du 19/08/2026).

RÈGLE : valeur inconnue ⇒ ``None`` + omission, JAMAIS un forfait.

Comme ``test_moteur_zero_invention`` (moteur legacy), chaque test épingle le
HTML RÉELLEMENT RENDU par le renderer résidentiel redessiné
(``residential.render.build_html``), pas la fonction qui le calcule — c'est le
trou par lequel « 87,4 % » et « 21 kg/arbre » codés en dur sont passés :
tout le monde interrogeait des fonctions, personne ne regardait le document.
Aucune BD, aucun WeasyPrint : ``SimpleTestCase``, rendu HTML pur.

M6 — la carte « Performance garantie » (page 2, ``options.py``) et la bande
« Nos garanties » (page 3, ``trust.py``) doivent toujours porter la MÊME
durée : les deux lisent ``theme.warranties_for(d)``, dérivée de la
composition réelle du devis, jamais un littéral recopié.

CO2SRC (2026-08-26, remplace M8) — le SEUL chiffre d'impact encore imprimé sur
un document client est la tonne ANNUELLE (production réelle du devis ×
``constants.CO2_T_PAR_MWH``). L'équivalence en arbres (22 kg/arbre/an) et le
cumul 25 ans (× 23,5) quittent tout rendu client : aucune source ne les porte.
"""

import re

from django.test import SimpleTestCase

from apps.ventes.quote_engine.residential import renderer, render
from apps.ventes.tests import _moteur_fixtures as F


def _ligne(designation, marque="", garantie_mois=None,
           garantie_production_mois=None, quantite=1, prix_unit_ht=100.0,
           taux_tva=20):
    """Ligne d'équipement minimale pour le renderer résidentiel (page 2)."""
    return {"designation": designation, "marque": marque,
            "quantite": quantite, "prix_unit_ht": prix_unit_ht,
            "taux_tva": taux_tva, "garantie_mois": garantie_mois,
            "garantie_production_mois": garantie_production_mois}


# ── Fixtures composition ──────────────────────────────────────────────────
_TABLEAU = _ligne("Tableau De Protection AC/DC", prix_unit_ht=1250)
_STRUCT = _ligne("Structure de fixation aluminium", quantite=8, prix_unit_ht=250)
_INSTALL = _ligne("Installation", prix_unit_ht=4000)


def _html_longi():
    """Même devis que l'échantillon par défaut, panneau LONGI (30 ans produit
    ET performance — mais 88,9 %, jamais tracé dans ce moteur) à la place de
    Canadian Solar, onduleurs SANS donnée produit."""
    base = F.donnees_residentiel()
    longi = _ligne("Panneau Longi 585W", marque="Longi", garantie_mois=144,
                   garantie_production_mois=360, quantite=8,
                   prix_unit_ht=1200, taux_tva=10)
    ond = _ligne("Onduleur réseau Huawei 5kW Monophasé", marque="Huawei",
                 prix_unit_ht=11667)
    ond_h = _ligne("Onduleur hybride Deye 5kW Monophasé", marque="Deye",
                   prix_unit_ht=16667)
    bat = _ligne("Batterie Lithium Dyness 5,12 kWh", marque="Dyness",
                 prix_unit_ht=13333)
    base["sans_items"] = [longi, ond, _TABLEAU, _STRUCT, _INSTALL]
    base["avec_items"] = [longi, ond_h, bat, _TABLEAU, _STRUCT, _INSTALL]
    return render.build_html(renderer._augment(base))


_STAT_CARD_RE = re.compile(
    r'Performance garantie</span>\s*<span class="p2-stat-v">([^<]+)</span>')
_BANDE_PERF_RE = re.compile(r'<b>(\d+) ans</b> — Performance')


class M6GarantiesResidentiellesTests(SimpleTestCase):
    """M6 — la carte-stat page 2 et la bande page 3 dérivent de la
    composition réelle (theme.warranties_for), jamais d'un littéral."""

    def test_le_devis_par_defaut_canadian_solar_garde_87_4(self):
        html = F.html_residentiel()
        self.assertIn("87,4", html)

    def test_carte_et_bande_donnent_la_meme_duree_sur_le_devis_par_defaut(self):
        html = F.html_residentiel()
        carte = _STAT_CARD_RE.search(html)
        bande = _BANDE_PERF_RE.search(html)
        self.assertIsNotNone(carte, "carte-stat « Performance garantie » absente")
        self.assertIsNotNone(bande, "entrée Performance absente de la bande")
        self.assertEqual(carte.group(1).strip(), f"{bande.group(1)} ans")

    def test_panneau_longi_le_pourcentage_canadian_solar_ne_sort_plus(self):
        # Longi est lui aussi garanti 30 ans — mais à 88,9 %, jamais tracé
        # dans ce moteur : le chiffre Canadian Solar ne doit plus fuiter.
        self.assertNotIn("87,4", _html_longi())

    def test_devis_longi_carte_et_bande_restent_coherentes_entre_elles(self):
        html = _html_longi()
        carte = _STAT_CARD_RE.search(html)
        bande = _BANDE_PERF_RE.search(html)
        self.assertIsNotNone(carte)
        self.assertIsNotNone(bande)
        self.assertEqual(carte.group(1).strip(), f"{bande.group(1)} ans")
        # La vraie donnée saisie (30 ans, garantie_production_mois=360) reste
        # affichée — seul le pourcentage inventé disparaît.
        self.assertEqual(bande.group(1), "30")

    def test_onduleur_sans_donnee_produit_est_omis(self):
        # « 10 ans » est documenté pour Huawei ET Deye à la fois (voir
        # theme._WARRANTY_FALLBACK) : aucune marque n'est LE produit par
        # défaut, donc plus aucun repli — sans donnée saisie, omission.
        html = _html_longi()
        self.assertNotIn("— Onduleur", html)

    def test_onduleur_avec_donnee_produit_reste_affiche(self):
        base = F.donnees_residentiel()
        pan = _ligne("Panneau X 585W", quantite=8, prix_unit_ht=1200,
                     taux_tva=10)
        ond = _ligne("Onduleur réseau 10kW", garantie_mois=96,
                     prix_unit_ht=11667)
        base["sans_items"] = [pan, ond, _TABLEAU, _STRUCT, _INSTALL]
        base["avec_items"] = [pan, ond, _TABLEAU, _STRUCT, _INSTALL]
        html = render.build_html(renderer._augment(base))
        self.assertIn("8 ans</b> — Onduleur", html)

    def test_panneau_sans_aucune_donnee_omet_carte_et_entree_performance(self):
        base = F.donnees_residentiel()
        pan = _ligne("Panneau X 585W", quantite=8, prix_unit_ht=1200,
                     taux_tva=10)
        ond = _ligne("Onduleur réseau 10kW", prix_unit_ht=11667)
        base["sans_items"] = [pan, ond, _TABLEAU, _STRUCT, _INSTALL]
        base["avec_items"] = [pan, ond, _TABLEAU, _STRUCT, _INSTALL]
        html = render.build_html(renderer._augment(base))
        self.assertNotIn("Performance garantie", html)
        self.assertNotIn("— Performance", html)
        self.assertNotIn("87,4", html)


class M8ImpactCo2ArbresTests(SimpleTestCase):
    """CO2SRC (règle « chiffres vérifiés », 2026-08-26) — remplace la garde M8.

    M8 vérifiait que le nombre d'arbres dérivait bien de 22 et non de 21. La
    vraie question n'était pas l'arrondi : c'était la SOURCE. Deux des trois
    chiffres d'impact ne reposaient sur rien de vérifiable et QUITTENT tout
    rendu client — le PDF résidentiel (pages 1 et rentabilité), le bandeau
    agricole et le site :
      · l'équivalence en ARBRES (22 kg de CO₂/arbre/an — ordre de grandeur de
        vulgarisation, variable d'un facteur 5 selon essence/âge/climat) ;
      · le CUMUL 25 ANS (tonne annuelle × 23,5 — coefficient qu'aucun calcul
        du moteur ne produit, et qui suppose le mix électrique marocain figé
        pendant un quart de siècle).
    Ce qui RESTE, et que ces tests épinglent : la tonne ANNUELLE, dérivée
    d'une production RÉELLE du devis × constants.CO2_T_PAR_MWH.
    """

    def test_la_tonne_annuelle_derive_de_la_production_reelle(self):
        from apps.ventes.quote_engine import constants
        d = renderer._augment(F.donnees_residentiel())
        html = render.build_html(d)
        attendu = d["prod_kwh"] * constants.CO2_T_PAR_MWH / 1000.0
        attendu_txt = (f"{attendu:.1f}".replace(".", ",") if attendu < 10
                       else str(round(attendu)))
        self.assertIn("tonnes de CO<sub>2</sub></b>", html)
        self.assertIn(attendu_txt, html)

    def test_plus_aucune_equivalence_en_arbres_sur_le_document(self):
        for variante in ("deux", "plus10"):
            html = render.build_html(
                renderer._augment(F.donnees_residentiel(variante)))
            self.assertNotIn("arbres", html, variante)

    def test_plus_aucun_cumul_co2_sur_25_ans(self):
        # Le variant « plus10 » déclenche la page rentabilité dédiée
        # (options.py) qui portait les trois cartes d'impact.
        html = render.build_html(
            renderer._augment(F.donnees_residentiel("plus10")))
        self.assertIn("de CO<sub>2</sub> évitées chaque année", html)
        self.assertNotIn("évitées sur", html)
        self.assertNotIn("25 ans</span>", html)

    def test_production_nulle_aucune_mention_de_co2(self):
        # _augment refuse prod_kwh=0 (garde M2) : on l'annule APRÈS
        # augmentation, pour tester la page RÉELLEMENT rendue par cover.py.
        d = renderer._augment(F.donnees_residentiel())
        d["prod_kwh"] = 0
        html = render.build_html(d)
        self.assertNotIn("arbres", html)
        self.assertNotIn("Et pour la planète&nbsp;:", html)
