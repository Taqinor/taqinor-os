"""SPL162 — structure de la scission du moteur (créé ici, étendu par chaque SPL).

Complément AST du golden ``test_moteur_golden_build_quote_data`` (la preuve
comportementale) : chaque nom déplacé est DÉFINI dans son nouveau module et
n'est PLUS défini dans ``builder.py`` (une seule définition, aucun jumeau), et
le nouveau module n'importe jamais ``builder`` (casse-cycle de SPL163/SPL164)
ni ``apps.ventes.utils.options`` en tête (``utils/options.py`` importe ces
prédicats au niveau module).

Run (sans base de données) :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_moteur_scission_structure -v 2
"""
import ast
from pathlib import Path

from django.test import SimpleTestCase

_MOTEUR = Path(__file__).resolve().parent.parent / "quote_engine"

#: SPL162 — helpers de CLASSEMENT de ligne : builder.py → lignes_classement.py.
NOMS_SPL162 = (
    "_WATT_RE", "_DEFAULT_WATT", "_BRAND_TOKENS", "_parse_marque",
    "_parse_watt", "_WATT_FICHE_TYPES", "_fiche_watt", "_is_battery",
    "_KWH_RE", "_battery_kwh_from_items", "_cout_onduleur", "_LigneArgentPdf",
    "_is_hybrid_inverter", "_is_reseau_inverter", "_is_offgrid_inverter",
    "_PANEL_MODULE_QUALIFIERS", "_PANEL_BRANDS", "_is_panel", "_is_inverter",
    "_is_smart_meter", "_is_wifi_dongle", "_item_classement", "_item_marque",
    "_line_to_item", "puissance_panneaux_lignes", "panneaux_et_watt_lu",
)
#: Helpers de COMPOSITION qui RESTENT dans builder (cibles de patch des tests
#: calepinage / deux optimiseurs, logger du builder).
RESTENT_DANS_BUILDER = (
    "_variante_de_ligne", "_blob_item", "_repartir_options",
    "_scalaires_par_option",
)


def _arbre(nom):
    return ast.parse((_MOTEUR / nom).read_text(encoding="utf-8"))


def _definis(arbre):
    """Noms DÉFINIS au niveau module (def, class, affectation) — pas les imports."""
    noms = set()
    for noeud in arbre.body:
        if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef,
                              ast.ClassDef)):
            noms.add(noeud.name)
        elif isinstance(noeud, ast.Assign):
            noms.update(c.id for c in noeud.targets if isinstance(c, ast.Name))
        elif isinstance(noeud, ast.AnnAssign) and isinstance(
                noeud.target, ast.Name):
            noms.add(noeud.target.id)
    return noms


def _imports_tete(arbre):
    """Modules importés au NIVEAU MODULE (les imports locaux sont exclus)."""
    mods = []
    for noeud in arbre.body:
        if isinstance(noeud, ast.ImportFrom):
            mods.append(("." * noeud.level) + (noeud.module or ""))
            mods.extend(("." * noeud.level) + a.name for a in noeud.names
                        if not noeud.module)
        elif isinstance(noeud, ast.Import):
            mods.extend(a.name for a in noeud.names)
    return mods


class Spl162LignesClassementTests(SimpleTestCase):
    def test_noms_definis_dans_lignes_classement_et_plus_dans_builder(self):
        lc = _definis(_arbre("lignes_classement.py"))
        builder = _definis(_arbre("builder.py"))
        for nom in NOMS_SPL162:
            with self.subTest(nom=nom):
                self.assertIn(nom, lc)
                self.assertNotIn(nom, builder)

    def test_composition_reste_dans_builder(self):
        builder = _definis(_arbre("builder.py"))
        lc = _definis(_arbre("lignes_classement.py"))
        for nom in RESTENT_DANS_BUILDER:
            with self.subTest(nom=nom):
                self.assertIn(nom, builder)
                self.assertNotIn(nom, lc)

    def test_lignes_classement_n_importe_ni_builder_ni_options_en_tete(self):
        mods = _imports_tete(_arbre("lignes_classement.py"))
        for mod in mods:
            with self.subTest(mod=mod):
                self.assertNotIn("builder", mod)
                self.assertNotEqual(mod, "apps.ventes.utils.options")

    def test_builder_lie_encore_les_noms_de_ses_importeurs(self):
        """Règle de ré-export : un importeur d'un autre propriétaire (ou un test
        dont le nom reste lié) lit toujours le MÊME objet via builder."""
        from apps.ventes.quote_engine import builder, lignes_classement
        for nom in ("_is_battery", "_is_panel", "_parse_marque",
                    "_line_to_item", "panneaux_et_watt_lu",
                    "_item_classement", "_item_marque", "_cout_onduleur"):
            with self.subTest(nom=nom):
                self.assertIs(getattr(builder, nom),
                              getattr(lignes_classement, nom))
        # C20 FACADE — builder n'expose plus ce qu'il n'utilise pas : les
        # importeurs lisent ces noms dans ``lignes_classement`` directement.
        for nom in ("_is_inverter", "_is_smart_meter", "_is_wifi_dongle",
                    "_parse_watt", "_parse_kwh"):
            with self.subTest(absent=nom):
                self.assertFalse(hasattr(builder, nom))
