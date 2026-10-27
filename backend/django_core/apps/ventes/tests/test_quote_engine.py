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

from django.test import SimpleTestCase

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
    from PIL import Image
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
    if logo is True:
        kw["embeded_image_path"] = str(theme._LIVE_ASSETS / "logo.png")
    elif logo:
        kw["embeded_image"] = Image.open(io.BytesIO(base64.b64decode(logo)))
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
