"""R3 — LE logo des documents rendus par le moteur, en un module PUR (PIL +
numpy ; aucune base, aucun Django, aucune dépendance nouvelle).

Deux sources, UN traitement :

* le logo Taqinor embarqué, ``assets/logo.png`` — octet pour octet le
  ``taqinor_main.png`` du pack officiel « Taqinor_Logo_Pack_Final »
  (17/10/2025, dossier Marketing/Taqinor_Logo) : mot-marque « TAQIN☀R » bleu
  nuit, le « O » remplacé par le soleil doré à 8 rayons traversé d'un éclair
  bleu nuit, tagline « TAQA. INNOVATION. NOR. » dessous. Couleurs LUES sur le
  fichier (mode des pixels intérieurs) : ``BLEU_NUIT`` #022F53, ``DORE``
  #FEC811. Le canevas carré 1024 est blanc et l'art n'en occupe que 30 % de la
  hauteur : imprimé tel quel il faisait un petit carré blanc au logo minuscule ;
* le logo TÉLÉVERSÉ d'une société (APDF4, ``CompanyProfile.logo_key``, reçu en
  data URI) — même pipeline, ligne pour ligne.

Pipeline (``detourer`` puis ``variante_sombre``) :

1. **rognage au trait** (bord utile de l'image, jamais le canevas) ;
2. **détourage** : un fond UNI et CLAIR (médiane du bord) devient transparent
   par DISTANCE AU FOND avec un alpha PROGRESSIF — jamais un seuil binaire.
   L'alpha d'un pixel de bord est la fraction du trajet fond → encre où il se
   trouve (l'encre est le point où le rayon fond→pixel sort du cube RGB :
   exact pour une encre sombre ou saturée — bleu nuit, doré, noir, rouge…) ;
   sa couleur est ramenée sur l'encre (dé-frange). Les pixels à plus de deux
   pixels du fond restent opaques quelle que soit leur teinte (encre grise) ;
3. **variante sombre** (en-têtes bleu nuit) : l'encre SOMBRE qui touche le fond
   passe en blanc (rampe sur la valeur max des canaux : ≤ 100 blanc, ≥ 150
   gardé) ; les couleurs VIVES (le doré du soleil, un rouge de marque) et les
   encres ENCLAVÉES (l'éclair dans le disque du soleil) restent — comme le
   logotype du site (``apps/web`` ``Logo.astro`` theme="dark") ;
4. **cache** ``lru_cache`` : l'asset une fois par processus et par variante,
   les logos téléversés par data URI (``_CACHE_SOCIETE`` entrées).

Choix PNG HD plutôt que vecteur : le seul original officiel est un raster
(les .svg/.eps/.pdf du pack embarquent ce même PNG) ; aucune police du moteur
ne reproduit les lettres du logo (le site, lui, approxime en Archivo) ; à
300 dpi la capitale imprimée (≤ 6 mm = 71 px) reste sous les 128 px de la
source — net sans ré-échantillonnage vers le haut.

Dimensionnement : par la HAUTEUR DE CAPITALE du mot-marque (``CAPITALE_MM``,
par rôle d'emplacement), jamais par le canevas ; la tagline n'est imprimée que
là où la hauteur le permet (``AVEC_TAGLINE``). Rendu dégradé : asset absent ⇒
``taqinor_b64`` rend '' et l'appelant garde son repli texte.
"""
from __future__ import annotations

import base64
import functools
import io
import logging
from html import escape
from pathlib import Path

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

ASSETS = Path(__file__).resolve().parent / "assets"
CHEMIN_LOGO = ASSETS / "logo.png"

#: Couleurs de marque lues sur ``assets/logo.png`` (modes des pixels intérieurs).
BLEU_NUIT = "#022F53"
DORE = "#FEC811"

#: Hauteur de CAPITALE du mot-marque imprimé, par rôle, en millimètres :
#: ``couverture`` (héros navy commercial/industriel, page 1 legacy, page 1
#: agricole), ``hero`` (héros photo résidentiel de 53 mm : le bloc titre absolu
#: ne laisse que ~11 mm au logo), ``onepage`` (bande de 21 mm), ``entete``.
CAPITALE_MM = {"couverture": 6.0, "hero": 5.5, "onepage": 5.0, "entete": 4.5}
#: La tagline accompagne le mot-marque seulement là où la hauteur le permet.
AVEC_TAGLINE = {"couverture": True, "hero": False, "onepage": True, "entete": False}
#: Largeur maximale d'un logo (téléversé) dans la boîte, en capitales.
_LARGEUR_MAX_EN_CAPITALES = 9.0

_VARIANTES = ("clair", "sombre")
_BLOCS = ("mot", "lockup", "embleme")
_FOND_CLAIR_MIN = 180.0     # luminance minimale d'un fond uni détourable
_BORD_UNI_MAX = 12.0        # écart (canal) toléré entre un pixel du bord et le fond
_BORD_UNI_PART = 0.5        # part minimale du bord qui doit être du fond (majorité : un logo rogné touche ses bords)
_COTE_MAX = 1024            # grand côté maximal d'un logo téléversé (la boîte max = 54 mm ≈ 640 px à 300 dpi)
_TRANSPARENCE_UTILE = 0.01  # part de pixels non opaques au-delà de laquelle l'image est déjà détourée
_VIF_MIN, _VIF_MAX = 100.0, 150.0   # rampe « encre sombre → blanc » (valeur max canal)
_ALPHA_VISIBLE = 0.02
_CACHE_SOCIETE = 16


# ── outils numpy ─────────────────────────────────────────────────────────────

def _rgba(img) -> np.ndarray:
    return np.asarray(img.convert("RGBA")).astype(np.float32)


def _luminance(rgb: np.ndarray) -> np.ndarray:
    return rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114


def _png(a: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA").save(buf, "PNG")
    return buf.getvalue()


def _dilater(m: np.ndarray) -> np.ndarray:
    """Dilatation 4-connexe d'un masque booléen."""
    d = m.copy()
    d[1:, :] |= m[:-1, :]
    d[:-1, :] |= m[1:, :]
    d[:, 1:] |= m[:, :-1]
    d[:, :-1] |= m[:, 1:]
    return d


def _atteignable(graine: np.ndarray, passable: np.ndarray) -> np.ndarray:
    """Pixels de ``passable`` reliés à ``graine`` (propagation géodésique,
    bornée par le périmètre de l'image)."""
    m = graine & passable
    for _ in range(sum(m.shape)):
        d = _dilater(m) & passable
        if (d == m).all():
            break
        m = d
    return m


def _bbox(masque: np.ndarray):
    ys, xs = np.where(masque)
    if not len(ys):
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def _rogner(a: np.ndarray) -> np.ndarray:
    b = _bbox(a[..., 3] > _ALPHA_VISIBLE * 255)
    return a if b is None else a[b[1]:b[3], b[0]:b[2]]


def _fond(a: np.ndarray):
    """Couleur du fond : médiane des pixels opaques du bord — ``None`` si le
    bord n'est pas majoritairement uni ou pas clair (rien n'est alors détouré).

    Un logo déjà ROGNÉ au trait (``utils.pdf._trim_image_whitespace``, sur le
    chemin /proposal et facture) a de l'encre sur ses quatre bords : le fond
    est la couleur MAJORITAIRE du bord (≥ ``_BORD_UNI_PART`` des pixels à
    ``_BORD_UNI_MAX`` près de la médiane), jamais l'écart moyen."""
    # Une image qui porte DÉJÀ une transparence utile (PNG détouré, rogné à
    # sa boîte alpha : une encre blanche touche alors ses bords) n'est jamais
    # re-détourée — son fond est sa transparence.
    if (a[..., 3] < 250).mean() > _TRANSPARENCE_UTILE:
        return None
    bord = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
    bord = bord[bord[:, 3] > 250][:, :3]
    if len(bord) < 4:
        return None
    med = np.median(bord, axis=0)
    if (np.abs(bord - med).max(axis=1) <= _BORD_UNI_MAX).mean() < _BORD_UNI_PART:
        return None
    if _luminance(med) < _FOND_CLAIR_MIN:
        return None
    return med


def _alpha_depuis_fond(rgb: np.ndarray, fond: np.ndarray) -> np.ndarray:
    """Fraction fond → encre de chaque pixel, l'encre étant la sortie du cube
    RGB le long du rayon fond → pixel (exacte pour une encre sombre/saturée)."""
    delta = rgb - fond
    dist = np.abs(delta).max(axis=2)
    # Pour chaque canal, facteur t tel que fond + t·delta touche 0 ou 255.
    with np.errstate(divide="ignore", invalid="ignore"):
        t_bas = np.where(delta < 0, -fond / delta, np.inf)
        t_haut = np.where(delta > 0, (255.0 - fond) / delta, np.inf)
    t = np.minimum(t_bas, t_haut).min(axis=2)        # ≥ 1 par construction
    t = np.where(np.isfinite(t), np.maximum(t, 1.0), 1.0)
    alpha = np.where(dist > 0, 1.0 / t, 0.0)
    return np.clip(alpha, 0.0, 1.0)


# ── pipeline ─────────────────────────────────────────────────────────────────

def detourer(img) -> np.ndarray:
    """Tableau RGBA float : rogné au trait, fond uni clair → transparent par
    alpha progressif, couleurs de bord dé-frangées. Fond non uni ou sombre :
    seul le rognage (par l'alpha existant) s'applique."""
    a = _rgba(img)
    fond = _fond(a)
    if fond is not None:
        rgb = a[..., :3]
        alpha = _alpha_depuis_fond(rgb, fond)
        # Encre grise : à plus de deux pixels du fond, un pixel reste opaque.
        proche_fond = _dilater(_dilater(alpha < _ALPHA_VISIBLE))
        alpha = np.where(proche_fond, alpha, np.where(alpha > 0, 1.0, 0.0))
        with np.errstate(divide="ignore", invalid="ignore"):
            encre = fond + (rgb - fond) / np.maximum(alpha, 1e-6)[..., None]
        a[..., :3] = np.where(alpha[..., None] > 0, np.clip(encre, 0, 255), rgb)
        a[..., 3] = a[..., 3] * alpha
    return _rogner(a)


def variante_sombre(a: np.ndarray) -> np.ndarray:
    """Variante pour fond sombre : l'encre sombre reliée au fond transparent
    passe en blanc ; couleurs vives et encres enclavées inchangées."""
    a = a.copy()
    alpha = a[..., 3] / 255.0
    valeur = a[..., :3].max(axis=2)
    blancheur = np.clip((_VIF_MAX - valeur) / (_VIF_MAX - _VIF_MIN), 0.0, 1.0)
    fond = alpha < 0.5
    atteint = _atteignable(fond, fond | (blancheur > 0))
    w = (blancheur * atteint * (alpha > 0))[..., None]
    a[..., :3] = a[..., :3] + w * (255.0 - a[..., :3])
    return a


def _segments_lignes(a: np.ndarray, ecart_min: int):
    """Blocs de lignes non vides séparés d'au moins ``ecart_min`` lignes vides."""
    pleines = np.where((a[..., 3] > _ALPHA_VISIBLE * 255).any(axis=1))[0]
    if not len(pleines):
        return []
    segs, debut, prec = [], int(pleines[0]), int(pleines[0])
    for y in pleines[1:]:
        if y - prec > ecart_min:
            segs.append((debut, prec + 1))
            debut = int(y)
        prec = int(y)
    segs.append((debut, prec + 1))
    return segs


def _est_dore(rgb: np.ndarray) -> np.ndarray:
    return (rgb[..., 0] > 200) & (rgb[..., 1] > 140) & (rgb[..., 2] < 120)


# ── logo TAQINOR embarqué ────────────────────────────────────────────────────

@functools.lru_cache(maxsize=1)
def _lockup_clair():
    """Le logo officiel détouré (mot-marque + tagline), ou ``None`` sans asset."""
    if not CHEMIN_LOGO.exists():
        return None
    with Image.open(CHEMIN_LOGO) as img:
        return detourer(img)


@functools.lru_cache(maxsize=1)
def mesures() -> dict:
    """Géométrie LUE sur l'asset : hauteur de capitale, du mot-marque, du
    lockup (avec tagline) et largeur, en pixels ; ``{}`` sans asset."""
    a = _lockup_clair()
    if a is None:
        return {}
    h, w = a.shape[:2]
    segs = _segments_lignes(a, max(2, h // 50))
    fin_mot = segs[-2][1] if len(segs) >= 2 else h
    mot = a[:fin_mot]
    # Capitale : hauteur de la première lettre (le « T », colonnes de gauche).
    gauche = mot[:, : max(1, int(w * 0.12)), 3] > 127
    lignes = np.where(gauche.any(axis=1))[0]
    cap = int(lignes.max() - lignes.min() + 1) if len(lignes) else fin_mot
    return {"cap": cap, "mot": int(fin_mot), "lockup": int(h), "largeur": int(w)}


def _bloc(a: np.ndarray, bloc: str) -> np.ndarray:
    m = mesures()
    if bloc == "mot":
        return a[: m["mot"]]
    if bloc == "embleme":
        b = _bbox(_est_dore(a[..., :3]) & (a[..., 3] > 127))
        if b is None:           # asset sans doré : le mot-marque tient lieu d'emblème
            return a[: m["mot"]]
        x0, y0, x1, y1 = b
        cote = max(x1 - x0, y1 - y0)
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        x0, y0 = max(0, cx - cote // 2), max(0, cy - cote // 2)
        return a[y0:y0 + cote, x0:x0 + cote]
    return a


@functools.lru_cache(maxsize=8)
def taqinor_png(variante: str = "sombre", bloc: str = "lockup") -> bytes:
    """PNG RGBA du logo Taqinor : ``variante`` clair|sombre, ``bloc``
    mot|lockup|embleme ; ``b''`` sans asset."""
    if variante not in _VARIANTES or bloc not in _BLOCS:
        raise ValueError(f"logo Taqinor : variante {variante!r} / bloc {bloc!r}")
    a = _lockup_clair()
    if a is None:
        return b""
    a = _bloc(a, bloc)
    if variante == "sombre":
        a = variante_sombre(a)
    return _png(a)


def taqinor_b64(variante: str = "sombre", bloc: str = "lockup") -> str:
    return base64.b64encode(taqinor_png(variante, bloc)).decode()


# ── logo téléversé d'une société (APDF4) ─────────────────────────────────────

def _decoder_uri(uri: str):
    """Image PIL d'une data URI base64, RAMENÉE à ``_COTE_MAX`` px de grand
    côté (``CompanyProfile.logo_key`` n'a aucune limite : un PNG 4000² coûtait
    ~1,6 Go en float32 sur ce pipeline) ; ``None`` si ce n'est pas une data URI."""
    entete, _, charge = (uri or "").partition(",")
    if ";base64" not in entete:
        return None
    img = Image.open(io.BytesIO(base64.b64decode(charge)))
    img.load()
    if max(img.size) > _COTE_MAX:
        img = img.convert("RGBA")
        img.thumbnail((_COTE_MAX, _COTE_MAX), Image.LANCZOS)
    return img


@functools.lru_cache(maxsize=_CACHE_SOCIETE)
def societe_png(uri: str, variante: str = "sombre") -> bytes:
    """PNG RGBA du logo téléversé (data URI) rogné, détouré, en variante
    ``clair`` ou ``sombre`` ; ``b''`` si l'URI n'est pas une image raster."""
    if variante not in _VARIANTES:
        raise ValueError(f"logo société : variante {variante!r}")
    try:
        img = _decoder_uri(uri)
        if img is None:
            return b""
        a = detourer(img)
        if variante == "sombre":
            a = variante_sombre(a)
        return _png(a)
    except Exception:  # noqa: BLE001 — SVG / corrompu / mode exotique : traité comme absent (D-ENF22-BLE001)
        logger.warning("logo.societe_png : erreur ignorée (mode dégradé)", exc_info=True)
        return b""


def societe_b64(uri: str, variante: str = "sombre") -> str:
    png = societe_png(uri, variante)
    return base64.b64encode(png).decode() if png else ""


# ── centre des QR ────────────────────────────────────────────────────────────

def _carre_blanc(a: np.ndarray, marge: float = 0.08) -> Image.Image:
    """Image RGBA carrée, fond blanc opaque, le logo centré avec une marge —
    ``qrcode`` redimensionne l'image centrale en CARRÉ (un logo large serait
    écrasé) et la colle telle quelle : le blanc fait la zone de silence."""
    h, w = a.shape[:2]
    cote = int(round(max(h, w) * (1 + 2 * marge))) or 1
    fond = Image.new("RGBA", (cote, cote), (255, 255, 255, 255))
    logo = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA")
    fond.alpha_composite(logo, ((cote - w) // 2, (cote - h) // 2))
    return fond  # RGBA opaque : ``qrcode`` compose, le PNG du QR reste RGBA


@functools.lru_cache(maxsize=1)
def taqinor_image_qr():
    """Centre des QR Taqinor : l'emblème (soleil, rayons, éclair) de l'asset —
    carré, lisible à 4-5 mm là où le mot-marque entier serait une tache ;
    ``None`` sans asset."""
    a = _lockup_clair()
    return None if a is None else _carre_blanc(_bloc(a, "embleme"))


def image_qr_societe(b64: str):
    """Centre des QR d'une société : son logo (base64 PNG, déjà clair) posé
    dans un carré blanc, jamais déformé ; ``None`` si illisible."""
    try:
        img = Image.open(io.BytesIO(base64.b64decode(b64)))
        img.load()
    except Exception:  # noqa: BLE001 — illisible : aucun logo central (D-ENF22-BLE001)
        logger.warning("logo.image_qr_societe : logo société illisible, QR sans image centrale", exc_info=True)
        return None
    return _carre_blanc(_rgba(img))


# ── HTML ─────────────────────────────────────────────────────────────────────

def boite_mm(role: str) -> tuple:
    """(hauteur, largeur) maximales de la boîte du logo pour un rôle, en mm :
    la hauteur découle de la capitale (``CAPITALE_MM``) et de la géométrie lue
    sur l'asset — avec ou sans tagline selon ``AVEC_TAGLINE``."""
    cap = CAPITALE_MM[role]
    m = mesures()
    if not m:
        return cap * 2.0, cap * _LARGEUR_MAX_EN_CAPITALES
    bloc = "lockup" if AVEC_TAGLINE[role] else "mot"
    return cap * m[bloc] / m["cap"], cap * _LARGEUR_MAX_EN_CAPITALES


def css_boite(role: str) -> str:
    h, w = boite_mm(role)
    return (f"max-height:{h:.2f}mm;max-width:{w:.1f}mm;width:auto;height:auto;"
            "object-fit:contain;display:block;")


def img_html(b64: str, role: str, alt: str = "logo", style: str = "") -> str:
    """Balise ``<img>`` du logo (base64 PNG) dimensionnée par la capitale du
    rôle ; '' sans image."""
    if not b64:
        return ""
    return (f'<img src="data:image/png;base64,{b64}" alt="{escape(alt, quote=True)}" '
            f'style="{css_boite(role)}{style}">')


def est_taqinor(b64: str):
    """Variante (« clair » | « sombre ») si ``b64`` EST le lockup Taqinor —
    l'asset embarqué, ou le même carré 1024 TÉLÉVERSÉ par le profil (cas de la
    prod) : égalité des octets en sortie du même pipeline, jamais un nom."""
    if not b64:
        return None
    for variante in _VARIANTES:
        if b64 == taqinor_b64(variante, "lockup"):
            return variante
    return None


def pour_role(b64: str, role: str) -> str:
    """Le logo à imprimer pour un rôle : le lockup Taqinor (embarqué ou
    téléversé) devient le bloc du rôle (mot-marque seul en « entete » /
    « hero », lockup ailleurs) ; tout autre logo (société, bandeau neutre)
    est rendu tel quel."""
    variante = est_taqinor(b64)
    return taqinor_b64(variante, bloc_taqinor(role)) if variante else b64


def image_qr(b64: str):
    """Centre des QR pour un logo base64 (clair) : l'emblème si c'est le lockup
    Taqinor (embarqué ou téléversé), sinon le logo dans un carré blanc."""
    return taqinor_image_qr() if est_taqinor(b64) else image_qr_societe(b64)


def bloc_taqinor(role: str) -> str:
    """Bloc du logo Taqinor pour un rôle : lockup là où la tagline passe,
    mot-marque ailleurs."""
    return "lockup" if AVEC_TAGLINE[role] else "mot"
