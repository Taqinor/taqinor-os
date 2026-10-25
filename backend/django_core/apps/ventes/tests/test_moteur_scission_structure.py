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


#: SPL167 — artefacts de rendu (toiture, schéma unifilaire, planche) et le bloc
#: post-littéral : builder.py → artefacts_rendu.py.
NOMS_SPL167 = (
    "_roof_photo_data_uri", "cle_toit_de_la_societe", "_roof_render_data_uri",
    "_sld_svg", "CALEPINAGE_LARGEUR_PX", "CALEPINAGE_HAUTEUR_PX",
    "_SVG_PROLOGUE_RE", "_SVG_TAILLE_RE", "_svg_planche_inline",
    "_conception_divergente_du_devis", "_planche_calepinage",
    "ajouter_artefacts_rendu",
)


class Spl167ArtefactsRenduTests(SimpleTestCase):
    def test_noms_definis_dans_artefacts_rendu_et_plus_dans_builder(self):
        ar = _definis(_arbre("artefacts_rendu.py"))
        builder = _definis(_arbre("builder.py"))
        for nom in NOMS_SPL167:
            with self.subTest(nom=nom):
                self.assertIn(nom, ar)
                self.assertNotIn(nom, builder)

    def test_build_quote_data_delegue_le_bloc_post_litteral(self):
        corps = _source_de("builder.py", "build_quote_data")
        for entete in ("CALEPDF/A8 — L'AFFICHE DU CALEPINAGE",
                       "CAL182 — LA PLANCHE EST UN ARTEFACT DE RENDU",
                       '"_embed_calepinage_planche"'):
            with self.subTest(entete=entete):
                self.assertNotIn(entete, corps)
        self.assertIn("ajouter_artefacts_rendu(", corps)
        self.assertIn('"_embed_calepinage_planche"',
                      _source_de("artefacts_rendu.py",
                                 "ajouter_artefacts_rendu"))

    def test_artefacts_rendu_n_importe_jamais_builder(self):
        for mod in _tous_imports(_arbre("artefacts_rendu.py")):
            with self.subTest(mod=mod):
                self.assertNotIn("builder", mod)

    def test_lecteur_d_affiche_plus_lie_dans_builder(self):
        """Un ``patch.object(builder, '_roof_render_data_uri')`` périmé doit
        lever, jamais devenir un no-op qui lit MinIO (CODE-FACTS)."""
        from apps.ventes.quote_engine import artefacts_rendu, builder
        self.assertFalse(hasattr(builder, "_roof_render_data_uri"))
        # Le littéral appelle le nom IMPORTÉ : le patch de l'auditeur
        # (coherence/contexte.py) sur builder reste effectif.
        self.assertIs(builder._roof_photo_data_uri,
                      artefacts_rendu._roof_photo_data_uri)
        # Ré-export pour test_pv41 (calepinage) et
        # test_acal_planche_devis_remplace (devis).
        for nom in ("_sld_svg", "_svg_planche_inline"):
            with self.subTest(nom=nom):
                self.assertIs(getattr(builder, nom),
                              getattr(artefacts_rendu, nom))
        for nom in ("cle_toit_de_la_societe", "CALEPINAGE_LARGEUR_PX",
                    "_planche_calepinage", "_conception_divergente_du_devis"):
            with self.subTest(absent=nom):
                self.assertFalse(hasattr(builder, nom))


#: SPL168 — format une-page legacy : generate_devis_premium.py →
#: legacy_onepage.py (liaison tardive ``_g.NOM``).
NOMS_SPL168 = ("_proposition_link", "_onepage_qr_uri", "_onepage_header_html",
               "page_onepage", "build_html_onepage")
#: Restent dans generate_devis_premium (lus ``G.*``, liste ARC11, ``globals()``
#: de ``_renvoi_detail_complet``, ou partagés avec ``build_html``).
RESTENT_DANS_GDP_SPL168 = (
    "ONEPAGE_HEADER_MM", "ONEPAGE_FOOTER_PX", "_mesure_onepage",
    "_render_pdf_weasyprint", "_onepage_html_qui_tient",
    "_renvoi_detail_complet", "_fdec_fr", "_css_arabe",
    "_attributs_langue_html",
)


def _appels_interdits(arbre):
    return [n.func.id for n in ast.walk(arbre) if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id in ("globals", "locals", "vars")]


class Spl168LegacyOnepageTests(SimpleTestCase):
    def test_noms_definis_dans_legacy_onepage_et_plus_dans_gdp(self):
        lo = _definis(_arbre("legacy_onepage.py"))
        gdp = _definis(_arbre("generate_devis_premium.py"))
        for nom in NOMS_SPL168:
            with self.subTest(nom=nom):
                self.assertIn(nom, lo)
                self.assertNotIn(nom, gdp)
        for nom in RESTENT_DANS_GDP_SPL168:
            with self.subTest(reste=nom):
                self.assertIn(nom, gdp)
                self.assertNotIn(nom, lo)

    def test_liaison_tardive_jamais_un_global_fige(self):
        """Seul import de tête : le MODULE ``_g`` ; jamais ``from
        .generate_devis_premium import KWC`` (même local) ; aucun ``globals()``."""
        arbre = _arbre("legacy_onepage.py")
        tete = [n for n in arbre.body
                if isinstance(n, (ast.Import, ast.ImportFrom))]
        self.assertEqual(len(tete), 1)
        self.assertEqual((tete[0].level, tete[0].module), (1, None))
        self.assertEqual([(a.name, a.asname) for a in tete[0].names],
                         [("generate_devis_premium", "_g")])
        figes = [n.lineno for n in ast.walk(arbre)
                 if isinstance(n, ast.ImportFrom)
                 and (n.module or "").endswith("generate_devis_premium")]
        self.assertEqual(figes, [])
        self.assertEqual(_appels_interdits(arbre), [])

    def test_gdp_n_importe_pas_legacy_onepage_en_tete(self):
        for mod in _imports_tete(_arbre("generate_devis_premium.py")):
            with self.subTest(mod=mod):
                self.assertNotIn("legacy_", mod)

    def test_reexport_pep562_pour_les_autres_proprietaires(self):
        from apps.ventes.quote_engine import generate_devis_premium as G
        from apps.ventes.quote_engine import legacy_onepage
        self.assertIs(G.build_html_onepage, legacy_onepage.build_html_onepage)
        for nom in ("page_onepage", "_onepage_header_html"):
            with self.subTest(absent=nom):
                self.assertFalse(hasattr(G, nom))


#: SPL169 — page d'étude legacy et gardes d'optimum : generate_devis_premium.py
#: → legacy_etude.py (groupe clos ; ``_phrase_methode_etude`` et
#: ``_libelle_avec_minuscule``, nés après le plan, ne servent que lui).
NOMS_SPL169 = (
    "make_chart_etude", "_BANKABLE_POSTES_FR", "_bankable_pct",
    "_bankable_decrit_ce_champ", "_bankable_concorde_avec_la_page",
    "_bankable_block_html", "_capacite_batterie_vendue",
    "_capacite_batterie_utile_vendue", "TOLERANCE_CAPACITE_KWH",
    "_branche_nommee", "_branche_phrase", "_phrase_methode_etude",
    "_libelle_avec_minuscule", "_config_identifiante", "_decrit",
    "_optimum_decrit_ce_devis", "_falaise_context", "_part_glitch_pct",
    "page_etude",
)


def _noms_globaux_gdp():
    """Noms de niveau module de gdp — définis ou importés au niveau module
    (blocs if/try/with compris, jamais un corps de fonction), ou déclarés
    ``global`` dans une de ses fonctions (posés par ``apply_quote_data``)."""
    arbre = _arbre("generate_devis_premium.py")
    noms, pile = set(), list(arbre.body)
    while pile:
        noeud = pile.pop()
        if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef,
                              ast.ClassDef)):
            noms.add(noeud.name)
            continue
        if isinstance(noeud, (ast.Import, ast.ImportFrom)):
            noms.update((a.asname or a.name).split(".")[0]
                        for a in noeud.names)
        if isinstance(noeud, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            noms.update(n.id for n in ast.walk(noeud) if isinstance(n, ast.Name)
                        and isinstance(n.ctx, ast.Store))
        for champ in ("body", "orelse", "finalbody", "handlers"):
            pile.extend(getattr(noeud, champ, None) or ())
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Global):
            noms.update(noeud.names)
    return noms


class Spl169LegacyEtudeTests(SimpleTestCase):
    def test_noms_definis_dans_legacy_etude_et_plus_dans_gdp(self):
        le = _definis(_arbre("legacy_etude.py"))
        gdp = _definis(_arbre("generate_devis_premium.py"))
        for nom in NOMS_SPL169:
            with self.subTest(nom=nom):
                self.assertIn(nom, le)
                self.assertNotIn(nom, gdp)

    def test_seule_reecriture_declaree_aucun_globals(self):
        arbre = _arbre("legacy_etude.py")
        self.assertEqual(_appels_interdits(arbre), [])
        texte = (_MOTEUR / "legacy_etude.py").read_text(encoding="utf-8")
        self.assertIn('getattr(_g, "ETUDE", None)', texte)
        tete = [n for n in arbre.body
                if isinstance(n, (ast.Import, ast.ImportFrom))]
        self.assertEqual([(a.name, a.asname) for n in tete for a in n.names],
                         [("generate_devis_premium", "_g")])

    def test_chaque_g_nom_existe_dans_gdp(self):
        """Toute qualification ``_g.NOM`` des modules legacy désigne un nom de
        niveau module de gdp (un nettoyage d'import « inutilisé » de gdp —
        ``garantie_ligne_onepage``… — casserait le rendu)."""
        globaux = _noms_globaux_gdp()
        for fichier in ("legacy_onepage.py", "legacy_etude.py"):
            for noeud in ast.walk(_arbre(fichier)):
                if (isinstance(noeud, ast.Attribute)
                        and isinstance(noeud.value, ast.Name)
                        and noeud.value.id == "_g"):
                    with self.subTest(fichier=fichier, nom=noeud.attr):
                        self.assertIn(noeud.attr, globaux)

    def test_appelants_par_import_local(self):
        self.assertIn("from .legacy_etude import page_etude",
                      _source_de("generate_devis_premium.py", "build_html"))
        self.assertIn("from .legacy_etude import _falaise_context",
                      _source_de("legacy_onepage.py", "page_onepage"))
        self.assertNotIn("_g._falaise_context",
                         _source_de("legacy_onepage.py", "page_onepage"))

    def test_reexport_pep562_pour_les_tests_devis(self):
        from apps.ventes.quote_engine import generate_devis_premium as G
        from apps.ventes.quote_engine import legacy_etude
        for nom in ("TOLERANCE_CAPACITE_KWH", "_bankable_block_html",
                    "_bankable_concorde_avec_la_page",
                    "_bankable_decrit_ce_champ", "_branche_nommee",
                    "_branche_phrase", "_config_identifiante", "_decrit",
                    "_part_glitch_pct", "_phrase_methode_etude",
                    "_falaise_context"):
            with self.subTest(nom=nom):
                self.assertIs(getattr(G, nom), getattr(legacy_etude, nom))
        for nom in ("page_etude", "_optimum_decrit_ce_devis",
                    "make_chart_etude"):
            with self.subTest(absent=nom):
                self.assertFalse(hasattr(G, nom))
