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
                    "_item_classement", "_item_marque"):
            with self.subTest(nom=nom):
                self.assertIs(getattr(builder, nom),
                              getattr(lignes_classement, nom))
        # C20 FACADE — builder n'expose plus ce qu'il n'utilise pas : les
        # importeurs lisent ces noms dans ``lignes_classement`` directement.
        # SPL163 — ``_cout_onduleur`` n'est plus lu que par la phase D1
        # (``etude_chiffrage``) : builder ne le lie plus.
        for nom in ("_is_inverter", "_is_smart_meter", "_is_wifi_dongle",
                    "_parse_watt", "_parse_kwh", "_cout_onduleur"):
            with self.subTest(absent=nom):
                self.assertFalse(hasattr(builder, nom))


#: SPL163 — phase D1 de build_quote_data (chiffrage de l'étude) et les helpers
#: de niveau module qu'elle est seule à lire : builder.py → etude_chiffrage.py.
NOMS_SPL163 = (
    "_DERIVEES_ETUDE_IC_ANCIENNES", "_etude_rendue", "_etude_ic_fraiche",
    "_etude_horaire_sans_stockage", "CLES_BLOCS_HORAIRES",
    "bloc_horaire_pour_kwc", "_libelle_ville", "_ville_du_devis", "_nombre",
    "chiffrer_etude",
)


def _source_de(nom_fichier, fonction):
    texte = (_MOTEUR / nom_fichier).read_text(encoding="utf-8")
    noeud = next(n for n in _arbre(nom_fichier).body
                 if isinstance(n, ast.FunctionDef) and n.name == fonction)
    return ast.get_source_segment(texte, noeud)


def _tous_imports(arbre):
    """Modules importés n'importe où (imports locaux compris)."""
    mods = []
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.ImportFrom):
            mods.append(("." * noeud.level) + (noeud.module or ""))
            mods.extend(a.name for a in noeud.names if not noeud.module)
        elif isinstance(noeud, ast.Import):
            mods.extend(a.name for a in noeud.names)
    return mods


class Spl163EtudeChiffrageTests(SimpleTestCase):
    def test_noms_definis_dans_etude_chiffrage_et_plus_dans_builder(self):
        ec = _definis(_arbre("etude_chiffrage.py"))
        builder = _definis(_arbre("builder.py"))
        for nom in NOMS_SPL163:
            with self.subTest(nom=nom):
                self.assertIn(nom, ec)
                self.assertNotIn(nom, builder)

    def test_build_quote_data_delegue_la_phase_d1(self):
        corps = _source_de("builder.py", "build_quote_data")
        self.assertNotIn("QX38 — productible CANONIQUE", corps)
        self.assertNotIn("Canonical performance figures", corps)
        self.assertIn("chiffrer_etude(", corps)
        self.assertIn("QX38 — productible CANONIQUE",
                      _source_de("etude_chiffrage.py", "chiffrer_etude"))

    def test_etude_chiffrage_n_importe_jamais_builder(self):
        for mod in _tous_imports(_arbre("etude_chiffrage.py")):
            with self.subTest(mod=mod):
                self.assertNotIn("builder", mod)
                self.assertNotEqual(mod, "apps.ventes.utils.options")

    def test_reexport_pour_les_autres_proprietaires(self):
        """public_views (CLES_BLOCS_HORAIRES), tests devis test_options et
        test_ciq129_cles_v1 lisent toujours le MÊME objet via builder."""
        from apps.ventes.quote_engine import builder, etude_chiffrage
        for nom in ("CLES_BLOCS_HORAIRES", "_etude_horaire_sans_stockage",
                    "_etude_rendue", "_nombre"):
            with self.subTest(nom=nom):
                self.assertIs(getattr(builder, nom),
                              getattr(etude_chiffrage, nom))
        for nom in ("bloc_horaire_pour_kwc", "_libelle_ville",
                    "_ville_du_devis", "_etude_ic_fraiche"):
            with self.subTest(absent=nom):
                self.assertFalse(hasattr(builder, nom))


#: SPL164 — phase E de build_quote_data (trois fonctions) et les helpers de
#: paiement / mentions : builder.py → conditions_commerciales.py.
NOMS_SPL164 = (
    "PAYMENT_TERMS_BY_MODE", "_PasDeLienSigner", "_normalize_site_host",
    "_taux_libelle", "_pct_simple", "repartition_paiement",
    "tranches_echeancier_en_montant", "tva_note_des_lignes",
    "_doc_texts_geles", "_doc_texts_envoyes", "_entreprise_avec_logo",
    "delais_validite_et_kit", "remises_et_puces", "conditions_et_liens",
)


class Spl164ConditionsCommercialesTests(SimpleTestCase):
    def test_noms_definis_dans_conditions_commerciales_et_plus_dans_builder(self):
        cc = _definis(_arbre("conditions_commerciales.py"))
        builder = _definis(_arbre("builder.py"))
        for nom in NOMS_SPL164:
            with self.subTest(nom=nom):
                self.assertIn(nom, cc)
                self.assertNotIn(nom, builder)

    def test_build_quote_data_delegue_la_phase_e(self):
        corps = _source_de("builder.py", "build_quote_data")
        for entete in ("Q5 (décision fondateur du 20/08/2026) — DÉLAIS",
                       "QJRREM — CHAQUE LIGNE PORTE LA REMISE GLOBALE",
                       "QX6 — CTA de signature"):
            with self.subTest(entete=entete):
                self.assertNotIn(entete, corps)
        for fonction in ("delais_validite_et_kit(", "remises_et_puces(",
                         "conditions_et_liens("):
            with self.subTest(fonction=fonction):
                self.assertIn(fonction, corps)
        # Le ShareLink est LU une seule fois, dans E3 (jamais dupliqué).
        e3 = _source_de("conditions_commerciales.py", "conditions_et_liens")
        self.assertEqual(e3.count("ShareLink.objects.filter("), 2)
        self.assertNotIn("ShareLink.objects", corps)

    def test_conditions_commerciales_n_importe_jamais_builder(self):
        for mod in _tous_imports(_arbre("conditions_commerciales.py")):
            with self.subTest(mod=mod):
                self.assertNotIn("builder", mod)
                self.assertNotEqual(mod, "apps.ventes.utils.options")

    def test_reexport_et_usage_propre_de_builder(self):
        """utils/company_settings et les tests devis (PAYMENT_TERMS_BY_MODE,
        tva_note_des_lignes) ; F-post de builder (répartition, tranches)."""
        from apps.ventes.quote_engine import builder, conditions_commerciales
        for nom in ("PAYMENT_TERMS_BY_MODE", "tva_note_des_lignes",
                    "repartition_paiement", "tranches_echeancier_en_montant",
                    "_pct_simple"):
            with self.subTest(nom=nom):
                self.assertIs(getattr(builder, nom),
                              getattr(conditions_commerciales, nom))
        for nom in ("_normalize_site_host", "_taux_libelle", "_doc_texts_geles",
                    "_doc_texts_envoyes", "_entreprise_avec_logo",
                    "_PasDeLienSigner"):
            with self.subTest(absent=nom):
                self.assertFalse(hasattr(builder, nom))


#: SPL165 — liste blanche des options PDF : builder.py → options_pdf.py.
NOMS_SPL165 = ("DEFAULT_PDF_OPTIONS", "LANGUES_SORTIE_PDF", "VARIANTES_PDF",
               "_SHARE_TOKEN_RE", "clean_pdf_options")


class Spl165OptionsPdfTests(SimpleTestCase):
    def test_noms_definis_dans_options_pdf_et_plus_dans_builder(self):
        op = _definis(_arbre("options_pdf.py"))
        builder = _definis(_arbre("builder.py"))
        for nom in NOMS_SPL165:
            with self.subTest(nom=nom):
                self.assertIn(nom, op)
                self.assertNotIn(nom, builder)

    def test_options_pdf_n_importe_que_re(self):
        self.assertEqual(_tous_imports(_arbre("options_pdf.py")),
                         ["__future__", "re"])

    def test_api_publique_et_builder_lisent_le_meme_objet(self):
        """``quote_engine.clean_pdf_options`` (public_views, tasks, vues devis)
        et l'usage propre de builder ; DEFAULT_PDF_OPTIONS ré-exporté pour
        test_pdf (facturation) et les tests devis."""
        from apps.ventes import quote_engine
        from apps.ventes.quote_engine import builder, options_pdf
        self.assertIs(quote_engine.clean_pdf_options,
                      options_pdf.clean_pdf_options)
        for nom in NOMS_SPL165[:3] + ("clean_pdf_options",):
            with self.subTest(nom=nom):
                self.assertIs(getattr(builder, nom), getattr(options_pdf, nom))
        self.assertFalse(hasattr(builder, "_SHARE_TOKEN_RE"))


class Spl166EtudeRestitutionTests(SimpleTestCase):
    """SPL166 — phase D2 (méthode, hypothèses, série mensuelle) et
    ``ligne_tarif_hypothese`` : builder.py → etude_restitution.py."""

    def test_noms_definis_dans_etude_restitution_et_plus_dans_builder(self):
        er = _definis(_arbre("etude_restitution.py"))
        builder = _definis(_arbre("builder.py"))
        for nom in ("restituer_etude", "ligne_tarif_hypothese"):
            with self.subTest(nom=nom):
                self.assertIn(nom, er)
                self.assertNotIn(nom, builder)

    def test_build_quote_data_delegue_la_phase_d2(self):
        corps = _source_de("builder.py", "build_quote_data")
        self.assertNotIn("# ── QF3 — bloc « Comment nous calculons", corps)
        self.assertNotIn("def _fr_int(", corps)
        self.assertIn("restituer_etude(", corps)
        self.assertIn("def _fr_int(",
                      _source_de("etude_restitution.py", "restituer_etude"))

    def test_etude_restitution_n_importe_jamais_builder(self):
        for mod in _tous_imports(_arbre("etude_restitution.py")):
            with self.subTest(mod=mod):
                self.assertNotIn("builder", mod)

    def test_reexport_pour_test_devis(self):
        from apps.ventes.quote_engine import builder, etude_restitution
        self.assertIs(builder.ligne_tarif_hypothese,
                      etude_restitution.ligne_tarif_hypothese)
