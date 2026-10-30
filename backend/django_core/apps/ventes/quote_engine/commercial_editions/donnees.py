# flake8: noqa
# D-ENF22 : exception de fichier entier signée — moteur de devis vendoré (règle #4 de CLAUDE.md), non réécrit pour le lint.
"""Modèle de vue des éditions commerciales — LA couche de lecture.

``modele(d)`` transforme la charge utile augmentée (``commercial.renderer.
_augment``) en un dictionnaire plat que les pages des deux éditions lisent.
Chaque valeur est LUE (``synthese_ci``, ``totaux_all``, ``chiffres_cles``)
et FORMATÉE par les helpers existants du moteur (``montants``, ``theme.fmt``,
``ci.couverture``, ``ci.blocs``) — aucune arithmétique ici, hormis la mise
à l'échelle des dessins (``graphiques``), comme ``ci/graphiques.py``.

Toute étiquette passe par ``ci.blocs.libelle`` (catalogue trilingue) ; la
fonction ``libelles_bilingues`` sert le français ET l'arabe du catalogue à
l'édition « Directe », jamais une traduction écrite ici.
"""
from __future__ import annotations

import html as _html
import re

from .. import i18n_labels, premium_base
from ..ci import blocs as ci_blocs
from ..ci import couverture as ci_couverture
from ..ci.categories import texte_ligne
from ..ci.installation import lignes_client
from ..ci.synthese import chiffres_cles, libelle_poste
from ..ci.tableau import sous_lignes_html
from ..figures import ancre
from ..industriel.finance import flux_principal, rangees_hypotheses
from ..montants import decimale, lignes_remisees
from ..sequence import sequence_affichage
from ..residential import theme


def _num(v, default=None):
    try:
        f = float(v)
        return f if f == f else default
    except (TypeError, ValueError):
        return default


def _txt(v):
    return str(v or "").strip()


# ── Libellés ────────────────────────────────────────────────────────────────

#: Clés NOUVELLES de cette étude, absentes du catalogue publié : hors
#: français elles impriment leur littéral FR (le catalogue lève KeyError sur
#: une clé inconnue — garde volontaire). À ajouter au catalogue (3 langues,
#: traductions fondateur) avant tout branchement sur /proposal.
CLES_A_CATALOGUER = set()


def L(d, cle, fr, **valeurs):
    """Le libellé ``cle`` dans la langue du document (repli ``fr``)."""
    try:
        return ci_blocs.libelle(d, cle, fr, **valeurs)
    except KeyError:
        CLES_A_CATALOGUER.add(cle)
        return fr.format(**valeurs) if valeurs else fr




# ── Lignes du tableau ───────────────────────────────────────────────────────

def lignes(d, fmt_mad, muted="#6B7280"):
    """``[("struct", {type, texte}) | ("item", {...})]`` du tableau des
    équipements, la même séquence que ``commercial.equip`` (regroupement
    C&I, remise ligne par ligne par ``montants.lignes_remisees``)."""
    items = [it for it in lignes_client(d.get("all_items") or [], d)
             if (_num(it.get("quantite"), 0.0) or 0.0) > 0]
    structure = d.get("lignes_structure") or []
    seq = (sequence_affichage(items, structure) if structure
           else [("item", it) for it in items])
    catalogue_seul = bool(d.get("regles_calcul_origine"))
    sortie = []
    for kind, it in seq:
        if kind == "struct":
            sortie.append(("struct", {"type": it.get("type"),
                                      "texte": it.get("texte", "") or ""}))
            continue
        (_it, pu_cat, pu_ht, _tot_cat, total,
         remisee) = lignes_remisees([it], catalogue_seul=catalogue_seul)[0]
        taux = _num(it.get("taux_tva"), 0.0) or 0.0
        sortie.append(("item", {
            "designation": it.get("designation") or "",
            "marque": _txt(it.get("marque")),
            "qte": f"{(_num(it.get('quantite'), 0.0) or 0.0):g}",
            "pu_cat": fmt_mad(pu_cat) if remisee else "",
            "pu_ht": fmt_mad(pu_ht),
            "taux": f"{taux:g} %",
            "total": fmt_mad(total),
            "sous_lignes": sous_lignes_html(it, 7.2, "#4A5263"),
        }))
    return sortie


def _rangee_item(it, fmt_mad, catalogue_seul):
    """Une rangée d'équipement formatée + ses nombres bruts (pour comparer
    les deux options) — la même remise ligne par ligne que ``lignes``."""
    (_it, pu_cat, pu_ht, _tot_cat, total,
     remisee) = lignes_remisees([it], catalogue_seul=catalogue_seul)[0]
    taux = _num(it.get("taux_tva"), 0.0) or 0.0
    qte = _num(it.get("quantite"), 0.0) or 0.0
    return {"designation": it.get("designation") or "", "marque": _txt(it.get("marque")),
            "qte": f"{qte:g}", "pu_cat": fmt_mad(pu_cat) if remisee else "", "pu_ht": fmt_mad(pu_ht),
            "taux": f"{taux:g} %", "total": fmt_mad(total),
            "sous_lignes": sous_lignes_html(it, 7.2, "#4A5263"),
            "_id": (it.get("designation") or "", round(qte, 6), round(float(pu_ht or 0), 2), round(taux, 3))}


def totaux_de(tot, fmt_mad, option):
    """La chaîne de totaux d'UNE option (``totaux_sans`` / ``totaux_avec`` du
    builder), formatée avec ses ancres étiquetées ``option`` ; TVA par taux
    quand le builder la sert (``tva_par_taux``)."""
    tot = tot or {}
    out = {}
    for cle, source in (("ht_brut", "sous_total_ht"), ("ht_net", "total_ht"), ("tva", "tva")):
        v = fmt_mad(_num(tot.get(cle), 0.0) or 0.0)
        out[cle] = v
        out[f"ancre_{cle}"] = ancre(source, v, option)
    v = fmt_mad(_num(tot.get("ttc"), 0.0) or 0.0)
    out["ttc"], out["ancre_ttc"] = v, ancre("total_ttc", v, option)
    remise = _num(tot.get("remise"), 0.0) or 0.0
    arrondi = _num(tot.get("arrondi"), 0.0) or 0.0
    out["remise"] = fmt_mad(remise) if remise > 0 else ""
    out["ancre_remise"] = ancre("remise", out["remise"], option) if remise > 0 else ""
    out["arrondi"] = fmt_mad(arrondi) if arrondi > 0 else ""
    out["ancre_arrondi"] = ancre("arrondi", out["arrondi"], option) if arrondi > 0 else ""
    out["tva_taux"] = [(f"{int(round(_num(t.get('taux'), 0.0) or 0))}", fmt_mad(_num(t.get("montant"), 0.0) or 0.0))
                       for t in (tot.get("tva_par_taux") or []) if isinstance(t, dict)]
    return out


def deux_options_detail(d, fmt_mad):
    """La page 2 à DEUX options, à la manière du résidentiel
    (``residential/options.py`` : ``_split_items`` + ``_pair_divergents``) :
    l'équipement COMMUN (même désignation, quantité, prix et taux des deux
    côtés), les rôles DIVERGENTS appariés en une rangée à deux valeurs
    « sans · avec », et ce qui n'existe que d'un côté — chaque côté regroupé
    par ``lignes_client`` comme le tableau C&I ; les totaux de chaque option
    sont ceux du builder. ``None`` sur un document mono-option."""
    from ..ci.options_cote import deux_options as _deux
    if not _deux(d, "com"):
        return None
    catalogue_seul = bool(d.get("regles_calcul_origine"))

    def rangees(items):
        its = [it for it in lignes_client(items or [], d) if (_num(it.get("quantite"), 0.0) or 0.0) > 0]
        return [_rangee_item(it, fmt_mad, catalogue_seul) for it in its]
    rs, ra = rangees(d.get("sans_items") or d.get("all_items")), rangees(d.get("avec_items"))
    if not ra:  # option « avec » sans lignes servies : la page 2 mono-option + la case du moteur
        return None
    ids_s = {r["_id"] for r in rs}
    ids_a = {r["_id"] for r in ra}
    communs = [r for r in rs if r["_id"] in ids_a]
    delta_s = [r for r in rs if r["_id"] not in ids_a]
    delta_a = [r for r in ra if r["_id"] not in ids_s]
    cnt_s, cnt_a = {}, {}
    for r in delta_s:
        cnt_s[r["designation"]] = cnt_s.get(r["designation"], 0) + 1
    for r in delta_a:
        cnt_a[r["designation"]] = cnt_a.get(r["designation"], 0) + 1
    appariables = {n for n in (cnt_s.keys() & cnt_a.keys()) if cnt_s[n] == 1 and cnt_a[n] == 1}
    par_avec = {r["designation"]: r for r in delta_a if r["designation"] in appariables}
    paires = [(r, par_avec[r["designation"]]) for r in delta_s if r["designation"] in appariables]
    seul_s = [r for r in delta_s if r["designation"] not in appariables]
    seul_a = [r for r in delta_a if r["designation"] not in appariables]
    # Fondateur 30/10 (« still too complicated ») : UNE table, les deux options
    # côte à côte en colonnes nommées — chaque ligne des deux offres, dans
    # l'ordre de l'offre « sans », puis ce qui n'existe qu'« avec ».
    par_avec_toutes = {}
    for r in ra:
        par_avec_toutes.setdefault(r["designation"], []).append(r)
    cote_a_cote, vus = [], set()
    for r in rs:
        if r["_id"] in ids_a:
            cote_a_cote.append((r, r)); vus.add(r["_id"])
        elif r["designation"] in appariables:
            ra_ = par_avec[r["designation"]]; cote_a_cote.append((r, ra_)); vus.add(ra_["_id"])
        else:
            cote_a_cote.append((r, None))
    for r in ra:
        if r["_id"] not in vus:
            cote_a_cote.append((None, r))
    synthese = d.get("com_synthese") or {}
    option = synthese.get("option_batterie") if isinstance(synthese.get("option_batterie"), dict) else {}
    tot_avec = d.get("totaux_avec") or (option.get("totaux") if isinstance(option.get("totaux"), dict) else {})
    return {"communs": communs, "paires": paires, "seul_sans": seul_s, "seul_avec": seul_a, "cote_a_cote": cote_a_cote,
            "titre_sans": L(d, "ci_opt_sans_batterie", "Sans batterie"),
            "titre_avec": _txt(d.get("libelle_avec")) or L(d, "ci_opt_avec_batterie", "Avec batterie"),
            "totaux_sans": totaux_de(d.get("totaux_sans") or d.get("totaux_all"), fmt_mad, "sans"),
            "totaux_avec": totaux_de(tot_avec, fmt_mad, "avec")}


def postes_hors_total(d):
    """AMOT86 — les postes « à chiffrer après la visite » (nom, quantité),
    hors chaîne de totaux ; [] sans poste."""
    synthese = d.get("com_synthese") or {}
    postes = ci_couverture.postes_echappes(
        ci_couverture.postes_hors_total(synthese))
    roles = ci_couverture.roles_client(d)
    sortie = []
    for poste in postes:
        nom = libelle_poste(poste, roles)
        qte = poste.get("quantite")
        sortie.append((nom[:1].upper() + nom[1:],
                       f"{qte:g}" if qte else ""))
    return sortie


def totaux(d, fmt_mad):
    """La chaîne canonique formatée + ses ancres QA-FIGURES."""
    tot = d.get("totaux_all") or {}
    ttc = _num(tot.get("ttc")) or d.get("_invest_ttc") or 0
    out = {}
    for cle, source in (("ht_brut", "sous_total_ht"), ("ht_net", "total_ht"),
                        ("tva", "tva")):
        v = fmt_mad(_num(tot.get(cle), 0.0) or 0.0)
        out[cle] = v
        out[f"ancre_{cle}"] = ancre(source, v)
    v = fmt_mad(ttc)
    out["ttc"] = v
    out["ancre_ttc"] = ancre("total_ttc", v)
    remise = _num(tot.get("remise"), 0.0) or 0.0
    arrondi = _num(tot.get("arrondi"), 0.0) or 0.0
    out["remise"] = fmt_mad(remise) if remise > 0 else ""
    out["ancre_remise"] = ancre("remise", out["remise"]) if remise > 0 else ""
    out["arrondi"] = fmt_mad(arrondi) if arrondi > 0 else ""
    out["ancre_arrondi"] = (ancre("arrondi", out["arrondi"])
                            if arrondi > 0 else "")
    return out


# ── Investissement (CIQ315 : base HT / deux / TTC) ──────────────────────────

def investissement(d, fmt_mad):
    """``{titre, montant, unite, note, ancre, secondaire}`` — la même règle
    que ``ci.couverture.bloc_investissement`` (base ``synthese_ci.argent.
    base``), les mêmes montants (``totaux_all.ht_net``, ``_invest_ttc``)."""
    synthese = d.get("com_synthese") or {}
    argent = synthese.get("argent") if isinstance(synthese, dict) else None
    base = argent.get("base") if isinstance(argent, dict) else None
    invest = d.get("_invest_ttc") or 0
    ht = (d.get("totaux_all") or {}).get("ht_net")
    ttc_txt = fmt_mad(invest)
    l_ht, l_ttc = L(d, "ci_ht", "HT"), L(d, "ci_ttc", "TTC")
    l_soit = L(d, "ci_soit", "soit")
    note = ci_couverture.note_tva(d, base) or ""
    hors_visite = bool(ci_couverture.postes_hors_total(synthese))

    def _cle(b):
        # La clé du catalogue que ``titre_investissement`` a choisie (arabe
        # du bloc prix, synthèse §0.2) : une lecture, pas un chiffre.
        sans, hv = ci_couverture.TITRES_INVESTISSEMENT[b]
        return (hv if hors_visite else sans)[0]
    if base in ("ht", "deux") and ht is not None:
        ht_txt = fmt_mad(ht)
        if base == "ht":
            return {"titre": ci_couverture.titre_investissement(d, synthese, "ht"),
                    "cle_titre": _cle("ht"),
                    "montant": ht_txt, "unite": l_ht,
                    "ancre": ancre("total_ht", ht_txt),
                    "secondaire": f"{l_soit} {ttc_txt}&nbsp;MAD&nbsp;{l_ttc}"
                    + ancre("total_affiche", ttc_txt), "note": note}
        return {"titre": ci_couverture.titre_investissement(d, synthese, "deux"),
                "cle_titre": _cle("deux"),
                "montant": ttc_txt, "unite": l_ttc,
                "ancre": ancre("total_affiche", ttc_txt),
                "secondaire": f"{l_soit} {ht_txt}&nbsp;MAD&nbsp;{l_ht}"
                + ancre("total_ht", ht_txt), "note": note}
    return {"titre": ci_couverture.titre_investissement(d, synthese, "ttc"),
            "cle_titre": _cle("ttc"),
            "montant": ttc_txt, "unite": "",
            "ancre": ancre("total_affiche", ttc_txt), "secondaire": "",
            "note": ""}


# ── Chiffres clés ───────────────────────────────────────────────────────────

def chiffres(d, fmt):
    """Les chiffres de couverture, déjà formatés, ou ``None`` quand non
    servis (jamais un « 0 », QJR119)."""
    synthese = d.get("com_synthese") or {}
    cc = chiffres_cles(synthese)
    argent = synthese.get("argent") if isinstance(synthese, dict) else {}
    argent = argent if isinstance(argent, dict) else {}
    energie = synthese.get("energie") if isinstance(synthese, dict) else {}
    energie = energie if isinstance(energie, dict) else {}
    eco1 = argent.get("economie_annee1") or {}
    masque = bool(d.get("com_masquer_economies"))
    economies = None if masque else d.get("com_economies")
    base = d.get("com_economie_base")
    if base in ("HT", "TTC"):
        base = L(d, f"ci_{base.lower()}", base)
    payback = None if masque else ci_couverture.retour_affiche(d, "com")
    payback_txt = ci_couverture.ans(payback) if payback is not None else None
    payback_num = _num(payback)
    argent_base_ttc = argent.get("base") == "ttc"
    out = {
        "kwc": premium_base.kwc_str(d.get("com_kwc")),
        "nb_panneaux": (synthese.get("systeme") or {}).get("nb_panneaux"),
        "production": (fmt(round(d["com_production"]))
                       if d.get("com_production") is not None else None),
        "autoconso": (f"{round(d['com_autoconso'])}"
                      if d.get("com_autoconso") is not None else None),
        "couverture": (f"{round(d['com_couverture'])}"
                       if d.get("com_couverture") is not None else None),
        "definitions": cc.get("definitions") or {},
        "economies": fmt(economies) if economies is not None else None,
        "economies_base": base or "",
        "economies_ttc": (ci_couverture.economie_ttc(d, "com", fmt)
                          if economies is not None else ""),
        "part_facture_pct": (f"{round(_num(eco1.get('part_facture_energie_pct')))}"
                             if _num(eco1.get("part_facture_energie_pct"))
                             is not None and not masque else None),
        "payback": payback_txt, "payback_num": payback_num,
        "payback_unite": (ci_couverture.unite_ans(d, payback_txt)
                          if payback_txt else ""),
        "payback_base": (L(d, "ci_ttc", "TTC") if argent_base_ttc
                         else L(d, "ci_ht", "HT")) if argent else "",
        "motif_investissement": ci_couverture.motif_investissement(d, "com"),
        # Le motif quand l'argent n'est pas chiffré (MT, factures absentes…),
        # texte de ``ci.couverture.ligne_non_chiffre`` sans son enveloppe.
        "motif_non_chiffre": __import__("re").sub(
            r"^<div[^>]*>|</div>$", "",
            _txt(ci_couverture.ligne_non_chiffre(d, "com", "x")))
        if (masque or (d.get("com_motif_argent") and economies is None)) else "",
        # A2 (revue 29/10) — texte TRILINGUE des helpers existants, jamais
        # le français brut de ``com_methode`` / ``com_note_pointe``.
        "methode": re.sub(r"^<div[^>]*>|</div>$", "",
                          _txt(ci_couverture.ligne_methode(d, "com", "x"))),
        "note_pointe": _txt(ci_couverture.note_pointe(d, "com")),
        "sous_reserve": bool(d.get("com_sous_reserve")),
        "a_confirmer": list(d.get("com_a_confirmer") or []),
        "postes_hors_total": bool(ci_couverture.postes_hors_total(synthese)),
        "tri_pct": None,
        "horizon": None,
        # AMOT100 — la tonne de CO₂ évitée SERVIE (``decarbonation.co2_evite``)
        # et la source du facteur ; None sans facteur réglé.
        "co2_t": None, "co2_facteur": "",
    }
    co2 = (synthese.get("decarbonation") or {}).get("co2_evite")         if isinstance(synthese, dict) else None
    if isinstance(co2, dict) and co2.get("t_an") is not None:
        out["co2_t"] = decimale(f"{co2['t_an']:g}")
        out["co2_facteur"] = L(
            d, "ci_co2_facteur", "facteur réseau {g} gCO₂/kWh — {source}",
            g=decimale(f"{co2['facteur_g_kwh']:g}"),
            source=_html.escape(str(co2.get("source") or ""), quote=False))
    indic = argent.get("indicateurs") or {}
    tri = _num(indic.get("tri_pct"))
    if tri is not None and not masque:
        out["tri_pct"] = decimale(f"{tri:.1f}")
        out["horizon"] = indic.get("tri_horizon_ans")
    # Le surplus (kWh/an, % de la production) — texte servi par la ligne
    # existante, sans son enveloppe.
    surplus = energie.get("surplus") or {}
    out["surplus_kwh"] = (fmt(round(_num(surplus.get("non_valorise_kwh_an"))))
                          if _num(surplus.get("non_valorise_kwh_an")) else None)
    out["surplus_pct"] = (f"{round(_num(surplus.get('non_valorise_pct_production')))}"
                          if _num(surplus.get("non_valorise_pct_production"))
                          is not None else None)
    return out


def bandeau_reserve(d, prefixe):
    """A4 — le bandeau « Devis préliminaire… » exactement quand le
    renderer actuel l'imprime (``ci.couverture.bandeau_reserve``, textes
    trilingues ``TEXTES_VISITE``), sans son enveloppe."""
    html = _txt(ci_couverture.bandeau_reserve(d, "com", prefixe))
    return re.sub(r"^<div[^>]*>|</div>$", "", html)


def lignes_methode(d):
    """Les lignes « source » sous les chiffres (méthode, surplus, tarif de
    repli, motif MT / non chiffré) — texte des helpers existants, sans
    leur ``<div>`` : ``[(classe, html)]``."""
    import re
    sortie = []
    from ..ci.mentions import ligne_tarif_grille
    grille = ligne_tarif_grille(
        ((d.get("com_synthese") or {}).get("argent") or {}).get("tarif"),
        ci_couverture.langue(d))
    if grille:  # même ordre que ``commercial.cover`` : la grille d'abord
        sortie.append(grille)
    for html in (ci_couverture.ligne_methode(d, "com", "x"),
                 ci_couverture.ligne_surplus(d, "com", "x")):
        texte = re.sub(r"^<div[^>]*>|</div>$", "", _txt(html))
        if texte:
            sortie.append(texte)
    if d.get("com_masquer_economies") or (
            d.get("com_motif_argent") and d.get("com_economies") is None):
        texte = re.sub(r"^<div[^>]*>|</div>$", "",
                       _txt(ci_couverture.ligne_non_chiffre(d, "com", "x")))
        if texte:
            sortie.append(texte)
    elif d.get("com_mt_mention"):
        sortie.append(ci_couverture.mention_client(d["com_mt_mention"]))
    return sortie


# ── Énergie, argent (séries servies pour les dessins) ───────────────────────

def energie_mensuelle(d):
    """Les 12 mois servis (``synthese_ci.energie.par_mois``) ou []."""
    energie = (d.get("com_synthese") or {}).get("energie") or {}
    mois = [m for m in energie.get("par_mois") or [] if isinstance(m, dict)]
    if len(mois) != 12:
        return []
    for m in mois:
        for cle in ("consommation_kwh", "production_kwh", "autoconso_kwh",
                    "surplus_kwh"):
            if _num(m.get(cle)) is None:
                return []
    return mois


def facture_avant_apres(d, fmt):
    """``{avant, apres, unite}`` de la facture d'énergie de l'année 1 quand
    le moteur la sert sur UN seul poste sans prime fixe (aucune addition
    ici) ; sinon ``None``. ``unite`` = la base de l'argent (HT/TTC)."""
    argent = (d.get("com_synthese") or {}).get("argent") or {}
    if d.get("com_masquer_economies") or argent.get("statut") != "calcule":
        return None
    avant, apres = argent.get("facture_avant") or {}, argent.get("facture_apres") or {}
    pa, pp = avant.get("energie_par_poste") or [], apres.get("energie_par_poste") or []
    if len(pa) != 1 or len(pp) != 1:
        return None
    if _num(avant.get("prime_fixe_mad")) or _num(apres.get("prime_fixe_mad")):
        return None
    cle = "mad_ttc" if argent.get("base") == "ttc" else "mad_ht"
    va, vp = _num(pa[0].get(cle)), _num(pp[0].get(cle))
    if va is None or vp is None or va <= 0:
        return None
    unite = L(d, "ci_ttc", "TTC") if cle == "mad_ttc" else L(d, "ci_ht", "HT")
    # A7 (revue 29/10) — deux montants arrondis séparément peuvent contredire
    # l'économie-titre (98 935 vs 98 933) et le moteur plafonne l'économie
    # sans rééchelonner les factures : les barres portent la PART servie
    # (``economie_annee1.part_facture_energie_pct``), jamais deux montants.
    return {"avant_num": va, "apres_num": vp, "unite": unite}


def changement(d, fmt):
    """Le cadrage « ce que le solaire change pour vous » du résidentiel,
    transposé : part de la facture d'énergie économisée (servie,
    ``economie_annee1.part_facture_energie_pct``), facture d'énergie de
    l'année 1 avant / après (servie, un poste, sans prime fixe) et leur
    lecture PAR MOIS — dérivée du servi exactement comme la couverture
    résidentielle (``round(annuel / 12)``, jamais un autre calcul) ; ``None``
    sans facture servie."""
    f = facture_avant_apres(d, fmt)
    if not f:
        return None
    c = chiffres(d, fmt)
    return {"pct": c["part_facture_pct"], "unite": f["unite"],
            "avant_an": fmt(round(f["avant_num"])), "apres_an": fmt(round(f["apres_num"])),
            "avant_mois": fmt(round(f["avant_num"] / 12)), "apres_mois": fmt(round(f["apres_num"] / 12)),
            "economie": c["economies"], "economie_base": c["economies_base"],
            # l'économie PAR MOIS, dérivée du servi annuel ÷ 12 comme la facture
            "economie_mois": (fmt(round(_num(d.get("com_economies")) / 12))
                              if (_num(d.get("com_economies")) or 0) > 0 and not d.get("com_masquer_economies") else None),
            "retour": c["payback"], "retour_unite": c["payback_unite"],
            "deux_options": bool(d.get("deux_options"))}


def _puces_equipement(items, fmt):
    """Les trois puces d'une carte d'option, comme le résidentiel : panneaux,
    onduleur(s), batterie(s) — désignations et quantités servies."""
    puces = []
    for motif in ("panneau", "onduleur", "batterie", "installation"):
        for it in items or []:
            des = str(it.get("designation") or "")
            if des.lower().startswith(motif):  # la désignation elle-même, pas un accessoire qui la cite
                q = _num(it.get("quantite"), 0.0) or 0.0
                puces.append(f"{fmt(q) if q != 1 else ''}{' × ' if q != 1 else ''}{des}".strip())
    return puces[:4]


def cartes_options(d, fmt, fmt_mad):
    """Les deux cartes d'option de la couverture, à la manière du résidentiel
    (prix TTC en grand, prix par kWc, retour, économie, part couverte,
    puces d'équipement) — chaque nombre vient de la charge utile servie :
    « sans » = l'offre servie (``_invest_ttc``, ``com_*``), « avec » =
    ``com_synthese.option_batterie`` (totaux et valeur chiffrée du moteur) ;
    le prix par kWc est le quotient des deux servis, comme au résidentiel.
    ``[]`` sur un document mono-option."""
    from ..ci.options_cote import deux_options as _deux
    if not _deux(d, "com"):
        return []
    synthese = d.get("com_synthese") or {}
    option = synthese.get("option_batterie") or {}
    totaux = option.get("totaux") if isinstance(option.get("totaux"), dict) else (d.get("totaux_avec") or {})
    valeur = option.get("valeur_chiffree") if isinstance(option.get("valeur_chiffree"), dict) else {}
    masque = bool(d.get("com_masquer_economies"))

    def carte(num, titre, kwc, ttc, economie, base, retour, couverture, items):
        kwc_n, ttc_n = _num(kwc), _num(ttc)
        return {"num": num, "titre": titre, "kwc": decimale(f"{kwc_n:g}") if kwc_n else None,
                "ttc": fmt_mad(ttc_n) if ttc_n else None,
                "par_kwc": fmt(round(ttc_n / kwc_n)) if (ttc_n and kwc_n) else None,
                "economie": (fmt(round(_num(economie))) if (not masque and _num(economie)) else None),
                "economie_mois": (fmt(round(_num(economie) / 12)) if (not masque and _num(economie)) else None),
                "economie_base": base, "retour": retour,
                "couverture": (f"{round(_num(couverture))}" if _num(couverture) is not None else None),
                "puces": _puces_equipement(items, fmt)}
    retour_sans = ci_couverture.retour_affiche(d, "com")
    retour_avec = _num(valeur.get("retour_simple_ans"))
    return [
        carte(1, L(d, "ci_opt_sans_batterie", "Sans batterie"), d.get("com_kwc"), d.get("_invest_ttc"),
              d.get("com_economies"), d.get("com_economie_base") or "",
              (ci_couverture.ans(retour_sans) if retour_sans is not None else None), d.get("com_couverture"),
              d.get("sans_items") or d.get("all_items")),
        carte(2, _txt(d.get("libelle_avec")) or L(d, "ci_opt_avec_batterie", "Avec batterie"),
              d.get("puissance_kwc_avec"), totaux.get("ttc"), valeur.get("economie_annuelle_mad"), "HT",
              (decimale(str(retour_avec)) if retour_avec else None), valeur.get("taux_couverture_pct"),
              d.get("avec_items")),
    ]


def cumul_annees(d, fmt):
    """La série du cumul net servie (``flux_*.flux[].cumul_mad``) pour la
    frise des 25 ans, ses jalons (``argent.jalons``) et le retour ; ou
    ``None`` quand l'argent n'est pas servi."""
    argent = (d.get("com_synthese") or {}).get("argent") or {}
    if d.get("com_masquer_economies") or argent.get("statut") != "calcule":
        return None
    cle, flux = flux_principal(argent)
    serie = [(int(_num(f.get("annee"), -1)), _num(f.get("cumul_mad")))
             for f in (flux or {}).get("flux") or [] if isinstance(f, dict)]
    serie = [(a, c) for a, c in serie if a >= 0 and c is not None]
    if len(serie) < 2:
        return None
    jalons = [(int(_num(j.get("annee"), 0)), _num(j.get("cumul_mad")))
              for j in (argent.get("jalons_ttc") if cle == "flux_ttc"
                        else argent.get("jalons")) or []
              if isinstance(j, dict) and _num(j.get("cumul_mad")) is not None]
    return {"serie": serie, "jalons": [(a, fmt(round(c))) for a, c in jalons],
            "horizon": (flux or {}).get("horizon_ans"),
            "retour": _num((flux or {}).get("retour_ans")),
            "base": (L(d, "ci_ttc", "TTC") if cle == "flux_ttc"
                     else L(d, "ci_ht", "HT"))}


# ── Garanties, échéancier, services, hypothèses, conditions ─────────────────

def garanties(d):
    """``[(n, unité, libellé)]`` — ``theme.warranties_for`` filtré par
    ``garanties_servies`` et traduit par ``textes_garantie`` (QJR118)."""
    sortie = []
    for n, u, label, _sub in ci_blocs.garanties_servies(
            d, [w for w in (theme.warranties_for(d) or [])
                if w and str(w[0]).strip()]):
        unite, etiquette = ci_blocs.textes_garantie(d, u, label, n)
        sortie.append((theme._esc(str(n)), unite, etiquette))
    return sortie


def echeancier(d, fmt_mad):
    """``[(pct, libellé, montant TTC | '')]`` des jalons servis."""
    jalons = (d.get("com_synthese") or {}).get("echeancier") or []
    sortie = []
    for j in jalons:
        if not isinstance(j, dict):
            continue
        montant = j.get("montant_ttc")
        sortie.append((ci_blocs._pct(j.get("pct")),
                       ci_blocs._libelle_jalon(d, j),
                       fmt_mad(montant) if montant is not None else ""))
    return sortie


def services_html(d, prefixe, navy, ink):
    return ci_blocs.bloc_services(d.get("com_synthese") or {}, prefixe,
                                  navy, ink, doc=d)


def financement_html(d, prefixe, navy, ink):
    return ci_blocs.bloc_financement(d.get("com_synthese") or {}, prefixe,
                                     navy, ink, doc=d)


def hypotheses(d, fmt, fmt_mad):
    """``[(libellé | None, valeur)]`` des bases du calcul (AMOT91)."""
    return rangees_hypotheses(d, d.get("com_synthese") or {}, fmt, fmt_mad,
                              lambda cle, fr, **v: L(d, cle, fr, **v),
                              compact=True, om=True)


def conditions(d):
    """``(titre, [puces])`` des conditions imprimées — la logique de
    ``ci.blocs.bloc_conditions`` sans son enveloppe."""
    from ..clauses_cgv import cgv_imprimees
    puces = ci_blocs.puces_conditions(d)
    if ci_blocs._echeancier_imprime(d):
        puces = [p for p in puces if not ci_blocs._PUCE_ECHEANCIER.match(p)]
    tva_note = _txt(d.get("tva_note"))
    if tva_note and not any(tva_note in p for p in puces):
        puces.append(tva_note)
    if not puces:
        return "", []
    titre = _txt(cgv_imprimees(d)["titre"])
    if titre in (ci_blocs.TITRE_CGV_DEFAUT, i18n_labels.libelle(
            "ci_cgv_titre", d.get("langue_sortie"))):
        titre = L(d, "ci_cgv_titre", ci_blocs.TITRE_CGV_DEFAUT)
    return titre, puces


def acceptation(d, fmt_mad):
    """Les champs du « Bon pour accord » : titre, mention, lignes
    ``[(libellé, valeur | '')]``, options à cocher ``[(texte)]``."""
    titre, mention = ci_blocs.textes_bpa(d)
    sig = d.get("signature_entreprise")
    sig = sig if isinstance(sig, dict) else {}
    valeurs = {
        "raison_sociale": _txt(sig.get("raison_sociale")),
        "signataire": ", ".join(v for v in (_txt(sig.get("signataire_nom")),
                                            _txt(sig.get("signataire_qualite")))
                                if v),
        "ice": _txt(sig.get("ice")),
        "date": ci_blocs._date_signature(sig.get("date")),
    }
    lignes_ = [(L(d, cat, fr) if cat else fr, valeurs[cle])
               for cle, cat, fr in ci_blocs.LIBELLES_ACCEPTATION]
    cases = [L(d, f"ci_bpa_option_{cle}",
               {"sans": "Sans batterie — {total} MAD TTC",
                "avec": "Avec batterie — {total} MAD TTC"}[cle], total=total)
             for cle, total in ci_blocs._options_accord(d, fmt_mad)]
    return {"titre": titre, "mention": mention, "lignes": lignes_,
            "cases": cases, "pour": L(d, "ci_pour_la_societe", "pour la société"),
            "signature": L(d, "ci_signature", "Signature"),
            "cachet": L(d, "ci_cachet", "Cachet de la société"),
            "accepte_nom": _txt(d.get("accepte_par_nom")),
            "date_acceptation": _txt(d.get("date_acceptation"))}


def categorie(d):
    """``{cle, label, accroche, titre_bloc, lignes[]}`` lus sur
    ``synthese_ci['categorie']`` (CIQ330)."""
    from ..commercial import categories as com_categories
    cat = (d.get("com_synthese") or {}).get("categorie")
    meta = com_categories.meta(d.get("com_category"), cat)
    cle = (cat.get("cle") if isinstance(cat, dict) else None) or \
        (d.get("com_category") if d.get("com_category")
         in com_categories.METADATA else "autre")
    langue = ci_blocs.langue(d)
    bloc = (cat.get("bloc") if isinstance(cat, dict) else None) or {}
    lignes_ = [texte_ligne(li, langue) for li in bloc.get("lignes") or []
               if isinstance(li, dict)]
    lignes_ = [li for li in lignes_ if _txt(li)]
    # A1 (CPDF6) — la phrase « Le soir et la nuit… » est imprimée page 1 :
    # la case ne la répète pas (même filtre que ``commercial.equip``).
    from ..commercial.equip import _sans_phrase_pointe
    bloc_html = "".join(f'<div class="c2b-li">{li}</div>' for li in lignes_)
    bloc_html = _sans_phrase_pointe(bloc_html, d) or ""
    lignes_ = re.findall(r'<div class="c2b-li">(.*?)</div>', bloc_html, re.S)
    return {"cle": cle, "label": "" if cle == "autre" else meta["label"],
            "icon": meta["icon"], "accroche": meta["accroche"],
            "titre_bloc": bloc.get("titre") or "", "lignes": lignes_}


def client(d):
    """Nom, adresse·ville·téléphone, titre du projet, identité légale."""
    nom, meta = ci_couverture.identite_client(d)
    entreprise = (d.get("com_synthese") or {}).get("entreprise_client")
    return {
        "nom": nom, "meta": meta,
        "titre_client": ci_couverture.client_titre(d, "com", nom),
        "ville": _txt(d.get("client_ville_libelle") or d.get("client_city")),
        "bloc_entreprise": ci_blocs.bloc_client(entreprise, "x", nom, doc=d),
        "interlocuteur": ci_couverture.ligne_interlocuteur(d, "x"),
        "entreprise": entreprise if isinstance(entreprise, dict) else {},
    }


def etapes_suivantes(d):
    return [L(d, cle, fr) for cle, fr in ci_couverture.ETAPES_SUIVANTES]


def qr(d):
    return ci_couverture.qr_proposition(d)


def option_avec_html(d, L_, fmt_mad, couleurs):
    return ci_blocs.bloc_option_avec(d, L_, fmt_mad, couleurs)


def options_proposees(d, fmt_mad):
    """``[(qté·désignation, taux, total HT, total TTC)]`` (QJR619)."""
    sortie = []
    for o in d.get("options_proposees") or []:
        q = _num(o.get("quantite"), 0.0) or 0.0
        sortie.append((f"{q:g}× " if q and q != 1 else "",
                       o.get("designation", ""),
                       f"{(_num(o.get('taux_tva'), 0.0) or 0.0):g} %",
                       fmt_mad(_num(o.get("total_ht"), 0.0) or 0.0),
                       fmt_mad(_num(o.get("total_ttc"), 0.0) or 0.0)))
    return sortie


def injection(d, fmt):
    """``(montant MAD/an formaté, mentions)`` du surplus injecté quand le
    moteur le sert (QX50/CIQ129/AMOT40) ; ``None`` sinon."""
    syn = d.get("com_synthese") or {}
    inj = _num(chiffres_cles(syn)["revente_mad_an"])
    if not inj or inj <= 0:
        return None
    from ..ci.mentions import mentions_revente, texte_revente
    rev = ((syn.get("argent") or {}).get("revente")) or {}
    mentions = mentions_revente(rev.get("mentions"), ci_blocs.langue(d))
    return (fmt(round(inj)), " ".join(mentions) if mentions
            else texte_revente(ci_blocs.langue(d)) + ".")


def installation_en_bref(d, L_, fmt):
    from ..commercial.equip import _rangees_installation
    return _rangees_installation(d, L_, fmt)


_TEL = re.compile(r"(\+?\d[\d ]{7,}\d)")


def _tel_insecable(html):
    """Les numéros de téléphone en espaces insécables (jamais coupés)."""
    return _TEL.sub(lambda mm: mm.group(1).replace(" ", "\u00a0"), html or "")


def vendeur(d, ident):
    brand = ident.get("brand_name") or "TAQINOR"
    return brand, _tel_insecable(ci_blocs.ligne_vendeur(brand, ident)), \
        _tel_insecable(ci_blocs.nettoyer_separateurs(premium_base.bande_legale(d, ident)))


def modele(d, ctx):
    """Le modèle de vue complet d'un document (lecture + formatage)."""
    fmt, fmt_mad = ctx["fmt"], ctx.get("fmt_mad") or ctx["fmt"]
    ident = ctx.get("ident") or {}
    brand, ligne_vendeur, bande_legale = vendeur(d, ident)
    deux_options = __import__(
        "apps.ventes.quote_engine.ci.options_cote", fromlist=["deux_options"]
    ).deux_options(d, "com")
    return {
        "d": d, "fmt": fmt, "fmt_mad": fmt_mad, "ident": ident,
        "brand": brand, "ligne_vendeur": ligne_vendeur,
        "bande_legale": bande_legale,
        "ref": d["ref"], "date": d["date"],
        "valid_until": _txt(d.get("valid_until")),
        "marques_correction": list(theme.marques_correction(d)),
        "client": client(d), "categorie": categorie(d),
        "chiffres": chiffres(d, fmt), "methode": lignes_methode(d),
        "invest": investissement(d, fmt_mad), "deux_options": deux_options,
        "lignes": lignes(d, fmt_mad), "hors_total": postes_hors_total(d),
        "totaux": totaux(d, fmt_mad),
        "options": options_proposees(d, fmt_mad), "injection": injection(d, fmt),
        "energie": energie_mensuelle(d), "facture": facture_avant_apres(d, fmt),
        "cumul": cumul_annees(d, fmt), "garanties": garanties(d),
        "changement": changement(d, fmt), "cartes": cartes_options(d, fmt, fmt_mad),
        "deux": deux_options_detail(d, fmt_mad),
        "echeancier": echeancier(d, fmt_mad),
        "hypotheses": hypotheses(d, fmt, fmt_mad), "conditions": conditions(d),
        "acceptation": acceptation(d, fmt_mad), "etapes": etapes_suivantes(d),
        "qr": qr(d), "note_client": _txt(d.get("note_client")),
        "langue": ci_blocs.langue(d), "rtl": i18n_labels.est_rtl(ci_blocs.langue(d)),
        # Palier de densité (0 = rendu nominal) posé par ``apercu.document``
        # quand le document ne tient pas — même mécanique que CIQ317.
        "palier": int(d.get("_palier_ed") or 0),
        "variante": str(d.get("_variante_ed") or "A"),
    }
