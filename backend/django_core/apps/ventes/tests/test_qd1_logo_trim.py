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

from django.test import TestCase

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
