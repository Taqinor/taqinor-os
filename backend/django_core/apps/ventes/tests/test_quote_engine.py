"""Moteur de devis premium — la suite est SCINDÉE en quatre modules.

Ce fichier pesait 3 704 lignes et 146,9 s en CI : 10 % de toute la suite
backend dans UN seul module, et donc à lui seul le plancher du shardage
(aucun nombre de lanes ne peut descendre une lane sous le module le plus
lourd). Le 2026-08-19 il a été découpé PAR SURFACE EXERCÉE, à durée
approximativement équilibrée, sans qu'un seul test change de nom ni une
seule assertion de valeur :

- `test_quote_engine_formats.py`      — rendu par FORMAT du moteur legacy
  (pages premium/une-page/étude/annexe, totaux, TVA, pompage) ;
- `test_quote_engine_residential.py`  — proposition résidentielle redessinée
  (pagination, fiches, cache chaud, signature, pied de page locataire) ;
- `test_quote_engine_documents.py`    — littéraux/gabarits du document, flux
  générateur → PDF, non-régression du layout toiture v2 ;
- `test_quote_engine_builder.py`      — builder et chiffres (sans rendu PDF).

Les fabriques communes vivent dans `_quote_engine_common.py` (préfixe `_` :
hors découverte Django). CE MODULE LES RÉ-EXPORTE : une douzaine d'autres
modules de test les importent depuis `apps.ventes.tests.test_quote_engine`
et continuent de fonctionner sans une seule ligne modifiée (imports NOMMÉS :
les classes de test ci-dessous ne sont jamais ré-exécutées par eux). Seule
exception : `QrMasqueVectoriseTest` (ERR-MOTEUR-QR-MASQUE-LENT-ACCEPTATION,
module désigné par la tâche) — sinon choisir la partie ci-dessus.
"""
import base64
import io
import time

from django.test import SimpleTestCase, TestCase, tag

from apps.ventes.tests._quote_engine_common import (
    DEUX_OPTIONS,
    User,
    _company_seq,
    _residential_sample_data,
    make_client,
    make_company,
    make_devis,
    make_produit,
    make_user,
)

# Noms ré-exportés volontairement (façade) : pas la surface complète du module.
__all__ = [
    'DEUX_OPTIONS', 'User', '_company_seq', '_residential_sample_data', 'make_client',
    'make_company', 'make_devis', 'make_produit', 'make_user',
]


def _qr_ancien_rendu(url, *, logo=True, correction="H", box_size=16, border=2,
                     front=(26, 43, 74)):
    """ORACLE — l'ancien rendu de ``theme.qr_data_uri`` (appel bibliothèque
    ``StyledPilImage`` + ``SolidFillColorMask``, boucle par pixel), gardé ICI
    seulement pour prouver que le nouveau rendu ne bouge pas d'un pixel."""
    import qrcode
    from qrcode.image.styledpil import StyledPilImage
    from qrcode.image.styles.colormasks import SolidFillColorMask
    from qrcode.image.styles.moduledrawers.pil import RoundedModuleDrawer
    from apps.ventes.quote_engine.residential import theme
    niveaux = {"M": qrcode.constants.ERROR_CORRECT_M,
               "H": qrcode.constants.ERROR_CORRECT_H}
    qr = qrcode.QRCode(error_correction=niveaux[correction],
                       box_size=box_size, border=border)
    qr.add_data(theme.normaliser_lien(url))
    qr.make(fit=True)
    kw = dict(image_factory=StyledPilImage, module_drawer=RoundedModuleDrawer(),
              color_mask=SolidFillColorMask(front_color=tuple(front),
                                            back_color=(255, 255, 255)))
    # R3 — l'image centrale est celle de ``quote_engine.logo`` (emblème
    # TAQINOR, logo société dans un carré blanc) : l'oracle ne porte que sur
    # le masque de couleur, jamais sur le choix du logo.
    from apps.ventes.quote_engine import logo as _logo
    if logo is True:
        kw["embeded_image"] = _logo.taqinor_image_qr()
    elif logo:
        kw["embeded_image"] = _logo.image_qr_societe(logo)
    buf = io.BytesIO()
    qr.make_image(**kw).save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _qr_logo_societe_b64(mode):
    """Logo société de test (base64 PNG) : RGBA semi-transparent ou RGB."""
    from PIL import Image
    fond, centre = ((200, 30, 30), (10, 120, 220)) if mode == "RGB" else (
        (200, 30, 30, 160), (10, 120, 220, 255))
    img = Image.new(mode, (120, 80), fond)
    img.paste(Image.new(mode, (40, 40), centre), (40, 20))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


class QrMasqueVectoriseTest(SimpleTestCase):
    """ERR-MOTEUR-QR-MASQUE-LENT-ACCEPTATION — ``theme.qr_data_uri`` rend le
    MÊME PNG (pixel pour pixel) que l'ancien ``SolidFillColorMask`` par pixel,
    pour chaque forme d'appel du moteur, mais en moins d'une seconde."""

    LIENS = (
        "https://taqinor.ma/proposition/abc123def456ghi789jkl",
        "taqinor.ma/proposition/Zx9_-Qw8Er7Ty6Ui5Op4As3Df2Gh1JkLmN0bVcXz",
        "https://api.taqinor.ma/p/1?t=0123456789abcdef0123456789abcdef&lang=fr",
    )
    # trust.py / agricole/pages.py (H/16, logo central) ; cover.py,
    # legacy_onepage.py, ci/couverture.py (vignette M/10, sans logo).
    PAGE3 = dict(logo=True, correction="H", box_size=16, border=2)
    VIGNETTE = dict(logo=False, correction="M", box_size=10, border=4)

    @staticmethod
    def _image(uri):
        from PIL import Image
        img = Image.open(io.BytesIO(base64.b64decode(uri.split(",", 1)[1])))
        img.load()
        return img

    def _assert_memes_pixels(self, lien, **kw):
        from apps.ventes.quote_engine.residential import theme
        nouveau = theme.qr_data_uri.__wrapped__(lien, **kw)
        self.assertTrue(nouveau.startswith("data:image/png;base64,"))
        a, n = self._image(_qr_ancien_rendu(lien, **kw)), self._image(nouveau)
        self.assertEqual((a.mode, a.size), (n.mode, n.size))
        self.assertTrue(a.tobytes() == n.tobytes(),
                        f"pixels différents : {lien} {kw}")

    def test_memes_pixels_page3_et_vignette_trois_liens(self):
        for lien in self.LIENS:
            for forme in (self.PAGE3, self.VIGNETTE):
                with self.subTest(lien=lien, forme=forme):
                    self._assert_memes_pixels(lien, **forme)

    def test_memes_pixels_logo_societe_et_agricole(self):
        lien = self.LIENS[0]
        for mode in ("RGBA", "RGB"):
            with self.subTest(logo_societe=mode):
                self._assert_memes_pixels(
                    lien, logo=_qr_logo_societe_b64(mode),
                    front=(26, 43, 74))  # forme exacte d'agricole/pages.py

    def test_budget_temps_moins_d_une_seconde_par_taille(self):
        from apps.ventes.quote_engine.residential import theme
        for forme in (self.PAGE3, self.VIGNETTE):
            with self.subTest(forme=forme):
                meilleur = float("inf")
                for _ in range(3):  # meilleur de 3 : insensible à un pic de charge
                    t0 = time.perf_counter()
                    theme.qr_data_uri.__wrapped__(self.LIENS[2], **forme)
                    meilleur = min(meilleur, time.perf_counter() - t0)
                self.assertLess(meilleur, 1.0)


class RpdfLegacyMiseEnPageTest(SimpleTestCase):
    """RPDF20-22 — rendus réels du 27/10 (devis 1344, résidentiel + étude,
    moteur legacy) : HTML exact remis à WeasyPrint (``render_html_for``),
    aucune base. Mise en page seulement : aucun chiffre ne change."""

    #: Le ``dimensionnement`` d'un devis horaire sans étude saisie : seule la
    #: tranche actuelle est publiable (aucun optimum ne décrit le devis).
    _DIM = {'falaise': {'tranche_actuelle': {'rang': 6,
                                             'libelle': '> 510 kWh/mois'}}}

    @staticmethod
    def _html(**surcharges):
        from apps.ventes.quote_engine import generate_devis_premium as G
        from apps.ventes.tests import _moteur_fixtures as F
        return G, G.render_html_for(F.donnees_legacy(pdf_mode='full',
                                                     **surcharges))

    def test_rpdf20_etude_sans_contenu_ni_rendue_ni_comptee(self):
        G, html = self._html(include_etude=True,
                             etude={'dimensionnement': self._DIM})
        self.assertEqual(G.PAGES_TOTAL, 3)
        self.assertNotIn(G._L('lg_etude_pied').format(ref=G.REF), html)
        # Test-du-test : une étude qui porte un chiffre réel garde sa page.
        G, html = self._html(include_etude=True,
                             etude={'dimensionnement': self._DIM,
                                    'production_annuelle': 25415})
        self.assertEqual(G.PAGES_TOTAL, 4)
        self.assertIn(G._L('lg_etude_pied').format(ref=G.REF), html)

    @tag('pdf')  # rendu WeasyPrint réel (WOW5)
    def test_rhor8_la_langue_n_ajoute_aucune_page_avec_l_etude(self):
        """ERR-RHOR8-PDF-AR-PAGES-ETUDE (devis 2007 / 2300 du rejeu RHOR8) :
        en arabe, l'interligne ``normal`` de « Noto Sans Arabic » gonflait les
        tableaux de la page 2 et WeasyPrint la fragmentait (AR 5 pages contre
        FR/EN 3 ou 4). Compte RÉEL des feuilles, par langue, sans et avec une
        étude à contenu : identique en fr/en/ar et égal à ``PAGES_TOTAL``.
        Fixture rouge avant le correctif (AR 4 et 5)."""
        from weasyprint import HTML
        from apps.ventes.quote_engine import generate_devis_premium as G
        from apps.ventes.quote_engine import i18n_labels
        from apps.ventes.tests import _moteur_fixtures as F
        gar = '12 ans produit · 30 ans performance linéaire (87,4 %)'
        desc = ('Module N-type TOPCon, rendement ≈ 22,9 %\n'
                'Certifié IEC 61215 / IEC 61730, fabricant Tier 1')
        for etude, attendu in ((None, 3), ({'production_annuelle': 25415}, 4)):
            for langue in ('fr', 'en', 'ar'):
                with self.subTest(etude=bool(etude), langue=langue):
                    d = F.donnees_legacy(
                        pdf_mode='full', include_etude=True, langue_sortie=langue,
                        libelles_document=i18n_labels.libelles(langue))
                    if etude:
                        d['etude'] = etude
                    # 12 lignes par option, une sur trois décrite (devis 2007).
                    for cle in ('sans_items', 'avec_items'):
                        base = d[cle]
                        d[cle] = [dict(base[i % len(base)],
                                       description=desc if i % 3 == 0 else '',
                                       garantie=gar if i % 3 == 0 else '')
                                  for i in range(12)]
                    html = G.render_html_for(d)
                    self.assertEqual(G.PAGES_TOTAL, attendu)
                    self.assertEqual(len(HTML(string=html).render().pages),
                                     attendu)

    def test_d_acal_116_deux_echeanciers_aucune_page_ajoutee(self):
        """D-ACAL-116 — Devis final à deux options, nouveaux rendus : une ligne
        d'échéances par option ; condition du fondateur, AUCUNE page ajoutée
        (format avec étude et sans, fr/en/ar)."""
        from weasyprint import HTML
        from apps.ventes.quote_engine import generate_devis_premium as G
        from apps.ventes.quote_engine import i18n_labels
        from apps.ventes.tests import _moteur_fixtures as F
        tranches = {b: {"acompte": a, "materiel": m, "solde": s, "pct_a": 30, "pct_m": 60,
                        "pct_s": 10, "solde2": m + s, "pct_s2": 70}
                    for b, a, m, s in (("sans", 18518.52, 37037.04, 6172.84),
                                       ("avec", 29629.63, 59259.26, 9876.54))}
        for etude, attendu in ((None, 3), ({'production_annuelle': 25415}, 4)):
            for langue in ('fr', 'en', 'ar'):
                with self.subTest(etude=bool(etude), langue=langue):
                    d = F.donnees_legacy(
                        pdf_mode='full', include_etude=True, langue_sortie=langue,
                        libelles_document=i18n_labels.libelles(langue), devis_final=True,
                        montants_tranches=tranches, phrases_pdf_2511=True)
                    if etude:
                        d['etude'] = etude
                    html = G.render_html_for(d)
                    # Nom d'option traduit par LA fonction du code (catalogue res_opt_sans).
                    self.assertIn(i18n_labels.nom_option("Sans batterie", langue) + " : ", html)
                    self.assertEqual(len(HTML(string=html).render().pages), attendu)

    def test_d_acal_111_phrase_facture_recalculee_aucune_page_ajoutee(self):
        """T4-X7-003 / D-ACAL-111 — la phrase approuvée suit aussi l'exemple
        « Facture actuelle ≈ … » des blocs « Comment nous calculons » : premium
        résidentiel (variante « long », page 3 la plus dense) toujours 3 pages,
        format avec étude toujours 4, fr/en/ar.

        Premium : le PDF du CLIENT sort de ``renderer.render_pdf_bytes`` (garde
        ERR114 + ``theme.compact_css``, chemin de ``PaginationReelle``) — c'est
        lui qui doit faire 3 pages. Le HTML BRUT en arabe imprime 5 feuilles
        même sans la phrase (docstring de ``theme.compact_css`` : pages 1 et 2
        débordent chacune) : sur ce chemin-là, la garde est « la phrase
        n'ajoute aucune feuille », dans les trois langues."""
        import fitz
        from weasyprint import HTML
        from apps.ventes.quote_engine import generate_devis_premium as G
        from apps.ventes.quote_engine import i18n_labels
        from apps.ventes.quote_engine.residential import render, renderer, sample_data
        from apps.ventes.tests import _moteur_fixtures as F
        neuf = {"factures_source": "etude_horaire", "phrases_pdf_2511": True}
        self.addCleanup(renderer._PDF_CACHE.clear)
        for langue in ('fr', 'en', 'ar'):
            phrase = i18n_labels.libelle("res_facture_recalculee_tranches", langue)
            with self.subTest(format="premium", langue=langue):
                # Même document, même drapeau, facture NON recalculée : sans la phrase.
                base = dict(sample_data.build("long"), langue_sortie=langue, phrases_pdf_2511=True,
                            libelles_document=i18n_labels.libelles(langue))
                d = dict(base, **neuf)
                html = render.build_html(renderer._augment(d))
                self.assertEqual(html.count(phrase), 2)  # couverture + méthode
                self.assertEqual(
                    len(HTML(string=html).render().pages),
                    len(HTML(string=render.build_html(renderer._augment(base))).render().pages))
                renderer._PDF_CACHE.clear()
                with fitz.open(stream=renderer.render_pdf_bytes(d), filetype="pdf") as pdf:
                    self.assertEqual(len(pdf), 3)
            with self.subTest(format="etude", langue=langue):
                d = F.donnees_legacy(
                    pdf_mode='full', include_etude=True, langue_sortie=langue,
                    libelles_document=i18n_labels.libelles(langue),
                    savings_method=sample_data.build("long")["savings_method"], **neuf)
                d['etude'] = {'production_annuelle': 25415}
                html = G.render_html_for(d)
                self.assertIn(phrase, html)
                self.assertEqual(len(HTML(string=html).render().pages), 4)

    @staticmethod
    def _page2(html):
        from apps.ventes.quote_engine import generate_devis_premium as G
        debut = html.index(G._L('lg_p2_titre'))
        return html[debut:html.index('<div class="page"', debut)]

    def test_rpdf21_totaux_longs_mettent_tableau_et_graphes_a_l_echelle(self):
        """Devis 1344 : 11 lignes, remise + arrondi + Total HT + TVA 10/20
        (7 rangées de totaux) — le graphe mensuel passait sous le pied de
        page. Les rangées de totaux au-delà de 4 comptent une demi-rangée ;
        sous l'échelle, les deux graphes (taille fixe, hors flex) la suivent,
        au ratio 4:1 de leur image."""
        from apps.ventes.tests import _moteur_fixtures as F
        from apps.ventes.quote_engine import generate_devis_premium as G
        base = F.donnees_legacy('plus5', pdf_mode='full',
                                scenario='Avec batterie')
        self.assertEqual(len(base['avec_items']), 11)
        html0 = G.render_html_for(base)
        p2 = self._page2(html0)
        # Test-du-test : 11 lignes et 4 totaux ⇒ page 2 d'hier, octet pour octet.
        self.assertNotIn('<style>.eq{font-size:', html0)
        self.assertIn('width:680px;height:170px;display:block;', p2)
        tva = [{'taux': 10.0, 'montant': 2508.0, 'ht_net': 25080.0},
               {'taux': 20.0, 'montant': 16602.0, 'ht_net': 83010.0}]
        d = dict(base, discount_pct=5,
                 totaux_avec=dict(base['totaux_avec'], arrondi=6.5,
                                  tva_par_taux=tva))
        html = G.render_html_for(d)
        p2 = self._page2(html)
        k = 11.0 / (11 + 0.5 * 3)
        self.assertIn('<style>.eq{font-size:', html)
        self.assertNotIn('width:680px;height:170px;', p2)
        self.assertIn(f'width:{int(680 * k)}px;height:{int(170 * k)}px;'
                      'display:block;', p2)

    def test_rpdf22_bon_pour_accord_dans_le_flux_jamais_sous_le_contenu(self):
        """Devis 1344, page 4 : le bandeau « Notre engagement » chevauchait le
        titre « Bon pour accord » — celui-ci était épinglé en absolu
        (``bottom:43px``) sous un contenu plafonné à 820 px, sans lien avec sa
        propre hauteur. Il est désormais dans la colonne flex de la page : le
        contenu (``flex:1;min-height:0``, rogné) prend la place qu'il laisse."""
        G, html = self._html()
        p3 = html[html.rindex(G._L('lg_confiance_bpa')):]
        self.assertNotIn('position:absolute;bottom:43px', p3)
        self.assertIn('flex-shrink:0;margin-top:auto;margin-bottom:43px;', p3)
        self.assertIn('overflow:hidden;max-height:820px;flex:1;min-height:0;',
                      p3)
        # Le pied reste absolu au bas de la feuille ; seule la page 3 change.
        self.assertIn('position:absolute;bottom:0;left:0;right:0;', p3)


@tag('pdf')  # rendu WeasyPrint + PyMuPDF réel (WOW5)
class RibDevisFinalPagesTest(SimpleTestCase):
    """T4-U1-009 — « Devis final » d'une société AVEC RIB et banque au profil :
    la ligne « Virement bancaire » sous l'échéancier (clé ``rib_sous_echeancier``
    du builder, nouveaux rendus) n'ajoute aucune page aux documents les plus
    denses de chaque marché — commercial 3, industriel 4, agricole 3 — et sort
    UNE fois. Mêmes fixtures que les gardes de densité CIQ317 (40 lignes,
    6 options, une note) et AGR310 (40 lignes)."""

    PROFIL = {'nom': 'SOCIETE RIB SARL', 'ice': '002222222000022',
              'rib': '011 780 0000123456789012 34', 'banque': 'Banque Exemple'}

    def _verifier(self, renderer, data, pages):
        import fitz
        from apps.ventes.quote_engine.rib_devis_final import CLE
        data.update({'devis_final': True, CLE: True, 'entreprise': dict(self.PROFIL)})
        with fitz.open(stream=renderer.render_pdf_bytes(data), filetype='pdf') as pdf:
            self.assertEqual(len(pdf), pages)
            texte = ''.join(page.get_text() for page in pdf)
        self.assertEqual(texte.count('Virement bancaire'), 1)
        self.assertIn('Banque Exemple', texte)

    def test_commercial_et_industriel_les_plus_denses(self):
        from apps.ventes.quote_engine.commercial import renderer as c_renderer
        from apps.ventes.quote_engine.commercial import sample_data as c_sample
        from apps.ventes.quote_engine.industriel import renderer as i_renderer
        from apps.ventes.quote_engine.industriel import sample_data as i_sample
        from apps.ventes.tests.test_ciq317_nomenclature_longue import _data
        for nom, sample, renderer, pages in (('commercial', c_sample, c_renderer, 3),
                                             ('industriel', i_sample, i_renderer, 4)):
            with self.subTest(marche=nom):
                self._verifier(renderer, _data(sample, 40, 6,
                                               note="Accès au toit par l'escalier de service."), pages)

    def test_agricole_le_plus_dense(self):
        from apps.ventes.quote_engine.agricole import renderer
        from apps.ventes.tests.test_agr310_renderer_agricole import data_complete
        self._verifier(renderer, data_complete(nb_lignes_extra=40), 3)


class ProvenanceUneLigneAcal1266Test(SimpleTestCase):
    """ACAL1266 (C-ACAL-REC-R5-06) — au PDF agricole, une entrée du point d'eau
    DÉCLARÉE et non mesurée tient sur UNE ligne « 30 m — déclaré par vous le …,
    à confirmer par la visite » et ne revient plus dans la liste « À confirmer
    par la visite » ; une entrée mesurée reste sur sa ligne sans réserve.
    Nouveaux rendus seulement (drapeau ``phrases_pdf_lot10``) : sans lui, le
    texte reçu par un devis envoyé ne bouge pas. Mutant : garder les deux
    listes ⇒ le libellé « Niveau statique » sort deux fois, échec."""

    SYNTHESE = {
        'provenance': {
            'niveau_statique_m': {'origine': 'saisie', 'detail': None,
                                  'date': '2026-11-20', 'valeur': 30},
            'niveau_dynamique_m': {'origine': 'saisie', 'detail': 'mesure_visite',
                                   'date': '2026-11-21', 'valeur': 40}},
        'a_confirmer_par_visite': ['niveau_statique_m', 'profondeur_forage_m']}

    def _html(self, une_ligne):
        from apps.ventes.quote_engine.agricole.pages import _provenance
        return _provenance(dict(self.SYNTHESE), 'fr', 'SOCIETE', une_ligne=une_ligne)

    def test_declaree_non_mesuree_sur_une_seule_ligne(self):
        from apps.ventes.quote_engine.agricole.pages import _entree
        html = self._html(True)
        self.assertIn('30 m — déclaré par vous le 20/11/2026, à confirmer par la visite', html)
        self.assertEqual(html.count(_entree('fr', 'niveau_statique_m')), 1)
        # La profondeur, sans ligne de provenance, reste dans la liste.
        self.assertIn(_entree('fr', 'profondeur_forage_m'), html)
        mesuree = next(li for li in html.split('<div class="ag-li">')
                       if _entree('fr', 'niveau_dynamique_m') in li)
        self.assertNotIn('à confirmer', mesuree)

    def test_sans_drapeau_texte_recu_inchange(self):
        from apps.ventes.quote_engine.agricole.pages import _entree
        html = self._html(False)
        self.assertNotIn(', à confirmer par la visite', html)
        self.assertEqual(html.count(_entree('fr', 'niveau_statique_m')), 2)


class FicheRemisePremiumMultivilla(TestCase):
    """ADOC198 (C-ADOC-VER4-002) — la fiche de remise premium liste le
    matériel VENDU × nombre de villas (``lignes_vendues``), comme le dossier
    de remise ; le moteur ne fait que RENDRE (règle #4)."""

    def test_quantites_x_n(self):
        from rest_framework.test import APIClient
        from apps.installations.services import create_installation_from_devis
        from apps.ventes.quote_engine.extra_docs import (
            _chantier_composants, build_fiche_remise_html,
        )
        company = make_company()
        user = make_user(company)
        devis = make_devis(
            company, user, make_client(company),
            [('Panneau 550W', '8', '1000'), ('Onduleur 5kW', '1', '9000')],
            reference='DEV-ADOC198-1', etude_params={'nombre_proprietes': 3})
        devis.statut = 'accepte'
        devis.save(update_fields=['statut'])
        chantier, _ = create_installation_from_devis(devis, user, company)
        composants = _chantier_composants(chantier)
        self.assertEqual(
            {c['designation']: int(c['quantite']) for c in composants},
            {'Panneau 550W': 24, 'Onduleur 5kW': 3})
        html = build_fiche_remise_html(
            {'entreprise_nom': 'ADOC198'}, {'nom': 'Alaoui'},
            {'reference': chantier.reference}, composants)
        self.assertIn('24', html)
        self.assertNotIn('prix_achat', html)
        # ACSV99 — la route applique la garde d'état : chantier installé.
        chantier.statut = 'installe'
        chantier.save(update_fields=['statut'])
        api = APIClient()
        api.force_authenticate(user)
        resp = api.get(
            f'/api/django/ventes/chantiers/{chantier.id}/fiche-remise-premium/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertNotIn(b'prix_achat', resp.content)

    def test_parc_pose_et_date_de_reception(self):
        """ACSV37 : la fiche liste le parc posé (n° de série, fin de garantie
        calculée) et date la remise de la réception, pas du jour d'impression."""
        from datetime import date
        from apps.installations.models import Installation
        from apps.sav.models import Equipement
        from apps.stock.models import Produit
        from apps.ventes.quote_engine.extra_docs import (
            _chantier_composants, build_fiche_remise_html,
        )
        company = make_company()
        chantier = Installation.objects.create(
            company=company, reference='CH-ACSV37', client=make_client(company),
            statut='installe', date_reception=date(2026, 8, 8))
        onduleur = Produit.objects.create(
            company=company, nom='Onduleur 5kW', sku='OND-ACSV37',
            marque='Huawei', prix_vente=9000, prix_achat=6000)
        panneau = Produit.objects.create(
            company=company, nom='Panneau 550W', sku='PAN-ACSV37',
            prix_vente=1000, prix_achat=700)
        Equipement.objects.create(
            company=company, produit=onduleur, installation=chantier,
            numero_serie='SN-1', date_pose=date(2026, 8, 8),
            date_fin_garantie=date(2036, 8, 8))
        for _ in range(10):
            Equipement.objects.create(
                company=company, produit=panneau, installation=chantier,
                date_pose=date(2026, 8, 8))
        composants = _chantier_composants(chantier)
        self.assertEqual(
            sorted((c['designation'], c['quantite']) for c in composants),
            [('Onduleur 5kW (N° SN-1)', 1), ('Panneau 550W', 10)])
        html = build_fiche_remise_html(
            {'entreprise_nom': 'ACSV37'}, {'nom': 'Alaoui'},
            {'reference': chantier.reference, 'date_reception': '08/08/2026'},
            composants)
        self.assertIn('SN-1', html)
        self.assertIn('08/08/2036', html)
        self.assertIn('Remis au client le 08/08/2026', html)
        self.assertNotIn('prix_achat', html)
        self.assertNotIn(date.today().strftime('%d/%m/%Y'), html)
