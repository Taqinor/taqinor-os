"""QJR118 — les garanties des PDF industriel et commercial se DÉRIVENT du devis.

Avant ce lot, ``industriel/trust.py`` et ``commercial/trust.py`` imprimaient des
durées LITTÉRALES (« 25 ans Performance panneaux · 5-10 ans Onduleurs · 10 ans
Installation ») alors que la source unique ``residential.theme`` (QRES5) porte
2 ans Installation / 10 ans Onduleur / 12 ans Panneaux / 30 ans Performance
à 87,4 %. L'engagement de pose imprimé était donc surévalué CINQ FOIS, et le
même document pouvait porter deux durées de performance contradictoires — ce
que le commentaire QRES5 de la source interdit explicitement.

Les trois paquets lisent désormais ``theme.warranties_for(d)``, qui dérive les
durées de la composition RÉELLE et OMET toute garantie non traçable.

Run (sans base de données) :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr118_garanties_derivees -v 2
"""
import re
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from apps.ventes.quote_engine.commercial import (
    render as c_render, renderer as c_renderer, sample_data as c_sample)
from apps.ventes.quote_engine.industriel import (
    render as i_render, renderer as i_renderer, sample_data as i_sample)
from apps.ventes.quote_engine.residential import theme
from apps.ventes.quote_engine.residential import trust as r_trust


_ENGINE = Path(__file__).resolve().parents[1] / "quote_engine"

# Composition COMPLÈTE portant ses durées catalogue structurées.
ITEMS_COMPLETS = [
    {"designation": "Panneau Canadian Solar TOPHiKu7 580W", "quantite": 12,
     "garantie_mois": 144, "garantie_production_mois": 360},
    {"designation": "Onduleur hybride Deye SUN-8K-SG05LP3", "quantite": 1,
     "garantie_mois": 120},
    {"designation": "Batterie lithium Deye BOS-B-Pack16-A3 16 kWh",
     "quantite": 1, "garantie_mois": 120},
]

# Composition SANS aucune durée saisie et sans le panneau par défaut : ni
# l'onduleur ni le panneau n'ont de garantie vérifiable → omission.
ITEMS_SANS_DUREE = [
    {"designation": "Panneau Longi Hi-MO 6 580W", "quantite": 12},
    {"designation": "Onduleur hybride Deye SUN-8K-SG05LP3", "quantite": 1},
]


def _fixture(sample_mod, renderer_mod, items):
    data = renderer_mod._augment(sample_mod.build())
    data["items"] = list(items)
    return data


def _cells(html, prefix):
    """[(valeur, libellé)] de la bande de garanties d'un PDF pro."""
    pat = (r'class="%s-warr-v">([^<]+)</div>\s*'
           r'<div class="%s-warr-l">([^<]+)<' % (prefix, prefix))
    return [(v.strip(), lab.strip()) for v, lab in re.findall(pat, html)]


def _residential_cells(data):
    """Même bande, côté résidentiel (page signature)."""
    ctx = {
        "d": data,
        "C": theme.C,
        "fmt": theme.fmt,
        "fonts": {"display": theme.FONT_DISPLAY, "serif": theme.FONT_SERIF,
                  "sans": theme.FONT_SANS},
        "ident": theme.company_identity(data),
    }
    html = r_trust.build(ctx)
    out = []
    for val, lab in re.findall(r'class="p3-gar-i"><b>([^<]+)</b> — ([^<]+)<',
                               html):
        out.append((val.strip(), lab.split(" (")[0].strip()))
    return out


class TestAucuneDureeLitterale(SimpleTestCase):
    """Plus une seule durée de garantie codée en dur dans les deux paquets."""

    #: Les trois cellules exactes que ce lot supprime.
    LITTERAUX = ("25 ans", "5-10 ans", "10 ans</div>")

    def _sources(self):
        for paquet in ("industriel", "commercial"):
            for path in sorted((_ENGINE / paquet).glob("*.py")):
                yield path, path.read_text(encoding="utf-8")

    def test_aucune_valeur_de_garantie_chiffree_en_dur(self):
        for path, src in self._sources():
            with self.subTest(fichier=path.name):
                self.assertFalse(
                    re.search(r'warr-v">\s*[-0-9]', src),
                    "%s code encore une durée de garantie en dur" % path.name)

    def test_les_litteraux_supprimes_ont_disparu(self):
        for path, src in self._sources():
            bande = [ligne for ligne in src.splitlines() if "warr-" in ligne]
            for lit in self.LITTERAUX:
                with self.subTest(fichier=path.name, litteral=lit):
                    self.assertFalse(
                        any(lit in ligne for ligne in bande),
                        "%s porte encore « %s »" % (path.name, lit))


class TestPariteTroisPaquets(SimpleTestCase):
    """Sur UNE MÊME fixture, les trois paquets affichent les mêmes durées."""

    def setUp(self):
        self.ind = _fixture(i_sample, i_renderer, ITEMS_COMPLETS)
        self.com = _fixture(c_sample, c_renderer, ITEMS_COMPLETS)
        self.attendu = [(f"{n} {u}", label)
                        for n, u, label, _sub in theme.warranties_for(self.ind)]

    def test_source_unique_non_vide(self):
        # Garde-fou du test lui-même : la fixture doit produire des garanties.
        self.assertIn(("2 ans", "Installation"), self.attendu)
        self.assertIn(("30 ans", "Performance"), self.attendu)

    def test_industriel_rend_les_garanties_derivees(self):
        cells = _cells(i_render.build_html(self.ind), "i3")
        self.assertEqual([c for c in cells if c[0] != "O&amp;M"], self.attendu)

    def test_commercial_rend_les_garanties_derivees(self):
        cells = _cells(c_render.build_html(self.com), "c3")
        self.assertEqual([c for c in cells if c[0] != "O&amp;M"], self.attendu)

    def test_residentiel_dit_la_meme_chose(self):
        self.assertEqual(_residential_cells(self.ind), self.attendu)

    def test_plus_aucune_promesse_de_pose_de_dix_ans(self):
        for html in (i_render.build_html(self.ind),
                     c_render.build_html(self.com)):
            bande = re.search(r'class="[ic]3-warr"(.+?)</div>\s*</div>',
                              html, re.S)
            self.assertIsNotNone(bande)
            self.assertNotIn("10 ans</div><div", bande.group(1)
                             .replace("\n", "").replace("  ", ""))
            self.assertIn("2 ans", bande.group(1))


class TestOmissionPropre(SimpleTestCase):
    """Une garantie non traçable ne s'invente pas : elle s'omet."""

    def setUp(self):
        self.ind = _fixture(i_sample, i_renderer, ITEMS_SANS_DUREE)
        self.com = _fixture(c_sample, c_renderer, ITEMS_SANS_DUREE)

    def test_onduleur_et_panneaux_absents_sans_donnee_produit(self):
        for html, prefix in ((i_render.build_html(self.ind), "i3"),
                             (c_render.build_html(self.com), "c3")):
            labels = [lab for _v, lab in _cells(html, prefix)]
            self.assertIn("Installation", labels)
            self.assertNotIn("Onduleur", labels)
            self.assertNotIn("Panneaux", labels)
            self.assertNotIn("Performance", labels)

    def test_bande_entiere_omise_sans_aucune_garantie(self):
        with mock.patch.object(theme, "warranties_for", return_value=[]):
            html_i = i_render.build_html(self.ind)
            html_c = c_render.build_html(self.com)
        self.assertNotIn('class="i3-warr"', html_i)
        self.assertNotIn('class="c3-warr"', html_c)
        # …et la page reste rendue (signature toujours présente).
        self.assertIn("Bon pour accord", html_i)
        self.assertIn("Bon pour accord", html_c)


class TestSpl162GarantiesDesFichesApresScission(SimpleTestCase):
    """SPL162 — ``warranties_for`` lit ses prédicats dans ``lignes_classement``.

    Un import cassé y est AVALÉ (``except`` → constante ``WARRANTIES``) : sans
    ce test, un nettoyage F401 de ``builder`` aurait silencieusement remplacé
    les garanties des fiches par la constante sur chaque PDF."""

    def test_composition_panneau_onduleur_batterie_rend_les_fiches(self):
        d = {'items': [
            {'designation': 'Panneau Longi Hi-MO 585W', 'marque': 'Longi',
             '_produit_nom': 'Panneau Longi Hi-MO 585W',
             'garantie_mois': 180, 'garantie_production_mois': 300},
            {'designation': 'Onduleur hybride Deye 8kW', 'marque': 'Deye',
             '_produit_nom': 'Onduleur hybride Deye 8kW',
             'garantie_mois': 60},
            {'designation': 'Batterie Dyness 10 kWh', 'marque': 'Dyness',
             '_produit_nom': 'Batterie Dyness 10 kWh',
             'garantie_mois': 120},
        ]}
        bandes = theme.warranties_for(d)
        self.assertNotEqual(bandes, list(theme.WARRANTIES))
        par_libelle = {w[2]: w for w in bandes}
        self.assertEqual(par_libelle['Onduleur'][0], '5')
        self.assertEqual(par_libelle['Panneaux'][0], '15')
        self.assertEqual(par_libelle['Performance'][0], '25')
        self.assertEqual(par_libelle['Batterie'][0], '10')


class TestVnt37GarantiesDeLaVente(SimpleTestCase):
    """VNT37 — ``utils/garanties.garanties_de_la_vente`` : les garanties de la
    facture sont celles de la bande du PDF devis du MÊME marché, en texte
    seul ; ``[]`` sans ligne et sur erreur (jamais les constantes)."""

    #: Panneaux Canadian Solar 144/360, onduleur Deye 120, batterie SANS durée.
    ITEMS = [
        {"designation": "Panneau Canadian Solar TOPHiKu7 580W",
         "marque": "Canadian Solar", "quantite": 12,
         "garantie_mois": 144, "garantie_production_mois": 360},
        {"designation": "Onduleur hybride Deye SUN-8K-SG05LP3",
         "marque": "Deye", "quantite": 1, "garantie_mois": 120},
        {"designation": "Batterie lithium Deye BOS-B-Pack16-A3 16 kWh",
         "marque": "Deye", "quantite": 1},
    ]
    #: Pompe + variateur (rôle pompage AGR7), durées structurées.
    ITEMS_POMPAGE = [
        {"designation": "Pompe immergée OSP 30-5", "quantite": 1,
         "role_pompage": "pompe", "garantie_mois": 24},
        {"designation": "Variateur VEICHI SI23 4 kW", "quantite": 1,
         "role_pompage": "variateur_pompage", "garantie_mois": 18},
    ]

    def _g(self, items, mode="residentiel", langue="fr"):
        from apps.ventes.utils.garanties import garanties_des_items
        return garanties_des_items(items, mode, langue)

    def test_residentiel_durees_des_fiches(self):
        g = self._g(self.ITEMS)
        self.assertEqual(
            [(x["designation"], x["duree"], x["detail"]) for x in g],
            [("Installation", "2 ans", ""), ("Onduleur", "10 ans", ""),
             ("Panneaux", "12 ans", ""),
             ("Performance", "30 ans", "87,4 % garanti")])
        self.assertNotIn("Batterie", [x["designation"] for x in g])
        self.assertNotIn("TAQINOR", repr(g))

    def test_arabe_texte_seul(self):
        g = self._g(self.ITEMS, langue="ar")
        self.assertEqual(len(g), 4)
        self.assertNotIn("<span", repr(g))
        self.assertNotIn("Onduleur", repr(g))
        self.assertIn("سنوات", g[1]["duree"])

    def test_sans_lignes_liste_vide(self):
        from apps.ventes.utils.garanties import garanties_de_la_vente
        self.assertEqual(self._g([]), [])
        self.assertEqual(self._g([], mode="agricole"), [])
        self.assertEqual(garanties_de_la_vente(None), [])

    def test_exception_liste_vide_jamais_les_constantes(self):
        with mock.patch.object(theme, "warranties_for",
                               side_effect=RuntimeError("boom")):
            self.assertEqual(self._g(self.ITEMS), [])
        with mock.patch("importlib.import_module",
                        side_effect=ImportError("cassé")):
            self.assertEqual(self._g(self.ITEMS), [])

    def test_agricole_liste_de_garanties_pompage(self):
        from apps.ventes.quote_engine.agricole.garanties import (
            garanties_pompage)
        g = self._g(self.ITEMS_POMPAGE, mode="agricole")
        attendu = garanties_pompage(self.ITEMS_POMPAGE)
        self.assertEqual(len(g), 2)
        self.assertEqual([x["texte"] for x in g],
                         [a["libelle"] for a in attendu])
        noms = " ".join(x["designation"] for x in g)
        self.assertNotIn("Onduleur", noms)
        self.assertNotIn("Installation", noms)
        self.assertEqual((g[0]["designation"], g[0]["duree"]),
                         ("Garantie constructeur de la pompe", "2 ans"))
        self.assertEqual(g[1]["duree"], "18 mois")

    def test_parite_bande_devis_residentiel_et_ci(self):
        data = _fixture(i_sample, i_renderer, self.ITEMS)
        attendu = [(x["duree"], x["designation"]) for x in self._g(self.ITEMS)]
        self.assertEqual(attendu, _residential_cells(data))
        cells = _cells(i_render.build_html(data), "i3")
        self.assertEqual(attendu, [c for c in cells if c[0] != "O&amp;M"])
        com = _fixture(c_sample, c_renderer, self.ITEMS)
        cells = _cells(c_render.build_html(com), "c3")
        self.assertEqual(attendu, [c for c in cells if c[0] != "O&amp;M"])

    def test_parite_bande_devis_agricole(self):
        from apps.ventes.quote_engine.agricole import pages
        from apps.ventes.quote_engine.agricole.garanties import (
            garanties_pompage)
        for lg in ("fr", "ar"):
            with self.subTest(langue=lg):
                html = pages._garanties(
                    {"garanties": garanties_pompage(self.ITEMS_POMPAGE)}, lg)
                bande = re.findall(r'class="ag-li">([^<]+)<', html)
                g = self._g(self.ITEMS_POMPAGE, mode="agricole", langue=lg)
                self.assertEqual([x["texte"] for x in g], bande)

    def test_garanties_de_la_vente_lit_l_option_retenue(self):
        from types import SimpleNamespace

        from apps.ventes.utils.garanties import garanties_de_la_vente
        lignes = [SimpleNamespace(
            designation=it["designation"], prix_unitaire=100, quantite=1,
            remise=0, taux_tva=20, ordre=0, role_devis=None,
            produit=SimpleNamespace(
                nom=it["designation"], marque=it["marque"], description="",
                garantie="", garantie_mois=it.get("garantie_mois"),
                garantie_production_mois=it.get("garantie_production_mois"),
                role_pompage=None, courbe_pompe=None))
            for it in self.ITEMS]
        devis = SimpleNamespace(taux_tva=20, mode_installation="residentiel")
        with mock.patch("apps.ventes.utils.options.option_lines",
                        return_value=lignes):
            g = garanties_de_la_vente(devis)
        self.assertEqual([x["designation"] for x in g],
                         ["Installation", "Onduleur", "Panneaux",
                          "Performance"])
