"""Génère les ressources de marque de Taqinor OS à partir du LOGO OFFICIEL —
le mot-symbole « TAQIN☀R » (le O = soleil porteur d'éclair) utilisé sur les
devis. Source de vérité unique de l'identité : le même logo.png que le moteur
de devis (quote_engine/assets/logo.png), pour que l'app, les PDF et l'icône
PWA partagent strictement la même marque.

Sorties (dans public/) :
  taqinor-logo.png        — mot-symbole rogné, fond rendu TRANSPARENT, texte
                            navy d'origine (pour surfaces claires : carte de
                            login). Bords lissés (alpha = couverture d'encre).
  taqinor-logo-light.png  — même mot-symbole recoloré en BLANC (le navy → blanc,
                            le soleil jaune conservé), fond transparent (pour
                            surfaces sombres + écrans de démarrage).
  splash/apple-splash-<w>x<h>.png — écrans de démarrage iOS (logo clair centré
                            sur le navy de marque), une image par résolution
                            d'iPhone courante. Imprime aussi les balises
                            <link rel="apple-touch-startup-image"> à coller dans
                            index.html.

Les icônes PWA carrées (pwa-192/512/maskable, apple-touch-icon, favicons) sont
générées séparément par gen_pwa_icons.py (glyphe « O » seul, lisible en petit).
Ce script ne les touche pas.

Régénérer :  python scripts/gen_brand_assets.py     (nécessite Pillow)
"""
import os

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
PUBLIC = os.path.join(HERE, "..", "public")
SRC = os.path.join(
    HERE, "..", "..", "backend", "django_core", "apps", "ventes",
    "quote_engine", "assets", "logo.png",
)
NAVY = (15, 23, 42, 255)  # #0f172a — fond de marque (theme/background_color)

# Résolutions (logiques CSS w×h @ dpr) des iPhone courants → pixels réels.
# Une balise par appareil ; iOS ignore simplement une requête non concordante.
IPHONES = [
    (375, 667, 2),   # SE 2/3, 6/7/8
    (414, 896, 2),   # XR, 11
    (375, 812, 3),   # X, XS, 11 Pro, 12/13 mini
    (414, 896, 3),   # XS Max, 11 Pro Max
    (390, 844, 3),   # 12, 13, 14
    (428, 926, 3),   # 12/13 Pro Max, 14 Plus
    (393, 852, 3),   # 14 Pro, 15/15 Pro, 16
    (430, 932, 3),   # 14 Pro Max, 15 Plus/Pro Max, 16 Plus
]


def _is_gold(r, g, b):
    """Pixel du soleil jaune (#F5C100 et nuances)."""
    return r >= 150 and g >= 110 and b <= 170 and (r - b) >= 60


def knockout(src, color=None):
    """Rend le fond blanc transparent, bords lissés (alpha = couverture d'encre).

    - pixels « soleil » jaunes : conservés tels quels (opaques).
    - autres pixels : alpha = 255 − luminance (blanc → transparent, encre →
      opaque) ; couleur = `color` si fourni (recolore l'encre), sinon couleur
      d'origine (conserve le navy).
    Renvoie l'image rognée à son contenu.
    """
    img = src.convert("RGBA")
    px = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if _is_gold(r, g, b):
                continue  # soleil conservé
            lum = 0.3 * r + 0.59 * g + 0.11 * b
            ink = max(0, min(255, round(255 - lum)))
            if ink < 10:
                ink = 0  # bruit quasi-blanc → totalement transparent (rognage)
            if color is not None:
                px[x, y] = (color[0], color[1], color[2], ink)
            else:
                px[x, y] = (r, g, b, ink)
    # Rogner sur le CONTENU réel = bbox du canal alpha (le RGB du fond blanc
    # reste 255 même à alpha 0, donc getbbox() global ne rognerait rien).
    bbox = img.split()[3].getbbox()
    img = img.crop(bbox) if bbox else img
    # Le mot-symbole est un visuel d'UI : on plafonne la largeur (poids/réseau).
    max_w = 800
    if img.width > max_w:
        s = max_w / img.width
        img = img.resize((max_w, max(1, round(img.height * s))), Image.LANCZOS)
    return img


def save(img, name):
    img.save(os.path.join(PUBLIC, name))
    print("wrote", name, img.size)


def splash(logo_light, css_w, css_h, dpr):
    pw, ph = css_w * dpr, css_h * dpr
    canvas = Image.new("RGBA", (pw, ph), NAVY)
    # Logo ~62 % de la largeur, centré.
    target_w = int(pw * 0.62)
    s = target_w / logo_light.width
    lw, lh = target_w, max(1, round(logo_light.height * s))
    lg = logo_light.resize((lw, lh), Image.LANCZOS)
    canvas.alpha_composite(lg, ((pw - lw) // 2, (ph - lh) // 2))
    out = f"splash/apple-splash-{pw}x{ph}.png"
    canvas.convert("RGB").save(os.path.join(PUBLIC, out))
    return out, pw, ph


def main():
    os.makedirs(os.path.join(PUBLIC, "splash"), exist_ok=True)
    src = Image.open(SRC)

    # Mot-symbole sombre (surfaces claires) + clair (surfaces sombres).
    dark = knockout(src)
    light = knockout(src, color=(255, 255, 255))
    save(dark, "taqinor-logo.png")
    save(light, "taqinor-logo-light.png")

    # Écrans de démarrage iOS + balises <link> correspondantes.
    print("\n<!-- Écrans de démarrage iOS (générés par gen_brand_assets.py) -->")
    for css_w, css_h, dpr in IPHONES:
        out, pw, ph = splash(light, css_w, css_h, dpr)
        media = (f"(device-width: {css_w}px) and (device-height: {css_h}px) "
                 f"and (-webkit-device-pixel-ratio: {dpr}) "
                 f"and (orientation: portrait)")
        print(f'    <link rel="apple-touch-startup-image" media="{media}" '
              f'href="/{out}" />')


if __name__ == "__main__":
    main()
