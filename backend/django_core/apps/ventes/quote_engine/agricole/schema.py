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

from .. import i18n_labels as _i18n
from ..lecture_pure import nombre_ou_none

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
#: AGR314 — les étiquettes du schéma et de la courbe vivent dans le catalogue
#: UNIQUE des libellés structurels du document (``quote_engine.i18n_labels``,
#: clés ``agr_schema_*``) ; cette table en est la vue par mot, inchangée.
_MOTS = ("forage", "pompe", "variateur", "panneaux", "bassin", "irrigation",
         "profondeur", "niveau", "distance", "hmt", "debit", "ligne_eau",
         "ligne_energie")
#: AGQ32 — le libellé précis de la distance vit sous une clé NEUVE (la clé
#: d'origine ``agr_schema_distance`` garde son texte : empreinte #898).
_CLE_PAR_MOT = {"distance": "agr_schema_distance_champ_coffret"}
LIBELLES = {mot: dict(_i18n.LIBELLES[_CLE_PAR_MOT.get(mot, f"agr_schema_{mot}")])
            for mot in _MOTS}

#: Phrase imprimée à la place de la courbe quand la pompe n'en a pas.
TEXTE_COURBE_ABSENTE = {
    "fr": "Courbe constructeur non disponible pour cette pompe.",
    "en": "Manufacturer curve not available for this pump.",
    "ar": "منحنى الصانع غير متوفر لهذه المضخة.",
}

# Géométrie du schéma (unités du viewBox).
_SCHEMA_L, _SCHEMA_H = 1000, 270
_BOITE_L, _BOITE_H = 120, 70
#: AGQ32 — ordonnées des deux lignes du schéma : l'eau, puis l'énergie.
_Y_EAU, _Y_ENERGIE = 40, 180

# Géométrie de la courbe (unités du viewBox) : marges du cadre de tracé.
_COURBE_L, _COURBE_H = 600, 360
_X0, _X1 = 70, 580   # abscisses du cadre (débit)
_Y0, _Y1 = 320, 30   # ordonnées du cadre (HMT : bas → haut)


def _langue(langue):
    return langue if langue in ("fr", "en", "ar") else "fr"


def _lib(cle, langue):
    t = LIBELLES[cle]
    return t.get(_langue(langue)) or t["fr"]


_num = nombre_ou_none


def _fr(v):
    """Nombre à la française (« 58,7 », « 90 ») — jamais un nombre inventé."""
    f = _num(v)
    if f is None:
        return None
    if f == int(f):
        return str(int(f))
    return f"{f:.1f}".rstrip("0").rstrip(".").replace(".", ",")


def _arabe(texte):
    return any("؀" <= c <= "ۿ" for c in str(texte))


def legende(x, y, texte, cadre, taille=13, couleur=INK, graisse="normal",
            ancre="middle"):
    """AGQ13 — une légende HTML (position en % du viewBox, taille en pt) ;
    ``cadre`` = (largeur imprimée en mm, largeur et hauteur du viewBox)."""
    largeur_mm, l_vb, h_vb = cadre
    return {"texte": str(texte), "ancre": ancre, "couleur": couleur,
            "graisse": graisse, "x_pct": round(x / l_vb * 100, 2),
            "y_pct": round(y / h_vb * 100, 2),
            "taille_pt": round(taille * largeur_mm / l_vb * 2.835, 1)}


def _texte(x, y, contenu, taille=13, couleur=INK, graisse="normal",
           ancre="middle", attrs="", legendes=None, cadre=None):
    """Un ``<text>`` SVG — sauf AGQ13 : un texte ARABE quand ``legendes``
    est une liste part en légende HTML positionnée (WeasyPrint ne façonne
    pas l'arabe d'un ``<text>`` SVG : lettres non liées, inversées).
    ``cadre`` = (largeur_mm, largeur viewBox, hauteur viewBox)."""
    if legendes is not None and cadre and _arabe(contenu):
        legendes.append(legende(x, y, contenu, cadre, taille=taille,
                                couleur=couleur, graisse=graisse,
                                ancre=ancre))
        return ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FONT}" '
            f'font-size="{taille}" font-weight="{graisse}" fill="{couleur}" '
            f'text-anchor="{ancre}"{attrs}>{html.escape(str(contenu))}</text>')


def superposer(svg, legendes):
    """AGQ13 — le SVG et ses légendes en HTML positionné par-dessus (texte
    bidi façonné par le moteur HTML) ; sans légende, le SVG tel quel."""
    if not svg or not legendes:
        return svg
    divs = []
    for lg in legendes:
        x = lg["x_pct"]
        gauche, aligne = {"start": (x, "left"), "end": (x - 30, "right")}.get(
            lg.get("ancre"), (x - 15, "center"))
        divs.append(
            f'<div style="position:absolute;left:{gauche:.2f}%;'
            f'top:{lg["y_pct"]:.2f}%;width:30%;margin-top:-1em;'
            f'line-height:1.2;text-align:{aligne};white-space:nowrap;'
            f'font-size:{lg["taille_pt"]}pt;color:{lg["couleur"]};'
            f'font-weight:{lg["graisse"]}">{html.escape(lg["texte"])}</div>')
    return (f'<div class="ag-sch" style="position:relative">{svg}'
            f'{"".join(divs)}</div>')


def _svg(largeur_mm, l_vb, h_vb, corps, titre):
    hauteur_mm = round(largeur_mm * h_vb / l_vb, 1)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{largeur_mm}mm" height="{hauteur_mm}mm" '
            f'viewBox="0 0 {l_vb} {h_vb}" role="img">'
            f'<title>{html.escape(titre)}</title>{corps}</svg>')


# ── schéma ──────────────────────────────────────────────────────────────────

def _fleche(x1, y1, x2, y2):
    """Flèche horizontale OU verticale de (x1, y1) à la pointe (x2, y2)."""
    sx, sy = (x2 > x1) - (x2 < x1), (y2 > y1) - (y2 < y1)
    bx, by = x2 - 10 * sx, y2 - 10 * sy
    px, py = 6 * sy, 6 * sx
    return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{bx:.1f}" y2="{by:.1f}" '
            f'stroke="{LINE}" stroke-width="2"/>'
            f'<polygon points="{x2:.1f},{y2:.1f} {bx + px:.1f},{by + py:.1f} '
            f'{bx - px:.1f},{by - py:.1f}" fill="{LINE}"/>')


def schema_svg(synthese, langue="fr", libelle_pompe=None, legendes=None):
    """Le schéma du système, en SVG (chaîne). Toujours rendu : les étapes
    sont des faits du kit ; seules les VALEURS absentes sont omises.

    AGQ32 — DEUX lignes : l'EAU (forage → pompe → [bassin] → irrigation) et
    l'ÉNERGIE (panneaux → variateur → pompe), la distance libellée « champ →
    coffret » entre panneaux et variateur.
    AGQ13 — en arabe les deux lignes se lisent de droite à gauche (flèches
    miroir) ; ``legendes`` (liste) reçoit alors les textes arabes, rendus en
    HTML par :func:`superposer`."""
    schema = (synthese or {}).get("schema") or {}
    langue = _langue(langue)
    rtl = _i18n.est_rtl(langue)
    cadre = (170, _SCHEMA_L, _SCHEMA_H)
    eau = ["forage", "pompe"]
    if _num(schema.get("bassin")) is not None:
        eau.append("bassin")
    eau.append("irrigation")
    pas = (_SCHEMA_L - 40 - _BOITE_L) / (len(eau) - 1)

    def _x(col):
        x = 20 + col * pas
        return _SCHEMA_L - x - _BOITE_L if rtl else x

    # (x, y, ligne) de chaque boîte : variateur sous la pompe, panneaux sous
    # la dernière étape de l'eau.
    pos = {cle: (_x(i), _Y_EAU, "eau") for i, cle in enumerate(eau)}
    pos["variateur"] = (_x(1), _Y_ENERGIE, "energie")
    pos["panneaux"] = (_x(len(eau) - 1), _Y_ENERGIE, "energie")
    etapes = ["forage", "pompe", "variateur", "panneaux"] + eau[2:]
    corps = []
    centres = {}
    for cle in etapes:
        x, y, ligne = pos[cle]
        centres[cle] = x + _BOITE_L / 2
        couleur = GOLD if cle == "panneaux" else (
            BLUE if cle in ("forage", "bassin", "irrigation") else NAVY)
        corps.append(
            f'<rect x="{x:.1f}" y="{y}" width="{_BOITE_L}" '
            f'height="{_BOITE_H}" rx="10" ry="10" fill="{WHITE}" '
            f'stroke="{couleur}" stroke-width="2" data-ligne="{ligne}"/>')
        corps.append(_texte(centres[cle], y + _BOITE_H / 2 + 5,
                            _lib(cle, langue), taille=15, couleur=couleur,
                            graisse="bold", attrs=f' data-etape="{cle}"',
                            legendes=legendes, cadre=cadre))

    def _horizontale(de, vers):
        xa, xb = pos[de][0], pos[vers][0]
        y = pos[de][1] + _BOITE_H / 2
        if xb > xa:
            return _fleche(xa + _BOITE_L + 4, y, xb - 2, y)
        return _fleche(xa - 4, y, xb + _BOITE_L + 2, y)

    for de, vers in zip(eau, eau[1:]):
        corps.append(_horizontale(de, vers))
    corps.append(_horizontale("panneaux", "variateur"))
    corps.append(_fleche(centres["variateur"], _Y_ENERGIE - 4,
                         centres["pompe"], _Y_EAU + _BOITE_H + 2))
    # Titres des deux lignes, au bord où commence la lecture.
    bord, sens = (_SCHEMA_L - 20, "end") if rtl else (20, "start")
    for ligne, y in (("ligne_eau", _Y_EAU - 10),
                     ("ligne_energie", _Y_ENERGIE - 10)):
        corps.append(_texte(bord, y, _lib(ligne, langue), taille=12,
                            couleur=MUTED, graisse="bold", ancre=sens,
                            legendes=legendes, cadre=cadre))

    # Valeurs SAISIES seulement, à côté de l'étape qu'elles décrivent.
    def _valeur(cx, y, cle_lib, valeur, unite, attr):
        txt = _fr(valeur)
        if txt is None:
            return
        corps.append(_texte(cx, y, f"{_lib(cle_lib, langue)} {txt} {unite}",
                            taille=12, couleur=MUTED,
                            attrs=f' data-valeur="{attr}"',
                            legendes=legendes, cadre=cadre))

    sous_eau = _Y_EAU + _BOITE_H + 22
    _valeur(centres["forage"], sous_eau, "profondeur",
            schema.get("profondeur_m"), "m", "profondeur_m")
    _valeur(centres["forage"], sous_eau + 18, "niveau", schema.get("niveau_m"),
            "m", "niveau_m")
    _valeur(centres["pompe"], _Y_EAU - 10, "hmt", schema.get("hmt_m"), "m",
            "hmt_m")
    _valeur((centres["panneaux"] + centres["variateur"]) / 2,
            _Y_ENERGIE + _BOITE_H / 2 - 8, "distance",
            schema.get("distance_m"), "m", "distance_m")
    if "bassin" in centres:
        txt = _fr(schema.get("bassin"))
        corps.append(_texte(centres["bassin"], sous_eau, f"{txt} m³",
                            taille=12, couleur=MUTED,
                            attrs=' data-valeur="bassin"'))
    if libelle_pompe:
        corps.append(_texte(centres["pompe"], _Y_EAU - 28, libelle_pompe,
                            taille=11, couleur=MUTED, legendes=legendes,
                            cadre=cadre))

    titre = " → ".join(_lib(c, langue) for c in eau)
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


def courbe_svg(synthese, langue="fr", libelle_pompe=None, legendes=None):
    """Courbe débit → HMT du constructeur + point retenu, en SVG ; ``None``
    sans courbe (la page imprime alors ``TEXTE_COURBE_ABSENTE``).
    ``legendes`` (AGQ13) : reçoit les titres d'axes arabes (HTML)."""
    pf = (synthese or {}).get("point_fonctionnement")
    courbe = _courbe_valide(pf)
    if courbe is None:
        return None
    langue = _langue(langue)
    cadre = (120, _COURBE_L, _COURBE_H)
    q_borne, h_borne = _bornes(courbe)
    corps = [
        f'<line x1="{_X0}" y1="{_Y0}" x2="{_X1}" y2="{_Y0}" '
        f'stroke="{INK}" stroke-width="1.5"/>',
        f'<line x1="{_X0}" y1="{_Y0}" x2="{_X0}" y2="{_Y1}" '
        f'stroke="{INK}" stroke-width="1.5"/>',
        _texte((_X0 + _X1) / 2, _Y0 + 32,
               f"{_lib('debit', langue)} (m³/h)", taille=13, couleur=MUTED,
               legendes=legendes, cadre=cadre),
        _texte(_X0 - 12, _Y1 - 10, f"{_lib('hmt', langue)} (m)", taille=13,
               couleur=MUTED, ancre="start", legendes=legendes, cadre=cadre),
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
                            couleur=MUTED, ancre="end", legendes=legendes,
                            cadre=cadre))
    titre = f"{_lib('pompe', langue)} — {_lib('debit', langue)} / " \
            f"{_lib('hmt', langue)}"
    return _svg(120, _COURBE_L, _COURBE_H, "".join(corps), titre)
