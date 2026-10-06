"""QJR428 (S5-3) — LA PREUVE D'ABORD : le one-page agricole rend-il, oui ou
non, un comparatif solaire-vs-carburant ?

`frontend/src/pages/ventes/generator/PanneauAgricole.jsx:125-127` promettait
au vendeur que les données « exploitation » du fermier permettent au PDF de
« dimensionner et chiffrer sur les données réelles du fermier (besoin en eau
FAO-56, économies vs carburant) ». La ronde 4 avait classé ce constat en
pensant que QJR236 avait supprimé le seul moteur produisant ce chiffre — FAUX
côté DONNÉE : `current_fuel`/`fuel_spend_current` (`domain/etude_schema.py`
`:198-200`) restent des entrées écran valides, et l'option PDF `current_fuel`
(`quote_engine/builder.py` `:676`, appliquée `:1690-1691`) existe toujours.
Ce que QJR236 a supprimé, c'est le RENDERER agricole premium multi-pages
(confirmé par `TestQjr32DispatchModeNormalise` et
`TestQjr307PreuveOctetsOnepageAgricole` dans `test_quote_engine_formats.py` :
« aucune entrée du registre ne sert le marché agricole » — le one-page
générique sert seul ce marché désormais).

Ce module PROUVE ce que devient `current_fuel` une fois dans le one-page :
un grep exhaustif de `quote_engine/generate_devis_premium.py` (le SEUL
fichier qui rend un PDF) ne contient AUCUNE occurrence de « carburant »,
« fuel », « butane » ou « diesel » — la donnée est bien threadée jusque dans
le dict `etude` (`build_quote_data`), mais rien en aval ne la LIT pour
produire un chiffre. Le test ci-dessous le CONFIRME par exécution (rendu
réel du one-page agricole, WeasyPrint) plutôt que par lecture de code seule.

RÉSULTAT (verdict de ce module, règle permanente de la tâche : le résultat
décide la suite) : le comparatif carburant N'ATTEINT PAS le une-page.

AGR316 (02→06/10/2026) — depuis AGR307 + AGR312, le document agricole de 3
pages (``quote_engine/agricole``) imprime le bloc ``economies`` DÉCLARÉ
(D-AGR-5, contrat partagé ``economie_pompage.json``) si et seulement si le
bloc public ``economie_pompage`` existe. Le texte « aucune promesse de
chiffre dans le PDF » devenait donc faux : l'écran dit désormais « Les
dépenses que le client DÉCLARE (datées) alimentent le bloc économies du
document 3 pages ; sans déclaration, le bloc est omis. Le une-page n'imprime
aucune économie. » Ce module PROUVE les deux moitiés par rendu réel (une-page
sans comparatif ; 3 pages avec / sans bloc), puis épingle ce texte en lisant
le SOURCE frontend depuis ce test backend — le même patron cross-stack que
`test_qjr204_replace_lines_vide.py`/`test_qx48_agronomy_v2.py`.

Aucun comportement backend n'est modifié (règle permanente 1) : ce module ne
fait que PROUVER l'état existant, puis épingler le texte écran.
"""
import json
from pathlib import Path

from django.test import SimpleTestCase, TestCase, tag

from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)


# WOW5 — cette classe RÉALISE un rendu WeasyPrint
# (``HTML(string=...).render()`` dans ``_render_onepage_html``) : elle est
# LOURDE et doit rester hors du palier rapide de la CI, comme tous les autres
# tests du moteur PDF. La classe suivante, elle, ne lit qu'un fichier source :
# elle reste délibérément dans le gate rapide.
@tag('pdf')
class TestQjr428ComparatifCarburantAbsentDuOnepage(TestCase):
    """Le devis porte les VRAIES données « exploitation » du fermier
    (`current_fuel` + `fuel_spend_current`, exactement les champs que
    `PanneauAgricole.jsx` collecte) : le one-page agricole réellement servi
    (dégradation QJR32/QJR236 depuis `pdf_mode: 'full'`) ne publie NULLE
    PART un comparatif solaire-vs-carburant."""

    LIGNES_POMPAGE = [
        ('Pompe immergée 5,5 CV', '1', '18000'),
        ('Variateur VEICHI 5,5 kW', '1', '9000'),
        ('Panneau mono 550W', '12', '1100'),
        ('Structures acier', '12', '375'),
    ]
    # `current_fuel`/`fuel_spend_current` : EXACTEMENT les deux champs de la
    # section « Votre exploitation » de PanneauAgricole.jsx (le premier posé
    # par le sélecteur `gen-farm-fuel`, le second par `gen-farm-fuelspend`).
    ETUDE_POMPAGE_AVEC_CARBURANT = {
        'pompe_cv': '5.5', 'pompe_kw': 4.05, 'type_pompe': 'immergee',
        'alim': 'tri', 'hmt_m': '80', 'debit_m3j': '45', 'champ_kwc': 5.68,
        'current_fuel': 'diesel', 'fuel_spend_current': 42000,
    }

    # Mots qui prouveraient, s'ils apparaissaient, qu'un comparatif carburant
    # est publié (aucun accent dans ces quatre mots : pas de piège d'entité
    # HTML — un simple ``in`` suffit à les trouver s'ils sont là).
    MOTS_COMPARATIF_CARBURANT = ('carburant', 'Carburant', 'diesel', 'Diesel',
                                 'butane', 'Butane')

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(
            self.company, self.user, self.client_obj, self.LIGNES_POMPAGE,
            reference='DEV-QJR428-AGRI',
            etude_params=dict(self.ETUDE_POMPAGE_AVEC_CARBURANT))
        self.devis.mode_installation = 'agricole'
        self.devis.save(update_fields=['mode_installation'])

    def _render_onepage_html(self, pdf_options=None):
        """Rend le HTML réellement servi (mêmes bornes déterministes que
        les autres tests de ce module : capture avant l'appel WeasyPrint,
        jamais les octets PDF finaux)."""
        from weasyprint import HTML
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.quote_engine import generate_devis_premium as G

        data = build_quote_data(self.devis, pdf_options)
        self.assertEqual(data['pdf_mode'], 'onepage',
                         "AGR312 — le une-page agricole se demande "
                         "explicitement (plus de dégradation de « full ») — "
                         "sinon ce test ne prouve pas la bonne page")
        cap = {}
        orig = G._render_pdf_weasyprint
        G._render_pdf_weasyprint = lambda html, out: cap.update(html=html)
        try:
            G.generate_premium_pdf(data, '/tmp/_qjr428_test.pdf')
        finally:
            G._render_pdf_weasyprint = orig
        return cap['html'], HTML(string=cap['html']).render()

    def test_current_fuel_atteint_bien_le_dict_etude_du_builder(self):
        """Sanity : la donnée VOYAGE jusque dans `build_quote_data` — si ce
        test échouait, l'absence de comparatif dans le PDF ne prouverait
        rien (la donnée ne serait même pas arrivée jusque-là)."""
        from apps.ventes.quote_engine.builder import build_quote_data
        data = build_quote_data(self.devis, {'pdf_mode': 'full'})
        self.assertEqual(data['etude'].get('current_fuel'), 'diesel')
        self.assertEqual(data['etude'].get('fuel_spend_current'), 42000)
        # AGR303 — la bascule morte du comparatif carburant a quitté la
        # charge utile (aucun renderer ne la lisait).
        self.assertNotIn('show_fuel_comparison', data)

    def test_le_one_page_agricole_ne_publie_AUCUN_comparatif_carburant(self):
        """LA PREUVE — d'abord. Un devis portant `current_fuel`+
        `fuel_spend_current` (données réelles du fermier) rend un one-page
        agricole dont AUCUN mot ne nomme un comparatif carburant : la donnée
        est conservée pour l'étude, mais aucun renderer ne la lit pour
        produire un chiffre. Ce résultat DÉCIDE le texte de l'écran
        (voir `TestQjr428TextePanneauAgricoleHonnete` ci-dessous)."""
        html, doc = self._render_onepage_html({'pdf_mode': 'onepage'})
        self.assertEqual(len(doc.pages), 1)
        for mot in self.MOTS_COMPARATIF_CARBURANT:
            self.assertNotIn(mot, html,
                             f"le mot {mot!r} apparaît dans le one-page agricole : "
                             "un comparatif carburant existe donc réellement — "
                             "revoir le verdict de cette tâche (le texte de "
                             "l'écran redeviendrait alors exact tel quel).")
        # La dépense forcée (42 000) n'apparaît nulle part comme un montant
        # « carburant » — ni au format entier ni au format espacé français.
        self.assertNotIn('42000', html)
        self.assertNotIn('42\N{NO-BREAK SPACE}000', html)
        self.assertNotIn('42 000', html)

    def test_le_une_page_n_imprime_aucune_economie_meme_avec_le_bloc(self):
        """AGR316 — le bloc public ``economie_pompage`` (AGR3) présent dans
        la charge utile n'atteint PAS le une-page : aucune ligne du bloc
        « Votre argent » du 3 pages n'y figure."""
        from weasyprint import HTML
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.quote_engine import generate_devis_premium as G

        data = build_quote_data(self.devis, {'pdf_mode': 'onepage'})
        data['_economie_pompage'] = _bloc_economie_pompage_public()
        cap = {}
        orig = G._render_pdf_weasyprint
        G._render_pdf_weasyprint = lambda html, out: cap.update(html=html)
        try:
            G.generate_premium_pdf(data, '/tmp/_agr316_onepage.pdf')
        finally:
            G._render_pdf_weasyprint = orig
        self.assertEqual(len(HTML(string=cap['html']).render().pages), 1)
        for libelle in LIBELLES_BLOC_ECONOMIES:
            self.assertNotIn(libelle, cap['html'])

    def test_le_meme_verdict_tient_quand_current_fuel_vient_de_l_option_pdf(self):
        """Second chemin AUTREFOIS possible pour `current_fuel` (l'option PDF
        forcée) : AGR303 l'a retirée — `clean_pdf_options` l'ignore, et
        l'étude rendue reste l'étude stockée. MÊME verdict : le one-page ne
        publie aucun comparatif carburant."""
        html, doc = self._render_onepage_html(
            {'pdf_mode': 'onepage', 'current_fuel': 'butane'})
        self.assertEqual(len(doc.pages), 1)
        for mot in self.MOTS_COMPARATIF_CARBURANT:
            self.assertNotIn(mot, html,
                             f"le mot {mot!r} apparaît alors que current_fuel "
                             "vient de l'option PDF forcée — même verdict "
                             "attendu que par etude_params.")


_CONTRATS = Path(__file__).resolve().parents[1] / 'contract_samples'

#: Libellés (sans accent ni entité HTML) que seul le bloc « Votre argent »
#: du document 3 pages imprime (``agricole/pages._argent``, i18n FR).
LIBELLES_BLOC_ECONOMIES = ('Votre argent', 'Charges du solaire par an')


def _bloc_economie_pompage_public():
    """Le bloc PUBLIC ``economie_pompage`` (AGR3) : l'``exemple`` du contrat
    partagé, sans ``vue_interne`` (jamais imprimée) — jamais redéfini ici."""
    bloc = json.loads((_CONTRATS / 'economie_pompage.json').read_text(
        encoding='utf-8'))['exemple']
    bloc.pop('vue_interne', None)
    return bloc


@tag('pdf')
class TestAgr316TroisPagesEconomiesDeclarees(SimpleTestCase):
    """AGR316 — rendu RÉEL du document agricole de 3 pages : le bloc
    économies est imprimé SI ET SEULEMENT SI ``economie_pompage`` existe."""

    def setUp(self):
        from apps.ventes.tests.test_agr310_renderer_agricole import fitz
        if fitz is None:  # pragma: no cover
            self.skipTest('PyMuPDF absent')

    def _texte_pdf(self, data):
        from apps.ventes.quote_engine.agricole import renderer
        from apps.ventes.tests.test_agr310_renderer_agricole import fitz
        doc = fitz.open(stream=renderer.render_pdf_bytes(data),
                        filetype='pdf')
        try:
            return len(doc), ' '.join(' '.join(page.get_text().split())
                                      for page in doc)
        finally:
            doc.close()

    def test_avec_economie_pompage_le_bloc_est_imprime(self):
        from apps.ventes.tests.test_agr310_renderer_agricole import (
            data_complete,
        )
        data = data_complete()
        self.assertTrue(data.get('_economie_pompage'))
        pages, texte = self._texte_pdf(data)
        self.assertEqual(pages, 3)
        for libelle in LIBELLES_BLOC_ECONOMIES:
            self.assertIn(libelle, texte)

    def test_sans_economie_pompage_le_bloc_est_omis(self):
        from apps.ventes.tests.test_agr310_renderer_agricole import (
            data_complete,
        )
        data = data_complete()
        data.pop('_economie_pompage')
        pages, texte = self._texte_pdf(data)
        self.assertEqual(pages, 3)
        for libelle in LIBELLES_BLOC_ECONOMIES:
            self.assertNotIn(libelle, texte)


class TestQjr428TextePanneauAgricoleHonnete(TestCase):
    """Le résultat de la classe ci-dessus (comparatif ABSENT du document)
    décide : le texte de `PanneauAgricole.jsx` ne doit plus promettre un
    chiffre carburant que le PDF ne rend pas. Ce test lit le SOURCE
    frontend depuis ce test backend (aucun exécuteur JS n'est requis pour
    vérifier un texte statique) et épingle l'alignement."""

    def _lire_panneau_agricole(self):
        # Racine du dépôt = 5 niveaux au-dessus de ce fichier
        # (tests/ -> ventes/ -> apps/ -> django_core/ -> backend/ -> RACINE).
        racine = Path(__file__).resolve().parents[5]
        chemin = (racine / 'frontend' / 'src' / 'pages' / 'ventes'
                  / 'generator' / 'PanneauAgricole.jsx')
        self.assertTrue(chemin.exists(),
                        f"PanneauAgricole.jsx introuvable à {chemin} — la "
                        "racine calculée est-elle toujours correcte ?")
        source = chemin.read_text(encoding='utf-8')
        # ESPACES NORMALISÉS. Le texte visé vit dans un commentaire JSX
        # RENVOYÉ À LA LIGNE : « aucune promesse de chiffre dans le\n
        # PDF ». Chercher la phrase telle quelle dans le source brut ne
        # mesure pas l'honnêteté du texte, mais la largeur de colonne du
        # jour — et un simple reformatage la ferait rougir (ou, pire, ferait
        # passer un ``assertNotIn`` sur une promesse fausse simplement
        # coupée en deux). On compare donc sur le texte à espaces normalisés,
        # ce que lit un humain.
        return ' '.join(source.split())

    def test_le_texte_dit_ce_que_les_documents_impriment_vraiment(self):
        source = self._lire_panneau_agricole()
        # L'ANCIENNE promesse fausse (« économies vs carburant » comme
        # chiffre du PDF) reste absente, et la phrase devenue fausse depuis
        # AGR307/AGR312 (« aucune promesse de chiffre dans le PDF ») aussi.
        self.assertNotIn('économies vs carburant', source)
        self.assertNotIn('aucune promesse de chiffre dans le PDF', source)
        # AGR316 — le texte exact : les dépenses DÉCLARÉES alimentent le bloc
        # économies du 3 pages (prouvé par
        # `TestAgr316TroisPagesEconomiesDeclarees`), le une-page n'en imprime
        # aucune (prouvé par la première classe).
        self.assertIn(
            'Les dépenses que le client DÉCLARE (datées) alimentent le bloc '
            'économies du document 3 pages ; sans déclaration, le bloc est '
            'omis. Le une-page n\u2019imprime aucune économie.', source)
        # Le besoin en eau FAO-56, LUI, atteint bel et bien le one-page
        # (cartes « HMT »/« Débit »/« Eau / jour », prouvées par
        # `test_pompage_curve_figures_water_per_day_one_page` dans
        # `test_quote_engine_formats.py`) — cette moitié de la promesse
        # reste donc affirmée telle quelle, jamais retirée par erreur.
        self.assertIn('FAO-56', source)
