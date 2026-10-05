# flake8: noqa
"""AGR310 — les trois pages du document agricole (D-AGR-2), en HTML.

P1 — l'eau et l'argent ; P2 — comment ça marche ; P3 — équipement, prix,
garanties, formalités. ``build_html(d)`` assemble les trois pages A4 (gabarit
de cadre et de pied partagé avec le canon v6 : ``residential.theme``).

TOUTES les valeurs viennent de ``d['synthese']`` (``synthese_agricole``,
AGR304-AGR309, posée par ``renderer._augment``) et de la chaîne de totaux
canonique du builder (``totaux_all`` : Sous-total HT → Remise → Total HT →
TVA → Total TTC, QJR162). AUCUN calcul ici : on met en page, on formate.

Ce que ce gabarit n'a PAS, volontairement : aucune mécanique batterie, aucune
courbe ONEE sur 25 ans, aucun donut, aucun CO₂, aucune hypothèse 82-21/ONEE
d'injection, aucune durée de ``theme.WARRANTIES`` (les garanties sont celles
des fiches des lignes, ``synthese['garanties']``).

Les textes client de ``d`` sont DÉJÀ échappés une fois (``data_rendu``,
QJR30) : ils sont imprimés tels quels ; les textes du gabarit sont des
constantes.
"""
from __future__ import annotations

from ..figures import ancre
from ..montants import fmt_centimes
from ..residential import theme
from ..sequence import sequence_affichage
from . import mentions
from .schema import TEXTE_COURBE_ABSENTE, courbe_svg
from .synthese import CONDITION_ECONOMIES

NB_PAGES = 3

#: Libellés lisibles des entrées de provenance (contrat AGR2).
LIBELLES_ENTREES = {
    "volume_m3_jour": "Volume d'eau par jour",
    "niveau_statique_m": "Niveau statique",
    "niveau_dynamique_m": "Niveau dynamique",
    "debit_exploitation_m3h": "Débit d'exploitation du forage",
    "profondeur_forage_m": "Profondeur du forage",
    "hmt_m": "Hauteur manométrique totale",
    "energie_actuelle": "Énergie actuelle",
    "plaque": "Plaque de la pompe",
    "localisation": "Localisation",
    "cultures": "Cultures",
    "surface_ha": "Surface",
}

LIBELLES_ENERGIE = {
    "butane": "butane (bouteilles)",
    "diesel": "gasoil (groupe électrogène)",
    "electrique": "réseau électrique (facture)",
    "aucune": "aucune (nouveau forage)",
}

LIBELLES_NON_INCLUS = {"forage": "le forage", "genie_civil": "le génie civil"}

MOIS_COURTS = ("Jan", "Fév", "Mar", "Avr", "Mai", "Juin", "Juil", "Août",
               "Sep", "Oct", "Nov", "Déc")
MOIS_LONGS = ("janvier", "février", "mars", "avril", "mai", "juin",
              "juillet", "août", "septembre", "octobre", "novembre",
              "décembre")


# ── formatage (aucun calcul) ────────────────────────────────────────────────

def _num(v):
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f != f else f


def _n(v, dec=1):
    """Nombre à la française, au plus ``dec`` décimales (« 134,2 », « 60 »)."""
    f = _num(v)
    if f is None:
        return None
    if dec == 0 or f == int(f):
        return theme.fmt(round(f))
    texte = f"{f:.{dec}f}".rstrip("0").rstrip(".")
    entier, _, frac = texte.partition(".")
    entier = theme.fmt(int(entier)) if entier.lstrip("-").isdigit() else entier
    return f"{entier},{frac}" if frac else entier


def _mad(v):
    f = _num(v)
    return None if f is None else fmt_centimes(f)


def _date_fr(iso):
    return mentions._date_jjmmaaaa(iso)


def _omission(synthese, bloc):
    for o in synthese.get("omissions") or []:
        if o.get("bloc") == bloc:
            return o.get("motif")
    return None


def _langue(d):
    return theme.langue_doc(d)


def _qj(poids):
    """Joint élastique (QRES62, même marqueur que le canon v6) : inerte au
    premier rendu, dimensionné ensuite d'après le vide MESURÉ de la page."""
    return f'<div class="qj" data-w="{int(poids)}"></div>'


# ── CSS ─────────────────────────────────────────────────────────────────────

def _css(C, fonts, compact):
    serif, display = fonts["serif"], fonts["display"]
    # Densité adaptative de la page 3 (jamais de débordement : le tableau se
    # resserre avant de pousser la clôture hors de la page).
    td_pad = "2.4px 6px" if compact else "5px 7px"
    td_fs = "7.6pt" if compact else "8.8pt"
    return f"""
.ag-pad {{ padding:11mm 13mm 0 13mm; }}
.ag-kicker {{ font-size:7.8pt; letter-spacing:.22em; text-transform:uppercase;
  color:{C['gold']}; font-weight:700; }}
.ag-title {{ font-family:{serif}; font-weight:700; font-size:23pt;
  color:{C['navy']}; line-height:1.05; margin:2px 0 6px; }}
.ag-sub {{ font-size:9pt; color:{C['muted']}; }}
.ag-sec {{ font-family:{serif}; font-weight:700; font-size:13pt;
  color:{C['navy']}; margin:9px 0 5px; }}
.ag-hero {{ margin-top:8px; background:{C['navy']}; color:#fff;
  border-radius:12px; padding:12px 16px; }}
.ag-hero-v {{ font-family:{display}; font-size:38pt; line-height:1; }}
.ag-hero-v small {{ font-size:15pt; }}
.ag-hero-l {{ font-size:11pt; margin-top:4px; color:#dbe3ef; }}
.ag-hero-e {{ display:inline-block; margin-top:6px; padding:2px 9px;
  border-radius:999px; background:{C['gold']}; color:{C['navy']};
  font-size:7.4pt; font-weight:700; letter-spacing:.04em; }}
.ag-cards {{ display:table; width:100%; border-spacing:6px 0;
  margin:8px -6px 0 -6px; }}
.ag-card {{ display:table-cell; border:1px solid {C['line']};
  border-radius:10px; background:#fff; padding:7px 9px; vertical-align:top; }}
.ag-card-l {{ font-size:7.6pt; color:{C['muted']}; text-transform:uppercase;
  letter-spacing:.08em; }}
.ag-card-v {{ font-family:{display}; font-size:17pt; color:{C['navy']};
  margin-top:2px; }}
.ag-card-s {{ font-size:7.6pt; color:{C['muted_2']}; margin-top:1px; }}
.ag-box {{ border:1px solid {C['line']}; border-radius:10px; background:#fff;
  padding:8px 11px; margin-top:7px; }}
.ag-box-gold {{ border-left:4px solid {C['gold']}; }}
.ag-tbl {{ width:100%; border-collapse:collapse; font-size:9pt; }}
.ag-tbl td {{ padding:4px 5px; border-bottom:1px solid {C['line_soft']};
  vertical-align:top; }}
.ag-tbl td.r {{ text-align:right; white-space:nowrap; font-weight:700;
  color:{C['navy']}; }}
.ag-note {{ font-size:7.8pt; color:{C['muted']}; line-height:1.35;
  margin-top:4px; }}
.ag-li {{ font-size:8.6pt; line-height:1.4; padding-left:10px;
  position:relative; margin-top:2px; }}
.ag-li:before {{ content:''; position:absolute; left:0; top:5px; width:5px;
  height:5px; border-radius:50%; background:{C['gold']}; }}
.ag-cols {{ display:table; width:100%; border-spacing:8px 0;
  margin:0 -8px; }}
.ag-col {{ display:table-cell; vertical-align:top; width:50%; }}
.ag-svg svg {{ width:100%; height:auto; }}
.ag-omis {{ font-size:8.4pt; color:{C['muted']}; font-style:italic;
  border:1px dashed {C['line']}; border-radius:8px; padding:7px 9px; }}
.ag-lines {{ width:100%; border-collapse:collapse; font-size:{td_fs};
  margin-top:4px; }}
.ag-lines th {{ text-align:left; color:{C['muted']}; font-size:6.8pt;
  text-transform:uppercase; letter-spacing:.04em; padding:{td_pad};
  border-bottom:1px solid {C['line']}; }}
.ag-lines th.r, .ag-lines td.r {{ text-align:right; white-space:nowrap; }}
.ag-lines td {{ padding:{td_pad}; border-bottom:1px solid {C['line_soft']};
  vertical-align:top; }}
.ag-lines td.t {{ font-weight:700; color:{C['navy']}; }}
.ag-mq {{ font-size:6.6pt; color:{C['muted_2']}; }}
.ag-tot {{ display:table; width:100%; margin-top:5px; }}
.ag-tot-g {{ display:table-cell; width:52%; vertical-align:top;
  padding-right:10px; }}
.ag-tot-d {{ display:table-cell; width:48%; vertical-align:top; }}
.ag-tot-t {{ width:100%; border-collapse:collapse; font-size:8.6pt; }}
.ag-tot-t td {{ padding:2.5px 6px; }}
.ag-tot-t td.r {{ text-align:right; white-space:nowrap; }}
.ag-tot-ttc td {{ border-top:2px solid {C['navy']}; font-family:{display};
  font-size:12pt; color:{C['navy']}; padding-top:4px; }}
.ag-small {{ font-size:7.8pt; line-height:1.35; color:{C['ink']}; }}
/* AGR311 — clôture « Bon pour accord » */
.ag-accord {{ border:1.5px solid {C['navy']}; border-radius:11px;
  background:#fff; padding:7px 10px; margin-top:6px; }}
.ag-accord-hd {{ display:table; width:100%; margin-bottom:4px; }}
.ag-accord-t {{ display:table-cell; font-family:{serif}; font-weight:700;
  font-size:12pt; color:{C['navy']}; }}
.ag-accord-v {{ display:table-cell; text-align:right; font-size:8pt;
  color:{C['ink']}; vertical-align:middle; }}
.ag-opts {{ width:100%; border-collapse:collapse; margin:2px 0 4px; }}
.ag-opt {{ font-size:{'7.2pt' if compact else '7.8pt'}; padding:1.5px 4px 1.5px 0;
  width:50%; vertical-align:top; }}
.ag-case {{ display:inline-block; width:8px; height:8px;
  border:1.2px solid {C['navy']}; border-radius:2px; margin-right:5px;
  vertical-align:-1px; }}
.ag-ech {{ width:100%; border-collapse:separate; border-spacing:4px 0;
  margin:2px -4px 4px; }}
.ag-ech td {{ background:{C['wash']}; border-radius:7px; padding:4px 7px;
  width:33%; }}
.ag-ech-l {{ font-size:6.8pt; color:{C['muted']}; text-transform:uppercase;
  letter-spacing:.04em; }}
.ag-ech-v {{ font-size:8.4pt; font-weight:700; color:{C['navy']}; }}
.ag-sigs {{ width:100%; border-collapse:separate; border-spacing:6px 0;
  margin:0 -6px; }}
.ag-sig {{ border:1px solid {C['line']}; border-radius:8px; padding:5px 8px;
  vertical-align:top; }}
.ag-sig-w {{ font-size:6.8pt; color:{C['muted']}; text-transform:uppercase;
  letter-spacing:.06em; }}
.ag-sig-n {{ font-size:8.6pt; font-weight:700; color:{C['navy']};
  margin-top:1px; }}
.ag-sig-z {{ height:{'13mm' if compact else '17mm'}; }}
.ag-sig-h {{ font-size:6.6pt; color:{C['muted_2']}; }}
.ag-qr {{ width:26mm; text-align:center; vertical-align:middle;
  font-size:6.8pt; color:{C['navy']}; font-weight:700; }}
.ag-qr img {{ width:22mm; height:22mm; }}
"""


# ── page 1 — l'eau et l'argent ──────────────────────────────────────────────

def _hero(synthese):
    eau = synthese.get("eau") or {}
    m3 = _n(eau.get("m3_jour"))
    hmt = _n(eau.get("hmt_m"))
    heures = _n(eau.get("heures_pompage"))
    if m3 is None:
        return ('<div class="ag-hero"><div class="ag-hero-v">Pompage solaire'
                '</div><div class="ag-hero-l">Volume d\'eau par jour non '
                'calculé : à confirmer par la visite.</div></div>')
    a_hmt = (f' à {hmt} m de hauteur{ancre("pompe_hmt_m", hmt)}'
             if hmt is not None else "")
    sur = f"sur {heures} h de pompage" if heures is not None else ""
    pastille = ('<span class="ag-hero-e">Estimation</span>'
                if eau.get("estimation") else "")
    return (f'<div class="ag-hero"><div class="ag-hero-v">{m3}'
            f'{ancre("pompe_volume_m3_jour", m3)} <small>m³ d\'eau par jour'
            f'{a_hmt}</small></div>'
            f'<div class="ag-hero-l">{sur}</div>{pastille}</div>')


def _cartes(synthese):
    eau = synthese.get("eau") or {}
    pompe = synthese.get("pompe") or {}
    champ = synthese.get("champ") or {}
    cartes = []
    cv, kw = _n(pompe.get("cv")), _n(pompe.get("kw"))
    if cv is not None or kw is not None:
        v = f"{cv} CV" if cv is not None else f"{kw} kW"
        s = f"{kw} kW" if cv is not None and kw is not None else ""
        cartes.append(("Puissance pompe", v, s))
    debit, hmt = _n(eau.get("debit_hmt_m3h")), _n(eau.get("hmt_m"))
    if debit is not None:
        cartes.append((f"Débit à {hmt} m" if hmt else "Débit",
                       f'{debit} m³/h{ancre("pompe_debit_m3h", debit)}', ""))
    kwc = _n(champ.get("kwc"), 2)
    if kwc is not None:
        nb = _n(champ.get("nb_panneaux"), 0)
        cartes.append(("Champ PV", f"{kwc} kWc",
                       f"{nb} panneaux" if nb else ""))
    ha = _n(((synthese.get("besoin_vs_livre") or {})
             .get("hectares_irrigables")))
    if ha is not None:
        cartes.append(("Surface irrigable", f"{ha} ha", ""))
    if not cartes:
        return ""
    cellules = "".join(
        f'<div class="ag-card"><div class="ag-card-l">{l}</div>'
        f'<div class="ag-card-v">{v}</div>'
        + (f'<div class="ag-card-s">{s}</div>' if s else "") + '</div>'
        for l, v, s in cartes)
    return f'<div class="ag-cards">{cellules}</div>'


def _argent(synthese, langue):
    eco = synthese.get("economies")
    if not isinstance(eco, dict):
        return ""
    lignes = []
    dep = eco.get("depense_actuelle") or {}
    energie = (synthese.get("energie_actuelle") or {}).get("valeur")
    if _mad(dep.get("annuelle_mad")) is not None:
        quoi = LIBELLES_ENERGIE.get(energie, "")
        lignes.append((f"Votre dépense actuelle par an"
                       + (f" — {quoi}" if quoi else ""),
                       f"{_mad(dep.get('annuelle_mad'))} MAD"))
    charges = eco.get("charges_solaires") or {}
    if _mad(charges.get("total_mad_an")) is not None:
        lignes.append(("Charges du solaire par an (barème)",
                       f"{_mad(charges.get('total_mad_an'))} MAD"))
    flux = ((eco.get("economie") or {}).get("flux") or [])
    an1 = next((f for f in flux if isinstance(f, dict)
                and f.get("annee") == 1), None)
    if an1 and _mad(an1.get("flux_mad")) is not None:
        lignes.append(("Économie nette, année 1",
                       f"{_mad(an1.get('flux_mad'))} MAD"))
    retour = _n((eco.get("economie") or {}).get("retour_ans"))
    if retour is not None:
        lignes.append(("Retour sur investissement, sans aide",
                       f"{retour} ans"))
    m3 = eco.get("mad_par_m3") or {}
    if _num(m3.get("actuel")) is not None and _num(m3.get("solaire")) is not None:
        lignes.append(("Coût du m³ : avant / avec le solaire",
                       f"{_n(m3.get('actuel'), 2)} / {_n(m3.get('solaire'), 2)}"
                       " MAD"))
    for r in eco.get("remplacements") or []:
        if not isinstance(r, dict):
            continue
        montant = _mad(r.get("montant_ttc_mad"))
        if r.get("annee") and montant is not None:
            lignes.append((f"Remplacement {r.get('composant')}, année "
                           f"{r.get('annee')} (compté)",
                           f"{montant} MAD TTC"))
    if not lignes:
        return ""
    corps = "".join(f'<tr><td>{l}</td><td class="r">{v}</td></tr>'
                    for l, v in lignes)
    # La date de déclaration la plus récente (ISO, lue telle quelle).
    dates = sorted(str(e.get("saisi_le"))[:10]
                   for e in eco.get("entrees_declarees") or []
                   if isinstance(e, dict) and _date_fr(e.get("saisi_le")))
    declare = ("Consommation et prix payé : "
               + mentions.phrase_provenance(
                   "declare", langue, date=dates[-1] if dates else None)
               + ".")
    notes = (f'{declare} Indexation du carburant : 0 %. L\'aide FDA '
             f'éventuelle n\'est pas comptée. '
             f'{CONDITION_ECONOMIES.get(langue) or CONDITION_ECONOMIES["fr"]}')
    return (f'<div class="ag-sec">Votre argent</div>'
            f'<div class="ag-box ag-box-gold"><table class="ag-tbl">{corps}'
            f'</table><div class="ag-note">{notes}</div></div>')


def _provenance(synthese, langue, nom_societe):
    prov = synthese.get("provenance") or {}
    lignes = []
    for cle, p in prov.items():
        if not isinstance(p, dict):
            continue
        detail = p.get("detail")
        if detail in ("mesure_visite", "foreur"):
            phrase = mentions.phrase_provenance(
                "mesure", langue, date=p.get("date"), nom_societe=nom_societe)
        elif p.get("origine") in ("saisie", "lead"):
            phrase = mentions.phrase_provenance(
                "declare", langue, date=p.get("date"))
        else:
            phrase = mentions.phrase_provenance("a_confirmer", langue)
        lib = LIBELLES_ENTREES.get(cle, cle.replace("_", " "))
        lignes.append(f'<div class="ag-li"><b>{lib}</b> : {phrase}</div>')
    visite = [LIBELLES_ENTREES.get(c, c.replace("_", " "))
              for c in synthese.get("a_confirmer_par_visite") or []]
    bloc_visite = (
        '<div class="ag-note"><b>À confirmer par la visite :</b> '
        + ", ".join(visite).lower() + ".</div>") if visite else ""
    if not lignes and not bloc_visite:
        return ""
    return (f'<div class="ag-sec">D\'où viennent ces chiffres</div>'
            f'<div class="ag-box">{"".join(lignes)}{bloc_visite}</div>')


def page1(ctx):
    d, synthese = ctx["d"], ctx["synthese"]
    langue = _langue(d)
    client = theme.titlecase_name(d.get("client_full") or d.get("client_name"))
    validite = (f" · offre valable jusqu'au {d.get('valid_until')}"
                if d.get("valid_until") else "")
    entete = (f'<div class="ag-kicker">Proposition · pompage solaire</div>'
              f'<div class="ag-title">L\'eau de votre exploitation, '
              f'pompée par le soleil</div>'
              f'<div class="ag-sub">{client or ""} · Réf. {d.get("ref", "")}'
              f' · {d.get("date", "")}{validite}</div>')
    return (f'<div class="ag-pad">{entete}{_qj(10)}{_hero(synthese)}'
            f'{_qj(15)}{_cartes(synthese)}{_qj(25)}'
            f'{_argent(synthese, langue)}{_qj(25)}'
            f'{_provenance(synthese, langue, ctx["nom_societe"])}'
            f'</div>')


# ── page 2 — comment ça marche ──────────────────────────────────────────────

def _barres_besoin(bvl):
    """Barres « besoin / livré » par mois, en SVG (mise à l'échelle seule)."""
    mois = bvl.get("mois") or []
    valeurs = [(_num(m.get("besoin_m3_jour")), _num(m.get("livre_m3_jour")))
               for m in mois if isinstance(m, dict)]
    if len(valeurs) != 12 or any(b is None or q is None for b, q in valeurs):
        return None
    haut = max(max(b, q) for b, q in valeurs) or 1.0
    l_vb, h_vb, x0, y0, y1 = 600, 260, 40, 220, 20
    pas = (l_vb - x0 - 10) / 12
    corps = [f'<line x1="{x0}" y1="{y0}" x2="{l_vb - 10}" y2="{y0}" '
             f'stroke="#1F2937" stroke-width="1.2"/>']
    for i, (b, q) in enumerate(valeurs):
        x = x0 + i * pas + 4
        for j, (v, coul) in enumerate(((b, "#9CA3AF"), (q, "#2C5F8A"))):
            h = (v / haut) * (y0 - y1)
            corps.append(f'<rect x="{x + j * (pas / 2 - 3):.1f}" '
                         f'y="{y0 - h:.1f}" width="{pas / 2 - 5:.1f}" '
                         f'height="{h:.1f}" fill="{coul}"/>')
        corps.append(f'<text x="{x + pas / 2 - 4:.1f}" y="{y0 + 16}" '
                     f'font-size="12" text-anchor="middle" fill="#6B7280" '
                     f'font-family="DejaVu Sans, Arial, sans-serif">'
                     f'{MOIS_COURTS[i]}</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {l_vb} '
            f'{h_vb + 10}" width="100%">{"".join(corps)}</svg>')


def page2(ctx):
    d, synthese = ctx["d"], ctx["synthese"]
    langue = _langue(d)
    schema = synthese.get("schema_svg") or ""
    courbe = courbe_svg(synthese, langue=langue)
    if courbe:
        bloc_courbe = f'<div class="ag-svg">{courbe}</div>'
    else:
        motif = (TEXTE_COURBE_ABSENTE.get(langue)
                 or TEXTE_COURBE_ABSENTE["fr"])
        bloc_courbe = f'<div class="ag-omis">{motif} Point de fonctionnement omis.</div>'
    bvl = synthese.get("besoin_vs_livre")
    barres = _barres_besoin(bvl) if isinstance(bvl, dict) else None
    if barres:
        serre = bvl.get("mois_le_plus_serre")
        try:
            serre_txt = MOIS_LONGS[int(serre) - 1]
        except (TypeError, ValueError, IndexError):
            serre_txt = None
        legende = ('<div class="ag-note">Gris : votre besoin par jour ; '
                   'bleu : l\'eau livrée par jour.'
                   + (f' Mois le plus serré : <b>{serre_txt}</b>.'
                      if serre_txt else "") + '</div>')
        bloc_besoin = f'<div class="ag-svg">{barres}</div>{legende}'
    else:
        motif = (_omission(synthese, "besoin_vs_livre")
                 or "comparaison besoin / eau livrée omise")
        bloc_besoin = f'<div class="ag-omis">Besoin et eau livrée par mois : {motif}.</div>'
    plaque_html = ""
    if synthese.get("mode_pompe") == "existante":
        plaque = (synthese.get("pompe") or {}).get("plaque")
        if isinstance(plaque, dict):
            elems = []
            if _n(plaque.get("kw")) is not None:
                elems.append(f"{_n(plaque.get('kw'))} kW")
            if _n(plaque.get("tension_v"), 0) is not None:
                elems.append(f"{_n(plaque.get('tension_v'), 0)} V")
            if plaque.get("phases"):
                elems.append(str(plaque.get("phases")))
            plaque_html = (
                '<div class="ag-sec">Votre pompe existante</div>'
                '<div class="ag-box">Plaque relevée : '
                + (" · ".join(elems) or "non lisible")
                + '. Le variateur et les panneaux sont dimensionnés sur '
                  'cette plaque.</div>')
        else:
            plaque_html = (
                '<div class="ag-sec">Votre pompe existante</div>'
                f'<div class="ag-omis">{_omission(synthese, "pompe.plaque") or "plaque non relevée"}.</div>')
    aide = (synthese.get("aide_fda") or {}).get("textes") or {}
    aide_txt = aide.get(langue) or aide.get("fr") or ""
    aide_html = (f'<div class="ag-sec">Aide de l\'État (FDA) : la règle</div>'
                 f'<div class="ag-box ag-small">{aide_txt}</div>'
                 if aide_txt else "")
    return (f'<div class="ag-pad">'
            f'<div class="ag-kicker">Votre installation</div>'
            f'<div class="ag-title">Comment ça marche</div>{_qj(10)}'
            f'<div class="ag-box ag-svg">{schema}</div>{_qj(30)}'
            f'<div class="ag-cols"><div class="ag-col">'
            f'<div class="ag-sec">Point de fonctionnement</div>{bloc_courbe}'
            f'</div><div class="ag-col">'
            f'<div class="ag-sec">Besoin et eau livrée</div>{bloc_besoin}'
            f'</div></div>{_qj(30)}{plaque_html}{_qj(15)}{aide_html}</div>')


# ── page 3 — équipement, prix, garanties ────────────────────────────────────

def _items(d):
    return [it for it in (d.get("all_items") or [])
            if isinstance(it, dict) and (_num(it.get("quantite")) or 0) > 0]


def _lignes(d):
    items = _items(d)
    structure = d.get("lignes_structure") or []
    seq = (sequence_affichage(items, structure) if structure
           else [("item", it) for it in items])
    rows = []
    for kind, it in seq:
        if kind == "struct":
            rows.append(f'<tr><td colspan="5"><b>{it.get("texte") or ""}'
                        f'</b></td></tr>')
            continue
        qte = _num(it.get("quantite")) or 0
        pu = _num(it.get("prix_unit_ht")) or 0
        taux = _num(it.get("taux_tva")) or 0
        marque = (it.get("marque") or "").strip()
        mq = f' <span class="ag-mq">{marque}</span>' if marque else ""
        rows.append(
            f'<tr><td>{it.get("designation") or ""}{mq}</td>'
            f'<td class="r">{qte:g}</td><td class="r">{fmt_centimes(pu)}</td>'
            f'<td class="r">{taux:g} %</td>'
            f'<td class="r t">{fmt_centimes(pu * qte)}</td></tr>')
    return "".join(rows)


def _totaux(d):
    tot = d.get("totaux_all") or {}
    lignes = [("Sous-total HT", "sous_total_ht", tot.get("ht_brut"), "")]
    if (_num(tot.get("remise")) or 0) > 0:
        lignes.append(("Remise", "remise", tot.get("remise"), "- "))
    if (_num(tot.get("arrondi")) or 0) > 0:
        lignes.append(("Arrondi commercial", "arrondi", tot.get("arrondi"),
                       "- "))
    lignes += [("Total HT", "total_ht", tot.get("ht_net"), ""),
               ("TVA", "tva", tot.get("tva"), "")]
    corps = ""
    for lib, cle, val, signe in lignes:
        f = fmt_centimes(_num(val) or 0)
        corps += (f'<tr><td>{lib}{ancre(cle, f)}</td>'
                  f'<td class="r">{signe}{f} MAD</td></tr>')
    ttc = fmt_centimes(_num(tot.get("ttc")) or 0)
    corps += (f'<tr class="ag-tot-ttc"><td>Total TTC'
              f'{ancre("total_ttc", ttc)}</td><td class="r">{ttc} MAD</td></tr>')
    return f'<table class="ag-tot-t">{corps}</table>'


def _garanties(synthese):
    gar = [g for g in synthese.get("garanties") or [] if isinstance(g, dict)]
    if not gar:
        return ('<div class="ag-small"><b>Garanties</b> : durées '
                'constructeur à lire sur les fiches produits.</div>')
    return ('<div class="ag-small"><b>Garanties</b></div>'
            + "".join(f'<div class="ag-li">{g.get("libelle")}</div>'
                      for g in gar))


def _formalites(synthese, langue):
    items = []
    for f in synthese.get("formalites") or []:
        textes = (f or {}).get("textes") or {}
        texte = textes.get(langue) or textes.get("fr")
        if texte:
            items.append(f'<div class="ag-li" data-formalite="{f.get("cle")}">'
                         f'{texte}</div>')
    if not items:
        return ""
    return ('<div class="ag-sec">Formalités</div>'
            f'<div class="ag-box">{"".join(items)}</div>')


def page3(ctx):
    d, synthese = ctx["d"], ctx["synthese"]
    langue = _langue(d)
    non_inclus = ", ".join(LIBELLES_NON_INCLUS.get(c, c)
                           for c in synthese.get("non_inclus") or [])
    non_inclus_html = (f'<div class="ag-small" style="margin-top:4px;">'
                       f'<b>Non inclus</b> : {non_inclus}.</div>'
                       if non_inclus else "")
    return (f'<div class="ag-pad">'
            f'<div class="ag-kicker">Votre kit de pompage</div>'
            f'<div class="ag-title">Équipement, prix et garanties</div>'
            f'<table class="ag-lines"><tr><th>Désignation</th>'
            f'<th class="r">Qté</th><th class="r">P.U. HT</th>'
            f'<th class="r">TVA</th><th class="r">Total HT</th></tr>'
            f'{_lignes(d)}</table>{_qj(20)}'
            f'<div class="ag-tot"><div class="ag-tot-g">{_garanties(synthese)}'
            f'{non_inclus_html}</div><div class="ag-tot-d">{_totaux(d)}'
            f'</div></div>{_qj(20)}{_formalites(synthese, langue)}{_qj(30)}'
            f'{cloture(ctx)}</div>')


# ── AGR311 — clôture de la page 3 (canon v6) ────────────────────────────────

#: Créneaux de l'échéancier (``PAYMENT_TERMS_BY_MODE['agricole']``, résolu
#: par le builder dans ``payment_terms``) et leur moment.
CRENEAUX = (
    ("acompte", "Acompte à la commande"),
    ("materiel", "À la réception du matériel"),
    ("solde", "Après mise en marche"),
)


def _lien_signature(d):
    """Le lien TOKENISÉ de la proposition (QRP1), sinon None : un repli
    « /signer/<réf> » n'est pas un lien de signature, aucun QR n'est imprimé."""
    lien = ((d.get("links") or {}).get("signer") or "").strip()
    return lien if "/proposition/" in lien else None


def _options_a_cocher(synthese):
    options = [o for o in synthese.get("options_kit") or []
               if isinstance(o, dict) and o.get("designation")]
    if not options:
        return ""
    cases = []
    for o in options:
        prix = _mad(o.get("total_ttc"))
        supplement = (f'<b>+ {prix} MAD TTC</b>' if prix is not None else "")
        cases.append(f'<td class="ag-opt"><span class="ag-case"></span>'
                     f'{o.get("designation")} {supplement}</td>')
    lignes = "".join(
        "<tr>" + "".join(cases[i:i + 2])
        + ("<td></td>" if len(cases[i:i + 2]) == 1 else "") + "</tr>"
        for i in range(0, len(cases), 2))
    return ('<div class="ag-small"><b>Options du kit</b> (cochez celles que '
            'vous retenez ; prix du supplément, hors total ci-dessus)</div>'
            f'<table class="ag-opts">{lignes}</table>')


def _echeancier(d):
    termes = d.get("payment_terms") or {}
    tot = _num((d.get("totaux_all") or {}).get("ttc"))
    montants = None
    for branche in ("sans", "avec"):
        m = (d.get("montants_tranches") or {}).get(branche) or {}
        if tot is not None and _num(m.get("total")) is not None \
                and abs(_num(m.get("total")) - tot) < 0.005:
            montants = m
            break
    cases = []
    for cle, libelle in CRENEAUX:
        pct = _num(termes.get(cle))
        if not pct:
            continue
        montant = _mad((montants or {}).get(cle)) if montants else None
        cases.append(f'<td><div class="ag-ech-l">{libelle}</div>'
                     f'<div class="ag-ech-v">{_n(pct)} %'
                     + (f' · {montant} MAD' if montant else "")
                     + '</div></td>')
    if not cases:
        return ""
    return f'<table class="ag-ech"><tr>{"".join(cases)}</tr></table>'


def cloture(ctx):
    """AGR311 — « Bon pour accord », options à cocher, date butoir ABSOLUE,
    QR « Scannez pour signer » (lien tokenisé seulement), échéancier. AUCUNE
    annexe de rétractation 31-08 : un achat d'exploitation n'est pas un achat
    « non professionnel » (art. 2) — question confiée au juriste."""
    d, synthese, C = ctx["d"], ctx["synthese"], ctx["C"]
    brand = ctx["ident"].get("brand_name") or ""
    client = theme.titlecase_name(d.get("client_full") or d.get("client_name"))
    validite = (f"Offre valable jusqu'au <b>{d.get('valid_until')}</b>"
                if d.get("valid_until") else "")
    lien = _lien_signature(d)
    qr_html = ""
    if lien:
        uri = theme.qr_data_uri(lien, front=(26, 43, 74))
        if uri:
            qr_html = (f'<td class="ag-qr"><img src="{uri}" alt="QR">'
                       f'<div>Scannez pour signer</div></td>')
    sig = (
        '<table class="ag-sigs"><tr>'
        f'<td class="ag-sig"><div class="ag-sig-w">Bon pour accord — le client'
        f'</div><div class="ag-sig-n">{client or ""}</div>'
        '<div class="ag-sig-z"></div><div class="ag-sig-h">Nom, date, mention '
        '« Bon pour accord » et signature</div></td>'
        f'<td class="ag-sig"><div class="ag-sig-w">Pour {brand}</div>'
        '<div class="ag-sig-n">Cachet et signature</div>'
        '<div class="ag-sig-z"></div><div class="ag-sig-h">Date</div></td>'
        f'{qr_html}</tr></table>')
    return (f'<div class="ag-accord"><div class="ag-accord-hd">'
            f'<span class="ag-accord-t">Bon pour accord</span>'
            f'<span class="ag-accord-v">{validite}</span></div>'
            f'{_options_a_cocher(synthese)}{_echeancier(d)}{sig}</div>')


# ── assemblage ──────────────────────────────────────────────────────────────

def densite_compacte(d) -> bool:
    """Page 3 resserrée quand le tableau et les options sont longs (≥ 9
    lignes affichées, ou ≥ 12 lignes + options)."""
    lignes = len(_items(d)) + len(d.get("lignes_structure") or [])
    options = len((d.get("synthese") or {}).get("options_kit") or [])
    return lignes >= 9 or lignes + options >= 12


def build_ctx(d):
    ident = theme.company_identity(d)
    return {
        "d": d,
        "synthese": d.get("synthese") or {},
        "C": theme.C,
        "fonts": {"display": theme.FONT_DISPLAY, "serif": theme.FONT_SERIF,
                  "sans": theme.FONT_SANS},
        "ident": ident,
        "nom_societe": (d.get("entreprise") or {}).get("nom"),
        "compact": densite_compacte(d),
    }


def build_html(d: dict, elastic: dict | None = None) -> str:
    """``elastic`` : {numéro de page: mm de vide MESURÉ à répartir sur les
    joints ``.qj``} (second passage du renderer) ; None → joints inertes."""
    from ..residential.render import _apply_elastic

    ctx = build_ctx(d)
    pages = [page1(ctx), page2(ctx), page3(ctx)]
    total = len(pages)
    elastic = elastic or {}
    body = "".join(
        '<div class="page">'
        + _apply_elastic(inner, float(elastic.get(n, 0.0)))
        + theme.page_footer(d, ctx["ident"], total_pages=total,
                            traduire=True).replace("{page}", str(n))
        + '</div>'
        for n, inner in enumerate(pages, start=1))
    langue = _langue(d)
    racine = "<html>" if langue == "fr" else f'<html lang="{langue}">'
    return (f"<!doctype html>{racine}<head><meta charset='utf-8'>"
            f"<style>{theme.base_css()}{theme.css_langue(d)}"
            f"{_css(ctx['C'], ctx['fonts'], ctx['compact'])}</style></head>"
            f"<body>{body}</body></html>")
