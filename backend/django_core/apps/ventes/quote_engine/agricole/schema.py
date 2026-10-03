"""AGR309 — schéma forage → pompe → variateur → panneaux → bassin →
irrigation, et courbe de la pompe avec son point de fonctionnement, en SVG
SERVEUR.

UN SEUL DESSIN POUR LES DEUX SUPPORTS. ``schema_svg`` est versé dans
``synthese_agricole['schema_svg']`` : la page /proposition le sert tel quel et
le renderer agricole (AGR310) l'imprime — jamais un second dessin côté
navigateur. ``courbe_svg`` sert la page 2 du document ; il rend ``None`` sans
courbe constructeur, et la page dit alors ``TEXTE_COURBE_ABSENTE``.

LES RÈGLES.
  * Seules les valeurs SAISIES de ``synthese['schema']`` sont écrites : une
    valeur absente est OMISE (aucun libellé, jamais un tiret ni un zéro).
  * Le bassin n'est dessiné que s'il est DÉCLARÉ (``schema['bassin']`` non
    nul) — aucun bassin dimensionné, aucun « ×2 » (AGR301).
  * Étiquettes d'un mot en fr / en / ar (l'arabe est écrit maintenant et relu
    par le fondateur après, sans bloquer l'envoi — D-AGR-11).
  * Tailles en mm (largeur) et viewBox en unités utilisateur : WeasyPrint et
    les navigateurs rendent le même dessin. Polices explicites, couleurs
    explicites, aucune ressource externe.
  * Tout texte variable est échappé ICI (``html.escape``) — les entrées de ce
    module sont la synthèse (données BRUTES servies aussi en JSON), pas
    ``data_rendu`` : il n'y a donc pas de double échappement (QJR154).

Matière : l'ancien ``agricole/schematic.py`` (supprimé par ce7e9f01, DV1) a
servi d'inspiration seulement ; rien n'en est ressuscité tel quel.
Fonctions PURES : aucun accès base, aucun réseau.
"""
from __future__ import annotations

import html

NAVY = "#1A2B4A"
GOLD = "#F5A623"
BLUE = "#2C5F8A"
BLUE_FILL = "#DCEBF7"
LINE = "#9CA3AF"
INK = "#1F2937"
MUTED = "#6B7280"
WHITE = "#FFFFFF"
FONT = "DejaVu Sans, Arial, sans-serif"

#: Étiquettes d'un mot par langue (repli : français).
LIBELLES = {
    "forage": {"fr": "Forage", "en": "Borehole", "ar": "البئر"},
    "pompe": {"fr": "Pompe", "en": "Pump", "ar": "المضخة"},
    "variateur": {"fr": "Variateur", "en": "Drive", "ar": "المغير"},
    "panneaux": {"fr": "Panneaux", "en": "Panels", "ar": "الألواح"},
    "bassin": {"fr": "Bassin", "en": "Tank", "ar": "الحوض"},
    "irrigation": {"fr": "Irrigation", "en": "Irrigation", "ar": "السقي"},
    "profondeur": {"fr": "Profondeur", "en": "Depth", "ar": "العمق"},
    "niveau": {"fr": "Niveau", "en": "Level", "ar": "المستوى"},
    "distance": {"fr": "Distance", "en": "Distance", "ar": "المسافة"},
    "hmt": {"fr": "HMT", "en": "Head", "ar": "الارتفاع"},
    "debit": {"fr": "Débit", "en": "Flow", "ar": "الصبيب"},
}

#: Phrase imprimée à la place de la courbe quand la pompe n'en a pas.
TEXTE_COURBE_ABSENTE = {
    "fr": "Courbe constructeur non disponible pour cette pompe.",
    "en": "Manufacturer curve not available for this pump.",
    "ar": "منحنى الصانع غير متوفر لهذه المضخة.",
}

# Géométrie du schéma (unités du viewBox).
_SCHEMA_L, _SCHEMA_H = 1000, 260
_BOITE_L, _BOITE_H, _BOITE_Y = 120, 70, 60

# Géométrie de la courbe (unités du viewBox) : marges du cadre de tracé.
_COURBE_L, _COURBE_H = 600, 360
_X0, _X1 = 70, 580   # abscisses du cadre (débit)
_Y0, _Y1 = 320, 30   # ordonnées du cadre (HMT : bas → haut)


def _langue(langue):
    return langue if langue in ("fr", "en", "ar") else "fr"


def _lib(cle, langue):
    t = LIBELLES[cle]
    return t.get(_langue(langue)) or t["fr"]


def _num(v):
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f != f else f


def _fr(v):
    """Nombre à la française (« 58,7 », « 90 ») — jamais un nombre inventé."""
    f = _num(v)
    if f is None:
        return None
    if f == int(f):
        return str(int(f))
    return f"{f:.1f}".rstrip("0").rstrip(".").replace(".", ",")


def _texte(x, y, contenu, taille=13, couleur=INK, graisse="normal",
           ancre="middle", attrs=""):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FONT}" '
            f'font-size="{taille}" font-weight="{graisse}" fill="{couleur}" '
            f'text-anchor="{ancre}"{attrs}>{html.escape(str(contenu))}</text>')


def _svg(largeur_mm, l_vb, h_vb, corps, titre):
    hauteur_mm = round(largeur_mm * h_vb / l_vb, 1)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{largeur_mm}mm" height="{hauteur_mm}mm" '
            f'viewBox="0 0 {l_vb} {h_vb}" role="img">'
            f'<title>{html.escape(titre)}</title>{corps}</svg>')


# ── schéma ──────────────────────────────────────────────────────────────────

def schema_svg(synthese, langue="fr", libelle_pompe=None):
    """Le schéma du système, en SVG (chaîne). Toujours rendu : les étapes
    sont des faits du kit ; seules les VALEURS absentes sont omises."""
    schema = (synthese or {}).get("schema") or {}
    langue = _langue(langue)
    etapes = ["forage", "pompe", "variateur", "panneaux"]
    if _num(schema.get("bassin")) is not None:
        etapes.append("bassin")
    etapes.append("irrigation")

    pas = (_SCHEMA_L - 40 - _BOITE_L) / max(len(etapes) - 1, 1)
    corps = []
    centres = {}
    for i, cle in enumerate(etapes):
        x = 20 + i * pas
        cx = x + _BOITE_L / 2
        centres[cle] = cx
        couleur = GOLD if cle == "panneaux" else (
            BLUE if cle in ("forage", "bassin", "irrigation") else NAVY)
        corps.append(
            f'<rect x="{x:.1f}" y="{_BOITE_Y}" width="{_BOITE_L}" '
            f'height="{_BOITE_H}" rx="10" ry="10" fill="{WHITE}" '
            f'stroke="{couleur}" stroke-width="2"/>')
        corps.append(_texte(cx, _BOITE_Y + _BOITE_H / 2 + 5, _lib(cle, langue),
                            taille=15, couleur=couleur, graisse="bold",
                            attrs=f' data-etape="{cle}"'))
        if i:
            x_prec = 20 + (i - 1) * pas + _BOITE_L
            y = _BOITE_Y + _BOITE_H / 2
            corps.append(
                f'<line x1="{x_prec + 4:.1f}" y1="{y}" x2="{x - 10:.1f}" '
                f'y2="{y}" stroke="{LINE}" stroke-width="2"/>')
            corps.append(
                f'<polygon points="{x - 2:.1f},{y} {x - 12:.1f},{y - 6} '
                f'{x - 12:.1f},{y + 6}" fill="{LINE}"/>')

    # Valeurs SAISIES seulement, sous l'étape qu'elles décrivent.
    def _valeur(cle_etape, rang, cle_lib, valeur, unite, attr):
        txt = _fr(valeur)
        if txt is None:
            return
        y = _BOITE_Y + _BOITE_H + 26 + rang * 20
        corps.append(_texte(centres[cle_etape], y,
                            f"{_lib(cle_lib, langue)} {txt} {unite}",
                            taille=12, couleur=MUTED,
                            attrs=f' data-valeur="{attr}"'))

    _valeur("forage", 0, "profondeur", schema.get("profondeur_m"), "m",
            "profondeur_m")
    _valeur("forage", 1, "niveau", schema.get("niveau_m"), "m", "niveau_m")
    _valeur("pompe", 0, "hmt", schema.get("hmt_m"), "m", "hmt_m")
    _valeur("panneaux", 0, "distance", schema.get("distance_m"), "m",
            "distance_m")
    if "bassin" in centres:
        txt = _fr(schema.get("bassin"))
        corps.append(_texte(centres["bassin"], _BOITE_Y + _BOITE_H + 26,
                            f"{txt} m³", taille=12, couleur=MUTED,
                            attrs=' data-valeur="bassin"'))
    if libelle_pompe:
        corps.append(_texte(centres["pompe"], _BOITE_Y - 14, libelle_pompe,
                            taille=11, couleur=MUTED))

    titre = " → ".join(_lib(c, langue) for c in etapes)
    return _svg(170, _SCHEMA_L, _SCHEMA_H, "".join(corps), titre)


# ── courbe ──────────────────────────────────────────────────────────────────

def _bornes(courbe):
    q_max = max(q for q, _ in courbe) or 1.0
    h_max = max(h for _, h in courbe) or 1.0
    return q_max * 1.05, h_max * 1.1


def coordonnees(debit_m3h, hmt_m, q_borne, h_borne):
    """(x, y) dans le viewBox de la courbe — exposé pour les tests."""
    x = _X0 + (float(debit_m3h) / q_borne) * (_X1 - _X0)
    y = _Y0 - (float(hmt_m) / h_borne) * (_Y0 - _Y1)
    return round(x, 1), round(y, 1)


def _courbe_valide(pf):
    courbe = (pf or {}).get("courbe") or []
    points = []
    for p in courbe:
        if not isinstance(p, (list, tuple)) or len(p) != 2:
            return None
        q, h = _num(p[0]), _num(p[1])
        if q is None or h is None:
            return None
        points.append((q, h))
    return points if len(points) >= 2 else None


def courbe_svg(synthese, langue="fr", libelle_pompe=None):
    """Courbe débit → HMT du constructeur + point retenu, en SVG ; ``None``
    sans courbe (la page imprime alors ``TEXTE_COURBE_ABSENTE``)."""
    pf = (synthese or {}).get("point_fonctionnement")
    courbe = _courbe_valide(pf)
    if courbe is None:
        return None
    langue = _langue(langue)
    q_borne, h_borne = _bornes(courbe)
    corps = [
        f'<line x1="{_X0}" y1="{_Y0}" x2="{_X1}" y2="{_Y0}" '
        f'stroke="{INK}" stroke-width="1.5"/>',
        f'<line x1="{_X0}" y1="{_Y0}" x2="{_X0}" y2="{_Y1}" '
        f'stroke="{INK}" stroke-width="1.5"/>',
        _texte((_X0 + _X1) / 2, _Y0 + 32,
               f"{_lib('debit', langue)} (m³/h)", taille=13, couleur=MUTED),
        _texte(_X0 - 12, _Y1 - 10, f"{_lib('hmt', langue)} (m)", taille=13,
               couleur=MUTED, ancre="start"),
    ]
    # Graduations : les débits et HMT de la courbe constructeur eux-mêmes.
    for q, h in courbe:
        x, _ = coordonnees(q, 0, q_borne, h_borne)
        _, y = coordonnees(0, h, q_borne, h_borne)
        corps.append(_texte(x, _Y0 + 16, _fr(q), taille=11, couleur=MUTED))
        corps.append(_texte(_X0 - 8, y + 4, _fr(h), taille=11, couleur=MUTED,
                            ancre="end"))
    pts = " ".join("%.1f,%.1f" % coordonnees(q, h, q_borne, h_borne)
                   for q, h in courbe)
    corps.append(f'<polyline points="{pts}" fill="none" stroke="{BLUE}" '
                 f'stroke-width="3" stroke-linejoin="round"/>')
    point = (pf or {}).get("point") or {}
    q_p, h_p = _num(point.get("debit_m3h")), _num(point.get("hmt_m"))
    if q_p is not None and h_p is not None:
        cx, cy = coordonnees(q_p, h_p, q_borne, h_borne)
        corps.append(
            f'<circle cx="{cx}" cy="{cy}" r="7" fill="{GOLD}" '
            f'stroke="{NAVY}" stroke-width="2" data-point="fonctionnement" '
            f'data-debit-m3h="{q_p}" data-hmt-m="{h_p}"/>')
        corps.append(_texte(cx + 12, cy - 10,
                            f"{_fr(q_p)} m³/h · {_fr(h_p)} m", taille=12,
                            couleur=NAVY, graisse="bold", ancre="start"))
    if libelle_pompe:
        corps.append(_texte(_X1, _Y1 - 10, libelle_pompe, taille=11,
                            couleur=MUTED, ancre="end"))
    titre = f"{_lib('pompe', langue)} — {_lib('debit', langue)} / " \
            f"{_lib('hmt', langue)}"
    return _svg(120, _COURBE_L, _COURBE_H, "".join(corps), titre)
