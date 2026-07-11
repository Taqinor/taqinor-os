# flake8: noqa
"""TAQINOR quote engine — RESIDENTIAL renderer (brand tokens + shared CSS).

The redesigned 3-page residential proposal. Part of the single quote engine
(`apps/ventes/quote_engine`); selected for `mode_installation == residentiel`
by `residential.renderer`. Reuses the engine's bundled fonts/logo.
"""
from __future__ import annotations
import base64
import functools
from html import escape
from pathlib import Path

# ── SCA27 — littéraux d'identité du fondateur (repli byte-identique) ──────────
# Reproduisent EXACTEMENT la ligne de pied de page historique. Tant qu'aucune
# identité société n'est fournie dans ``data["entreprise"]`` (CompanyProfile),
# le pied de page reste strictement identique à aujourd'hui.
_FOOT_DEFAULT_NOM = "TAQINOR"
_FOOT_DEFAULT_EMAIL = "contact@taqinor.com"
_FOOT_DEFAULT_TEL = "+212 6 61 85 04 10"

# Engine assets (fonts + logo), one level up at quote_engine/assets.
_LIVE_ASSETS = Path(__file__).resolve().parent.parent / "assets"
_FONT_DIR = _LIVE_ASSETS / "fonts"

# ── Brand palette (extracted from the live engine) ──────────────────────────
C = {
    "navy":      "#1A2B4A",
    "navy_900":  "#12203b",
    "navy_700":  "#243a5e",
    "gold":      "#F5A623",
    "gold_soft": "#E8A020",
    "green":     "#16A34A",
    "green_bg":  "#e8f5e9",
    "ink":       "#1f2937",
    "muted":     "#6b7280",
    "muted_2":   "#9BA3AE",
    "line":      "#E5E7EB",
    "line_soft": "#EFF1F4",
    "paper":     "#FFFFFF",
    "wash":      "#F7F9FC",
    "wash_navy": "#0f1d36",
    "blue":      "#2C5F8A",
}

FONT_DISPLAY = "'DM Serif Display', Georgia, serif"
FONT_SERIF = "'Playfair Display', Georgia, serif"
FONT_SANS = "'DM Sans', system-ui, sans-serif"


def _font_b64(name: str) -> str:
    p = _FONT_DIR / name
    return base64.b64encode(p.read_bytes()).decode() if p.exists() else ""


@functools.lru_cache(maxsize=1)
def logo_dark_b64() -> str:
    """Logo recolored white-on-transparent for navy headers.

    QX8 — pur (aucun argument, lit un asset figé) : le recolorage par pixel +
    l'encodage b64 sont mis en cache une fois par processus, donc une rafale de
    rendus ne refait plus la boucle par pixel."""
    from PIL import Image
    import io
    p = _LIVE_ASSETS / "logo.png"
    img = Image.open(p).convert("RGBA")
    px = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if r > 230 and g > 230 and b > 230:          # white bg -> transparent
                px[x, y] = (0, 0, 0, 0)
            elif r < 120 and g < 120 and b < 120:        # dark ink -> white
                px[x, y] = (255, 255, 255, a)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


@functools.lru_cache(maxsize=1)
def logo_color_b64() -> str:
    # QX8 — asset figé, encodé une fois par processus (cache pur).
    p = _LIVE_ASSETS / "logo.png"
    return base64.b64encode(p.read_bytes()).decode()


# This renderer's own bundled assets (the page-1 hero photo).
_RESID_ASSETS = Path(__file__).resolve().parent / "assets"


def hero_image_b64(kwc=None, mode: str = "residentiel") -> str:
    """Base64 JPEG of the page-1 hero photo (real installation), chosen by
    NEAREST power (kWc) from the shared installation-photo library
    (quote_engine/assets/installations/) instead of a single fixed image. Falls
    back to this package's bundled hero.jpg, then "" (flat navy)."""
    try:
        from .. import installations          # Django: quote_engine.installations
    except ImportError:                        # standalone dev harness
        import installations
    b = installations.pick_b64(kwc, mode)
    if b:
        return b
    p = _RESID_ASSETS / "hero.jpg"
    return base64.b64encode(p.read_bytes()).decode() if p.exists() else ""


@functools.lru_cache(maxsize=1)
def font_face_css() -> str:
    # QX8 — @font-face (6 woff2 encodés en b64) figé, calculé une fois par
    # processus : plus de relecture/encodage des polices à chaque rendu.
    faces = [
        ("DM Serif Display", 400, "DMSerifDisplay-400.woff2"),
        ("Playfair Display", 400, "PlayfairDisplay-400.woff2"),
        ("Playfair Display", 700, "PlayfairDisplay-700.woff2"),
        ("DM Sans", 400, "DMSans-400.woff2"),
        ("DM Sans", 500, "DMSans-500.woff2"),
        ("DM Sans", 700, "DMSans-700.woff2"),
    ]
    out = []
    for fam, wt, fn in faces:
        b64 = _font_b64(fn)
        if not b64:
            continue
        out.append(
            f"@font-face{{font-family:'{fam}';font-weight:{wt};font-style:normal;"
            f"src:url('data:font/woff2;base64,{b64}') format('woff2');}}")
    return "\n".join(out)


def fmt(n) -> str:
    """1234567 -> '1 234 567' (thin-space groups, FR style)."""
    try:
        n = round(float(n))
    except (TypeError, ValueError):
        return str(n)
    return f"{n:,.0f}".replace(",", " ")


# French name particles that stay lowercase inside a name.
_NAME_PARTICLES = {"de", "du", "des", "la", "le", "les", "van", "von",
                   "el", "al", "ben", "bin", "ould", "aït", "ait"}


def titlecase_name(name) -> str:
    """Display-case a person's name: 'meryem hida' -> 'Meryem Hida'.

    Leaves already-mixed-case tokens (e.g. 'McAdam', 'TAQINOR') untouched, keeps
    French/Arabic particles lowercase mid-name, and splits on spaces/hyphens so
    'jean-pierre' -> 'Jean-Pierre'. Never raises on odd input.
    """
    s = str(name or "").strip()
    if not s:
        return ""

    def cap_token(tok, first):
        if not tok:
            return tok
        # Respect intentional internal capitals (McAdam, TAQINOR, d'Or).
        if tok[1:] != tok[1:].lower():
            return tok
        low = tok.lower()
        if not first and low in _NAME_PARTICLES:
            return low
        return low[:1].upper() + low[1:]

    out = []
    for i, word in enumerate(s.split(" ")):
        parts = word.split("-")
        out.append("-".join(
            cap_token(p, first=(i == 0 and j == 0))
            for j, p in enumerate(parts)))
    return " ".join(out)


def join_meta(*parts, sep=" · ") -> str:
    """Join non-empty, stripped meta fragments with `sep` (no dangling commas/dots
    when a field like the address or city is missing)."""
    clean = [str(p).strip().strip(",").strip() for p in parts if p and str(p).strip()]
    return sep.join(c for c in clean if c)


def fiche_slug(designation, marque="") -> str:
    """Map an equipment line to its fiche-technique page slug on taqinor.ma.

    Keyword-classified on the designation + brand, EXACTLY mirroring the slugs
    built by docs/WEB_PLAN.md W141–W145 (the /produits/<slug> pages), so a quote
    link always points at a real datasheet page. Returns '' when no datasheet is
    known (TAQINOR's own structures/socles/installation/transport/services)."""
    blob = f"{designation} {marque}".lower()
    if "panneau" in blob or "panel" in blob:
        return "jinko-710" if "jinko" in blob else "canadian-solar-710"
    if "onduleur" in blob or "inverter" in blob:
        if "hybride" in blob or "hybrid" in blob:
            return "onduleur-deye-hybride"
        if "réseau" in blob or "reseau" in blob or "injection" in blob:
            return "onduleur-huawei-reseau"
        return "onduleur-huawei-reseau"
    if "batterie" in blob or "battery" in blob:
        return "batterie-dyness"
    # QF9 — le Smart Meter et la Clé Wifi (dongle) sont des accessoires Huawei :
    # le builder retire déjà ces lignes d'un devis non-Huawei. Garde-fou : ne
    # renvoyer leur fiche Huawei que si la ligne est bien Huawei, pour qu'une
    # ligne obsolète glissée jusqu'ici ne pointe pas vers une fiche Huawei.
    if "smart meter" in blob or "compteur" in blob:
        return "smart-meter-huawei" if "huawei" in blob else ""
    if "dongle" in blob or "wifi" in blob:
        return "wifi-dongle-huawei" if "huawei" in blob else ""
    return ""


# SCA27 — les fiches-techniques (/produits/<slug>) sont des pages RÉELLES de
# taqinor.ma (le fondateur) ; leurs slugs (jinko-710, batterie-dyness…) n'existent
# que là. On ne les lie donc QUE lorsque la base pointe sur taqinor.ma : le PDF
# d'un autre locataire n'affiche plus un lien produit vers le site du fondateur
# (la fiche est alors omise → texte simple). Rendu du fondateur inchangé.
_FICHE_HOST = "taqinor.ma"


def fiche_href(designation, marque="", produits_base="taqinor.ma/produits") -> str:
    """Full https URL of a line's fiche-technique page, or '' if none.

    SCA27 — omise si ``produits_base`` ne pointe pas sur ``taqinor.ma`` (seul
    hôte des fiches) : liens produits = site du fondateur uniquement, sinon
    omis. Base par défaut = taqinor.ma → comportement fondateur byte-identique.
    """
    slug = fiche_slug(designation, marque)
    if not slug:
        return ""
    base = (produits_base or "taqinor.ma/produits").strip().rstrip("/")
    if _FICHE_HOST not in base.lower():
        return ""
    if not base.startswith("http"):
        base = "https://" + base
    return f"{base}/{slug}"


def base_css() -> str:
    """Page frame + design tokens shared by all three pages."""
    return f"""
{font_face_css()}
* {{ margin:0; padding:0; box-sizing:border-box; }}
@page {{ size: A4; margin: 0; }}
html, body {{ font-family:{FONT_SANS}; color:{C['ink']}; -weasy-hyphens:none; }}
.page {{
  position:relative; width:210mm; height:297mm; overflow:hidden;
  background:{C['paper']}; page-break-after:always;
}}
.page:last-child {{ page-break-after:auto; }}
.pad {{ padding:14mm 14mm 0 14mm; }}
.row {{ display:flex; }}
.gold {{ color:{C['gold']}; }}
.muted {{ color:{C['muted']}; }}
.serif {{ font-family:{FONT_SERIF}; }}
.display {{ font-family:{FONT_DISPLAY}; }}
.kicker {{ font-size:8.5pt; letter-spacing:.22em; text-transform:uppercase;
  color:{C['muted_2']}; font-weight:700; }}
.h-sec {{ font-family:{FONT_SERIF}; font-weight:700; font-size:15pt;
  color:{C['navy']}; }}

/* Shared footer (FIXED — no overlapping chips like the live page-1 bug) */
.foot {{
  position:absolute; left:0; right:0; bottom:0; height:13mm;
  background:{C['navy']}; color:#cdd5e2; display:flex; align-items:center;
  justify-content:space-between; padding:0 14mm; font-size:7.6pt;
}}
.foot b {{ color:#fff; font-weight:700; letter-spacing:.04em; }}
.foot a {{ color:{C['gold']}; text-decoration:none; }}

/* Reusable card */
.card {{ border:1px solid {C['line']}; border-radius:12px; background:{C['paper']}; }}
.pill {{ display:inline-block; padding:3px 10px; border-radius:999px;
  font-size:7.6pt; font-weight:700; letter-spacing:.04em; }}
"""


# ── Identité société — littéraux d'identité HISTORIQUES (Taqinor), défauts ──
# de repli. Toute valeur d'identité société vide retombe sur ces littéraux, de
# sorte qu'un devis sans profil enrichi reste rendu strictement à l'identique et
# qu'aucune identité d'un autre tenant ne fuit dans le rendu résidentiel.
_DEFAULT_BRAND = "TAQINOR"
_DEFAULT_EMAIL = "contact@taqinor.com"
_DEFAULT_PHONE = "+212 6 61 85 04 10"
_DEFAULT_SITE = "taqinor.ma"


def _esc(v) -> str:
    """Échappe le minimum HTML pour une valeur d'identité insérée en texte."""
    return (str(v or "").replace("&", "&amp;")
            .replace("<", "&lt;").replace(">", "&gt;"))


def company_identity(data: dict) -> dict:
    """Résout l'identité société AFFICHÉE (marque/contact/site) depuis
    ``data['entreprise']`` — QX7 (chips/marque) + SCA27 (tenant-safe).

    ``data['entreprise']`` est le dict renvoyé par
    ``parametres.selectors.company_identity`` (threadé par le builder). Sémantique
    SCA27/DC1 par champ : le NOM ne remplace le littéral fondateur que s'il est
    fourni ; email/téléphone/site ne remplacent le littéral fondateur que
    lorsqu'ils sont renseignés. Donc :
      • une société AVEC profil enrichi voit SON identité partout (plus de fuite
        multi-tenant) ;
      • une société SANS profil (ou Taqinor) garde une sortie byte-identique.
    La bande légale complète (capital/RC/ICE/gérant) N'est PAS construite ici —
    elle est composée par ``trust.py`` (SCA27) directement depuis
    ``data['entreprise']`` avec le littéral fondateur en repli. Toutes les valeurs
    renvoyées sont des chaînes déjà échappées, prêtes à insérer.
    """
    ent = data.get("entreprise") or {}
    nom = (ent.get("nom") or "").strip()
    email = (ent.get("email") or "").strip()
    tel = (ent.get("telephone") or "").strip()
    adresse = (ent.get("adresse") or "").strip()
    # Site : le builder a déjà résolu ``data['site_url']`` depuis le champ
    # CANONIQUE ``site_web`` (SCA27, normalisé) ; repli Taqinor si vide.
    site = (data.get("site_url") or "").strip().rstrip("/") or _DEFAULT_SITE

    return {
        # Marque courte (footer, « Pourquoi … », signature TAQINOR).
        "brand": _esc(nom.upper()) if nom else _DEFAULT_BRAND,
        "brand_name": _esc(nom) if nom else _DEFAULT_BRAND,
        "email": _esc(email) if email else _DEFAULT_EMAIL,
        "phone": _esc(tel) if tel else _DEFAULT_PHONE,
        "site": _esc(site),
        "adresse": _esc(adresse),
        # A-t-on une vraie identité société (au moins un champ renseigné) ?
        "has_profile": bool(nom or email or tel or adresse
                            or (data.get("site_url") or "").strip()),
    }


def page_footer(data: dict, ident: dict | None = None, total_pages: int = 3) -> str:
    # QX6 — le pied lit le NOMBRE RÉEL de pages rendues (jamais « / 3 » codé).
    ident = ident or company_identity(data)
    site = ident.get("site") or _DEFAULT_SITE
    return f"""
<div class="foot">
  <div><b>{ident['brand_name']}</b> &nbsp;·&nbsp; {ident['email']} &nbsp;·&nbsp; {ident['phone']}</div>
  <div>Page {{page}} / {total_pages} &nbsp;·&nbsp; Réf. {data['ref']} &nbsp;·&nbsp; <a>{site}</a></div>
</div>
"""
