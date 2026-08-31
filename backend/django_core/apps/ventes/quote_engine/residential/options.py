# flake8: noqa
"""Page 2 — VOTRE INSTALLATION : détail du projet + finance.

Restructured vs the old design: the old page 2 carried TWO near-identical
13-row equipment tables (~80 % duplicated). Here we show ONE "équipement commun
aux deux options" table + a small per-option delta ("ce que chaque option
ajoute"), then promote the finance charts (25-yr payback curve gets real space).

build(ctx) returns the INNER HTML of one A4 page (no .page wrapper, no footer).
Every class is prefixed `p2-` so it never clashes with pages 1/3.
"""
from __future__ import annotations


def _qty_par_designation(items):
    """{désignation: quantité TOTALE} — somme des lignes de même désignation."""
    out = {}
    for it in items:
        try:
            q = float(it.get("quantite") or 0)
        except (TypeError, ValueError):
            q = 0.0
        out[it["designation"]] = out.get(it["designation"], 0.0) + q
    return out


def _identite_par_designation(items):
    """{désignation: (quantité TOTALE, prix unitaires HT triés)}.

    QJR29 — L'IDENTITÉ DE FACTURATION D'UNE LIGNE INCLUT SON PRIX. La quantité
    seule ne suffit pas : une même désignation, en même quantité, mais
    FACTURÉE À DEUX PRIX différents d'une option à l'autre n'est pas la même
    ligne. ``prix_unit_ht`` porte DÉJÀ la remise de ligne (voir
    ``builder._line_to_item`` : ``pu × (1 − remise/100)``), donc ce seul
    nombre couvre le prix ET la remise.
    """
    qtes = _qty_par_designation(items)
    prix = {}
    for it in items:
        try:
            p = round(float(it.get("prix_unit_ht") or 0), 2)
        except (TypeError, ValueError):
            p = 0.0
        prix.setdefault(it["designation"], []).append(p)
    return {nom: (qtes[nom], tuple(sorted(prix.get(nom, ()))))
            for nom in qtes}


def _split_items(sans_items, avec_items):
    """Partition lines by designation AND quantity across the two options.

    Returns (shared, delta_sans, delta_avec). `shared` keeps the order of
    sans_items; the value used is the sans-side line (prices match avec-side).

    L-2OPT (chantier « deux optimiseurs », 24/08/2026) — L'APPARTENANCE SE
    JUGE SUR (DÉSIGNATION, QUANTITÉ). Depuis que les deux options peuvent
    porter des nombres de panneaux différents (22 sans / 26 avec), une même
    désignation présente des deux côtés n'est PLUS forcément un équipement
    commun : à quantités divergentes elle part en delta de CHAQUE option, avec
    SA quantité. L'ancien découpage la déclarait « commune » et n'imprimait
    qu'UNE quantité — celle du côté sans — pour les deux options : le client
    lisait 22 panneaux sur une option qui en compte 26.

    QJR29 — LE PRIX FAIT PARTIE DE L'IDENTITÉ. Le découpage ignorait le prix
    unitaire : une ligne facturée à DEUX PRIX différents dans les deux
    variantes était déclarée « commune » et imprimée UNE fois, au prix du côté
    SANS, pendant que le total de l'option 2 était calculé avec le prix AVEC —
    le tableau de la page 2 ne se réconciliait plus avec un total que le client
    peut additionner. Elle part désormais en delta de chaque option (puis
    ``_pair_divergents`` en fait UNE ligne à deux valeurs, prix compris).

    Quantités ET prix égaux ⇒ ``shared``, exactement comme avant (tout devis
    dont aucune ligne ne porte de variante est rendu au bit près).
    """
    sans_q = _identite_par_designation(sans_items)
    avec_q = _identite_par_designation(avec_items)
    common = {n for n in (sans_q.keys() & avec_q.keys())
              if sans_q[n] == avec_q[n]}

    shared = [it for it in sans_items if it["designation"] in common]
    delta_sans = [it for it in sans_items if it["designation"] not in common]
    delta_avec = [it for it in avec_items if it["designation"] not in common]
    return shared, delta_sans, delta_avec


def _pair_divergents(delta_sans, delta_avec):
    """L-2OPTPDF (ordre fondateur, 28/08/2026) — APPARIE LES RÔLES DIVERGENTS.

    ``_split_items`` sort du tableau commun toute désignation dont la quantité
    diffère d'une option à l'autre (15 panneaux sans / 14 avec) : elle atterrit
    dans le delta de CHAQUE option. Le client lisait alors « Panneau … »,
    « Structure … », « Socle … » DEUX FOIS, une fois par carte — trois rôles
    répétés qui gonflaient la page et poussaient le devis à 4 pages.

    Ici on les APPARIE : une désignation présente des deux côtés devient UNE
    ligne à deux valeurs (« 15 · 14 ») dans le tableau d'équipement ; les cartes
    « Spécifique à l'option N » ne gardent que ce qui n'existe VRAIMENT que d'un
    côté (onduleur réseau vs hybride, batterie, compteur…).

    Retourne ``(paires, seul_sans, seul_avec)``. L'ordre de ``delta_sans`` est
    conservé. Une désignation portée par PLUSIEURS lignes du même côté n'est pas
    appariable (on ne saurait pas quelle ligne va avec quelle ligne) : elle reste
    dans les deltas, exactement comme avant.
    """
    cnt_s, cnt_a = {}, {}
    for it in delta_sans:
        cnt_s[it["designation"]] = cnt_s.get(it["designation"], 0) + 1
    for it in delta_avec:
        cnt_a[it["designation"]] = cnt_a.get(it["designation"], 0) + 1
    communs = {n for n in (cnt_s.keys() & cnt_a.keys())
               if cnt_s[n] == 1 and cnt_a[n] == 1}
    par_avec = {it["designation"]: it for it in delta_avec
                if it["designation"] in communs}
    paires = [(it, par_avec[it["designation"]]) for it in delta_sans
              if it["designation"] in communs]
    seul_sans = [it for it in delta_sans if it["designation"] not in communs]
    seul_avec = [it for it in delta_avec if it["designation"] not in communs]
    return paires, seul_sans, seul_avec


def _produits_href(produits_base):
    """https URL of the fiches library hub from a bare 'taqinor.ma/produits'."""
    base = (produits_base or "taqinor.ma/produits").strip().rstrip("/")
    return base if base.startswith("http") else "https://" + base


def _name_html(it, produits_base):
    """Product name, linked to its fiche-technique page on taqinor.ma when one
    exists (panels, inverters, batteries, meter, dongle) — a tiny ' ›' marks it
    clickable; TAQINOR's own lines (structures, socles, installation…) stay
    plain text."""
    from . import theme
    desig = it["designation"]
    href = theme.fiche_href(desig, it.get("marque") or "", produits_base)
    if not href:
        return f'<span class="p2-name">{desig}</span>'
    return (f'<a class="p2-name p2-fiche-lnk" href="{href}">{desig}'
            f'<span class="p2-fiche-i">&rsaquo;</span></a>')


def _row(it, fmt, produits_base="taqinor.ma/produits"):
    """One <tr> for the shared equipment table."""
    marque = it.get("marque") or ""
    qte = it["quantite"]
    qte_txt = f"{qte:g}"
    pu = fmt(it["prix_unit_ht"])
    tva = f"{int(round(it['taux_tva']))}%"
    total_ht = fmt(it["prix_unit_ht"] * it["quantite"])
    marque_html = (f'<span class="p2-mk">{marque}</span>' if marque else "")
    return (
        f'<tr>'
        f'<td class="p2-d">{_name_html(it, produits_base)}{marque_html}</td>'
        f'<td class="p2-c">{qte_txt}</td>'
        f'<td class="p2-r">{pu}</td>'
        f'<td class="p2-c p2-tva">{tva}</td>'
        f'<td class="p2-r p2-tot">{total_ht}</td>'
        f'</tr>'
    )


def _deux_valeurs(v_sans, v_avec):
    """« 15 · 14 » — la valeur SANS puis la valeur AVEC, jamais une seule.

    Valeurs identiques ⇒ un seul nombre (rien à comparer : on n'écrit pas
    « 1 · 1 »). Les deux nombres sont typés : le second, celui de l'option
    recommandée, porte la couleur navy des totaux.
    """
    if v_sans == v_avec:
        return v_sans
    return (f'<span class="p2-vs">{v_sans}</span>'
            f'<span class="p2-vsep"> &middot; </span>'
            f'<span class="p2-va">{v_avec}</span>')


def _row_pair(pair, fmt, produits_base="taqinor.ma/produits"):
    """L-2OPTPDF — UNE ligne de tableau pour un rôle présent dans les DEUX
    options avec des quantités (ou des prix) différents.

    Les colonnes Qté / P.U. HT / Total HT y portent DEUX valeurs « sans · avec »
    au lieu de dupliquer la ligne entière dans les deux cartes d'option. La
    chaîne P.U. → Total HT par ligne est intégralement préservée : chaque
    colonne montre simplement sa valeur de chaque côté.
    """
    s, a = pair
    marque = s.get("marque") or a.get("marque") or ""
    marque_html = (f'<span class="p2-mk">{marque}</span>' if marque else "")
    qte = _deux_valeurs(f'{s["quantite"]:g}', f'{a["quantite"]:g}')
    pu = _deux_valeurs(fmt(s["prix_unit_ht"]), fmt(a["prix_unit_ht"]))
    # QJR31 — LE TAUX AUSSI EST PAR COLONNE. Seule cellule de cette ligne à
    # n'avoir qu'UNE valeur, elle imprimait TOUJOURS le taux du côté SANS : sur
    # une paire dont les deux variantes ne portent pas le même taux (10 %
    # panneaux / 20 % le reste), le taux affiché ne décrivait pas la moitié du
    # couple. ``_deux_valeurs`` rend un seul nombre quand les deux coïncident :
    # tout l'existant est byte-identique. La chaîne des totaux, elle, était
    # déjà juste (``tva_par_taux``) — c'est l'affichage par ligne qui mentait.
    tva = _deux_valeurs(f"{int(round(s['taux_tva']))}%",
                        f"{int(round(a['taux_tva']))}%")
    tot = _deux_valeurs(fmt(s["prix_unit_ht"] * s["quantite"]),
                        fmt(a["prix_unit_ht"] * a["quantite"]))
    return (
        f'<tr class="p2-tr-2v">'
        f'<td class="p2-d">{_name_html(s, produits_base)}{marque_html}</td>'
        f'<td class="p2-c">{qte}</td>'
        f'<td class="p2-r">{pu}</td>'
        f'<td class="p2-c p2-tva">{tva}</td>'
        f'<td class="p2-r p2-tot">{tot}</td>'
        f'</tr>'
    )


def _entry_row(entry, fmt, produits_base="taqinor.ma/produits"):
    """Une entrée de tableau : ligne simple (``it``) ou ligne appariée."""
    kind, payload = entry
    if kind == "paire":
        return _row_pair(payload, fmt, produits_base)
    return _row(payload, fmt, produits_base)


def _entry_item(entry):
    """L'item représentatif d'une entrée (côté SANS pour une paire) — sert au
    modèle de hauteur, qui ne mesure que la longueur de la désignation."""
    kind, payload = entry
    return payload[0] if kind == "paire" else payload


def _delta_lines(items, fmt, produits_base="taqinor.ma/produits"):
    """Compact list of the extra products one option adds."""
    out = []
    for it in items:
        qte = it["quantite"]
        q = f"{qte:g}× " if qte and qte != 1 else ""
        total_ht = fmt(it["prix_unit_ht"] * it["quantite"])
        out.append(
            f'<li><span class="p2-dl-n">{q}{_name_html(it, produits_base)}</span>'
            f'<span class="p2-dl-p">{total_ht} HT</span></li>'
        )
    return "".join(out)


def _totals_chain(label, accent, tot, fmt, C, recommended=False):
    """One compact HT→TVA→TTC chain card for a single option."""
    rows = [
        f'<div class="p2-tl"><span>Sous-total HT</span>'
        f'<span>{fmt(tot["ht_brut"])}</span></div>'
    ]
    if tot.get("remise", 0) and tot["remise"] > 0:
        rows.append(
            f'<div class="p2-tl p2-tl-rem"><span>Remise</span>'
            f'<span>− {fmt(tot["remise"])}</span></div>'
        )
        rows.append(
            f'<div class="p2-tl"><span>Total HT</span>'
            f'<span>{fmt(tot["ht_net"])}</span></div>'
        )
    for t in tot.get("tva_par_taux", []):
        taux = int(round(t["taux"]))
        rows.append(
            f'<div class="p2-tl p2-tl-sub"><span>TVA {taux}%</span>'
            f'<span>{fmt(t["montant"])}</span></div>'
        )
    badge = '<span class="p2-badge">Recommandé</span>' if recommended else ""
    return (
        f'<div class="p2-tot-card" style="border-top:3px solid {accent}">'
        f'<div class="p2-tot-head"><span class="p2-tot-opt" '
        f'style="color:{accent}">{label}</span>{badge}</div>'
        f'<div class="p2-tot-rows">{"".join(rows)}</div>'
        f'<div class="p2-tot-grand">'
        f'<span>Total TTC</span>'
        f'<span class="p2-grand-v">{fmt(tot["ttc"])} <small>MAD</small></span>'
        f'</div>'
        f'</div>'
    )


def build_pages(ctx) -> list:
    """QRES17 — pagination VARIABLE (fondateur, 2026-07-18).

    Rend 1..N pages « Votre installation » : un devis standard tient sur UNE
    page (l'historique) ; un devis chargé (10+ lignes) découpe proprement —
    page équipement (tableau complet, découpé par tranches de hauteur s'il le
    faut, avec « suite ») puis page rentabilité dédiée (courbe plus grande +
    garanties). Le pied « Page n / N » suit tout seul (QX6). Jamais de
    débordement rogné ni de 4ᵉ page orpheline.
    """
    from . import theme
    from .. import constants

    d = ctx["d"]
    C = ctx["C"]
    fmt = ctx["fmt"]
    fonts = ctx["fonts"]
    charts = ctx["charts"]
    links = d.get("links", {})

    # QX5 — deux options seulement quand le devis en porte réellement deux.
    # Mono-option : la page 2 abandonne le découpage delta et renomme l'en-tête
    # « commun aux deux options ». Repli sûr : sans drapeau, deux-options.
    deux_options = bool(d.get("deux_options", True))
    avec_ok = bool(d.get("avec_ok", True))
    # Z2 (ORDRE FONDATEUR, 20/08/2026) — sans AUCUNE donnée réelle d'ancrage, la
    # couche économique du document est OMISE (cf. renderer.ancrage_reel_absent) :
    # la rentabilité (payback, gain net 25 ans, courbe de cashflow) descend du
    # même tarif de repli × taux forfaitaire que la synthèse de la page 1 et part
    # avec elle. L'équipement, les totaux et la TVA — eux — sont les données du
    # devis : ils restent rendus à l'identique.
    # QJR209 — même lecture double qu'en page 1 : ``masquer_economies`` (dossier
    # MT sans économies d'étude) masque exactement la même couche que
    # ``masquer_synthese``. Un seul des deux suffit à l'omettre d'un seul tenant.
    masquer_eco = bool(d.get("masquer_synthese") or d.get("masquer_economies"))

    if deux_options:
        shared, delta_sans, delta_avec = _split_items(
            d["sans_items"], d["avec_items"]
        )
        # L-2OPTPDF — les rôles présents des DEUX côtés (quantités divergentes)
        # remontent dans le tableau, en UNE ligne à deux valeurs ; les cartes
        # d'option ne gardent que le vraiment spécifique.
        paires, delta_sans, delta_avec = _pair_divergents(
            delta_sans, delta_avec)
    else:
        # Une seule option : toutes ses lignes forment le tableau d'équipement
        # (aucun delta à comparer).
        shared = d["avec_items"] if avec_ok else d["sans_items"]
        delta_sans, delta_avec, paires = [], [], []

    # ENTRÉES du tableau d'équipement, DANS L'ORDRE DU DEVIS côté « sans » :
    # une paire reprend la place qu'occupait sa ligne. Aucune paire (tout devis
    # non divergent, ou mono-option) ⇒ liste strictement égale à ``shared``,
    # donc HTML et pagination inchangés au bit près.
    if paires:
        _par_nom = {s["designation"]: (s, a) for s, a in paires}
        _shared_noms = {it["designation"] for it in shared}
        entries, _vus = [], set()
        for it in d["sans_items"]:
            nom = it["designation"]
            if nom in _par_nom and nom not in _vus:
                entries.append(("paire", _par_nom[nom]))
                _vus.add(nom)
            elif nom in _shared_noms and nom not in _vus:
                _vus.add(nom)
                entries.extend(("solo", x) for x in shared
                               if x["designation"] == nom)
    else:
        entries = [("solo", it) for it in shared]

    # ── Top spec list ────────────────────────────────────────────────────────
    # L-2OPT — quand les deux options n'ont PAS le même nombre de panneaux, un
    # scalaire unique ne décrit qu'une des deux : la bande porte alors les DEUX
    # valeurs (« 15,6 · 18,5 » / « kWc installés (sans · avec) »). Sinon, ou sur
    # un document mono-option, l'affichage historique est intact.
    _kwc_s, _kwc_a = d.get("puissance_kwc_sans"), d.get("puissance_kwc_avec")
    _nb_s, _nb_a = d.get("nb_panneaux_sans"), d.get("nb_panneaux_avec")
    _divergent = bool(deux_options and d.get("panneaux_divergents"))

    def _num(v):
        return f'{v:g}'.replace(".", ",")

    # QJR17 (d) — VIGNETTES CONDITIONNELLES, comme partout ailleurs dans le
    # moteur. Ces deux vignettes formataient leur valeur SANS garde : depuis M2
    # (puissance jamais déduite du prix) et M3 (watt jamais forfaitaire), la
    # valeur peut être ``None`` — ``f'{None:g}'`` lève alors une TypeError, le
    # renderer résidentiel meurt et le document repart sur le moteur legacy.
    # Donnée absente ⇒ vignette OMISE (jamais un « 0 », jamais un « None W ») ;
    # devis normal ⇒ chaîne byte-identique à avant.
    if _divergent and _kwc_s and _kwc_a:
        spec_kwc = (f'{_num(_kwc_s)} · {_num(_kwc_a)}',
                    "kWc installés (sans · avec)")
    elif d.get("puissance_kwc"):
        spec_kwc = (_num(d["puissance_kwc"]), "kWc installés")
    else:
        spec_kwc = None
    _w_s, _w_a = d.get("watt_par_panneau_sans"), d.get("watt_par_panneau_avec")
    if _divergent and _nb_s and _nb_a:
        # Puissance unitaire écrite seulement si elle est LA MÊME des deux
        # côtés ; deux modèles de panneau différents ⇒ le détail est dans le
        # tableau comparatif, jamais un watt qui vaudrait pour une seule option.
        _wtxt = f' · {_w_s:g} W' if (_w_s and _w_s == _w_a) else ''
        spec_pan = (f'{_nb_s:g} · {_nb_a:g}',
                    f'panneaux (sans · avec){_wtxt}')
    elif d.get("nb_panneaux"):
        _wp = d.get("watt_par_panneau")
        _wp_txt = f' · {_wp:g} W' if _wp else ''
        spec_pan = (f'{d["nb_panneaux"]:g}', f'panneaux{_wp_txt}')
    else:
        spec_pan = None
    # PDFPROD (27/08/2026) — la production DÉRIVE du kWc : quand les champs PV
    # divergent, le scalaire ``prod_kwh`` ne décrit qu'UNE des deux options
    # (celle de l'AVEC, repli documenté du builder) — la bande annonçait donc
    # une production unique à côté d'un « 15,62 · 18,46 kWc ». Mêmes gardes que
    # la vignette de la page 1 : les deux valeurs doivent réellement différer
    # (une production SAISIE dans l'étude vaut pour les deux options), et la
    # paire est écrite un cran plus petit — une production s'écrit sur 5 à
    # 6 chiffres, la colonne de la bande fait ~36 mm et ne doit pas passer à la
    # ligne. Devis non divergent (tout l'existant) ⇒ HTML byte-identique.
    _pr_s, _pr_a = d.get("prod_kwh_sans"), d.get("prod_kwh_avec")
    if _divergent and _pr_s and _pr_a and _pr_s != _pr_a:
        spec_prod = (f'<span style="font-size:13pt;">{fmt(_pr_s)} · '
                     f'{fmt(_pr_a)}</span>',
                     "kWh / an produits (sans · avec)")
    else:
        spec_prod = (fmt(d["prod_kwh"]), "kWh / an produits")
    # QJR17 (d) — une vignette sans donnée n'existe pas (``None`` ci-dessus).
    specs = [s for s in (spec_kwc, spec_pan, spec_prod) if s]
    spec_html = "".join(
        f'<div class="p2-spec"><span class="p2-spec-v">{v}</span>'
        f'<span class="p2-spec-l">{l}</span></div>'
        for v, l in specs
    )

    produits_link = links.get("produits", d.get("site_url", "taqinor.ma"))

    rows_html = "".join(_row(it, fmt, produits_link) for it in shared)
    delta_sans_html = _delta_lines(delta_sans, fmt, produits_link)
    delta_avec_html = _delta_lines(delta_avec, fmt, produits_link)

    # QX5 — le bloc « ce que chaque option ajoute » n'existe QUE pour un vrai
    # devis à deux options ; mono-option → aucun découpage delta.
    # QRES27 — en-têtes recomposés (« Spécifique à … », plus de « ajoute »
    # pendu), texte NAVY sur la barre or (jamais blanc sur #F5A623 — contraste)
    # et une ligne « Pourquoi » sous l'option recommandée qui JUSTIFIE la
    # recommandation au lieu de la seule pastille.
    if deux_options:
        deltas_html = (
            '<div class="p2-deltas">'
            '<div class="p2-dcard">'
            f'<div class="p2-dhead" style="background:{C["navy"]}">'
            'Spécifique à l&rsquo;option 1 — Sans batterie</div>'
            f'<div class="p2-dbody"><ul>{delta_sans_html}</ul></div></div>'
            '<div class="p2-dcard">'
            f'<div class="p2-dhead" style="background:{C["gold"]};'
            f'color:{C["navy"]}">'
            'Spécifique à l&rsquo;option 2 — Avec batterie</div>'
            f'<div class="p2-dbody"><ul>{delta_avec_html}</ul>'
            '<div class="p2-dwhy">Pourquoi nous la recommandons : vos '
            'soirées et les coupures passent sur batterie.</div></div></div>'
            '</div>')
    else:
        deltas_html = ""

    if deux_options:
        totals_html = (
            _totals_chain("Option 1 — Sans batterie", C["navy"],
                          d["totaux_sans"], fmt, C)
            + _totals_chain("Option 2 — Avec batterie", C["gold"],
                            d["totaux_avec"], fmt, C, recommended=True))
        # L-2OPTPDF — dès qu'une ligne appariée entre dans le tableau, celui-ci
        # n'est plus « commun » aux deux options : il les COMPARE. Sans paire
        # (tout devis à deux options non divergent) le libellé historique est
        # rendu à l'identique.
        equipement_lbl = ("Équipement des deux options" if paires
                          else "Équipement commun aux deux options")
    else:
        # QX5 — une seule carte de totaux pour l'unique option réelle.
        _tot = d["totaux_avec"] if avec_ok else d["totaux_sans"]
        _lbl = ("Total — Avec batterie" if avec_ok
                else "Total — Sans batterie")
        _acc = C["gold"] if avec_ok else C["navy"]
        totals_html = _totals_chain(_lbl, _acc, _tot, fmt, C)
        equipement_lbl = "Votre équipement"

    tva_note = d.get("tva_note", "")

    # ── QJ30 — multi-propriétés (rendu ; dégrade à la mise en page à plat) ────
    # (A) ×N villas identiques : ligne « × N propriétés identiques » + total mis
    #     à l'échelle. (B) villas différentes : sous-totaux par villa + total
    #     général. Vides → aucun rendu (page 2 inchangée au bit près).
    multi_html = ""
    _nprop = d.get("nombre_proprietes")
    if _nprop and _nprop > 1:
        _dtm = d.get("display_total_multi")
        _tot_txt = (f' — total pour {_nprop} propriétés : {fmt(_dtm)} MAD'
                    if _dtm else "")
        multi_html += (
            f'<div class="p2-multi-n">&times;&nbsp;{_nprop} propriétés '
            f'identiques{_tot_txt}</div>')
    _mv = d.get("multi_villa") or {}
    if _mv.get("groupes"):
        _vrows = ""
        for g in _mv["groupes"]:
            t = g.get("totaux") or {}
            _vrows += (
                f'<tr><td>{g.get("label", "")}</td>'
                f'<td class="p2-r">{fmt(t.get("ht_net", 0))}</td>'
                f'<td class="p2-r p2-tot">{fmt(t.get("ttc", 0))} MAD</td></tr>')
        _gt = _mv.get("grand_total") or {}
        _vrows += (
            f'<tr class="p2-multi-gt"><td>Total général</td>'
            f'<td class="p2-r">{fmt(_gt.get("ht_net", 0))}</td>'
            f'<td class="p2-r">{fmt(_gt.get("ttc", 0))} MAD</td></tr>')
        multi_html += (
            '<div class="p2-multi-lbl">Détail par propriété</div>'
            '<table class="p2-multi"><thead><tr>'
            '<th>Propriété</th><th class="p2-r">Total HT</th>'
            '<th class="p2-r">Total TTC</th></tr></thead>'
            f'<tbody>{_vrows}</tbody></table>')
    if multi_html:
        multi_html = f'<div class="p2-multi-wrap">{multi_html}</div>'

    # ── Payback takeaway figures (read straight off the quote data) ───────────
    def _yrs(v):
        return f"{v:g}".replace(".", ",") if v else "—"
    roi_s, roi_a = d.get("roi_s"), d.get("roi_a")
    # QX5 — deux options → fourchette de ROI ; mono-option → le ROI de l'option
    # réelle seul (jamais une fourchette entre une option et un fantôme).
    if deux_options and roi_s and roi_a:
        lo, hi = sorted((roi_s, roi_a))
        roi_range = f"{_yrs(lo)} – {_yrs(hi)} ans"
    else:
        _roi_one = (roi_a if avec_ok else roi_s)
        roi_range = f"{_yrs(_roi_one)} ans" if _roi_one else "—"
    # QX5 — gain net 25 ans + libellé calés sur l'option réellement présente
    # (jamais « option avec batterie » sur un devis sans batterie).
    if deux_options or avec_ok:
        _eco_ref, _tot_ref = d.get("eco_a_ann", 0), d.get("total_avec", 0)
        gain25_label = "option avec batterie" if deux_options else "avec batterie"
    else:
        _eco_ref, _tot_ref = d.get("eco_s_ann", 0), d.get("total_sans", 0)
        gain25_label = "sans batterie"
    # QRES58 — le gain net 25 ans sort du VRAI cashflow (dégradation 0,5 %/an
    # intégrée — ce que les hypothèses promettent) : plus jamais un eco×25 plat
    # qui surévaluait ~7 % ; repli Σ(0,995^t) ≈ 23,56 si le cumul manque.
    _cf_ref = (d.get("cashflow_avec") if (deux_options or avec_ok)
               else d.get("cashflow_sans")) or []
    if _cf_ref:
        gain25 = max(0, round(_cf_ref[-1]))
    else:
        gain25 = max(0, round(_eco_ref * 23.56 - _tot_ref))
    gain25 = round(gain25 / 1000) * 1000
    # QRES28 — le multiple (« ≈ 5,6× votre investissement ») rend le gain net
    # tangible ; calculé, jamais inventé (gain net / investissement).
    gain_mult = (round(gain25 / _tot_ref, 1) if _tot_ref and gain25 > 0
                 else None)
    gain_mult_txt = (f"{gain_mult:g}".replace(".", ",")
                     if gain_mult and gain_mult >= 1 else None)
    gain_mult_sub = (
        f" — soit ≈ <b>{gain_mult_txt}×</b> votre investissement"
        if gain_mult_txt else "")

    # ── L-2OPT — TABLEAU COMPARATIF DE SYNTHÈSE (deux optimiseurs) ───────────
    # Rendu UNIQUEMENT sur un document à deux options dont les compositions
    # DIVERGENT réellement (nombres de panneaux différents) : c'est là que les
    # deux cartes de totaux ne suffisent plus à comprendre ce qui change d'une
    # option à l'autre. Un devis à deux options « classique » (même champ PV
    # des deux côtés) reste rendu au bit près — donc sans 4ᵉ page induite.
    #
    # RÈGLE FONDATEUR — ZÉRO CHIFFRE INVENTÉ : chaque ligne lit une valeur DÉJÀ
    # calculée par le moteur ; une ligne dont une valeur manque est OMISE (ni
    # tiret de remplissage, ni estimation). Seule exception assumée, le tiret de
    # la case « Batteries » côté SANS : l'absence de stockage y est un FAIT du
    # devis, pas une donnée manquante.
    cmp_rows = []
    if _divergent:
        def _cell_pan(nb, watt):
            return f'{nb:g} × {watt:g} W' if watt else f'{nb:g}'

        if _nb_s and _nb_a:
            cmp_rows.append(("Panneaux", _cell_pan(_nb_s, _w_s),
                             _cell_pan(_nb_a, _w_a)))
        if _kwc_s and _kwc_a:
            cmp_rows.append(("Puissance", f'{_num(_kwc_s)} kWc',
                             f'{_num(_kwc_a)} kWc'))
        _bat_kwh = d.get("batterie_kwh_total")
        if _bat_kwh:
            cmp_rows.append(("Batteries", "—", f'{_num(_bat_kwh)} kWh'))
        _ts, _ta = d.get("totaux_sans") or {}, d.get("totaux_avec") or {}
        if _ts.get("ttc") and _ta.get("ttc"):
            cmp_rows.append(("Prix TTC", f'{fmt(_ts["ttc"])} MAD',
                             f'{fmt(_ta["ttc"])} MAD'))
        _eco_s, _eco_a = d.get("eco_s_ann"), d.get("eco_a_ann")
        if not masquer_eco and _eco_s and _eco_a:
            # QJR210 — CE TABLEAU N'EXISTE QUE SUR UN DEVIS DIVERGENT, celui-là
            # même dont les deux colonnes peuvent être chiffrées par deux
            # moteurs différents (QJR28) : « Économies estimées » y déclarait un
            # modèle unique pour les deux. Le libellé lit désormais le modèle
            # EFFECTIF de chaque colonne — mot commun quand les deux coïncident
            # (tout l'existant : « estimées »), mot OMIS quand elles divergent
            # ou quand une clé manque. Jamais un modèle déclaré au nom de
            # l'autre colonne.
            _m_s = d.get("savings_model_sans")
            _m_a = d.get("savings_model_avec")
            if _m_s and _m_a and _m_s == _m_a:
                _mot = " calculées" if _m_s == "horaire" else " estimées"
            else:
                _mot = ""
            cmp_rows.append((f"Économies{_mot} / an",
                             f'{fmt(_eco_s)} MAD', f'{fmt(_eco_a)} MAD'))
        if not masquer_eco and roi_s and roi_a:
            cmp_rows.append(("Retour sur investissement",
                             f'{_yrs(roi_s)} ans', f'{_yrs(roi_a)} ans'))

    def _cmp_table(rows):
        _crows = "".join(
            f'<tr><td class="p2-cmp-k">{k}</td>'
            f'<td class="p2-cmp-v">{a}</td>'
            f'<td class="p2-cmp-v p2-cmp-a">{b}</td></tr>'
            for k, a, b in rows)
        return ('<table class="p2-cmp"><thead><tr><th></th>'
                '<th>Sans batterie</th><th>Avec batterie</th></tr></thead>'
                f'<tbody>{_crows}</tbody></table>')

    # L-2OPTPDF — À PARTIR DE 4 LIGNES, LE COMPARATIF SE LIT SUR DEUX COLONNES.
    # Les valeurs comparées sont courtes (« 15 × 710 W », « 12 400 MAD ») et le
    # tableau occupait 182 mm de large pour ~40 mm de contenu : posé en deux
    # demi-tableaux côte à côte, il porte EXACTEMENT les mêmes lignes sur
    # MOITIÉ MOINS de hauteur — la place qui manquait pour garder le devis
    # divergent sur sa pagination normale. Chaque demi-tableau garde son
    # en-tête « Sans batterie / Avec batterie » : aucune colonne muette.
    _CMP_2UP_MIN = 4
    if len(cmp_rows) >= _CMP_2UP_MIN:
        _mid = (len(cmp_rows) + 1) // 2
        comparatif_html = (
            '<div class="p2-cmp-grid">'
            f'<div class="p2-cmp-col">{_cmp_table(cmp_rows[:_mid])}</div>'
            f'<div class="p2-cmp-col">{_cmp_table(cmp_rows[_mid:])}</div>'
            '</div>')
    elif cmp_rows:
        comparatif_html = _cmp_table(cmp_rows)
    else:
        comparatif_html = ""

    # QRES3 — sous-titre du graphe fidèle au devis : « deux scénarios »
    # seulement quand le document porte réellement deux options.
    fin_sub = ("gain cumulé, deux scénarios — le point marque le retour "
               "sur investissement" if deux_options
               else "gain cumulé — le point marque le retour sur investissement")
    # ── Q1 (décision fondateur du 20/08/2026) — LE CREUX DE LA COURBE EST DIT ─
    # La courbe plonge en année 12 : c'est la provision de remplacement de
    # l'onduleur. Elle vaut le PRIX RÉEL de l'onduleur de ce devis (plus un
    # pourcentage forfaitaire du CAPEX), et la légende l'écrit — un creux
    # inexpliqué se lit comme une erreur de graphe. Aucun onduleur chiffré ⇒
    # aucune provision ⇒ aucune mention (la courbe n'a alors pas de creux).
    _cf_assum = d.get("cashflow_assumptions") or {}
    _prov = _cf_assum.get("inverter_replace_cost")
    if _prov:
        _an = _cf_assum.get("inverter_replace_year") or 12
        fin_sub += (f" · remplacement onduleur provisionné en année {_an} "
                    f"({f'{int(_prov):,}'.replace(',', ' ')} MAD)")

    # QRES57 — les garanties vivent en bande fine sur la page signature
    # (trust.py, source unique theme.WARRANTIES) : plus de cartes badges en
    # page 2 — l'espace revient à la courbe de rentabilité.

    # ── QRES17 — modèle de hauteur (mm) : décide si tout tient sur UNE page ──
    # Estimations calibrées sur le rendu réel (110 dpi) avec marge de sécurité ;
    # la garde CI (pages exactes + bande légale non rognée) verrouille le tout.
    def _row_mm(it):
        return 4.5 + (3.2 if len(str(it.get("designation") or "")) > 55
                      else 0.0)

    def _table_mm(entries):
        # L-2OPTPDF — une ligne appariée mesure comme une ligne simple : ses
        # deux valeurs tiennent DANS les colonnes existantes (c'est tout
        # l'intérêt du format « 15 · 14 » face à deux lignes dupliquées).
        return 6.5 + sum(_row_mm(_entry_item(e)) for e in entries)

    def _deltas_mm():
        if not deux_options:
            return 0.0
        rows = max(len(delta_sans), len(delta_avec), 1)
        return 7.0 + rows * 4.6

    def _comparatif_mm():
        """L-2OPT — hauteur du tableau comparatif, IMPUTÉE au même budget.

        Sans cela le comparatif s'ajouterait par-dessus une page déjà jugée
        « tient sur une page » et déborderait sur une 4ᵉ page. Absent ⇒ 0,0,
        donc décision de pagination identique à l'historique.
        """
        if not cmp_rows:
            return 0.0
        # L-2OPTPDF — sur deux colonnes, la hauteur est celle de la PLUS HAUTE
        # des deux moitiés (arrondi supérieur), pas celle des N lignes.
        n = len(cmp_rows)
        if n >= _CMP_2UP_MIN:
            n = (n + 1) // 2
        return 5.0 + n * 4.0

    # QRES49/57 (fondateur, 2026-07-18) — un devis de la taille RÉELLE des
    # devis du fondateur (~13 lignes, fixture « plus5 ») tient en 3 pages AVEC
    # la grande courbe : on a retiré de la page 2 ce qui était redondant (les
    # cartes badges → bande fine sur la page signature ; la ligne « fiches
    # techniques » → fusionnée à la légende TVA). Seuls les très gros devis
    # (~12 lignes communes et plus) passent en 4 pages.
    fits_one = (_table_mm(entries) + _deltas_mm() + _comparatif_mm()) <= 68.0

    # ── PRODMOIS + CALEPDF — UNE rangée de visuels sur la page détail ────────
    # Deux artefacts la peuplent, dans la MÊME hauteur (19 mm, fixée par le
    # CSS) : l'affiche de calepinage à gauche (quand la bande porte déjà la
    # photo du client) et la bande « production mois par mois » à droite. Un
    # seul des deux ⇒ il occupe la rangée seul ; aucun des deux ⇒ pas de
    # rangée.
    #
    # Hauteur du bloc (image 19 mm + ses marges) IMPUTÉE au même budget de
    # pagination que le tableau : la rangée n'est rendue que s'il reste
    # réellement de la place, avec 4 mm de garde en plus du modèle. Elle ne
    # change JAMAIS ``fits_one`` (calculé ci-dessus SANS elle) — donc aucun
    # devis ne bascule de 3 à 4 pages à cause d'elle : soit il y a la place,
    # soit la rangée s'omet. Un devis chargé (page équipement découpée) ne la
    # reçoit pas non plus : sa page détail est pleine par définition.
    # Résolus ICI (et pas plus bas, avec la bande) : le budget de pagination a
    # besoin de savoir si la rangée de visuels existera.
    roof_photo = (d.get("roof_photo") or "").strip()
    roof_render = (d.get("roof_render") or "").strip()
    # Sans photo, le calepinage prend la place du schéma illustratif DANS la
    # bande : il ne se répète alors pas dans la rangée.
    plan_dans_la_bande = bool(roof_render and not roof_photo)

    _VISUELS_MM = 21.0
    _prod_chart = (charts or {}).get("production") or ""
    _plan_a_part = roof_render if not plan_dans_la_bande else ""
    visuels_html = ""
    if (_prod_chart or _plan_a_part) and fits_one:
        _reste = 68.0 - 4.0 - (_table_mm(entries) + _deltas_mm()
                               + _comparatif_mm())
        if _reste >= _VISUELS_MM:
            _cells = ""
            if _plan_a_part:
                _cells += (
                    '<div class="p2-vis-plan">'
                    f'<img class="p2-roof-plan" src="{_plan_a_part}" '
                    'alt="Calepinage — implantation des panneaux sur votre '
                    'toiture">'
                    '<div class="p2-roof-cap">Votre calepinage</div></div>')
            if _prod_chart:
                _cells += (
                    f'<div class="p2-vis-prod"><img src="{_prod_chart}" '
                    'alt="Production solaire estimée, mois par mois"></div>')
            visuels_html = f'<div class="p2-visuels">{_cells}</div>'

    def _chunk_rows(items, budgets):
        """Découpe les lignes par tranches de hauteur (budgets mm par page)."""
        out, cur, h, bi = [], [], 0.0, 0
        for it in items:
            ih = _row_mm(_entry_item(it))
            budget = budgets[min(bi, len(budgets) - 1)]
            if cur and h + ih > budget:
                out.append(cur)
                cur, h, bi = [], 0.0, bi + 1
            cur.append(it)
            h += ih
        if cur:
            out.append(cur)
        return out

    style = f"""
<style>
  .p2-wrap {{ padding:6mm 14mm 5mm 14mm; }}

  /* Section header */
  .p2-kick {{ font-size:8.5pt; letter-spacing:.22em; text-transform:uppercase;
    color:{C['gold']}; font-weight:700; }}
  .p2-title {{ font-family:{fonts['serif']}; font-weight:700; font-size:21.5pt;
    color:{C['navy']}; line-height:1.04; margin-top:1.5mm; letter-spacing:-.3px; }}

  /* Top band: roof schematic + spec list */
  .p2-band {{ display:flex; align-items:center; gap:6mm; margin-top:2mm;
    padding:1.2mm 5mm; background:{C['wash']}; border:1px solid {C['line']};
    border-radius:12px; }}
  .p2-roof {{ flex:0 0 32mm; text-align:center; }}
  .p2-roof img {{ width:30mm; height:auto; }}
  /* QRES39 — photo réelle de toiture : cadrée, arrondie, légendée */
  .p2-roof-photo {{ width:30mm; height:17.5mm; object-fit:cover;
    border-radius:9px; display:block; margin:0 auto; }}
  /* CALEPDF/A1 — l'affiche de calepinage a une BOÎTE FIXE de 17,5 mm dans la
     bande (elle n'y entre QUE faute de photo, à la place du schéma illustratif
     ~22,7 mm : la bande ne peut donc que rétrécir, jamais grandir) et de 16 mm
     dans la rangée de visuels. ``contain`` et non ``cover`` : un plan
     d'implantation ne se recadre pas, on verrait moins de panneaux qu'il n'y
     en a. Deux classes ⇒ l'emporte sur ``.p2-roof img`` (1 classe + 1 balise). */
  .p2-roof .p2-roof-plan {{ width:30mm; height:17.5mm; object-fit:contain;
    background:#FFFFFF; border-radius:9px; display:block; margin:0 auto; }}
  .p2-roof-cap {{ font-size:6.3pt; color:{C['muted_2']}; margin-top:0.8mm;
    letter-spacing:.06em; text-transform:uppercase; font-weight:700; }}
  .p2-specs {{ flex:1; display:flex; gap:5mm; }}
  .p2-spec {{ flex:1; display:flex; flex-direction:column; gap:1mm;
    padding-left:5mm; border-left:2px solid {C['line']}; }}
  .p2-spec:first-child {{ border-left:none; padding-left:0; }}
  .p2-spec-v {{ font-family:{fonts['display']}; font-size:18pt;
    color:{C['navy']}; line-height:1; }}
  .p2-spec-l {{ font-size:8pt; color:{C['muted']}; line-height:1.2; }}

  /* PRODMOIS + CALEPDF — rangée de visuels : calepinage | production mois par
     mois. TABLE CSS, pas flex (RENDERING_NOTES §1). Les deux images ont une
     HAUTEUR FIXE ≤ 19 mm, donc la rangée mesure toujours ~19 mm quel que soit
     son contenu — c'est ce que _VISUELS_MM budgète. La cellule du plan est
     hors du flux de la bande : les vignettes techniques gardent leurs ~44,7 mm
     de colonne (plancher PDFPROD de 36 mm). */
  .p2-visuels {{ display:table; width:100%; table-layout:fixed;
    margin-top:2mm; }}
  .p2-vis-plan {{ display:table-cell; width:36mm; vertical-align:middle;
    text-align:center; padding-right:5mm; }}
  .p2-vis-plan .p2-roof-plan {{ width:31mm; height:16mm; object-fit:contain;
    background:#FFFFFF; border:1px solid {C['line']}; border-radius:7px;
    display:block; margin:0 auto; }}
  .p2-vis-plan .p2-roof-cap {{ margin-top:0.6mm; }}
  .p2-vis-prod {{ display:table-cell; vertical-align:middle; }}
  .p2-vis-prod img {{ height:19mm; width:auto; max-width:100%;
    display:block; margin:0 auto; }}

  /* Block label */
  .p2-lbl {{ font-size:8.5pt; letter-spacing:.16em; text-transform:uppercase;
    color:{C['navy']}; font-weight:700; margin:3mm 0 1.5mm; }}

  /* Shared equipment table */
  .p2-tbl {{ width:100%; border-collapse:collapse; font-size:8.7pt; }}
  .p2-tbl thead th {{ font-size:7.4pt; letter-spacing:.08em;
    text-transform:uppercase; color:{C['muted_2']}; font-weight:700;
    text-align:left; padding:0 0 2mm; border-bottom:1.5px solid {C['line']}; }}
  .p2-tbl th.p2-c, .p2-tbl td.p2-c {{ text-align:center; }}
  /* QRES36 — gouttière P.U. ↔ TVA (les deux colonnes se frôlaient) */
  .p2-tbl th:nth-child(4), .p2-tbl td:nth-child(4) {{ padding-left:14px; }}
  .p2-tbl th.p2-r, .p2-tbl td.p2-r {{ text-align:right; }}
  .p2-tbl tbody td {{ padding:1.15mm 0; border-bottom:1px solid {C['line_soft']};
    vertical-align:middle; }}
  .p2-tbl tbody tr:nth-child(even) td {{ background:{C['wash']}; }}
  .p2-tbl tbody td.p2-d {{ padding-left:2.5mm; }}
  .p2-tbl tbody td.p2-tot {{ padding-right:2.5mm; }}
  .p2-name {{ color:{C['ink']}; font-weight:600; text-decoration:none; }}
  .p2-fiche-lnk {{ color:{C['navy']}; }}
  .p2-fiche-i {{ color:{C['gold']}; font-weight:700; margin-left:3px; }}
  .p2-mk {{ color:{C['muted']}; font-size:7.6pt; margin-left:5px; }}
  .p2-tva {{ color:{C['muted']}; font-size:8pt; }}
  .p2-tot {{ font-weight:700; color:{C['navy']}; white-space:nowrap; }}

  /* L-2OPTPDF — ligne à deux valeurs (rôle présent dans les deux options avec
     des quantités différentes) : une seule ligne de tableau, jamais la même
     désignation répétée dans les deux cartes d'option. NE PAS écrire ici la
     paire de mots que les gardes de non-régression cherchent dans le document
     — la feuille de style part sur TOUTES les pages, y compris celles d'un
     devis non divergent. */
  .p2-tr-2v td {{ white-space:nowrap; }}
  .p2-tr-2v td.p2-d {{ white-space:normal; }}
  .p2-vs {{ color:{C['muted']}; }}
  .p2-vsep {{ color:{C['line']}; }}
  .p2-va {{ color:{C['navy']}; font-weight:700; }}
  .p2-lbl-leg {{ float:right; font-size:7.2pt; font-weight:600;
    letter-spacing:0; text-transform:none; color:{C['muted']}; }}
  .p2-lbl-leg b {{ color:{C['navy']}; font-weight:700; }}

  /* Per-option delta mini-cards */
  .p2-deltas {{ display:flex; gap:5mm; margin-top:1.5mm; align-items:stretch; }}
  .p2-dcard {{ flex:1; border:1px solid {C['line']}; border-radius:10px;
    overflow:hidden; display:flex; flex-direction:column; }}
  .p2-dhead {{ padding:2.2mm 3.5mm; font-size:8.4pt; font-weight:700;
    color:#fff; }}
  .p2-dhead small {{ font-weight:500; opacity:.85; }}
  /* QRES35 — display:block (PAS flex-column) : WeasyPrint rétrécissait la
     colonne désignation et superposait prix et « Pourquoi » (cf.
     RENDERING_NOTES, pièges flex). */
  .p2-dbody {{ display:block; }}
  .p2-dbody ul {{ list-style:none; width:100%; }}
  .p2-dwhy {{ padding:1.1mm 3.5mm 1.4mm; font-size:7.6pt; color:{C['muted']};
    border-top:1px solid {C['line_soft']}; }}
  .p2-dbody li {{ display:flex; justify-content:space-between; align-items:center;
    padding:1.7mm 3.5mm; font-size:8.5pt; border-bottom:1px solid {C['line_soft']}; }}
  .p2-dbody li:last-child {{ border-bottom:none; }}
  .p2-dl-n {{ color:{C['ink']}; }}
  .p2-dl-p {{ color:{C['navy']}; font-weight:700; white-space:nowrap;
    margin-left:6px; }}

  .p2-fiche {{ font-size:8pt; color:{C['muted']}; margin-top:1.5mm; }}
  .p2-fiche-btn {{ text-decoration:none; color:{C['navy']}; font-weight:700;
    white-space:nowrap; }}
  .p2-fiche-i {{ color:{C['gold']}; font-weight:700; }}

  /* Totals chains side by side */
  .p2-totals {{ display:flex; gap:5mm; margin-top:2mm; }}
  .p2-tot-card {{ flex:1; border:1px solid {C['line']};
    border-radius:0 0 10px 10px; background:{C['paper']};
    box-shadow:0 1px 3px rgba(26,43,74,.05); }}
  .p2-tot-head {{ display:flex; justify-content:space-between; align-items:center;
    padding:2.6mm 4mm 1.5mm; }}
  .p2-tot-opt {{ font-size:9pt; font-weight:700; }}
  .p2-badge {{ font-size:6.6pt; font-weight:700; letter-spacing:.05em;
    text-transform:uppercase; color:{C['navy']}; background:{C['gold']};
    padding:1.5px 7px; border-radius:999px; }}
  .p2-tot-rows {{ padding:0 4mm; }}
  .p2-tl {{ display:flex; justify-content:space-between; font-size:8.4pt;
    color:{C['ink']}; padding:1.1mm 0; }}
  .p2-tl-sub {{ color:{C['muted']}; font-size:8pt; }}
  .p2-tl-rem {{ color:{C['green']}; }}
  .p2-tot-grand {{ display:flex; justify-content:space-between; align-items:baseline;
    margin:1.5mm 4mm 0; padding:2.4mm 0; border-top:1.5px solid {C['line']}; }}
  .p2-tot-grand > span:first-child {{ font-size:8.6pt; font-weight:700;
    color:{C['navy']}; text-transform:uppercase; letter-spacing:.06em; }}
  .p2-grand-v {{ font-family:{fonts['display']}; font-size:17pt;
    color:{C['navy']}; }}
  .p2-grand-v small {{ font-family:{fonts['sans']}; font-size:8.5pt;
    color:{C['muted']}; font-weight:600; }}
  .p2-tva-note {{ font-size:7.4pt; color:{C['muted']}; margin-top:1.5mm;
    text-align:center; }}

  /* Finance: rentabilité — the curve gets real height BESIDE airy stats */
  .p2-fin {{ margin-top:1.5mm; }}
  /* QRES29 — sous-titre sur SA ligne (l'inline collait au titre serif) */
  .p2-fin-head {{ display:block; }}
  .p2-fin-title {{ display:block; font-family:{fonts['serif']};
    font-weight:700; font-size:13pt; color:{C['navy']}; }}
  .p2-fin-sub {{ display:block; font-size:7.8pt; color:{C['muted']};
    margin-top:0.2mm; }}
  .p2-side-gain .p2-stat-s b {{ color:{C['gold_soft']}; }}
  .p2-callout {{ margin-top:6mm; background:{C['navy']}; color:#fff;
    border-radius:12px; padding:5mm 7mm; font-family:{fonts['display']};
    font-size:13.5pt; line-height:1.25; }}
  .p2-callout b {{ color:{C['gold']}; font-weight:400; }}
  /* margin-left:auto est ignoré par WeasyPrint sur ce conteneur flex →
     marge déterministe pour caler le TOTAL TTC sur le rail monétaire droit. */
  .p2-totals-solo {{ width:60%; margin-left:40%; }}
  .p2-tbl tbody td {{ font-feature-settings:'tnum' 1; }}
  .p2-dcard, .p2-badge {{ box-shadow:0 1px 2px rgba(26,43,74,.04),
    0 5px 14px rgba(26,43,74,.05); }}

  /* CSS table: chart cell (left, full height) + stats cell (right, airy) */
  /* QRES51/57 — courbe agrandie (retour fondateur) : 42 mm — l'espace des
     anciennes cartes badges lui revient. */
  .p2-fin-grid {{ display:table; width:100%; table-layout:fixed; margin-top:1.5mm; }}
  .p2-fin-cc {{ display:table-cell; width:62%; vertical-align:middle; }}
  .p2-fin-cc img {{ display:block; height:42mm; width:auto; max-width:100%; }}
  /* QRES63 — page légère (mono-option minimal) : la courbe et ses stats
     grandissent pour nourrir l'espace disponible, avant toute respiration */
  .p2-light .p2-fin-cc img {{ height:52mm; }}
  .p2-light .p2-fin-sc .p2-stat-v {{ font-size:16.5pt; }}
  .p2-light .p2-fin-sc .p2-stat-s {{ font-size:7.8pt; }}
  .p2-fin-sc {{ display:table-cell; width:38%; vertical-align:middle;
    padding-left:8mm; }}
  .p2-side-stat {{ margin-bottom:2.5mm; }}
  .p2-side-stat:last-child {{ margin-bottom:0; }}
  .p2-stat-k {{ display:block; font-size:6.7pt; letter-spacing:.12em;
    text-transform:uppercase; color:{C['muted_2']}; font-weight:700;
    margin-bottom:0.8mm; }}
  .p2-stat-v {{ display:block; font-family:{fonts['display']}; font-size:14.5pt;
    color:{C['navy']}; line-height:1; }}
  .p2-stat-v small {{ font-family:{fonts['sans']}; font-size:8pt;
    color:{C['muted']}; font-weight:600; }}
  .p2-stat-s {{ display:block; font-size:7.2pt; color:{C['muted']};
    margin-top:0.8mm; line-height:1.2; }}
  .p2-stat-s b {{ color:{C['green']}; font-weight:700; }}
  .p2-fin-cap {{ font-size:7.3pt; color:{C['muted']}; text-align:center;
    margin-top:2mm; font-style:italic; }}
  .p2-fin-cap b {{ color:{C['navy']}; font-weight:700; font-style:normal; }}

  /* QRES17 — pages de continuation / page rentabilité dédiée */
  .p2-cont-note {{ font-size:7.6pt; color:{C['muted']}; font-style:italic;
    margin-top:2mm; text-align:right; }}
  /* QRES37/38 — page rentabilité : courbe pleine largeur (bornée par la
     largeur, jamais par une hauteur fixe qui la faisait déborder), stats en
     rangée de trois sous la courbe. */
  .p2-fin-wide {{ display:block; width:100%; height:auto; margin-top:4mm; }}
  .p2-finstats {{ display:flex; gap:8mm; margin-top:5mm; }}
  .p2-finstats .p2-side-stat {{ flex:1; margin-bottom:0; padding:4mm 5mm;
    background:{C['paper']}; border:1px solid {C['line']}; border-radius:11px;
    box-shadow:0 1px 2px rgba(26,43,74,.04),0 5px 14px rgba(26,43,74,.05); }}
  .p2-fin-xl .p2-fin-sub {{ margin-top:0; }}
  .p2-fin-xl {{ margin-top:6mm; }}

  /* QRES53 — bande impact environnemental (page rentabilité) */
  .p2-impact {{ display:flex; gap:8mm; margin-top:1mm; }}
  .p2-imp-c {{ flex:1; text-align:center; padding:3.5mm 3mm;
    background:linear-gradient(180deg,{C['green_bg']},#ffffff 85%);
    border:1px solid {C['green_bg']}; border-left:4px solid {C['green']};
    border-radius:11px; }}
  .p2-imp-v {{ display:block; font-family:{fonts['display']}; font-size:14.5pt;
    color:{C['green']}; }}
  .p2-imp-l {{ display:block; font-size:7pt; color:{C['muted']};
    margin-top:1mm; line-height:1.3; }}

  /* L-2OPT — tableau comparatif de synthèse (deux optimiseurs). Compact par
     construction : il s'insère sous les cartes de totaux sans pousser de 4ᵉ
     page (sa hauteur est imputée au budget de pagination). */
  .p2-cmp {{ width:100%; border-collapse:collapse; font-size:8.1pt;
    margin-top:2mm; }}
  .p2-cmp thead th {{ font-size:7pt; letter-spacing:.08em;
    text-transform:uppercase; color:{C['muted_2']}; font-weight:700;
    text-align:right; padding:0 2.5mm 1.2mm; border-bottom:1.5px solid {C['line']}; }}
  .p2-cmp thead th:first-child {{ text-align:left; }}
  .p2-cmp td {{ padding:0.85mm 2.5mm; border-bottom:1px solid {C['line_soft']};
    text-align:right; font-feature-settings:'tnum' 1; }}
  .p2-cmp tbody tr:last-child td {{ border-bottom:none; }}
  /* L-2OPTPDF — comparatif sur deux colonnes. TABLE CSS, pas flex
     (RENDERING_NOTES §1 : WeasyPrint rétrécit les colonnes d'un flex).
     ``table-layout:fixed`` ⇒ deux demi-largeurs strictement égales. */
  .p2-cmp-grid {{ display:table; width:100%; table-layout:fixed;
    margin-top:2mm; }}
  .p2-cmp-col {{ display:table-cell; vertical-align:top; }}
  .p2-cmp-col:first-child {{ padding-right:6mm; }}
  .p2-cmp-grid .p2-cmp {{ margin-top:0; }}
  /* Colonne de libellés bornée : les valeurs (``nowrap``) gardent leur place
     même dans une demi-largeur. */
  .p2-cmp-grid .p2-cmp .p2-cmp-k {{ width:44%; }}
  .p2-cmp-grid .p2-cmp td, .p2-cmp-grid .p2-cmp thead th {{
    padding-left:1.6mm; padding-right:1.6mm; }}
  .p2-cmp .p2-cmp-k {{ text-align:left; color:{C['muted']}; }}
  .p2-cmp .p2-cmp-v {{ color:{C['ink']}; font-weight:600; white-space:nowrap; }}
  .p2-cmp .p2-cmp-a {{ color:{C['navy']}; }}

  /* QJ30 — multi-propriétés */
  .p2-multi-wrap {{ margin-top:2.5mm; }}
  .p2-multi-n {{ background:{C['wash']}; border:1px solid {C['gold']};
    border-radius:8px; padding:1.6mm 4mm; font-size:8.4pt; color:{C['navy']};
    font-weight:700; margin-bottom:2mm; }}
  .p2-multi-lbl {{ font-size:8pt; letter-spacing:.12em; text-transform:uppercase;
    color:{C['navy']}; font-weight:700; margin:1mm 0 1.2mm; }}
  .p2-multi {{ width:100%; border-collapse:collapse; font-size:8.3pt; }}
  .p2-multi th {{ font-size:7pt; letter-spacing:.06em; text-transform:uppercase;
    color:{C['muted_2']}; font-weight:700; text-align:left;
    padding:0 4mm 1mm 0; border-bottom:1px solid {C['line']}; }}
  .p2-multi td {{ padding:1.1mm 4mm 1.1mm 0; border-bottom:1px solid {C['line_soft']};
    color:{C['ink']}; }}
  .p2-multi .p2-multi-gt td {{ font-weight:800; color:{C['navy']};
    border-top:1.5px solid {C['navy']}; border-bottom:none; }}
</style>
"""

    # ── QRES17 — fragments réutilisables, composés en 1..N pages ─────────────
    head_html = (
        '<div class="p2-kick">Votre installation</div>'
        '<div class="p2-title">Le détail de votre projet</div>')
    cont_head_html = (
        '<div class="p2-kick">Votre installation</div>'
        '<div class="p2-title">Équipement — suite</div>')
    fin_head_html = (
        '<div class="p2-kick">Votre rentabilité</div>'
        '<div class="p2-title">Rentabilité de votre investissement</div>')

    # QRES39 — la VRAIE toiture du client (photo/plan joint au devis) remplace
    # le schéma illustratif quand elle existe ; repli schéma sinon.
    #
    # CALEPDF/A1 (revue adversariale) — LA BANDE NE S'ÉLARGIT PAS. Une première
    # version posait les deux vignettes côte à côte en faisant passer la colonne
    # visuelle de 32 à 64 mm : les trois vignettes techniques tombaient alors à
    # ~34 mm de colonne, sous le plancher de 36 mm que PDFPROD documente juste
    # au-dessus (« la colonne de la bande fait ~36 mm et ne doit pas passer à la
    # ligne ») — un devis à champs PV divergents aurait fait passer « kWh / an
    # produits (sans · avec) » à la ligne et grandi la bande, sur la page même
    # où la bande « production » est budgétée au millimètre. La bande reste donc
    # EXACTEMENT ce qu'elle était, et le calepinage descend d'une rangée (voir
    # ``visuels_html`` plus bas), où il partage la hauteur de la bande
    # production sans rien coûter.
    #
    # Deux cas seulement :
    #   · photo présente → la bande porte la PHOTO (rendu historique) et le
    #     calepinage, s'il existe, va dans la rangée du dessous ;
    #   · pas de photo → le calepinage PREND la place du schéma illustratif
    #     dans la bande (une implantation réelle vaut mieux qu'un glyphe) et ne
    #     se répète pas plus bas.
    def _vignette(src, legende, alt, cls="p2-roof-photo"):
        return (f'<img class="{cls}" src="{src}" alt="{alt}">'
                f'<div class="p2-roof-cap">{legende}</div>')

    if roof_photo:
        band_visual = "<div>" + _vignette(
            roof_photo, "Votre toiture",
            "Votre toiture — implantation des panneaux") + "</div>"
    elif plan_dans_la_bande:
        band_visual = "<div>" + _vignette(
            roof_render, "Votre calepinage",
            "Calepinage — implantation des panneaux sur votre toiture",
            cls="p2-roof-plan") + "</div>"
    else:
        band_visual = (f'<img src="{charts["roof"]}" '
                       'alt="Schéma de l\'installation">')
    band_html = (
        f'<div class="p2-band">'
        f'<div class="p2-roof">{band_visual}</div>'
        f'<div class="p2-specs">{spec_html}</div></div>')

    def _table_html(items, label):
        rows = "".join(_entry_row(e, fmt, produits_link) for e in items)
        # L-2OPTPDF — la légende n'apparaît QUE sur une page qui porte
        # réellement une ligne à deux valeurs, et TIENT SUR LA LIGNE du
        # libellé : elle ne coûte pas un millimètre de hauteur.
        leg = ('<span class="p2-lbl-leg">deux valeurs&nbsp;: '
               '<b>sans</b> &middot; <b>avec</b> batterie</span>'
               if any(k == "paire" for k, _ in items) else "")
        return (
            f'<div class="p2-lbl">{label}{leg}</div>'
            '<table class="p2-tbl"><thead><tr>'
            '<th class="p2-d">Désignation</th>'
            '<th class="p2-c">Qté</th>'
            '<th class="p2-r">P.U. HT</th>'
            '<th class="p2-c">TVA</th>'
            '<th class="p2-r">Total HT</th>'
            f'</tr></thead><tbody>{rows}</tbody></table>')

    # QRES57 — la ligne « fiches techniques » fusionne avec la légende TVA
    # (une seule ligne de légende sous les totaux, ~5 mm rendus à la courbe).
    fiche_inline = (
        ' &middot; fiches techniques&nbsp;: <a class="p2-fiche-btn" '
        f'href="{_produits_href(produits_link)}">{produits_link}'
        '<span class="p2-fiche-i"> &rsaquo;</span></a>')

    # QRES30/48 — mono-option : carte de totaux PLEINE LARGEUR (les montants
    # internes s'alignent déjà à droite, donc le TOTAL TTC retombe sur le rail
    # monétaire — sans laisser un demi-bloc mort à gauche).
    totals_wrap_cls = ""
    closing_html = (
        f'{deltas_html}'
        f'<div class="p2-totals{totals_wrap_cls}">{totals_html}</div>'
        # L-2OPT — le comparatif se lit JUSTE SOUS les deux cartes de totaux,
        # à l'endroit où le client compare. Vide ⇒ page inchangée.
        f'{comparatif_html}'
        f'<div class="p2-tva-note">{tva_note}{fiche_inline}</div>'
        f'{multi_html}')

    # M6 (audit du 19/08/2026) — la carte « Performance garantie » lisait
    # « 30 ans / 87,4 % » en DUR sur tous les devis, y compris un panneau
    # Longi (garanti 30 ans mais à 88,9 %). Elle lit désormais la MÊME source
    # que la bande de garanties de la page signature (theme.warranties_for) :
    # jamais deux chiffres contradictoires dans le même document. Aucune
    # entrée « Performance » (composant non reconnu / hors gamme par défaut,
    # sans donnée produit) ⇒ la carte-stat est OMISE entièrement.
    _perf_warranty = next(
        (w for w in theme.warranties_for(d) if w[2] == "Performance"), None)

    def _perf_stat_html():
        if not _perf_warranty:
            return ""
        n, u, _label, sub = _perf_warranty
        return f"""
        <div class="p2-side-stat">
          <span class="p2-stat-k">Performance garantie</span>
          <span class="p2-stat-v">{n} {u}</span>
          <span class="p2-stat-s">panneaux — {sub}</span>
        </div>"""

    _stats_html = f"""
        <div class="p2-side-stat">
          <span class="p2-stat-k">Retour sur investissement</span>
          <span class="p2-stat-v">{roi_range}</span>
          <span class="p2-stat-s">l'installation se rembourse</span>
        </div>
        <div class="p2-side-stat p2-side-gain">
          <span class="p2-stat-k">Gain net sur 25 ans</span>
          <span class="p2-stat-v">≈ {fmt(gain25)} <small>MAD</small></span>
          <span class="p2-stat-s">{gain25_label}{gain_mult_sub}</span>
        </div>{_perf_stat_html()}"""
    # QRES59 — libellé NEUTRE (beaucoup de clients sont chez une régie, pas
    # l'ONEE) ; seule mention « toute hausse vous profite » du document.
    # Z4 (ORDRE FONDATEUR, 20/08/2026) — le SEUL décrochement de la courbe est la
    # provision de remplacement de l'onduleur : le tracé s'aplatit cette
    # année-là puis repart à sa pente normale. Il était SILENCIEUX (les
    # hypothèses détaillées vivent sur la proposition en ligne, pas sur le
    # papier — QRES61), donc illisible autrement que comme une erreur de
    # graphique. La légende, juste sous la courbe, le NOMME. L'année vient de
    # ``pricing`` (source unique du modèle), jamais d'un littéral recopié.
    from ..pricing import INVERTER_REPLACE_YEAR as _REPL_AN
    _fin_cap = (
        '<div class="p2-fin-cap">Projection <b>à tarif électricité '
        'constant</b> — toute hausse future du prix de l\'électricité '
        'accélère votre rentabilité, votre coût solaire restant fixe. '
        f'Le palier en année&nbsp;{_REPL_AN} : provision de remplacement '
        'de l\'onduleur, déjà déduite.</div>')

    # QRES46 — sur la page rentabilité dédiée, le bandeau navy porte déjà le
    # gain net : la carte-stat « Gain net » disparaît (plus de doublon).
    _stats_xl_html = f"""
        <div class="p2-side-stat">
          <span class="p2-stat-k">Retour sur investissement</span>
          <span class="p2-stat-v">{roi_range}</span>
          <span class="p2-stat-s">l'installation se rembourse</span>
        </div>{_perf_stat_html()}"""

    def _fin_html(xl=False):
        if masquer_eco:
            return ""
        if xl:
            # QRES38 — page rentabilité dédiée : composition VERTICALE (courbe
            # pleine largeur, stats en rangée dessous) — la page respire au
            # lieu de laisser sa moitié basse vide.
            # QRES51 — variante haute de la courbe (charts['payback_xl']) :
            # affichée sur 182 mm, elle gagne ~20 mm de hauteur et ses
            # polices déjà agrandies deviennent très lisibles.
            return f"""
  <div class="p2-fin p2-fin-xl">
    <div class="p2-fin-sub">{fin_sub}</div>
    <img class="p2-fin-wide" src="{charts.get('payback_xl', charts['payback'])}"
      alt="Courbe de rentabilité sur 25 ans">
    <div class="p2-finstats">{_stats_xl_html}</div>
    {_fin_cap}
  </div>"""
        return f"""
  <div class="p2-fin">
    <div class="p2-fin-head">
      <span class="p2-fin-title">Rentabilité sur 25 ans</span>
      <span class="p2-fin-sub">{fin_sub}</span>
    </div>

    <div class="p2-fin-grid">
      <div class="p2-fin-cc">
        <img src="{charts['payback']}" alt="Courbe de rentabilité sur 25 ans">
      </div>
      <div class="p2-fin-sc">{_stats_html}</div>
    </div>

    {_fin_cap}
  </div>"""

    def _wrap_page(inner, dense_c=""):
        return f'{style}<div class="p2-wrap{dense_c}">{inner}</div>'

    if fits_one:
        # Mise en page historique : tout sur UNE page (devis ≤ ~11 lignes).
        # QRES62 — joints élastiques : le renderer mesure le vide résiduel de
        # la page rendue et le redistribue sur ces joints (aucun bas de page
        # « tassé en haut, troué en bas »).
        # QRES63 — page LÉGÈRE (≤ 4 lignes, ex. devis mono-option minimal) :
        # la courbe grandit (52 mm) au lieu de laisser l'élastique combler un
        # vide géant — l'espace nourrit le contenu avant les respirations.
        light_cls = (" p2-light"
                     if (not deux_options and len(entries) <= 4) else "")
        return [_wrap_page(
            head_html + band_html + visuels_html
            + _table_html(entries, equipement_lbl)
            + '<div class="qj" data-w="35"></div>'
            + closing_html
            + '<div class="qj" data-w="65"></div>'
            + _fin_html(), light_cls)]

    # ── Devis chargé : page(s) équipement + page rentabilité dédiée ──────────
    # Budgets (mm) : 1ʳᵉ page équipement (bande projet + titre + clôture
    # tableau), pages « suite » (titre court seulement — la clôture suit le
    # DERNIER morceau de tableau).
    chunks = _chunk_rows(entries, budgets=[118.0, 165.0])
    # Z2 — les intérieurs sont gardés pour pouvoir, en mode « économies omises »,
    # replier l'encart environnemental sur la DERNIÈRE page équipement (dans son
    # gabarit ``p2-wrap``) au lieu de publier une page « rentabilité » vide.
    inners = []
    for i, chunk in enumerate(chunks):
        is_first = i == 0
        is_last = i == len(chunks) - 1
        label = equipement_lbl if is_first else f"{equipement_lbl} (suite)"
        inner = (head_html + band_html if is_first else cont_head_html)
        inner += _table_html(chunk, label)
        if not is_last:
            inner += ('<div class="p2-cont-note">Suite de l\'équipement '
                      'page suivante &rsaquo;</div>')
        else:
            # QRES62 — joint élastique avant la clôture (totaux) : absorbe le
            # vide résiduel mesuré de la dernière page équipement.
            inner += '<div class="qj" data-w="100"></div>' + closing_html
        inners.append(inner)

    # QRES28 — la page rentabilité dédiée (espace abondant) reçoit le bandeau
    # navy de gain net (le chiffre-héros du document, en pleine largeur).
    _callout = ""
    if gain_mult_txt and not masquer_eco:
        _callout = (
            f'<div class="p2-callout">≈ {fmt(gain25)} MAD de gain net sur '
            f'25 ans — <b>{gain_mult_txt}× le prix de votre installation'
            '</b></div>')

    # QRES66 (fondateur, 18/08/2026) — la bande « Financement possible —
    # et si vous financiez ? » (économies − crédit = dans votre poche) est
    # SUPPRIMÉE de la page rentabilité. Ne pas la réintroduire.
    # QRES53 — l'impact environnemental complète la page rentabilité (le
    # retour de l'investissement ne se compte pas qu'en dirhams) : même facteur
    # de calcul que la page 1 — M8 (19/08/2026) : SOURCE UNIQUE dans
    # quote_engine.constants (CO2_T_PAR_MWH), alignée sur le site web.
    #
    # CO2SRC (règle « chiffres vérifiés », 2026-08-26) — DEUX DES TROIS CARTES
    # SONT RETIRÉES, et ne doivent pas revenir sans source nommée :
    #   · « ≈ N arbres plantés » reposait sur 22 kg de CO₂/arbre/an, un ordre
    #     de grandeur de vulgarisation que rien ne source (l'absorption varie
    #     d'un facteur 5 selon l'essence, l'âge et le climat) ;
    #   · « ≈ N t évitées sur 25 ans » multipliait la tonne annuelle par 23,5 —
    #     un coefficient présenté comme « dégradation panneau 0,5 %/an
    #     intégrée » mais qu'aucun calcul du moteur ne produit (le cashflow
    #     25 ans, lui, a bien son modèle) et qui suppose en plus un mix
    #     électrique marocain FIGÉ pendant un quart de siècle.
    # Reste la tonne ANNUELLE : dérivée d'une production RÉELLE du devis. La
    # rangée devient une carte unique, pleine largeur.
    _prod = d.get("prod_kwh") or 0
    impact_html = ""
    if _prod:
        _co2_t = _prod * constants.CO2_T_PAR_MWH / 1000.0

        def _fr1(v):
            return (f"{v:.1f}".replace(".", ",") if v < 10
                    else fmt(round(v)))
        impact_html = (
            '<div class="p2-lbl" style="margin-top:7mm">Et pour la planète'
            '</div>'
            '<div class="p2-impact">'
            f'<div class="p2-imp-c"><span class="p2-imp-v">≈ {_fr1(_co2_t)} '
            't</span><span class="p2-imp-l">de CO<sub>2</sub> évitées '
            'chaque année</span></div>'
            '</div>')

    # QRES62 — joints élastiques de la page rentabilité : le vide mesuré se
    # répartit entre courbe→bandeau→financement→impact (page toujours pleine).
    if masquer_eco:
        # Z2 — la page « rentabilité » n'a plus de contenu légitime (courbe,
        # payback et gain net sont omis) : on ne publie PAS une page-titre vide
        # avec un seul encart environnemental. L'impact rejoint la dernière page
        # équipement — le document reste composé, avec UNE page de moins.
        inners[-1] += impact_html
        return [_wrap_page(x) for x in inners]
    pages = [_wrap_page(x) for x in inners]
    pages.append(_wrap_page(
        fin_head_html + _fin_html(xl=True)
        + '<div class="qj" data-w="40"></div>' + _callout
        + '<div class="qj" data-w="35"></div>'
        + '<div class="qj" data-w="25"></div>' + impact_html))
    return pages


def build(ctx) -> str:
    """Compat : forme mono-chaîne (concatène les pages équipement)."""
    return "".join(build_pages(ctx))
