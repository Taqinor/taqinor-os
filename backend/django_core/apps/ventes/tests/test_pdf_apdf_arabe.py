"""APDF6 (C-APDF-002) — les documents ARABES n'embarquent plus d'@font-face
woff2 « Noto Sans Arabic » vendorisé (homonyme de la police système de
l'image : glyphes superposés mesurés) ; une seule CSS arabe partagée
(``premium_base.css_arabe``) : police système, letter-spacing 0.

Rendu réel des trois moteurs (résidentiel, agricole, une-page / legacy) ;
aucune doublure du moteur.

Test-du-test : réintroduire ``_font_face("Noto Sans Arabic", 400, ...)``
dans ``_css_arabe`` ⇒ ``test_aucun_font_face_homonyme`` échoue.

APDF11 — le devis résidentiel premium arabe est une page RTL
(``ResidentielRtlTests``), toujours 3 pages ; fr et en inchangés.

APDF47 — les woff2 « NotoSansArabic » ont quitté ``assets/fonts/`` : plus
aucun chargeur ne les lit (``test_aucune_police_vendorisee_chargee``).
"""
import ast
import copy
import os
import re
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase, TestCase, tag

from apps.ventes.quote_engine import generate_devis_premium as G
from apps.ventes.quote_engine import premium_base
from apps.ventes.quote_engine.agricole import pages as agr_pages
from apps.ventes.quote_engine.agricole import renderer as agr_renderer
from apps.ventes.quote_engine.residential import theme
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)
from apps.ventes.tests.test_agr310_renderer_agricole import data_complete
from apps.ventes.tests.test_pdf_apdf_identite import MARCHES, rendre_pdf
from apps.ventes.utils import libelles_ar

FONT_FACE_ARABE = re.compile(
    r"@font-face\s*\{[^}]*Noto Sans Arabic", re.IGNORECASE)


def _data_agricole_ar():
    from apps.ventes.quote_engine import i18n_labels
    d = data_complete()
    d['langue_sortie'] = 'ar'
    d['libelles_document'] = i18n_labels.libelles('ar')
    return agr_renderer._augment(d)


# ── APDF47 — plus aucun woff2 arabe vendorisé ni chargeur ─────────────────
# Test-du-test : restaurer ``_load_gfont("NotoSansArabic-400.woff2")`` (dans
# ``_css_arabe`` ou au chargement du module) ⇒
# ``test_aucune_police_vendorisee_chargee`` échoue (lecture enregistrée par
# l'espion, ou nom de fichier cité hors commentaire).
_WOFF2_ARABE = 'NotoSansArabic'
_RACINE_DJANGO = Path(G.__file__).resolve().parents[3]


def _ids_docstrings(arbre):
    ids = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, (ast.Module, ast.ClassDef, ast.FunctionDef,
                              ast.AsyncFunctionDef)) and noeud.body:
            tete = noeud.body[0]
            if (isinstance(tete, ast.Expr) and isinstance(tete.value, ast.Constant)
                    and isinstance(tete.value.value, str)):
                ids.add(id(tete.value))
    return ids


def _citations_woff2_arabe():
    """``chemin:ligne`` de chaque littéral (hors commentaire / docstring) qui
    nomme un woff2 arabe dans le code servi : ``apps/`` et ``templates/`` du
    backend, hors tests et migrations (le grep de la tâche, sans ses
    commentaires)."""
    trouves = []
    for base in ('apps', 'templates'):
        for dossier, sous, fichiers in os.walk(_RACINE_DJANGO / base):
            sous[:] = [d for d in sous
                       if d not in ('__pycache__', 'migrations', 'tests')]
            for nom in fichiers:
                if nom.startswith('test') or not nom.endswith(('.py', '.html')):
                    continue
                chemin = Path(dossier) / nom
                texte = chemin.read_bytes().decode('utf-8', 'replace')
                if _WOFF2_ARABE not in texte:
                    continue
                rel = chemin.relative_to(_RACINE_DJANGO).as_posix()
                if nom.endswith('.html'):
                    sans = re.sub(
                        r'<!--.*?-->|\{#.*?#\}'
                        r'|\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}',
                        '', texte, flags=re.S)
                    if _WOFF2_ARABE in sans:
                        trouves.append(rel)
                    continue
                arbre = ast.parse(texte)
                docs = _ids_docstrings(arbre)
                trouves += [
                    f'{rel}:{n.lineno}' for n in ast.walk(arbre)
                    if isinstance(n, ast.Constant) and isinstance(n.value, str)
                    and _WOFF2_ARABE in n.value and id(n) not in docs]
    return trouves


class PoliceArabeTests(SimpleTestCase):

    def test_une_seule_css_partagee(self):
        css = premium_base.css_arabe(libelles=True, document=True)
        self.assertNotIn('@font-face', css)
        self.assertIn('letter-spacing:0', css)
        self.assertEqual(theme.css_langue({'langue_sortie': 'ar'}),
                         premium_base.css_arabe(libelles=True))
        self.assertEqual(G._css_arabe(),
                         premium_base.css_arabe(libelles=True, document=True))

    def test_aucun_font_face_homonyme(self):
        self.assertIsNone(FONT_FACE_ARABE.search(G._css_arabe()))
        self.assertIsNone(FONT_FACE_ARABE.search(
            theme.css_langue({'langue_sortie': 'ar'})))
        html = agr_pages.build_html(_data_agricole_ar())
        self.assertIsNone(FONT_FACE_ARABE.search(html))
        self.assertIn('letter-spacing:0', html)

    def test_aucune_police_vendorisee_chargee(self):
        # Les woff2 arabes ont quitté le dossier que lisent les trois chargeurs.
        for dossier in {G.FONT_DIR, theme._FONT_DIR, libelles_ar._FONT_DIR}:
            self.assertEqual(
                sorted(p.name for p in dossier.glob(f'{_WOFF2_ARABE}*')), [])
        # Aucun rendu arabe ne demande un woff2 arabe à un chargeur.
        lus = []

        def espion(chargeur):
            def lire(nom, *args, **kwargs):
                lus.append(nom)
                return chargeur(nom, *args, **kwargs)
            return lire

        theme.font_face_css.cache_clear()
        with mock.patch.object(G, '_load_gfont', espion(G._load_gfont)), \
                mock.patch.object(theme, '_font_b64', espion(theme._font_b64)), \
                mock.patch.object(libelles_ar, '_load_font_base64',
                                  espion(libelles_ar._load_font_base64)):
            G._css_arabe()
            theme.css_langue({'langue_sortie': 'ar'})
            agr_pages.build_html(_data_agricole_ar())
            _html_residentiel('ar')
            libelles_ar.arabic_font_face_css()
        self.assertTrue(lus, 'espion non branché : aucune police lue')
        self.assertEqual([n for n in lus if _WOFF2_ARABE in str(n)], [])
        # Plus aucun nom de woff2 arabe cité hors commentaire (grep de la tâche).
        self.assertEqual(_citations_woff2_arabe(), [])


class OnePageArabeTests(TestCase):
    def setUp(self):
        self.company = make_company(slug='apdf6-co', nom='APDF6')
        self.user = make_user(self.company)
        self.devis = make_devis(
            self.company, self.user, make_client(self.company), [
                ('Panneau mono 550W', '12', '1100'),
                ('Onduleur réseau 5kW', '1', '11700'),
            ], reference='DEV-APDF6-1')

    def _html(self):
        from apps.ventes.quote_engine.builder import (
            build_quote_data, clean_pdf_options)
        data = build_quote_data(self.devis, clean_pdf_options(
            {'pdf_mode': 'onepage', 'langue_sortie': 'ar'}))
        capture = {}
        orig = G._render_pdf_weasyprint
        G._render_pdf_weasyprint = lambda html, out: capture.update(html=html)
        try:
            G.generate_premium_pdf(data, '/tmp/_apdf6_test.pdf')
        finally:
            G._render_pdf_weasyprint = orig
        return capture.get('html', '')

    def test_onepage_ar_sans_font_face_homonyme(self):
        html = self._html()
        self.assertTrue(html)
        self.assertIsNone(FONT_FACE_ARABE.search(html))
        self.assertIn('DEV-APDF6-1', html)

    @tag('pdf')
    def test_onepage_ar_chiffres_lisibles(self):
        """Texte extrait du PDF réel : la référence se relit (la superposition
        de glyphes la rendait illisible à l'extraction comme à l'œil)."""
        try:
            import fitz
        except ImportError:  # pragma: no cover
            self.skipTest('PyMuPDF absent')
        from weasyprint import HTML
        pdf = HTML(string=self._html()).write_pdf()
        doc = fitz.open(stream=pdf, filetype='pdf')
        try:
            texte = '\n'.join(p.get_text() for p in doc)
        finally:
            doc.close()
        self.assertIn('DEV-APDF6-1', texte)


# ── APDF11 — devis résidentiel premium arabe en page RTL ───────────────────
# Test-du-test : retirer ``dir="rtl"`` de ``residential/render.py`` ⇒
# ``test_ar_dir_rtl`` échoue.

def _donnees_residentiel(langue):
    from apps.ventes.quote_engine import i18n_labels
    from apps.ventes.quote_engine.residential import sample_data
    d = dict(sample_data.build("deux"))
    if langue != "fr":
        d["langue_sortie"] = langue
        d["libelles_document"] = i18n_labels.libelles(langue)
    return d


def _html_residentiel(langue):
    from apps.ventes.quote_engine.residential import render, renderer
    return render.build_html(renderer._augment(_donnees_residentiel(langue)))


class ResidentielRtlTests(SimpleTestCase):

    def test_ar_dir_rtl(self):
        html = _html_residentiel("ar")
        racine = re.search(r"<html[^>]*>", html).group(0)
        self.assertIn('dir="rtl"', racine)
        self.assertIn('lang="ar"', racine)

    def test_fr_ltr_inchange(self):
        self.assertIn("<!doctype html><html><head>", _html_residentiel("fr"))
        racine_en = re.search(r"<html[^>]*>", _html_residentiel("en")).group(0)
        self.assertEqual(racine_en, '<html lang="en">')

    @tag('pdf')
    def test_ar_trois_pages(self):
        try:
            import fitz
            from apps.ventes.quote_engine.residential import renderer
            renderer._PDF_CACHE.clear()
            pdf = renderer.render_pdf_bytes(_donnees_residentiel("ar"))
        except (ImportError, OSError):  # pragma: no cover — hôte sans libs
            self.skipTest('WeasyPrint / PyMuPDF indisponible')
        doc = fitz.open(stream=pdf, filetype='pdf')
        try:
            self.assertEqual(len(doc), 3)
            # Page 2 : le titre traduit est calé à DROITE (page RTL).
            titre = 'تفاصيل مشروعكم'
            zones = doc[1].search_for(titre)
            if zones:
                self.assertGreater(zones[0].x1, doc[1].rect.width * 0.6)
        finally:
            doc.close()


# APDF46 (C-APDF-004, C-APDF-002) — garde de la classe « libellé de gabarit
# resté en français / glyphe illisible ».
#
# Un devis par marché (résidentiel, commercial, industriel, agricole) est RENDU
# pour de vrai dans chaque format (défaut, une-page, include_etude,
# devis_final) en anglais puis en arabe (``generate_premium_devis_pdf`` :
# registre des renderers et repli legacy, MinIO en mémoire —
# ``test_pdf_apdf_identite.rendre_pdf``), puis lu par PyMuPDF : aucun libellé de
# la liste ``LIBELLES_GABARIT_FR`` (données saisies exclues : les désignations
# et le client du devis d'essai n'en contiennent aucun), aucun caractère
# U+1F000+ (pictogramme sans police), et en arabe aucun ``@font-face``
# « Noto Sans Arabic » vendorisé dans le HTML remis à WeasyPrint (APDF6).
# Couvre APDF6, APDF8 à APDF11 et APDF15.
#
# Test-du-test : remettre un seul libellé français en dur (ex. « Prochaines
# étapes » dans ``residential/trust.py``) ⇒ le cas correspondant échoue.

#: LA liste des libellés de gabarit français (une constante) : les 19 de la
#: sonde PDEV-2 (résidentiel APDF8 + une-page APDF9) et trois puces / titres
#: (APDF9, APDF10). Écrits TELS QU'IMPRIMÉS (les titres mis en capitales par
#: CSS le sont aussi à l'extraction) et comparés à la casse près : la phrase
#: de méthode « … production annuelle × part autoconsommée … » (donnée du
#: builder) n'est pas le libellé « PRODUCTION ANNUELLE » du une-page.
LIBELLES_GABARIT_FR = (
    # APDF8 — devis résidentiel premium.
    "Valable jusqu", "Votre installation solaire",
    "Consultez votre proposition interactive", "Bonjour", "kWc installés",
    "Le détail de votre projet", "VOTRE ÉQUIPEMENT", "Pourquoi",
    "NOS GARANTIES", "Prochaines étapes", "Validité de l",
    "Bon pour accord", "La preuve, en ligne",
    # APDF9 — une-page legacy.
    "Consultez votre", "DEVIS N°", "PUISSANCE CRÊTE", "PRODUCTION ANNUELLE",
    "ÉCONOMIE ANNUELLE", "PRIX PAR KWC", "Validité : jusqu", "Siège : ",
    # APDF9 / APDF10 — titre des clauses et puces CGV par défaut.
    "Acompte à la commande", "Tarifs de référence",
    "CLAUSES PARTICULIÈRES",
)

FORMATS = {
    'defaut': {},
    'onepage': {'pdf_mode': 'onepage'},
    'include_etude': {'include_etude': True},
    'devis_final': {'devis_final': True},
}


def rendu_et_html(devis, options):
    """(octets du PDF, HTML remis à WeasyPrint) — ``weasyprint.HTML`` est
    ESPIONNÉ (le vrai rendu a lieu), jamais remplacé."""
    import weasyprint
    vrai, recus = weasyprint.HTML, []

    def espion(*args, **kwargs):
        recus.append(kwargs.get('string') or (args[0] if args else ''))
        return vrai(*args, **kwargs)

    with mock.patch('weasyprint.HTML', espion):
        pdf = rendre_pdf(devis, options)
    return pdf, '\n'.join(str(h) for h in recus)


def texte_pdf_normalise(octets):
    import fitz
    doc = fitz.open(stream=octets, filetype='pdf')
    try:
        texte = '\n'.join(page.get_text() for page in doc)
    finally:
        doc.close()
    return texte.replace('\xa0', ' ').replace(' ', ' ')


@tag('pdf')
class GardeLanguesTests(TestCase):

    def setUp(self):
        self.company = make_company(slug='apdf46-co', nom='APDF46')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _devis(self, marche):
        lignes, etude, mode = MARCHES[marche]
        devis = make_devis(self.company, self.user, self.client_obj, lignes,
                           reference=f'DEV-APDF46-{marche[:4].upper()}',
                           etude_params=dict(etude) if etude else None)
        devis.mode_installation = mode
        devis.save(update_fields=['mode_installation'])
        return devis

    def test_aucun_libelle_fr_ni_glyphe_marche_format_langue(self):
        rendus = []
        for marche in MARCHES:
            devis = self._devis(marche)
            for nom, options in FORMATS.items():
                for langue in ('en', 'ar'):
                    with self.subTest(marche=marche, format=nom,
                                      langue=langue):
                        pdf, html = rendu_et_html(
                            devis, dict(options, langue_sortie=langue))
                        texte = texte_pdf_normalise(pdf)
                        rendus.append((marche, nom, langue))
                        self.assertEqual(
                            [lib for lib in LIBELLES_GABARIT_FR
                             if lib in texte], [])
                        self.assertEqual(
                            [hex(ord(c)) for c in set(texte)
                             if ord(c) >= 0x1F000], [])
                        if langue == 'ar':
                            self.assertIsNone(FONT_FACE_ARABE.search(html))
        self.assertEqual(len(rendus), len(MARCHES) * len(FORMATS) * 2,
                         rendus)


# APDF8-APDF10 (C-APDF-004) — les libellés FIXES des gabarits suivent la langue
# du document ; le français reste octet pour octet celui d'hier.
#
# APDF8 — devis résidentiel premium (couverture, détail, page de confiance) :
# chaque libellé passe par ``i18n_labels`` (clés ``res_*``) via
# ``residential.cover.libelle_fixe``. Rendu réel : PDF servi par /proposal
# (``test_pdf_apdf_identite.rendre_pdf``, MinIO en mémoire) lu par PyMuPDF, et
# HTML du gabarit sur les données d'échantillon (sans base).
# Test-du-test : remettre « Votre installation solaire » en dur dans
# ``residential/cover.py`` ⇒ ``test_en_et_ar_aucun_libelle_fr`` (variante sans
# économies) échoue.

#: APDF8 — libellés de gabarit français du devis résidentiel (sondes PDEV-2 /
#: PLANG-3). Comparaison sans casse : deux titres sont mis en capitales par CSS.
LIBELLES_RESIDENTIEL = (
    "Valable jusqu", "Votre installation solaire",
    "Consultez votre proposition interactive", "Bonjour", "kWc installés",
    "Le détail de votre projet", "VOTRE ÉQUIPEMENT", "Pourquoi",
    "NOS GARANTIES", "Prochaines étapes", "Validité de l",
    "Bon pour accord", "La preuve, en ligne",
)


def texte_html(html):
    """Texte visible d'un HTML de gabarit (styles et balises retirés)."""
    import html as H
    import re
    s = re.sub(r"<style.*?</style>", " ", html, flags=re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", H.unescape(s))


def trouves(texte, libelles):
    bas = texte.lower()
    return [lib for lib in libelles if lib.lower() in bas]


def html_residentiel(langue, **surcharges):
    """HTML du gabarit résidentiel premium (données d'échantillon)."""
    from apps.ventes.quote_engine import i18n_labels
    from apps.ventes.quote_engine.residential import render, renderer
    from apps.ventes.quote_engine.residential import sample_data
    d = copy.deepcopy(dict(sample_data.build("deux")))
    d.update(copy.deepcopy(surcharges))
    if langue != "fr":
        d["langue_sortie"] = langue
        d["libelles_document"] = i18n_labels.libelles(langue)
    return render.build_html(renderer._augment(d))


#: Branches du gabarit dont les libellés diffèrent (économies masquées,
#: option unique, recommandation hybride, devis final).
VARIANTES = {
    "base": {},
    "sans_economies": {"masquer_economies": True},
    "option_unique": {"deux_options": False, "avec_ok": True},
    "hybride": {"pourquoi_avec": (
        "Pourquoi nous la recommandons : l'onduleur hybride est prêt pour "
        "la batterie — vous l'ajoutez quand vous voulez, sans changer "
        "d'onduleur."), "libelle_avec": "Hybride, batterie plus tard"},
    "devis_final": {"devis_final": True},
}


class ResidentielLibellesHtmlTests(SimpleTestCase):
    """APDF8 — HTML du gabarit (sans base ni WeasyPrint)."""

    def test_en_et_ar_aucun_libelle_fr(self):
        for langue in ("en", "ar"):
            for nom, surcharges in VARIANTES.items():
                with self.subTest(langue=langue, variante=nom):
                    texte = texte_html(html_residentiel(langue, **surcharges))
                    self.assertEqual(
                        trouves(texte, LIBELLES_RESIDENTIEL), [])

    def test_fr_porte_ses_libelles(self):
        texte = texte_html(html_residentiel("fr"))
        absents = [lib for lib in LIBELLES_RESIDENTIEL
                   if lib not in ("Votre installation solaire",
                                  "VOTRE ÉQUIPEMENT")
                   and lib.lower() not in texte.lower()]
        self.assertEqual(absents, [])
        texte = texte_html(html_residentiel("fr", masquer_economies=True))
        self.assertIn("Votre installation solaire", texte)
        texte = texte_html(html_residentiel(
            "fr", deux_options=False, avec_ok=True))
        self.assertIn("Votre équipement", texte)

    def test_chaque_cle_res_porte_trois_langues_et_ses_gabarits(self):
        import re
        from apps.ventes.quote_engine import i18n_labels as L
        for cle, trad in L.LIBELLES.items():
            if not cle.startswith("res_"):
                continue
            with self.subTest(cle=cle):
                for langue in ("fr", "en", "ar"):
                    self.assertTrue(trad[langue].strip())
                    self.assertEqual(
                        sorted(re.findall(r"\{\w+\}", trad[langue])),
                        sorted(re.findall(r"\{\w+\}", trad["fr"])))

    def test_graphe_mensuel_nomme_les_deux_factures(self):
        """AGNR6 (D-AGNR-1 option (a)) — là où le gabarit rend
        ``factures_mensuelles_estimation`` (note du graphe mensuel), la source
        ``facture_hiver_ete`` imprime le libellé client du catalogue ; la
        facture d'hiver seule garde « variation mensuelle estimée »."""
        from apps.ventes.quote_engine import i18n_labels as L
        from apps.ventes.quote_engine.residential import (
            charts, renderer, sample_data)
        fr = "Estimation — deux factures (hiver/été)"
        self.assertEqual(L.libelle("res_estimation_deux_factures", "fr"), fr)
        deux = {"factures_mensuelles_estimation": True,
                "source_consommation": "facture_hiver_ete"}
        self.assertEqual(charts.note_variation_mensuelle(deux), fr)
        en = dict(deux, langue_sortie="en", libelles_document=L.libelles("en"))
        self.assertEqual(charts.note_variation_mensuelle(en),
                         L.libelle("res_estimation_deux_factures", "en"))
        # Image matplotlib : l'arabe garde le français du graphe.
        self.assertEqual(charts.note_variation_mensuelle(
            dict(deux, langue_sortie="ar")), fr)
        self.assertEqual(charts.note_variation_mensuelle(
            dict(deux, source_consommation="facture_hiver")),
            "variation mensuelle estimée")
        self.assertIsNone(charts.note_variation_mensuelle(
            dict(deux, factures_mensuelles_estimation=False)))
        # Câblage : la note atteint le graphe que la couverture imprime.
        d = renderer._augment(dict(copy.deepcopy(sample_data.build("deux")),
                                   **deux))
        with mock.patch.object(charts, "bill_before_after",
                               return_value="") as graphe:
            charts.build_all(d)
        self.assertEqual(graphe.call_args.kwargs["variation_estimee"], fr)


@tag("pdf")
class ResidentielLibellesTests(TestCase):
    """APDF8 — PDF RÉEL du devis résidentiel en en / ar / fr."""

    def setUp(self):
        from apps.ventes.tests.test_pdf_apdf_identite import (
            devis_residentiel)
        from apps.ventes.tests._quote_engine_common import make_company
        self.company = make_company(slug="apdf8-co", nom="APDF8")
        self.devis = devis_residentiel(self.company, "DEV-APDF8-1")

    def _texte(self, langue):
        from apps.ventes.tests.test_pdf_apdf_identite import (
            rendre_pdf, texte_pdf)
        return texte_pdf(rendre_pdf(self.devis, {"langue_sortie": langue}))

    def test_en_aucun_libelle_fr(self):
        texte = self._texte("en")
        self.assertEqual(trouves(texte, LIBELLES_RESIDENTIEL), [])
        # Les données saisies restent telles quelles.
        self.assertIn("Panneau Canadien Solar 710W", texte)

    def test_ar_aucun_libelle_fr(self):
        texte = self._texte("ar")
        self.assertEqual(trouves(texte, LIBELLES_RESIDENTIEL), [])

    def test_fr_texte_inchange(self):
        texte = self._texte("fr")
        for libelle in ("Le détail de votre projet", "Prochaines étapes",
                        "Bon pour accord", "Bonjour"):
            self.assertIn(libelle, texte)
        self.assertEqual(texte, self._texte("fr"))


# ── APDF9 — une-page legacy + titre des clauses particulières ──────────────

#: APDF9 — libellés de gabarit français du UNE PAGE (sonde PLANG-3).
LIBELLES_UNE_PAGE = (
    "Consultez votre", "DEVIS N°", "PUISSANCE CRÊTE", "PRODUCTION ANNUELLE",
    "ÉCONOMIE ANNUELLE", "PRIX PAR KWC", "Validité : jusqu", "Siège : ",
    "Clauses particulières",
)


def texte_normalise(texte):
    """Espaces insécables ramenés à l'espace (le gabarit en pose avant « : »)."""
    return texte.replace("\xa0", " ").replace(" ", " ")


def html_une_page(langue, **surcharges):
    """HTML EXACT du une-page legacy (données d'échantillon, sans base)."""
    from apps.ventes.quote_engine import generate_devis_premium as G
    from apps.ventes.quote_engine import i18n_labels
    from apps.ventes.tests import _moteur_fixtures as mf
    surcharges = dict(surcharges, pdf_mode="onepage")
    if langue != "fr":
        surcharges["langue_sortie"] = langue
        surcharges["libelles_document"] = i18n_labels.libelles(langue)
    return G.render_html_for(mf.donnees_legacy("deux", **surcharges))


class UnePageLibellesHtmlTests(SimpleTestCase):
    """APDF9 — HTML du une-page (profil, adresse, clause gelée)."""

    SURCHARGES = {
        "entreprise": {"nom": "SOLAIRE EXEMPLE SARL", "adresse": "1 rue A",
                       "ice": "001111111000011"},
        "clauses_cgv": [{"nom": "Clause A", "corps_texte": "Texte A."}],
    }

    def test_en_et_ar_aucun_libelle_fr(self):
        for langue in ("en", "ar"):
            with self.subTest(langue=langue):
                texte = texte_normalise(texte_html(
                    html_une_page(langue, **self.SURCHARGES)))
                self.assertEqual(trouves(texte, LIBELLES_UNE_PAGE), [])
                # Les données saisies restent telles quelles.
                self.assertIn("Clause A", texte)
                self.assertIn("1 rue A", texte)

    def test_fr_inchange(self):
        texte = texte_normalise(texte_html(
            html_une_page("fr", **self.SURCHARGES)))
        for libelle in ("Consultez votre", "DEVIS N°", "Siège : ",
                        "Clauses particulières"):
            self.assertIn(libelle.lower(), texte.lower())

    def test_titre_clauses_par_langue(self):
        from apps.ventes.quote_engine import clauses_cgv
        clause = [{"nom": "A", "corps_texte": "B"}]
        self.assertIn(clauses_cgv.TITRE, clauses_cgv.bloc_clauses_html(clause))
        self.assertEqual(clauses_cgv.TITRE, "Clauses particulières")
        self.assertIn("Special terms",
                      clauses_cgv.bloc_clauses_html(clause, langue="en"))


@tag("pdf")
class UnePageLibellesTests(TestCase):
    """APDF9 — une-page RÉEL (résidentiel et agricole) en en / ar / fr."""

    def setUp(self):
        from apps.ventes.tests.test_pdf_apdf_identite import MARCHES
        from apps.ventes.tests.test_pdf_apdf_identite import (
            devis_residentiel, profil)
        from apps.ventes.tests._quote_engine_common import (
            make_client, make_company, make_devis, make_user)
        self.company = make_company(slug="apdf9-co", nom="APDF9")
        profil(self.company, nom="SOLAIRE EXEMPLE SARL", adresse="1 rue A",
               ice="001111111000011")
        lignes, etude, mode = MARCHES["agricole"]
        # UN utilisateur et UN client pour les deux devis (username et
        # (société, e-mail) sont uniques).
        user, client = make_user(self.company), make_client(self.company)
        agricole = make_devis(self.company, user, client, lignes,
                              reference="DEV-APDF9-AGRI",
                              etude_params=dict(etude))
        agricole.mode_installation = mode
        agricole.save(update_fields=["mode_installation"])
        self.devis = [devis_residentiel(self.company, "DEV-APDF9-RES",
                                        user=user, client=client),
                      agricole]

    def _rendu(self, devis, langue):
        import fitz
        from apps.ventes.tests.test_pdf_apdf_identite import rendre_pdf
        pdf = rendre_pdf(devis, {"pdf_mode": "onepage",
                                 "langue_sortie": langue})
        doc = fitz.open(stream=pdf, filetype="pdf")
        try:
            return (texte_normalise("\n".join(p.get_text() for p in doc)),
                    len(doc))
        finally:
            doc.close()

    def test_onepage_en(self):
        for devis in self.devis:
            with self.subTest(devis=devis.reference):
                texte, _pages = self._rendu(devis, "en")
                self.assertEqual(trouves(texte, LIBELLES_UNE_PAGE), [])

    def test_onepage_ar(self):
        for devis in self.devis:
            with self.subTest(devis=devis.reference):
                texte, _pages = self._rendu(devis, "ar")
                self.assertEqual(trouves(texte, LIBELLES_UNE_PAGE), [])

    def test_onepage_fr_inchange_une_page(self):
        for devis in self.devis:
            with self.subTest(devis=devis.reference):
                texte, pages = self._rendu(devis, "fr")
                self.assertEqual(pages, 1)
                self.assertIn("DEVIS", texte)
                for langue in ("en", "ar"):
                    self.assertEqual(self._rendu(devis, langue)[1], 1)


# ── APDF10 — puces CGV par défaut + note de TVA dans la langue du document ─

#: APDF10 — morceaux français des puces CGV par défaut et de la note de TVA.
PUCES_FR = ("Acompte à la commande", "à la réception du matériel",
            "après la mise en marche", "TVA : 10% panneaux",
            "Tarifs de référence")
TERMES = {"acompte": 40, "materiel": 50, "solde": 10}


def _pourcentages(puces):
    import re
    return sorted(re.findall(r"(\d+)&#37;", " ".join(puces)))


class PucesCgvLangueHtmlTests(SimpleTestCase):
    """APDF10 — ``cgv_bullets_remplies`` (PDF C&I + page publique), pur."""

    def _puces(self, langue, **data):
        from apps.ventes.quote_engine.builder import tva_note_des_lignes
        from apps.ventes.quote_engine.clauses_cgv import (
            cgv_bullets_remplies)

        class _Ligne:
            def __init__(self, taux, designation):
                self.taux_tva, self.designation = taux, designation
                self.produit = None

        note = tva_note_des_lignes(
            [_Ligne(10, "Panneau Jinko 710W"), _Ligne(20, "Onduleur 10kW")],
            20, langue=langue)
        return cgv_bullets_remplies(dict(
            {"langue_sortie": langue, "payment_terms": TERMES,
             "tva_note": note, "valid_until": "01/02/2027"}, **data))

    def test_en_et_ar_puces_traduites_memes_pourcentages(self):
        fr = self._puces("fr")
        for langue in ("en", "ar"):
            with self.subTest(langue=langue):
                puces = self._puces(langue)
                self.assertEqual(trouves(" ".join(puces), PUCES_FR), [])
                self.assertEqual(_pourcentages(puces), _pourcentages(fr))
                self.assertEqual(len(puces), len(fr))

    def test_fr_inchange(self):
        from apps.ventes.quote_engine.clauses_cgv import remplir_cgv_bullets
        from apps.ventes.quote_engine.generate_devis_premium import (
            DEFAULT_DOC_TEXTS)
        attendu = remplir_cgv_bullets(
            DEFAULT_DOC_TEXTS["cgv_bullets"], acompte=40, materiel=50,
            solde=10, tva_note=("TVA : 10% panneaux photovoltaïques · 20% "
                                "autres équipements et prestations"),
            valid_until="01/02/2027")
        self.assertEqual(self._puces("fr"), attendu)

    def test_surcharge_societe_conservee(self):
        perso = ["Clause société {acompte}&#37; non traduite"]
        for langue in ("fr", "en", "ar"):
            with self.subTest(langue=langue):
                self.assertEqual(
                    self._puces(langue, doc_texts={"cgv_bullets": perso}),
                    ["Clause société 40&#37; non traduite"])

    def test_suite_des_cgv_bornees_en_et_ar(self):
        """Puces trop longues (page 3 résidentielle, APDF13) ou tronquées par
        le contrat de pages C&I (``_cgv_max``) : la ligne « suite »
        (``ci_cgv_suite``) existe en en / ar — plus de KeyError au rendu."""
        from apps.ventes.quote_engine import i18n_labels as L
        from apps.ventes.quote_engine.ci import blocs
        from apps.ventes.quote_engine.residential import trust
        longues = [f"Clause {n} : " + "texte contractuel long " * 6
                   for n in range(1, 9)]
        for langue in ("en", "ar"):
            with self.subTest(langue=langue):
                attendu = L.libelle("ci_cgv_suite", langue)
                d = {"langue_sortie": langue}
                self.assertIn(attendu,
                              trust.puces_cgv_bornees(d, longues)[-1])
                d.update(doc_texts={"cgv_bullets": longues}, _cgv_max=2)
                self.assertIn(attendu, blocs.puces_conditions(d)[-1])
        self.assertEqual(L.libelle("ci_cgv_suite", "fr"),
                         "Suite des conditions : proposition en ligne")


@tag("pdf")
class PucesCgvLangueTests(TestCase):
    """APDF10 — conditions du PDF C&I RÉEL en en / ar (sans CGV société)."""

    def setUp(self):
        from apps.ventes.tests.test_pdf_apdf_identite import MARCHES
        from apps.ventes.tests._quote_engine_common import (
            make_client, make_company, make_devis, make_user)
        self.company = make_company(slug="apdf10-co", nom="APDF10")
        user, client = make_user(self.company), make_client(self.company)
        self.devis = []
        for mode in ("commercial", "industriel"):
            lignes, _etude, _mode = MARCHES[mode]
            devis = make_devis(self.company, user, client, lignes,
                               reference=f"DEV-APDF10-{mode[:3].upper()}")
            devis.mode_installation = mode
            devis.save(update_fields=["mode_installation"])
            self.devis.append(devis)

    def _texte(self, devis, langue):
        from apps.ventes.tests.test_pdf_apdf_identite import (
            rendre_pdf, texte_pdf)
        return texte_normalise(texte_pdf(rendre_pdf(
            devis, {"langue_sortie": langue})))

    def test_ci_en_puces_traduites(self):
        for devis in self.devis:
            with self.subTest(devis=devis.reference):
                self.assertEqual(
                    trouves(self._texte(devis, "en"), PUCES_FR), [])

    def test_ci_ar_puces_traduites(self):
        for devis in self.devis:
            with self.subTest(devis=devis.reference):
                self.assertEqual(
                    trouves(self._texte(devis, "ar"), PUCES_FR), [])

    def test_surcharge_societe_conservee(self):
        from apps.parametres.models_documents import DocumentTemplates
        modele = DocumentTemplates.get(company=self.company)
        modele.cgv_bullets = ["CLAUSE-SOCIETE-APDF10 conservée"]
        modele.save()
        for langue in ("fr", "en", "ar"):
            with self.subTest(langue=langue):
                self.assertIn("CLAUSE-SOCIETE-APDF10 conservée",
                              self._texte(self.devis[0], langue))
