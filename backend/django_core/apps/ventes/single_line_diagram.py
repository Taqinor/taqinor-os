"""FG252 — Brouillon de schéma unifilaire (SVG) pour le dossier technique.

Module PUR (aucune écriture base, aucun effet de bord) qui produit, à partir
d'une configuration électrique simple, un schéma unifilaire SVG de la chaîne :

    Panneaux → String(s) → Onduleur → Comptage → ONEE (réseau)

C'est un BROUILLON technique (pas un livrable client) : il sert au dossier
technique (demande de raccordement, étude). Il NE PASSE PAS par le moteur de
devis premium (`quote_engine/`) ni par `/proposal`, et ne change aucun statut
de devis (RULE #4).

Sortie : une chaîne SVG autonome (XML), JSON-sérialisable, sans aucun prix ni
prix d'achat / marge — uniquement des grandeurs électriques publiques.

Le module est volontairement sans dépendance : le SVG est assemblé à la main
(pas de lib de dessin) pour rester portable et testable hors-Django.

PV83 (ARC6) — POURQUOI CE MODULE N'EST **PAS** UN SHIM SUR
``core.electrique.schema``. Le noyau (PV39) rend un schéma unifilaire v2 : la
chaîne CANONIQUE d'un dossier de raccordement (fusibles gPV, coffret DC,
parafoudres, sectionneur, amorces MPPT, DDR, compteur de production, TGBT),
dessinée DEPUIS un ``ResultatElectrique`` — donc uniquement les organes que les
règles ont retenus, plus un tableau d'équipements. Ce module-ci, lui, dessine
cinq blocs FIXES (Panneaux → String(s) → Onduleur → Comptage → ONEE) à partir
d'un simple dict d'ÉTIQUETTES, sans calcul électrique. Les signatures
(``params`` vs ``(entree, resultat)``), la planche (980 × 260 px vs A4/A3
paysage) et le contenu diffèrent de bout en bout : brancher l'un sur l'autre
changerait le rendu des deux endpoints existants, pas leur implémentation. Le
v1 reste donc ici, INCHANGÉ, comme brouillon d'étiquettes ; le v2 est appelé
par les consommateurs qui disposent d'une conception électrique complète
(``Devis.electrical_design``, PV41). Un test épingle les deux
(``test_pv83_shims_electrique``).
"""
from __future__ import annotations

from html import escape

from core.electrique.schema import blocs_etage_mt
from core.electrique.types import EtageMt, TransformateurMt


def _esc(text) -> str:
    """Échappe un texte pour l'insérer en contenu/attribut SVG."""
    return escape(str(text if text is not None else ""), quote=True)


def _coerce_int(value, default=0):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return n if n >= 0 else default


def _coerce_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_diagram_params(params=None):
    """Normalise/valide les paramètres d'entrée du schéma.

    Accepte un dict tolérant (issu d'un devis ou d'une requête) et renvoie une
    structure propre et bornée, JAMAIS d'exception sur entrée farfelue.

    Clés reconnues :
      - n_panneaux (int) : nombre de panneaux.
      - puissance_panneau_wc (int) : Wc unitaire (étiquette).
      - n_strings (int) : nombre de chaînes (≥1 si des panneaux existent).
      - onduleur (str) : libellé onduleur.
      - puissance_onduleur_kw (float) : kW AC onduleur (étiquette).
      - phases (1|3) : monophasé / triphasé.
      - has_battery (bool) : ajoute une branche batterie sous l'onduleur.
      - injection (bool) : True = injection réseau (ONEE), False = autonome.
      - titre (str) : titre du schéma.
      - etage_mt (EtageMt | dict, facultatif) : CIQ664 — l'étage moyenne
        tension d'un site livré en MT (relevé validé). Absent, le schéma est
        celui d'avant, octet pour octet.
    """
    p = dict(params or {})
    n_panneaux = _coerce_int(p.get("n_panneaux"), 0)
    n_strings = _coerce_int(p.get("n_strings"), 0)
    if n_panneaux > 0 and n_strings <= 0:
        n_strings = 1
    if n_panneaux <= 0:
        n_strings = 0
    # Une chaîne ne peut pas compter plus de strings que de panneaux.
    if n_strings > n_panneaux > 0:
        n_strings = n_panneaux
    phases = 3 if _coerce_int(p.get("phases"), 1) == 3 else 1
    cfg = {
        "n_panneaux": n_panneaux,
        "puissance_panneau_wc": _coerce_int(p.get("puissance_panneau_wc"), 0),
        "n_strings": n_strings,
        "onduleur": (str(p.get("onduleur") or "Onduleur")).strip()[:80]
        or "Onduleur",
        "puissance_onduleur_kw": round(
            _coerce_float(p.get("puissance_onduleur_kw"), 0.0), 2),
        "phases": phases,
        "has_battery": bool(p.get("has_battery")),
        "injection": bool(p.get("injection", True)),
        "titre": (str(p.get("titre") or "Schéma unifilaire").strip()[:120]
                  or "Schéma unifilaire"),
    }
    etage = _normaliser_etage_mt(p.get("etage_mt"))
    if etage is not None:
        cfg["etage_mt"] = etage
    return cfg


def _normaliser_etage_mt(valeur):
    """CIQ664 — l'étage MT normalisé en dict, ou ``None`` (site BT).

    Accepte un ``EtageMt`` ou un dict tolérant ; ne lève jamais. Un transformateur
    sans nombre ni puissance exploitables est ignoré (rien n'est inventé)."""
    if valeur is None or valeur is False:
        return None
    if isinstance(valeur, EtageMt):
        brut = {
            "transformateurs": [
                {"nb": t.nb, "kva": t.kva, "rapport": t.rapport}
                for t in valeur.transformateurs],
            "cellule": valeur.cellule,
            "compteur_production": valeur.compteur_production,
            "injection_limitee": valeur.injection_limitee,
        }
    elif isinstance(valeur, dict):
        brut = valeur
    else:
        return None
    transformateurs = []
    for t in brut.get("transformateurs") or []:
        if not isinstance(t, dict):
            continue
        nb = _coerce_int(t.get("nb"), 0)
        kva = _coerce_float(t.get("kva"), 0.0)
        if nb > 0 and kva > 0:
            transformateurs.append({
                "nb": nb, "kva": kva,
                "rapport": str(t.get("rapport") or "").strip()[:40]})
    return {
        "transformateurs": transformateurs,
        "cellule": str(brut.get("cellule") or "").strip()[:80],
        "compteur_production": bool(brut.get("compteur_production")),
        "injection_limitee": bool(brut.get("injection_limitee")),
    }


def _en_etage(etage):
    """Le dict normalisé → l'``EtageMt`` du noyau électrique."""
    return EtageMt(
        transformateurs=tuple(
            TransformateurMt(t["nb"], t["kva"], t.get("rapport", ""))
            for t in etage["transformateurs"]),
        cellule=etage["cellule"],
        compteur_production=etage["compteur_production"],
        injection_limitee=etage["injection_limitee"])


def etage_mt_depuis_releve(releve, injection_limitee=False):
    """CIQ664 — l'``EtageMt`` d'un RELEVÉ DE VISITE MT VALIDÉ, sinon ``None``.

    ``releve`` = le bloc ``releve_ci`` d'une visite (``visites.selectors``,
    CIQ606/CIQ660). Seul un relevé VALIDÉ (``validee_le``) dont le niveau de
    tension CONSTATÉ est ``mt`` donne un étage : un site BT, une visite non
    validée ou un niveau « non relevé » ne dessinent rien. Les transformateurs
    sont ceux relevés au poste (``poste_mt``) ; ``injection_limitee`` est posé
    par l'appelant d'après la SORTIE du moteur C&I (CIQ2) — jamais devinée ici.
    Fonction pure, ne lève jamais."""
    if not isinstance(releve, dict) or not releve.get("validee_le"):
        return None
    tension = releve.get("niveau_tension")
    if not isinstance(tension, dict) or tension.get("non_releve"):
        return None
    if tension.get("constate") != "mt":
        return None
    poste = releve.get("poste_mt")
    poste = poste if isinstance(poste, dict) else {}
    etage = _normaliser_etage_mt({
        "transformateurs": poste.get("transformateurs"),
        "cellule": poste.get("cellule_protection"),
        "injection_limitee": bool(injection_limitee),
    })
    return _en_etage(etage)


def _lignes_sous_libelle(texte, largeur=24):
    """Coupe ``texte`` en lignes de ``largeur`` caractères au plus, aux mots."""
    lignes, courante = [], ""
    for mot in str(texte).split():
        candidate = (courante + " " + mot).strip()
        if len(candidate) <= largeur or not courante:
            courante = candidate
        else:
            lignes.append(courante)
            courante = mot
    if courante:
        lignes.append(courante)
    return lignes


def _box(x, y, w, h, label, sublabel="", fill="#ffffff", stroke="#1f3a5f"):
    """Bloc rectangulaire avec libellé (+ sous-libellé optionnel)."""
    cx = x + w / 2
    parts = [
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="2"/>',
    ]
    if isinstance(sublabel, (list, tuple)):
        # CIQ664 — sous-libellé sur plusieurs lignes (blocs de l'étage MT).
        parts.append(
            f'<text x="{cx}" y="{y + h / 2 - 20}" text-anchor="middle" '
            f'font-size="13" font-weight="600" fill="#1f3a5f">'
            f'{_esc(label)}</text>')
        for i, ligne in enumerate(sublabel):
            parts.append(
                f'<text x="{cx}" y="{y + h / 2 - 4 + 13 * i}" '
                f'text-anchor="middle" font-size="11" fill="#555">'
                f'{_esc(ligne)}</text>')
    elif sublabel:
        parts.append(
            f'<text x="{cx}" y="{y + h / 2 - 4}" text-anchor="middle" '
            f'font-size="13" font-weight="600" fill="#1f3a5f">'
            f'{_esc(label)}</text>')
        parts.append(
            f'<text x="{cx}" y="{y + h / 2 + 14}" text-anchor="middle" '
            f'font-size="11" fill="#555">{_esc(sublabel)}</text>')
    else:
        parts.append(
            f'<text x="{cx}" y="{y + h / 2 + 4}" text-anchor="middle" '
            f'font-size="13" font-weight="600" fill="#1f3a5f">'
            f'{_esc(label)}</text>')
    return "".join(parts)


def _arrow(x1, y, x2, color="#1f3a5f"):
    """Flèche horizontale (sens de l'énergie) de x1 à x2 à l'ordonnée y."""
    return (
        f'<line x1="{x1}" y1="{y}" x2="{x2 - 8}" y2="{y}" '
        f'stroke="{color}" stroke-width="2"/>'
        f'<polygon points="{x2},{y} {x2 - 9},{y - 5} {x2 - 9},{y + 5}" '
        f'fill="{color}"/>')


def build_single_line_svg(params=None) -> str:
    """FG252 — assemble le schéma unifilaire SVG depuis des paramètres.

    Renvoie une chaîne SVG autonome. Toujours valide (au pire un schéma
    minimal avec un avertissement) — jamais d'exception sur entrée vide.
    """
    cfg = normalize_diagram_params(params)

    width, height = 980, 260
    row_y = 92            # ordonnée de la rangée principale
    box_w, box_h = 150, 70
    gap = 60              # espace flèche entre deux blocs
    etage_mt = cfg.get("etage_mt")
    if etage_mt is not None:
        box_h = 96        # les blocs MT portent un sous-libellé sur 3 lignes

    n = cfg["n_panneaux"]
    n_strings = cfg["n_strings"]
    wc = cfg["puissance_panneau_wc"]
    kwc = round(n * wc / 1000.0, 2) if (n and wc) else 0.0

    panneaux_sub = []
    if n:
        panneaux_sub.append(f"{n} module(s)")
    if wc:
        panneaux_sub.append(f"{wc} Wc")
    if kwc:
        panneaux_sub.append(f"{kwc} kWc")
    panneaux_sub = " · ".join(panneaux_sub) or "—"

    strings_sub = f"{n_strings} chaîne(s)" if n_strings else "—"

    ond_sub = []
    if cfg["puissance_onduleur_kw"]:
        ond_sub.append(f"{cfg['puissance_onduleur_kw']} kW")
    ond_sub.append("triphasé" if cfg["phases"] == 3 else "monophasé")
    ond_sub = " · ".join(ond_sub)

    reseau_label = "ONEE (réseau)" if cfg["injection"] else "Site (autonome)"
    reseau_sub = "Injection / soutirage" if cfg["injection"] else "Hors réseau"

    # Chaîne de blocs : Panneaux → Strings → Onduleur → Comptage → ONEE.
    blocks = [
        ("Panneaux PV", panneaux_sub, "#fff7e6"),
        ("String(s) DC", strings_sub, "#eef6ff"),
        (cfg["onduleur"], ond_sub, "#e9f7ef"),
        ("Comptage", "Compteur bidirectionnel"
         if cfg["injection"] else "Compteur", "#f3eefb"),
        (reseau_label, reseau_sub, "#fdeeee"),
    ]
    if etage_mt is not None:
        # CIQ664 — l'étage MT s'insère AVANT le réseau : comptage →
        # transformateur → cellule → découplage → [compteur] → [limiteur] →
        # réseau. Chaque bloc est « à confirmer » (aucune règle sourcée).
        blocs_mt = [
            (b.titre, _lignes_sous_libelle(b.sous_titre.replace("\n", " ")),
             "#fdf6e3")
            for b in blocs_etage_mt(_en_etage(etage_mt))]
        blocks[-1:-1] = blocs_mt
        width = max(width, 20 + len(blocks) * (box_w + gap) - gap + 20)
        height = 300

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} '
        f'{height}" width="{width}" height="{height}" '
        f'font-family="Helvetica, Arial, sans-serif">',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff"/>',
        f'<text x="20" y="34" font-size="18" font-weight="700" '
        f'fill="#1f3a5f">{_esc(cfg["titre"])}</text>',
        '<text x="20" y="54" font-size="11" fill="#888">'
        'Brouillon — dossier technique (schéma unifilaire)</text>',
    ]

    x = 20
    centers = []
    for i, (label, sub, fill) in enumerate(blocks):
        svg.append(_box(x, row_y, box_w, box_h, label, sub, fill=fill))
        centers.append(x + box_w / 2)
        if i < len(blocks) - 1:
            svg.append(_arrow(x + box_w, row_y + box_h / 2, x + box_w + gap))
        x += box_w + gap

    # Branche batterie (optionnelle) sous l'onduleur (3e bloc, index 2).
    if cfg["has_battery"]:
        ond_cx = centers[2]
        bat_y = row_y + box_h + 36
        svg.append(
            f'<line x1="{ond_cx}" y1="{row_y + box_h}" x2="{ond_cx}" '
            f'y2="{bat_y}" stroke="#1f3a5f" stroke-width="2"/>')
        svg.append(
            f'<polygon points="{ond_cx},{bat_y} {ond_cx - 5},{bat_y - 9} '
            f'{ond_cx + 5},{bat_y - 9}" fill="#1f3a5f"/>')
        svg.append(_box(ond_cx - box_w / 2, bat_y, box_w, 50,
                        "Batterie", "Stockage DC", fill="#fff0f3"))

    if n <= 0:
        svg.append(
            '<text x="20" y="240" font-size="11" fill="#b00">'
            'Aucun panneau renseigné — schéma indicatif.</text>')

    svg.append('</svg>')
    return "".join(svg)


def diagram_params_from_devis(devis):
    """Déduit des paramètres de schéma depuis un Devis (best-effort, lecture).

    Parcourt les lignes du devis pour compter les panneaux (et leur Wc) et
    repérer un onduleur + une batterie via les mots-clés de classification
    partagés avec ``solar_design`` (alignés sur ``quote_engine/builder.py``).
    N'écrit rien, ne lève jamais sur données incomplètes.
    """
    from . import solar_classification as sc

    n_panneaux = 0
    wc = 0
    onduleur_nom = ""
    onduleur_kw = 0.0
    has_battery = False
    injection = True

    for ligne in devis.lignes.all():
        desig = ligne.designation or ""
        prod_nom = ""
        produit = getattr(ligne, "produit", None)
        if produit is not None:
            prod_nom = getattr(produit, "nom", "") or ""
        qte = _coerce_int(getattr(ligne, "quantite", 0), 0)
        if sc.is_panel(desig, prod_nom):
            n_panneaux += qte
            pw = sc.parse_watt(desig) or sc.parse_watt(prod_nom)
            if pw:
                wc = max(wc, int(pw))
        elif sc.is_battery(desig):
            has_battery = True
        elif sc.is_any_inverter(desig):
            if not onduleur_nom:
                onduleur_nom = desig[:80]
            kw = sc.parse_kw(desig) or sc.parse_kw(prod_nom)
            if kw:
                onduleur_kw = max(onduleur_kw, float(kw))
            if sc.is_hybrid_inverter(desig):
                has_battery = has_battery or True
            if not sc.is_reseau_inverter(desig) and \
                    sc.is_hybrid_inverter(desig):
                # Hybride : injection possible mais pas garantie ; on garde
                # injection par défaut, l'utilisateur ajuste.
                pass

    etude = getattr(devis, "etude_params", None) or {}
    phases = 3 if _coerce_int(etude.get("phases"), 1) == 3 else 1
    if "injection" in etude:
        injection = bool(etude.get("injection"))

    return {
        "n_panneaux": n_panneaux,
        "puissance_panneau_wc": wc,
        "n_strings": etude.get("n_strings") or (1 if n_panneaux else 0),
        "onduleur": onduleur_nom or "Onduleur",
        "puissance_onduleur_kw": onduleur_kw,
        "phases": phases,
        "has_battery": has_battery,
        "injection": injection,
        "titre": f"Schéma unifilaire — {devis.reference}",
    }
