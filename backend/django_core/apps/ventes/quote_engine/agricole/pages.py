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

from .. import i18n_labels
from ..figures import ancre
from ..lecture_pure import nombre_ou_none
from ..montants import fmt_centimes, lignes_remisees, tronquer_au_mot
from ..residential import theme
from ..sequence import sequence_affichage
from . import mentions
from .schema import TEXTE_COURBE_ABSENTE, courbe_svg
from .synthese import CONDITION_ECONOMIES

NB_PAGES = 3

def _t(langue, cle, **valeurs):
    """AGR314 — libellé STRUCTUREL ``cle`` du catalogue unique
    (``quote_engine.i18n_labels``, repli français ; une clé absente lève
    ``KeyError`` au test), ses gabarits remplis de valeurs DÉJÀ formatées."""
    texte = i18n_labels.libelle(cle, langue)
    return texte.format(**valeurs) if valeurs else texte


# ── formatage (aucun calcul) ────────────────────────────────────────────────

_num = nombre_ou_none


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
    # ``compact`` : 0 aéré, 1 resserré, 2 serré (AGR314 — tableau long + 8
    # options, ou police arabe aux lignes plus hautes).
    td_pad = {0: "5px 7px", 1: "2.4px 6px"}.get(compact, "1.4px 5px")
    td_fs = {0: "8.8pt", 1: "7.6pt"}.get(compact, "7pt")
    serre = ("" if compact < 2 else
             ".ag-title{font-size:19pt;}.ag-sec{font-size:11pt;"
             "margin:5px 0 3px;}.ag-li{font-size:7.4pt;}"
             ".ag-small{font-size:7.2pt;}.ag-box{padding:5px 9px;}")
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
.ag-was {{ text-decoration:line-through; color:{C['muted_2']}; }}
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
.ag-opt {{ font-size:{('7.8pt', '7.2pt')[min(compact, 1)] if compact < 2 else '6.8pt'}; padding:1.5px 4px 1.5px 0;
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
.ag-sig-z {{ height:{('17mm', '13mm', '9mm')[min(compact, 2)]}; }}
.ag-sig-h {{ font-size:6.6pt; color:{C['muted_2']}; }}
.ag-qr {{ width:26mm; text-align:center; vertical-align:middle;
  font-size:6.8pt; color:{C['navy']}; font-weight:700; }}
.ag-qr img {{ width:22mm; height:22mm; }}
""" + serre


# ── page 1 — l'eau et l'argent ──────────────────────────────────────────────

def _hero(synthese, lg):
    eau = synthese.get("eau") or {}
    m3 = _n(eau.get("m3_jour"))
    hmt = _n(eau.get("hmt_m"))
    heures = _n(eau.get("heures_pompage"))
    if m3 is None:
        return (f'<div class="ag-hero"><div class="ag-hero-v">'
                f'{_t(lg, "agr_hero_sans_volume_titre")}</div>'
                f'<div class="ag-hero-l">{_t(lg, "agr_hero_sans_volume")}'
                f'</div></div>')
    a_hmt = (f' {_t(lg, "agr_hero_a_hmt", hmt=hmt)}'
             f'{ancre("pompe_hmt_m", hmt)}' if hmt is not None else "")
    sur = (_t(lg, "sur_heures_pompage", heures=heures)
           if heures is not None else "")
    pastille = (f'<span class="ag-hero-e">{_t(lg, "estimation")}</span>'
                if eau.get("estimation") else "")
    return (f'<div class="ag-hero"><div class="ag-hero-v">{m3}'
            f'{ancre("pompe_volume_m3_jour", m3)} <small>'
            f'{_t(lg, "agr_hero_m3_jour")}{a_hmt}</small></div>'
            f'<div class="ag-hero-l">{sur}</div>{pastille}</div>')


def _cartes(synthese, lg):
    eau = synthese.get("eau") or {}
    pompe = synthese.get("pompe") or {}
    champ = synthese.get("champ") or {}
    cartes = []
    cv, kw = _n(pompe.get("cv")), _n(pompe.get("kw"))
    if cv is not None or kw is not None:
        v = f"{cv} CV" if cv is not None else f"{kw} kW"
        s = f"{kw} kW" if cv is not None and kw is not None else ""
        cartes.append((_t(lg, "puissance_pompe"), v, s))
    debit, hmt = _n(eau.get("debit_hmt_m3h")), _n(eau.get("hmt_m"))
    if debit is not None:
        cartes.append((_t(lg, "debit_a_hmt", hmt=hmt) if hmt
                       else _t(lg, "agr_debit"),
                       f'{debit} m³/h{ancre("pompe_debit_m3h", debit)}', ""))
    kwc = _n(champ.get("kwc"), 2)
    if kwc is not None:
        nb = _n(champ.get("nb_panneaux"), 0)
        cartes.append((_t(lg, "champ_pv"), f"{kwc} kWc",
                       _t(lg, "agr_panneaux_n", n=nb) if nb else ""))
    ha = _n(((synthese.get("besoin_vs_livre") or {})
             .get("hectares_irrigables")))
    if ha is not None:
        cartes.append((_t(lg, "agr_surface_irrigable"), f"{ha} ha", ""))
    if not cartes:
        return ""
    cellules = "".join(
        f'<div class="ag-card"><div class="ag-card-l">{l}</div>'
        f'<div class="ag-card-v">{v}</div>'
        + (f'<div class="ag-card-s">{s}</div>' if s else "") + '</div>'
        for l, v, s in cartes)
    return f'<div class="ag-cards">{cellules}</div>'


def _composant(lg, cle):
    return (_t(lg, f"agr_composant_{cle}")
            if f"agr_composant_{cle}" in i18n_labels.LIBELLES else cle)


def _argent(synthese, lg):
    eco = synthese.get("economies")
    if not isinstance(eco, dict):
        return ""
    lignes = []
    dep = eco.get("depense_actuelle") or {}
    energie = (synthese.get("energie_actuelle") or {}).get("valeur")
    if _mad(dep.get("annuelle_mad")) is not None:
        cle_energie = f"agr_energie_{energie}"
        quoi = (_t(lg, cle_energie)
                if cle_energie in i18n_labels.LIBELLES else "")
        lignes.append((_t(lg, "agr_depense_actuelle")
                       + (f" — {quoi}" if quoi else ""),
                       f"{_mad(dep.get('annuelle_mad'))} MAD"))
    charges = eco.get("charges_solaires") or {}
    if _mad(charges.get("total_mad_an")) is not None:
        lignes.append((_t(lg, "agr_charges_solaires"),
                       f"{_mad(charges.get('total_mad_an'))} MAD"))
    flux = ((eco.get("economie") or {}).get("flux") or [])
    an1 = next((f for f in flux if isinstance(f, dict)
                and f.get("annee") == 1), None)
    if an1 and _mad(an1.get("flux_mad")) is not None:
        lignes.append((_t(lg, "agr_economie_nette_an1"),
                       f"{_mad(an1.get('flux_mad'))} MAD"))
    retour = _n((eco.get("economie") or {}).get("retour_ans"))
    if retour is not None:
        lignes.append((_t(lg, "agr_retour_sans_aide"),
                       _t(lg, "agr_n_ans", n=retour)))
    m3 = eco.get("mad_par_m3") or {}
    if _num(m3.get("actuel")) is not None and _num(m3.get("solaire")) is not None:
        lignes.append((_t(lg, "agr_cout_m3"),
                       f"{_n(m3.get('actuel'), 2)} / {_n(m3.get('solaire'), 2)}"
                       " MAD"))
    for r in eco.get("remplacements") or []:
        if not isinstance(r, dict):
            continue
        montant = _mad(r.get("montant_ttc_mad"))
        if r.get("annee") and montant is not None:
            lignes.append((_t(lg, "agr_remplacement",
                              composant=_composant(lg, r.get("composant")),
                              annee=r.get("annee")),
                           f"{montant} MAD TTC"))
    if not lignes:
        return ""
    corps = "".join(f'<tr><td>{l}</td><td class="r">{v}</td></tr>'
                    for l, v in lignes)
    # La date de déclaration la plus récente (ISO, lue telle quelle).
    dates = sorted(str(e.get("saisi_le"))[:10]
                   for e in eco.get("entrees_declarees") or []
                   if isinstance(e, dict) and _date_fr(e.get("saisi_le")))
    declare = _t(lg, "agr_conso_prix_paye", phrase=mentions.phrase_provenance(
        "declare", lg, date=dates[-1] if dates else None))
    notes = (f'{declare} {_t(lg, "agr_indexation")} '
             f'{_t(lg, "agr_fda_non_comptee")} '
             f'{CONDITION_ECONOMIES.get(lg) or CONDITION_ECONOMIES["fr"]}')
    return (f'<div class="ag-sec">{_t(lg, "agr_votre_argent")}</div>'
            f'<div class="ag-box ag-box-gold"><table class="ag-tbl">{corps}'
            f'</table><div class="ag-note">{notes}</div></div>')


def _entree(lg, cle):
    """Libellé d'une entrée de provenance (contrat AGR2) ; une clé hors
    catalogue (donnée nouvelle) est imprimée lisible, jamais traduite."""
    cle_i18n = f"agr_entree_{cle}"
    if cle_i18n in i18n_labels.LIBELLES:
        return _t(lg, cle_i18n)
    return str(cle).replace("_", " ")


def _provenance(synthese, lg, nom_societe):
    prov = synthese.get("provenance") or {}
    lignes = []
    for cle, p in prov.items():
        if not isinstance(p, dict):
            continue
        detail = p.get("detail")
        if detail in ("mesure_visite", "foreur"):
            phrase = mentions.phrase_provenance(
                "mesure", lg, date=p.get("date"), nom_societe=nom_societe)
        elif p.get("origine") in ("saisie", "lead"):
            phrase = mentions.phrase_provenance(
                "declare", lg, date=p.get("date"))
        else:
            phrase = mentions.phrase_provenance("a_confirmer", lg)
        lignes.append(f'<div class="ag-li"><b>{_entree(lg, cle)}</b> : '
                      f'{phrase}</div>')
    visite = [_entree(lg, c) for c in synthese.get("a_confirmer_par_visite")
              or []]
    bloc_visite = (
        f'<div class="ag-note"><b>{_t(lg, "agr_a_confirmer_visite")}</b> '
        + ", ".join(visite) + ".</div>") if visite else ""
    if not lignes and not bloc_visite:
        return ""
    return (f'<div class="ag-sec">{_t(lg, "agr_provenance_titre")}</div>'
            f'<div class="ag-box">{"".join(lignes)}{bloc_visite}</div>')


def page1(ctx):
    d, synthese = ctx["d"], ctx["synthese"]
    lg = _langue(d)
    client = theme.titlecase_name(d.get("client_full") or d.get("client_name"))
    validite = (" · " + _t(lg, "agr_valable_court", date=d.get("valid_until"))
                if d.get("valid_until") else "")
    entete = (f'<div class="ag-kicker">{_t(lg, "agr_kicker_p1")}</div>'
              f'<div class="ag-title">{_t(lg, "agr_titre_p1")}</div>'
              f'<div class="ag-sub">{client or ""} · {_t(lg, "reference")} '
              f'{d.get("ref", "")} · {d.get("date", "")}{validite}</div>')
    # ADEV67 (C-ADEV-044) — « Document mis à jour le … / Remplace le devis
    # … » : même décision du builder, même helper que les autres marchés.
    entete += "".join(f'<div class="ag-sub">{m}</div>'
                      for m in theme.marques_correction(d))
    return (f'<div class="ag-pad">{entete}{_qj(10)}{_hero(synthese, lg)}'
            f'{_qj(15)}{_cartes(synthese, lg)}{_qj(25)}'
            f'{_argent(synthese, lg)}{_qj(25)}'
            f'{_provenance(synthese, lg, ctx["nom_societe"])}'
            f'</div>')


# ── page 2 — comment ça marche ──────────────────────────────────────────────

def _barres_besoin(bvl, lg):
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
                     f'{_t(lg, f"agr_moisc_{i + 1}")}</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {l_vb} '
            f'{h_vb + 10}" width="100%">{"".join(corps)}</svg>')


def page2(ctx):
    d, synthese = ctx["d"], ctx["synthese"]
    lg = _langue(d)
    schema = synthese.get("schema_svg") or ""
    courbe = courbe_svg(synthese, langue=lg)
    if courbe:
        bloc_courbe = f'<div class="ag-svg">{courbe}</div>'
    else:
        motif = TEXTE_COURBE_ABSENTE.get(lg) or TEXTE_COURBE_ABSENTE["fr"]
        bloc_courbe = (f'<div class="ag-omis">{motif} '
                       f'{_t(lg, "agr_point_omis")}</div>')
    bvl = synthese.get("besoin_vs_livre")
    barres = _barres_besoin(bvl, lg) if isinstance(bvl, dict) else None
    if barres:
        try:
            serre = int(bvl.get("mois_le_plus_serre"))
            serre_txt = (_t(lg, f"agr_mois_{serre}")
                         if 1 <= serre <= 12 else None)
        except (TypeError, ValueError):
            serre_txt = None
        # AMOT44 (C-AMOT-056) — un besoin AGRONOMIQUE PLEIN (FAO-56) n'est
        # pas « votre besoin » : la légende le qualifie comme la page web.
        if bvl.get("base_besoin") == "agronomique_plein":
            _phrase = mentions.PHRASES_PROVENANCE["agronomique"]
            _leg = _t(lg, "agr_base_besoin_agronomique",
                      phrase=_phrase.get(lg) or _phrase["fr"])
        else:
            _leg = _t(lg, "agr_legende_barres")
        legende = (f'<div class="ag-note">{_leg}'
                   + (f' {_t(lg, "agr_mois_serre", mois=serre_txt)}'
                      if serre_txt else "") + '</div>')
        bloc_besoin = f'<div class="ag-svg">{barres}</div>{legende}'
    else:
        motif = _omission(synthese, "besoin_vs_livre")
        # Le motif de la synthèse est écrit en français : il n'est imprimé
        # tel quel que dans un document français.
        texte = (_t(lg, "agr_besoin_omis_motif", motif=motif)
                 if motif and lg == "fr" else _t(lg, "agr_besoin_omis"))
        bloc_besoin = f'<div class="ag-omis">{texte}</div>'
    plaque_html = ""
    if synthese.get("mode_pompe") == "existante":
        titre = f'<div class="ag-sec">{_t(lg, "agr_pompe_existante")}</div>'
        plaque = (synthese.get("pompe") or {}).get("plaque")
        if isinstance(plaque, dict):
            elems = []
            if _n(plaque.get("kw")) is not None:
                elems.append(f"{_n(plaque.get('kw'))} kW")
            if _n(plaque.get("tension_v"), 0) is not None:
                elems.append(f"{_n(plaque.get('tension_v'), 0)} V")
            if plaque.get("phases"):
                elems.append(str(plaque.get("phases")))
            plaque_html = (titre + '<div class="ag-box">' + _t(
                lg, "agr_plaque_relevee",
                plaque=" · ".join(elems) or _t(lg, "agr_plaque_illisible"))
                + '</div>')
        else:
            plaque_html = (titre + '<div class="ag-omis">'
                           + _t(lg, "agr_plaque_non_relevee") + '</div>')
    aide = (synthese.get("aide_fda") or {}).get("textes") or {}
    aide_txt = aide.get(lg) or aide.get("fr") or ""
    aide_html = (f'<div class="ag-sec">{_t(lg, "agr_aide_titre")}</div>'
                 f'<div class="ag-box ag-small">{aide_txt}</div>'
                 if aide_txt else "")
    return (f'<div class="ag-pad">'
            f'<div class="ag-kicker">{_t(lg, "agr_kicker_p2")}</div>'
            f'<div class="ag-title">{_t(lg, "agr_titre_p2")}</div>{_qj(10)}'
            f'<div class="ag-box ag-svg">{schema}</div>{_qj(30)}'
            f'<div class="ag-cols"><div class="ag-col">'
            f'<div class="ag-sec">{_t(lg, "agr_point_fonctionnement")}</div>'
            f'{bloc_courbe}</div><div class="ag-col">'
            f'<div class="ag-sec">{_t(lg, "agr_besoin_livre_titre")}</div>'
            f'{bloc_besoin}</div></div>{_qj(30)}{plaque_html}{_qj(15)}'
            f'{aide_html}</div>')


# ── page 3 — équipement, prix, garanties ────────────────────────────────────

def _items(d):
    return [it for it in (d.get("all_items") or [])
            if isinstance(it, dict) and (_num(it.get("quantite")) or 0) > 0]


#: AMOT37 (C-AMOT-046) — libellé DÉCLARÉ de la ligne de regroupement (le
#: détail reste sur la proposition en ligne). en/ar à relire (CIQM22).
_LIBELLE_REGROUPEMENT = {
    "fr": "Autres équipements ({n} lignes) — détail sur la proposition en "
          "ligne",
    "en": "Other equipment ({n} lines) — details in the online proposal",
    "ar": "معدات أخرى ({n} سطر) — التفاصيل في العرض عبر الإنترنت",
}


def _ligne_regroupee(reste, lg):
    """AMOT37 — UNE ligne qui regroupe ``reste`` : total HT = Σ des lignes
    regroupées (aucun dirham ne disparaît), TVA affichée si unique."""
    total = sum(ligne[4] for ligne in lignes_remisees(reste))
    taux = {(_num(it.get("taux_tva")) or 0) for it in reste}
    taux_txt = f"{taux.pop():g} %" if len(taux) == 1 else "—"
    libelle = _LIBELLE_REGROUPEMENT.get(lg, _LIBELLE_REGROUPEMENT["fr"])
    return (f'<tr><td>{libelle.format(n=len(reste))}</td>'
            f'<td class="r"></td><td class="r"></td>'
            f'<td class="r">{taux_txt}</td>'
            f'<td class="r t">{fmt_centimes(total)}</td></tr>')


def _lignes(d):
    items = _items(d)
    # AMOT37 — regroupement DÉCLARÉ posé par le renderer quand même la
    # densité serrée ne tient pas en 3 pages : les ``garder`` premières
    # lignes restent, la suite tient en UNE ligne au total exact.
    garder = d.get("_regrouper_apres")
    reste = []
    if isinstance(garder, int) and 0 <= garder < len(items) - 1:
        items, reste = items[:garder], items[garder:]
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
        taux = _num(it.get("taux_tva")) or 0
        marque = (it.get("marque") or "").strip()
        mq = f' <span class="ag-mq">{marque}</span>' if marque else ""
        # AMOT45 (C-AMOT-057) — la remise globale LIGNE PAR LIGNE (QJRREM),
        # par LE helper unique : P.U. catalogue barré + P.U. remisé, et
        # Σ des totaux de ligne = Total HT.
        (_it, pu_cat, pu_rem, _tot_cat, tot_rem,
         remisee) = lignes_remisees([it])[0]
        pu_txt = (f'<span class="ag-was">{fmt_centimes(pu_cat)}</span> '
                  f'{fmt_centimes(pu_rem)}' if remisee
                  else fmt_centimes(pu_rem))
        rows.append(
            f'<tr><td>{it.get("designation") or ""}{mq}</td>'
            f'<td class="r">{qte:g}</td><td class="r">{pu_txt}</td>'
            f'<td class="r">{taux:g} %</td>'
            f'<td class="r t">{fmt_centimes(tot_rem)}</td></tr>')
    if reste:
        rows.append(_ligne_regroupee(reste, _langue(d)))
    return "".join(rows)


def _totaux(d, lg):
    tot = d.get("totaux_all") or {}
    lignes = [("sous_total_ht", tot.get("ht_brut"), "")]
    if (_num(tot.get("remise")) or 0) > 0:
        lignes.append(("remise", tot.get("remise"), "- "))
    if (_num(tot.get("arrondi")) or 0) > 0:
        lignes.append(("arrondi", tot.get("arrondi"), "- "))
    lignes += [("total_ht", tot.get("ht_net"), ""),
               ("tva", tot.get("tva"), "")]
    corps = ""
    for cle, val, signe in lignes:
        f = fmt_centimes(_num(val) or 0)
        corps += (f'<tr><td>{_t(lg, cle)}{ancre(cle, f)}</td>'
                  f'<td class="r">{signe}{f} MAD</td></tr>')
    ttc = fmt_centimes(_num(tot.get("ttc")) or 0)
    corps += (f'<tr class="ag-tot-ttc"><td>{_t(lg, "total_ttc")}'
              f'{ancre("total_ttc", ttc)}</td><td class="r">{ttc} MAD</td></tr>')
    return f'<table class="ag-tot-t">{corps}</table>'


def _duree(lg, mois):
    """La durée d'une garantie (mois structurés de la fiche) en mots."""
    if mois % 12 == 0:
        ans = mois // 12
        return _t(lg, "agr_n_an" if ans == 1 else "agr_n_ans", n=ans)
    return _t(lg, "agr_n_mois", n=mois)


def _libelle_garantie(lg, g):
    cle = f"agr_garantie_{g.get('composant')}"
    mois = g.get("mois")
    if cle in i18n_labels.LIBELLES and isinstance(mois, int) and mois > 0:
        return _t(lg, cle, duree=_duree(lg, mois))
    return g.get("libelle") or ""


def _garanties(synthese, lg):
    gar = [g for g in synthese.get("garanties") or [] if isinstance(g, dict)]
    if not gar:
        return (f'<div class="ag-small"><b>{_t(lg, "agr_garanties")}</b> : '
                f'{_t(lg, "agr_garanties_fiches")}</div>')
    return (f'<div class="ag-small"><b>{_t(lg, "agr_garanties")}</b></div>'
            + "".join(f'<div class="ag-li">{_libelle_garantie(lg, g)}</div>'
                      for g in gar))


def _formalites(synthese, lg):
    items = []
    for f in synthese.get("formalites") or []:
        textes = (f or {}).get("textes") or {}
        texte = textes.get(lg) or textes.get("fr")
        if texte:
            items.append(f'<div class="ag-li" data-formalite="{f.get("cle")}">'
                         f'{texte}</div>')
    if not items:
        return ""
    return (f'<div class="ag-sec">{_t(lg, "agr_formalites")}</div>'
            f'<div class="ag-box">{"".join(items)}</div>')


def page3(ctx):
    d, synthese = ctx["d"], ctx["synthese"]
    lg = _langue(d)
    non_inclus = ", ".join(
        _t(lg, f"agr_non_inclus_{c}")
        if f"agr_non_inclus_{c}" in i18n_labels.LIBELLES else str(c)
        for c in synthese.get("non_inclus") or [])
    non_inclus_html = (f'<div class="ag-small" style="margin-top:4px;">'
                       f'<b>{_t(lg, "agr_non_inclus")}</b> : {non_inclus}.'
                       f'</div>' if non_inclus else "")
    entetes = "".join(
        (f'<th>{_t(lg, cle)}</th>' if cle == "designation"
         else f'<th class="r">{_t(lg, cle)}</th>')
        for cle in ("designation", "qte", "pu_ht", "tva", "total_ht"))
    return (f'<div class="ag-pad">'
            f'<div class="ag-kicker">{_t(lg, "agr_kicker_p3")}</div>'
            f'<div class="ag-title">{_t(lg, "agr_titre_p3")}</div>'
            f'<table class="ag-lines"><tr>{entetes}</tr>'
            f'{_lignes(d)}</table>{_qj(20)}'
            f'<div class="ag-tot"><div class="ag-tot-g">'
            f'{_garanties(synthese, lg)}{non_inclus_html}</div>'
            f'<div class="ag-tot-d">{_totaux(d, lg)}</div></div>{_qj(20)}'
            f'{_formalites(synthese, lg)}{_note_et_clauses(d, lg)}'
            f'{_qj(30)}{cloture(ctx)}</div>')


def _note_et_clauses(d, lg):
    """ADEV67 (C-ADEV-044) — la note CLIENT (déjà échappée par le builder)
    et les clauses/CGV gelées (QJR668), comme les autres marchés ; rien
    quand ni l'une ni les autres n'existent (jamais un bloc vide)."""
    from ..clauses_cgv import bloc_clauses_html
    note = (d.get("note_client") or "").strip()
    note_html = (f'<div class="ag-small" style="margin-top:6px;">'
                 f'<b>{_t(lg, "ci_note")}</b> : {note}</div>'
                 if note else "")
    clauses_html = bloc_clauses_html(
        d.get("clauses_cgv"), couleur_titre="#1A2B4A", couleur_texte="#334155",
        taille_pt="7")
    return note_html + clauses_html


# ── AGR311 — clôture de la page 3 (canon v6) ────────────────────────────────

#: Créneaux de l'échéancier (``PAYMENT_TERMS_BY_MODE['agricole']``, résolu
#: par le builder dans ``payment_terms``), dans l'ordre.
CRENEAUX = ("acompte", "materiel", "solde")


def _lien_signature(d):
    """Le lien TOKENISÉ de la proposition (QRP1), sinon None : un repli
    « /signer/<réf> » n'est pas un lien de signature, aucun QR n'est imprimé."""
    lien = ((d.get("links") or {}).get("signer") or "").strip()
    return lien if "/proposition/" in lien else None


def _options_a_cocher(synthese, lg):
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
    return (f'<div class="ag-small">{_t(lg, "agr_options_kit")}</div>'
            f'<table class="ag-opts">{lignes}</table>')


def _echeancier(d, lg):
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
    for cle in CRENEAUX:
        pct = _num(termes.get(cle))
        if not pct:
            continue
        montant = _mad((montants or {}).get(cle)) if montants else None
        cases.append(f'<td><div class="ag-ech-l">'
                     f'{_t(lg, f"agr_creneau_{cle}")}</div>'
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
    d, synthese = ctx["d"], ctx["synthese"]
    lg = _langue(d)
    brand = ctx["ident"].get("brand_name") or ""
    client = theme.titlecase_name(d.get("client_full") or d.get("client_name"))
    validite = (_t(lg, "agr_valable", date=d.get("valid_until"))
                if d.get("valid_until") else "")
    lien = _lien_signature(d)
    qr_html = ""
    if lien:
        uri = theme.qr_data_uri(lien, front=(26, 43, 74))
        if uri:
            qr_html = (f'<td class="ag-qr"><img src="{uri}" alt="QR">'
                       f'<div>{_t(lg, "agr_scannez")}</div></td>')
    sig = (
        '<table class="ag-sigs"><tr>'
        f'<td class="ag-sig"><div class="ag-sig-w">{_t(lg, "agr_bpa_client")}'
        f'</div><div class="ag-sig-n">{client or ""}</div>'
        f'<div class="ag-sig-z"></div><div class="ag-sig-h">'
        f'{_t(lg, "agr_bpa_mention")}</div></td>'
        f'<td class="ag-sig"><div class="ag-sig-w">'
        f'{_t(lg, "agr_bpa_pour", societe=brand)}</div>'
        f'<div class="ag-sig-n">{_t(lg, "agr_bpa_cachet")}</div>'
        f'<div class="ag-sig-z"></div><div class="ag-sig-h">'
        f'{_t(lg, "bpa_date")}</div></td>'
        f'{qr_html}</tr></table>')
    return (f'<div class="ag-accord"><div class="ag-accord-hd">'
            f'<span class="ag-accord-t">{_t(lg, "bon_pour_accord")}</span>'
            f'<span class="ag-accord-v">{validite}</span></div>'
            f'{_options_a_cocher(synthese, lg)}{_echeancier(d, lg)}{sig}'
            f'</div>')


# ── AGR319 — annexe « Note de calcul du kit de pompage » (dossier FDA) ─────

#: Composantes de la HMT (contrat AGR2 › ``hmt.composantes``), dans l'ordre.
COMPOSANTES_HMT = ("niveau_dynamique_m", "denivele_m", "pertes_lineaires_m",
                   "pertes_singulieres_m", "pression_service_m")


def _ligne_role(d, role):
    for it in _items(d):
        if it.get("role_pompage") == role:
            return it
    return None


def _equipement_annexe(d, synthese, lg):
    lignes = []
    champ = synthese.get("champ") or {}
    kwc, nb = _n(champ.get("kwc"), 2), _n(champ.get("nb_panneaux"), 0)
    if kwc is not None and nb is not None:
        lignes.append(_t(lg, "agr_annexe_champ", kwc=kwc, n=nb))
    for role in ("pompe", "variateur_pompage"):
        it = _ligne_role(d, role)
        if it is None:
            continue
        texte = it.get("designation") or ""
        marque = (it.get("marque") or "").strip()
        if marque:
            texte += f" — {marque}"
        mois = it.get("garantie_mois")
        if isinstance(mois, int) and not isinstance(mois, bool) and mois > 0:
            texte += " · " + _t(lg, "agr_annexe_garantie",
                                duree=_duree(lg, mois))
        lignes.append(texte)
    if not lignes:
        lignes.append(_t(lg, "agr_annexe_omis"))
    return "".join(f'<div class="ag-li">{l}</div>' for l in lignes)


def _hmt_annexe(d, synthese, lg, nom_societe):
    etude = d.get("etude") or {}
    hmt = _n((synthese.get("eau") or {}).get("hmt_m"))
    if hmt is None:
        return f'<div class="ag-omis">{_t(lg, "agr_annexe_omis")}</div>'
    comp = etude.get("hmt_composantes") or {}
    lignes = "".join(
        f'<tr><td>{_t(lg, f"agr_comp_{c}")}</td>'
        f'<td class="r">{_n(comp.get(c), 2)} m</td></tr>'
        for c in COMPOSANTES_HMT if _n(comp.get(c), 2) is not None)
    prov = (synthese.get("provenance") or {}).get("hmt_m")
    phrase = ""
    # Une HMT CALCULÉE se lit par ses composantes ci-dessus ; seule une HMT
    # mesurée ou déclarée porte une phrase de provenance (jamais « à
    # confirmer » plaqué sur un calcul).
    cle = None
    if isinstance(prov, dict):
        cle = ("mesure" if prov.get("detail") in ("mesure_visite", "foreur")
               else "declare" if prov.get("origine") in ("saisie", "lead")
               else None)
    if cle:
        phrase = _t(lg, "agr_annexe_provenance",
                    phrase=mentions.phrase_provenance(
                        cle, lg, date=prov.get("date"),
                        nom_societe=nom_societe))
    return (f'<div class="ag-small"><b>{_t(lg, "agr_annexe_hmt", hmt=hmt)}'
            f'</b></div>'
            + (f'<table class="ag-tbl">{lignes}</table>' if lignes else "")
            + (f'<div class="ag-note">{phrase}</div>' if phrase else ""))


def _debit_et_mois_annexe(d, synthese, lg):
    etude = d.get("etude") or {}
    conception = etude.get("conception") or {}
    q = _n(conception.get("debit_conception_m3h"))
    blocs = []
    try:
        mois = int(conception.get("mois_critique"))
        mois_txt = _t(lg, f"agr_mois_{mois}") if 1 <= mois <= 12 else None
    except (TypeError, ValueError):
        mois_txt = None
    if q is not None and mois_txt:
        blocs.append(f'<div class="ag-small">'
                     f'{_t(lg, "agr_annexe_debit_conception", q=q, mois=mois_txt)}'
                     f'</div>')
    serie = (etude.get("production") or {}).get("m3_jour_mois")
    if isinstance(serie, (list, tuple)) and len(serie) == 12 and all(
            _num(v) is not None for v in serie):
        entetes = "".join(f'<td class="r"><b>{_t(lg, f"agr_moisc_{i}")}</b>'
                          f'</td>' for i in range(1, 13))
        valeurs = "".join(f'<td class="r">{_n(v)}</td>' for v in serie)
        blocs.append(f'<div class="ag-small" style="margin-top:4px;">'
                     f'{_t(lg, "agr_annexe_m3_mois")}</div>'
                     f'<table class="ag-tbl"><tr>{entetes}</tr>'
                     f'<tr>{valeurs}</tr></table>')
    if not blocs:
        return f'<div class="ag-omis">{_t(lg, "agr_annexe_omis")}</div>'
    return "".join(blocs)


def _hypotheses_annexe(d, lg):
    hyps = [h for h in ((d.get("etude") or {}).get("hypotheses_pompage")
                        or []) if isinstance(h, dict) and h.get("cle")]
    if not hyps:
        return f'<div class="ag-omis">{_t(lg, "agr_annexe_omis")}</div>'
    lignes = []
    for h in hyps:
        source = (_t(lg, "agr_annexe_est") if h.get("statut") == "estimation"
                  or not h.get("source") else theme._esc(h.get("source")))
        valeur = h.get("valeur")
        valeur = _n(valeur, 3) if _num(valeur) is not None \
            else theme._esc(valeur if valeur is not None else "")
        lignes.append(f'<tr><td>{theme._esc(h.get("cle"))}</td>'
                      f'<td class="r">{valeur}</td><td>{source}</td></tr>')
    return f'<table class="ag-tbl">{"".join(lignes)}</table>'


def _fiches_annexe(d, lg):
    fiches = []
    # Au plus six fiches, 220 caractères chacune : l'annexe tient sur UNE page.
    for it in _items(d):
        if len(fiches) >= 6:
            break
        description = (it.get("description") or "").strip()
        if not description:
            continue
        marque = (it.get("marque") or "").strip()
        titre = it.get("designation") or ""
        if marque:
            titre += f" — {marque}"
        fiches.append(f'<div class="ag-li"><b>{titre}</b> : '
                      # AMOT46 — troncature sur le texte BRUT, au mot.
                      f'{tronquer_au_mot(description, 220)}</div>')
    if not fiches:
        return f'<div class="ag-omis">{_t(lg, "agr_annexe_omis")}</div>'
    return "".join(fiches)


def _references_annexe(d, lg):
    refs = [r for r in d.get("references_pompage") or []
            if isinstance(r, dict) and r.get("titre")]
    if not refs:
        return (f'<div class="ag-small">'
                f'{_t(lg, "agr_annexe_aucune_reference")}</div>')
    return "".join(
        f'<div class="ag-li">{theme._esc(r.get("titre"))}'
        + (f' — {theme._esc(r.get("ville"))}' if r.get("ville") else "")
        + (f' ({theme._esc(r.get("mise_en_service"))})'
           if r.get("mise_en_service") else "")
        + '</div>' for r in refs)


def page_annexe_note_calcul(ctx):
    """AGR319 — annexe rendue SEULEMENT sur ``include_note_calcul`` : kWc et
    panneaux, pompe et variateur (marque, garantie), HMT retenue et ses
    composantes avec provenance, débit de conception, m³/jour par mois,
    hypothèses et leurs sources (ou EST.), fiches produits, références de la
    société. JAMAIS un montant d'aide, jamais ``prix_achat``."""
    d, synthese = ctx["d"], ctx["synthese"]
    lg = _langue(d)
    sec = '<div class="ag-sec">{}</div>'.format
    return (f'<div class="ag-pad">'
            f'<div class="ag-kicker">{_t(lg, "agr_annexe_kicker")}</div>'
            f'<div class="ag-title">{_t(lg, "agr_annexe_titre")}</div>'
            f'{sec(_t(lg, "agr_annexe_equipement"))}'
            f'<div class="ag-box">{_equipement_annexe(d, synthese, lg)}</div>'
            f'{sec(_t(lg, "agr_entree_hmt_m"))}'
            f'<div class="ag-box">'
            f'{_hmt_annexe(d, synthese, lg, ctx["nom_societe"])}</div>'
            f'{sec(_t(lg, "agr_debit"))}'
            f'<div class="ag-box">{_debit_et_mois_annexe(d, synthese, lg)}'
            f'</div>'
            f'{sec(_t(lg, "agr_annexe_hypotheses"))}'
            f'<div class="ag-box">{_hypotheses_annexe(d, lg)}</div>'
            f'{sec(_t(lg, "agr_annexe_fiches"))}'
            f'<div class="ag-box">{_fiches_annexe(d, lg)}</div>'
            f'{sec(_t(lg, "agr_annexe_references"))}'
            f'<div class="ag-box">{_references_annexe(d, lg)}</div>'
            f'</div>')


# ── assemblage ──────────────────────────────────────────────────────────────

def densite_compacte(d) -> int:
    """Densité de la page 3 : 0 aérée, 1 resserrée (≥ 9 lignes affichées, ou
    ≥ 12 lignes + options), 2 serrée (≥ 16 lignes + options)."""
    lignes = len(_items(d)) + len(d.get("lignes_structure") or [])
    options = len((d.get("synthese") or {}).get("options_kit") or [])
    if i18n_labels.est_rtl(_langue(d)):
        # AGR314 — la police arabe a des lignes plus hautes : on resserre
        # plus tôt (mesuré : 12 lignes + 8 options à ~275 mm sur 284).
        seuils = (7, 9, 13)
    else:
        seuils = (9, 12, 16)
    if lignes + options >= seuils[2]:
        return 2
    return 1 if lignes >= seuils[0] or lignes + options >= seuils[1] else 0


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
        # AMOT37 — le renderer peut IMPOSER une densité plus serrée quand
        # le contenu déborde de la bande de pied.
        "compact": max(densite_compacte(d), int(d.get("_compact_min") or 0)),
    }


def build_html(d: dict, elastic: dict | None = None) -> str:
    """``elastic`` : {numéro de page: mm de vide MESURÉ à répartir sur les
    joints ``.qj``} (second passage du renderer) ; None → joints inertes."""
    from ..residential.render import _apply_elastic

    ctx = build_ctx(d)
    pages = [page1(ctx), page2(ctx), page3(ctx)]
    # AGR319 — +1 page SEULEMENT sur l'option explicite ``include_note_calcul``.
    if d.get("include_note_calcul"):
        pages.append(page_annexe_note_calcul(ctx))
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
    # AGR314 — même traitement de langue que le une-page legacy
    # (``_attributs_langue_html``) : ``lang`` + ``dir="rtl"`` en arabe, d'où
    # WeasyPrint tire l'alignement à droite et l'ordre miroir des tableaux ;
    # la police arabe vendorisée s'applique à tout le document arabe.
    if langue == "fr":
        racine = "<html>"
    else:
        racine = (f'<html lang="{langue}" '
                  f'dir="{i18n_labels.direction(langue)}">')
    # APDF6 — LA CSS arabe partagée (police système, letter-spacing 0) ;
    # ``theme.css_langue`` porte déjà la part « libellés ».
    from ..premium_base import css_arabe as _css_arabe_partagee
    css_arabe = (_css_arabe_partagee(libelles=True, document=True)
                 if i18n_labels.est_rtl(langue) else "")
    return (f"<!doctype html>{racine}<head><meta charset='utf-8'>"
            f"<style>{theme.base_css()}{theme.css_langue(d)}"
            f"{_css(ctx['C'], ctx['fonts'], ctx['compact'])}{css_arabe}"
            f"</style></head><body>{body}</body></html>")
