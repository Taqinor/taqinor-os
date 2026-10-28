"""QD1 — Rognage des marges du logo avant embarquement dans les PDF documents.

Le logo était embarqué dans un canevas à larges marges ; la règle CSS
``max-height`` s'appliquait au canevas et rapetissait le logo visible. On rogne
désormais les marges (transparentes d'abord, sinon blanches) avant
l'embarquement. Ce module teste le helper PUR ``_trim_image_whitespace`` :

  * une image avec un carré coloré centré et de larges marges transparentes est
    rognée à la taille du carré (le ratio n'est jamais distordu) ;
  * même chose avec des marges BLANCHES (image sans canal alpha) ;
  * une image sans marge n'est pas modifiée ;
  * dégradation propre sur des octets invalides (image inchangée, aucun crash).
"""
from io import BytesIO

from django.test import SimpleTestCase, TestCase

from apps.ventes.utils.pdf import _trim_image_whitespace


def _png_with_transparent_margin(box=40, margin=60, color=(200, 30, 30, 255)):
    from PIL import Image
    size = box + 2 * margin
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    for x in range(margin, margin + box):
        for y in range(margin, margin + box):
            img.putpixel((x, y), color)
    out = BytesIO()
    img.save(out, format='PNG')
    return out.getvalue(), box, size


def _png_with_white_margin(box=40, margin=60, color=(10, 40, 200)):
    from PIL import Image
    size = box + 2 * margin
    img = Image.new('RGB', (size, size), (255, 255, 255))
    for x in range(margin, margin + box):
        for y in range(margin, margin + box):
            img.putpixel((x, y), color)
    out = BytesIO()
    img.save(out, format='PNG')
    return out.getvalue(), box, size


def _dims(raw):
    from PIL import Image
    return Image.open(BytesIO(raw)).size


class TrimTransparentMarginTests(TestCase):
    def test_trims_transparent_margin_to_content(self):
        raw, box, size = _png_with_transparent_margin()
        trimmed, ext = _trim_image_whitespace(raw)
        self.assertEqual(ext, 'png')
        self.assertNotEqual(trimmed, raw)
        w, h = _dims(trimmed)
        self.assertEqual((w, h), (box, box))  # rogné au contenu
        self.assertLess(w, size)

    def test_preserves_aspect_ratio(self):
        from PIL import Image
        img = Image.new('RGBA', (300, 300), (0, 0, 0, 0))
        # Contenu rectangulaire 100×40 → doit rester 100×40 après rognage.
        for x in range(50, 150):
            for y in range(50, 90):
                img.putpixel((x, y), (0, 100, 0, 255))
        out = BytesIO()
        img.save(out, format='PNG')
        trimmed, ext = _trim_image_whitespace(out.getvalue())
        self.assertEqual(_dims(trimmed), (100, 40))


class TrimWhiteMarginTests(TestCase):
    def test_trims_white_margin_to_content(self):
        raw, box, size = _png_with_white_margin()
        trimmed, ext = _trim_image_whitespace(raw)
        self.assertEqual(ext, 'png')
        self.assertEqual(_dims(trimmed), (box, box))


class TrimNoopTests(TestCase):
    def test_full_bleed_image_unchanged(self):
        from PIL import Image
        img = Image.new('RGB', (120, 60), (12, 34, 56))  # pas de marge
        out = BytesIO()
        img.save(out, format='PNG')
        raw = out.getvalue()
        trimmed, ext = _trim_image_whitespace(raw)
        self.assertEqual(trimmed, raw)
        self.assertIsNone(ext)

    def test_invalid_bytes_degrade_cleanly(self):
        raw = b'not-an-image'
        trimmed, ext = _trim_image_whitespace(raw)
        self.assertEqual(trimmed, raw)
        self.assertIsNone(ext)


# ── R3 — ``quote_engine.logo`` : LE traitement d'image des logos du moteur ──
#
# Module PUR (PIL + numpy, aucune base) : rognage au trait, détourage du fond
# uni clair par DISTANCE AU FOND avec alpha progressif (jamais un seuil
# binaire), variante sombre (encre sombre reliée au fond → blanc ; couleurs
# vives et encres enclavées gardées), géométrie lue sur l'asset TAQINOR,
# centre des QR carré, cache ``lru_cache``.

def _png_bytes(img):
    out = BytesIO()
    img.save(out, format='PNG')
    return out.getvalue()


def _uri(img):
    import base64
    return 'data:image/png;base64,' + base64.b64encode(_png_bytes(img)).decode()


def _canevas_navy(largeur=120, hauteur=60, bord=True):
    """Rectangle bleu nuit sur canevas blanc, bord gauche à 50 % (anticrénelé)."""
    from PIL import Image
    img = Image.new('RGB', (200, 160), (255, 255, 255))
    navy = (2, 47, 83)
    img.paste(Image.new('RGB', (largeur, hauteur), navy), (40, 50))
    if bord:
        mixte = tuple((c + 255) // 2 for c in navy)
        img.paste(Image.new('RGB', (1, hauteur), mixte), (39, 50))
    return img


class LogoDetourageTests(SimpleTestCase):

    def test_fond_blanc_transparent_alpha_progressif_et_defrange(self):
        from apps.ventes.quote_engine.logo import detourer
        a = detourer(_canevas_navy())
        self.assertEqual(a.shape[:2], (60, 121))              # rogné au trait
        self.assertEqual(int(a[30, 60, 3]), 255)               # intérieur opaque
        self.assertEqual(tuple(int(v) for v in a[30, 60, :3]), (2, 47, 83))
        self.assertAlmostEqual(float(a[30, 0, 3]) / 255, 0.5, delta=0.06)  # bord à 50 %
        # dé-frange : la couleur du pixel de bord est l'encre, pas le mélange
        self.assertLess(float(a[30, 0, :3].max()), 100)

    def test_fond_non_clair_jamais_detoure(self):
        from PIL import Image
        from apps.ventes.quote_engine.logo import detourer, variante_sombre
        rouge = Image.new('RGB', (120, 60), (220, 20, 20))
        a = detourer(rouge)
        self.assertEqual(a.shape[:2], (60, 120))
        self.assertEqual(int(a[..., 3].min()), 255)
        s = variante_sombre(a)                                 # vif : gardé
        self.assertEqual(tuple(int(v) for v in s[30, 60, :3]), (220, 20, 20))

    def test_variante_sombre_encre_blanche_vive_gardee_enclave_gardee(self):
        from PIL import Image
        from apps.ventes.quote_engine.logo import detourer, variante_sombre
        img = _canevas_navy(bord=False)
        # Disque doré avec un carré bleu nuit ENCLAVÉ (l'éclair du soleil).
        from PIL import ImageDraw
        dessin = ImageDraw.Draw(img)
        dessin.ellipse((120, 90, 190, 150), fill=(254, 200, 17))
        img.paste(Image.new('RGB', (10, 10), (2, 47, 83)), (150, 115))
        s = variante_sombre(detourer(img))
        # repère : le rognage commence en x=40, y=50
        self.assertEqual(tuple(int(v) for v in s[30, 60, :3]), (255, 255, 255))   # lettre → blanc
        self.assertEqual(tuple(int(v) for v in s[70, 95, :3]), (254, 200, 17))    # doré gardé
        self.assertEqual(tuple(int(v) for v in s[70, 115, :3]), (2, 47, 83))      # enclave gardée

    def test_asset_taqinor_mesures_et_variantes(self):
        import io
        import numpy as np
        from PIL import Image
        from apps.ventes.quote_engine import logo
        m = logo.mesures()
        self.assertEqual(m['cap'], 128)
        self.assertLess(m['mot'], m['lockup'])
        self.assertGreater(m['largeur'], 6 * m['cap'])
        for variante, bloc, attendu in (('sombre', 'mot', (255, 255, 255)),
                                        ('clair', 'mot', (2, 47, 83))):
            a = np.asarray(Image.open(io.BytesIO(logo.taqinor_png(variante, bloc)))
                           .convert('RGBA')).astype(int)
            opaque = a[a[..., 3] > 250][:, :3]
            lettres = (np.abs(opaque - attendu).max(axis=1) <= 3).sum()
            dore = ((opaque[:, 0] > 240) & (opaque[:, 1] > 190) & (opaque[:, 2] < 30)).sum()
            self.assertGreater(lettres, 30_000, (variante, attendu))
            self.assertGreater(dore, 10_000, variante)
            # L'éclair bleu nuit reste dans le disque, sur les deux variantes.
            self.assertGreater((np.abs(opaque - (2, 47, 83)).max(axis=1) <= 3).sum(), 1_000)
        self.assertEqual(a.shape[0], m['mot'])
        with self.assertRaises(ValueError):
            logo.taqinor_png('gris', 'mot')

    def test_boite_par_capitale_jamais_par_canevas(self):
        from apps.ventes.quote_engine import logo
        m = logo.mesures()
        h, w = logo.boite_mm('entete')
        self.assertAlmostEqual(h, 4.5 * m['mot'] / m['cap'], places=3)
        h2, _ = logo.boite_mm('couverture')
        self.assertAlmostEqual(h2, 6.0 * m['lockup'] / m['cap'], places=3)
        self.assertIn(f'max-height:{h:.2f}mm', logo.css_boite('entete'))
        self.assertIn('height:auto', logo.img_html('AAAA', 'entete'))
        self.assertEqual(logo.img_html('', 'entete'), '')
        self.assertEqual(logo.bloc_taqinor('entete'), 'mot')
        self.assertEqual(logo.bloc_taqinor('hero'), 'mot')
        self.assertEqual(logo.bloc_taqinor('couverture'), 'lockup')
        self.assertLess(logo.boite_mm('hero')[0], 11.0)       # tient sous le bloc titre du héros

    def test_centre_qr_carre_blanc_jamais_deforme(self):
        from PIL import Image
        from apps.ventes.quote_engine import logo
        qr = logo.taqinor_image_qr()
        self.assertEqual(qr.mode, 'RGBA')
        self.assertEqual(qr.width, qr.height)
        self.assertEqual(qr.getpixel((0, 0)), (255, 255, 255, 255))
        import base64
        large = Image.new('RGB', (120, 40), (220, 20, 20))
        carre = logo.image_qr_societe(base64.b64encode(_png_bytes(large)).decode())
        self.assertEqual(carre.width, carre.height)
        rouge = [x for x in range(carre.width) if carre.getpixel((x, carre.height // 2))[:3] == (220, 20, 20)]
        self.assertEqual(len(rouge), 120)                     # largeur intacte
        self.assertIsNone(logo.image_qr_societe('AAAA'))

    def test_logo_societe_cache_et_uri_illisible(self):
        from apps.ventes.quote_engine import logo
        uri = _uri(_canevas_navy())
        logo.societe_png.cache_clear()
        logo.societe_png(uri, 'sombre')
        logo.societe_png(uri, 'sombre')
        self.assertEqual(logo.societe_png.cache_info().misses, 1)
        self.assertGreaterEqual(logo.societe_png.cache_info().hits, 1)
        self.assertNotEqual(logo.societe_png(uri, 'sombre'), logo.societe_png(uri, 'clair'))
        self.assertEqual(logo.societe_b64('data:image/svg+xml;base64,PHN2Zz48L3N2Zz4=', 'sombre'), '')
        self.assertEqual(logo.societe_b64('pas une uri', 'sombre'), '')
        self.assertEqual(logo.societe_b64('', 'clair'), '')
        logo.taqinor_png.cache_clear()
        logo.taqinor_png('sombre', 'lockup')
        logo.taqinor_png('sombre', 'lockup')
        self.assertEqual(logo.taqinor_png.cache_info().misses, 1)
