"""Génère les icônes PWA de Taqinor OS à partir du GLYPHE « O » du logo —
le soleil porteur d'éclair de TAQIN[O]R (le O du mot-symbole).

Source : le logo officiel des devis (logo.png, vectoriel rastérisé 1024px). On
isole le seul soleil+éclair (disque doré + rayons + éclair navy), on retire le
fond blanc et les fragments des lettres voisines (N/R), puis on centre le glyphe
sur une tuile navy de marque (solide, jamais transparent — exigé par iOS).

Sorties (remplacent les fichiers existants, mêmes noms -> manifeste inchangé) :
  public/pwa-192.png, public/pwa-512.png,
  public/pwa-maskable-512.png (glyphe dans la zone sûre centrale ~62 %),
  public/apple-touch-icon-180.png,
  public/favicon-32.png, public/favicon-16.png, public/favicon.ico

(favicon.svg reste tel quel : on ne régénère pas un vectoriel depuis un raster.)

Régénérer :  python scripts/gen_pwa_icons.py     (nécessite Pillow)
"""
import math
import os

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
PUBLIC = os.path.join(HERE, "..", "public")
# Logo canonique des devis (source de vérité de l'identité).
SRC = os.path.join(
    HERE, "..", "..", "backend", "django_core", "apps", "ventes",
    "quote_engine", "assets", "logo.png",
)
NAVY = (15, 23, 42, 255)  # #0f172a — fond d'icône de marque (inchangé)

# Le soleil « O » dans logo.png (1024px) : centre et demi-côté couvrant les rayons.
GLYPH_CX, GLYPH_CY, GLYPH_HALF = 741, 449, 134
DISC_R = 76  # rayon interne du disque : l'éclair (navy) est forcément dedans


def extract_glyph():
    src = Image.open(SRC).convert("RGBA")
    g = src.crop((
        GLYPH_CX - GLYPH_HALF, GLYPH_CY - GLYPH_HALF,
        GLYPH_CX + GLYPH_HALF, GLYPH_CY + GLYPH_HALF,
    )).convert("RGBA")
    w, h = g.size
    c = w / 2
    px = g.load()
    for y in range(h):
        for x in range(w):
            r, gr, b, _ = px[x, y]
            d = math.hypot(x - c, y - c)
            gold = r >= 150 and gr >= 110 and b <= 170 and (r - b) >= 60
            lum = 0.3 * r + 0.59 * gr + 0.11 * b
            bolt = d < DISC_R and lum < 150 and b >= r - 10 and not gold
            if not (gold or bolt):
                px[x, y] = (r, gr, b, 0)  # fond blanc, fragments de lettres, halos
    return g.crop(g.getbbox())


def tile(glyph, size, frac, out):
    # Tuile navy OPAQUE (les icônes installées exigent un fond solide).
    t = Image.new("RGBA", (size, size), NAVY)
    w, h = glyph.size
    s = int(size * frac) / max(w, h)
    gg = glyph.resize((max(1, round(w * s)), max(1, round(h * s))), Image.LANCZOS)
    t.alpha_composite(gg, ((size - gg.width) // 2, (size - gg.height) // 2))
    t.convert("RGB").save(os.path.join(PUBLIC, out))


def make_ico(glyph, out="favicon.ico"):
    """Favicon multi-tailles (16/32/48) : même glyphe sur tuile navy opaque."""
    base = Image.new("RGBA", (64, 64), NAVY)
    w, h = glyph.size
    s = int(64 * 0.84) / max(w, h)
    gg = glyph.resize((max(1, round(w * s)), max(1, round(h * s))), Image.LANCZOS)
    base.alpha_composite(gg, ((64 - gg.width) // 2, (64 - gg.height) // 2))
    base.convert("RGB").save(
        os.path.join(PUBLIC, out), sizes=[(16, 16), (32, 32), (48, 48)])


def main():
    glyph = extract_glyph()
    print("glyphe nettoyé :", glyph.size)
    # Réguliers : petite marge égale (~80 % du cadre).
    tile(glyph, 192, 0.80, "pwa-192.png")
    tile(glyph, 512, 0.80, "pwa-512.png")
    tile(glyph, 180, 0.80, "apple-touch-icon-180.png")
    # Maskable : glyphe dans la zone sûre centrale (~62 %) -> jamais rogné
    # (largement dans la zone sûre de 80 % exigée par la spec maskable).
    tile(glyph, 512, 0.62, "pwa-maskable-512.png")
    # Favicons (onglets navigateur). Glyphe un peu plus grand aux petites
    # tailles pour rester lisible.
    tile(glyph, 32, 0.86, "favicon-32.png")
    tile(glyph, 16, 0.90, "favicon-16.png")
    make_ico(glyph)
    print("icônes écrites dans", os.path.normpath(PUBLIC))


if __name__ == "__main__":
    main()
