"""Blocs HTML COMMUNS aux documents commercial (``c1c``/``c3c``) et
industriel (``i1``/``i4``), lus sur la charge utile du builder ou sur
``synthese_ci``.

Rendu SEUL : aucun calcul d'argent, aucun accès base, aucun statut touché
(règle #4). Les textes client arrivent DÉJÀ échappés une fois
(``builder.echapper_textes_client``, QJR30) : ces blocs ne les échappent pas
une seconde fois.
"""
from __future__ import annotations

import re

from ..montants import decimale
from ..i18n_labels_ci import LIBELLES_CI
from ..i18n_labels_ci_pages import LIBELLES_CI_PAGES

#: CPDF — les libellés propres aux pages C&I (résolus ici, jamais versés au
#: catalogue ``i18n_labels.LIBELLES`` publié dans ``libelles_document``).
_LIBELLES_CPDF = {**LIBELLES_CI, **LIBELLES_CI_PAGES}


def _txt(valeur):
    return str(valeur).strip() if valeur is not None else ""


# ── CIQ333 — libellés STRUCTURELS dans la langue du document ───────────────

def libelle(d, cle, fr, **valeurs):
    """Le libellé ``cle`` du catalogue ``i18n_labels`` dans la langue du
    document (``theme.libelle_doc``) ; ``fr`` = le littéral historique du
    gabarit, rendu tel quel pour un document français (octet pour octet).
    ``valeurs`` : des valeurs DÉJÀ formatées (aucun chiffre fabriqué ici).
    CPDF — les clés des tables ``i18n_labels_ci*`` se lisent dans ces tables
    (jamais versées au catalogue publié)."""
    from .. import i18n_labels
    from ..residential import theme
    d = d if isinstance(d, dict) else {}
    cpdf = _LIBELLES_CPDF.get(cle)
    if cpdf is None:
        texte = theme.libelle_doc(d, cle, fr)
    else:
        texte = libelle_cpdf(cle, langue(d)) if langue(d) != "fr" else fr
        if langue(d) != "fr" and i18n_labels.est_rtl(langue(d)):
            texte = f'<span class="i18n-rtl" dir="rtl">{texte}</span>'
    return texte.format(**valeurs) if valeurs else texte


def libelle_cpdf(cle, langue_doc="fr"):
    """CPDF — un libellé des tables ``i18n_labels_ci*`` dans ``langue_doc``
    (repli français), sans balise de direction."""
    table = _LIBELLES_CPDF[cle]
    return table.get(langue_doc) or table["fr"]


def langue(d):
    """La langue normalisée du document ('fr' par défaut)."""
    from ..residential import theme
    return theme.langue_doc(d if isinstance(d, dict) else {})


def joindre(morceaux, separateur=" &middot; "):
    """CPDF6 — les morceaux NON vides joints : jamais de séparateur orphelin
    ni de puce vide."""
    return separateur.join(m for m in (_txt(x) for x in morceaux) if m)


def ligne_vendeur(marque, ident):
    """CPDF6 — « <b>Marque</b> · e-mail · téléphone » du bloc de signature,
    champs vides omis (UNE composition pour les pages commerciale et
    industrielle)."""
    return joindre([f"<b>{marque}</b>", (ident or {}).get("email"),
                    (ident or {}).get("phone")], " &nbsp;·&nbsp; ")


def nettoyer_separateurs(html, separateur=" &middot; "):
    """CPDF6 — une ligne déjà composée (bande légale) sans morceau vide."""
    return joindre(str(html or "").split(separateur), separateur)


def garanties_servies(d, garanties):
    """CPDF6 — la garantie « Batterie » seulement quand une option SERVIE
    porte une batterie (``avec_ok`` du rendu) ; sinon retirée."""
    batterie = d.get("avec_ok", True) and not d.get("avec_batterie_differee")
    return [g for g in garanties if batterie or str(g[2]) != "Batterie"]


# ── CIQ309 — bloc client entreprise ─────────────────────────────────────────

#: Champs d'identité légale imprimés, dans l'ordre (clé de
#: ``entreprise_client`` → libellé). Champ vide ⇒ OMIS, jamais un tiret.
CHAMPS_LEGAUX = (("ice", "ICE"), ("rc", "RC"), ("if_fiscal", "IF"))


def bloc_client(entreprise, prefixe, nom_affiche="", doc=None):
    """``<div>`` d'identité de l'entreprise cliente sous le nom du client
    (couverture), ou '' quand rien n'est servi.

    ``entreprise`` : la forme ``entreprise_client`` du contrat
    ``proposal_data.json`` (CIQ4) — ``{raison_sociale, ice, rc, if_fiscal,
    siege, interlocuteur, fonction}``. Chaque champ vide est omis ; aucune
    donnée de marge. La raison sociale n'est pas répétée quand elle est
    déjà le nom imprimé en gras juste au-dessus (``nom_affiche``)."""
    if not isinstance(entreprise, dict):
        return ""
    morceaux = []
    raison = _txt(entreprise.get("raison_sociale"))
    if raison and raison.casefold() != _txt(nom_affiche).casefold():
        morceaux.append(libelle(doc, "ci_raison_sociale", "Raison sociale")
                        + f"&#160;: {raison}")
    for cle, sigle in CHAMPS_LEGAUX:
        valeur = _txt(entreprise.get(cle))
        if valeur:
            morceaux.append(f"{sigle}&#160;: {valeur}")
    siege = _txt(entreprise.get("siege"))
    if siege:
        morceaux.append(libelle(doc, "ci_siege", "Siège")
                        + f"&#160;: {siege}")
    interlocuteur = _txt(entreprise.get("interlocuteur"))
    fonction = _txt(entreprise.get("fonction"))
    # AMOT92 — « À l'attention de Pharmacie X » sous « Pharmacie X » : le
    # contact saisi EST la société, la ligne n'apprend rien (omise).
    if interlocuteur.casefold() in {raison.casefold(),
                                    _txt(nom_affiche).casefold()}:
        interlocuteur = ""
    if interlocuteur:
        morceaux.append(libelle(doc, "ci_a_l_attention", "À l'attention de")
                        + " " + interlocuteur
                        + (f", {fonction}" if fonction else ""))
    elif fonction:
        morceaux.append(libelle(doc, "ci_a_l_attention_fonction",
                                "À l'attention de la fonction")
                        + f"&#160;: {fonction}")
    if not morceaux:
        return ""
    # Style EN LIGNE : un document sans entreprise cliente garde son HTML
    # octet pour octet (aucune règle CSS ajoutée à la feuille de la page).
    return (f'<div class="{prefixe}-ent" style="margin-top:1.5mm;'
            f'font-size:7.5pt;line-height:1.35;">'
            + " &#183; ".join(morceaux) + "</div>")


# ── CIQ314 — services (O&M, suivi de production) ────────────────────────────

LEGENDE_GARANTIES = ("Durées : garanties du fabricant (fiches produit) ; "
                     "pose : engagement de l'installateur.")


def legende_garanties(d):
    """CIQ333 — la légende des garanties dans la langue du document."""
    return libelle(d, "ci_legende_garanties", LEGENDE_GARANTIES)


#: CPDF — « Onduleur (option 1) / (option 2) » de ``theme.warranties_for``
#: (deux onduleurs aux garanties différentes) : en C&I l'option 1 est l'offre
#: sans batterie, l'option 2 l'option avec batterie.
_OPTION_GARANTIE = {" (option 1)": ("ci_opt_sans_batterie", "Sans batterie"),
                    " (option 2)": ("ci_opt_avec_batterie", "Avec batterie")}


def textes_garantie(d, unite, etiquette, n=None):
    """CIQ333 — ``(unité, libellé)`` ÉCHAPPÉS d'une cellule de garantie
    (``theme.warranties_for``) : « ans » et les composants connus suivent la
    langue du document ; tout autre texte reste tel quel. CPDF — « ans »
    accordé à ``n`` en arabe ; « (option 1/2) » dit « sans / avec batterie »."""
    from .. import i18n_labels
    from ..residential import theme
    etiquette, option = str(etiquette), ""
    for suffixe, (cle_option, fr_option) in _OPTION_GARANTIE.items():
        if etiquette.endswith(suffixe):
            etiquette = etiquette[:-len(suffixe)]
            option = libelle(d, cle_option, fr_option)
            option = f" ({option if langue(d) == 'ar' else option.lower()})"
    unite_txt, etiquette_txt = theme._esc(str(unite)), theme._esc(etiquette)
    if langue(d) == "fr":
        return unite_txt, etiquette_txt + option
    if str(unite) == "ans":
        from .couverture import annees_accordees
        unite_txt = annees_accordees(libelle(d, "ci_ans", unite_txt),
                                     langue(d), n)
    cle = f"ci_garantie_{etiquette.strip().lower()}"
    if cle in i18n_labels.LIBELLES:
        etiquette_txt = libelle(d, cle, etiquette_txt)
    return unite_txt, etiquette_txt + option


def _montant(valeur):
    from ..montants import fmt_centimes
    return fmt_centimes(valeur)


def bloc_services(synthese, prefixe, couleur_titre, couleur_texte, doc=None):
    """``<div>`` des services RÉELLEMENT portés par le devis
    (``synthese_ci['services']``) : la ligne O&M nommée et son prix (ou
    « tarif sur demande » — AMOT98, D-ACI-17=a : l'alerte interne « prix à
    renseigner » reste à l'ERP), le délai d'intervention saisi. Rien d'autre :
    aucune « supervision », aucune « performance garantie » (D-CIQ-12).
    '' quand le devis ne porte aucun service. ``doc`` : la charge utile
    (langue du document, CIQ333)."""
    services = synthese.get("services") if isinstance(synthese, dict) else None
    if not isinstance(services, dict):
        return ""
    lignes = []
    om = services.get("om_option")
    if isinstance(om, dict):
        detail = []
        for li in om.get("lignes") or []:
            ht = li.get("total_ht") if isinstance(li, dict) else None
            nom = _txt(li.get("designation")) if isinstance(li, dict) else ""
            prix = (f"{_montant(ht)} MAD " + libelle(doc, "ci_ht", "HT")
                    if ht and ht > 0
                    else libelle(doc, "ci_tarif_sur_demande",
                                 "tarif sur demande"))
            # CPDF — la désignation standard (« Exploitation et maintenance
            # (O&M) », « … C&I ») répète le libellé « Maintenance (O&M) » :
            # le prix seul ; une autre désignation reste nommée.
            from .installation import designation_client
            nom = designation_client(nom)
            standard = nom.replace("&amp;", "&") == \
                "Exploitation et maintenance (O&M)"
            detail.append(prix if standard or not nom else f"{nom} — {prix}")
        statut = om.get("statut")
        suffixe = (libelle(doc, "ci_propose_non_inclus",
                           " (proposé, non inclus dans le total)")
                   if statut == "propose" else "")
        lignes.append(libelle(doc, "ci_maintenance", "Maintenance (O&amp;M)")
                      + "&#160;: " + " ; ".join(detail) + suffixe)
    suivi = services.get("suivi_production")
    if isinstance(suivi, dict) and suivi.get("delai_intervention"):
        lignes.append(
            libelle(doc, "ci_suivi_production", "Suivi de production")
            + "&#160;: "
            + libelle(doc, "ci_intervention_sous",
                      "intervention sous {heures}&#160;h",
                      heures=f"{suivi['delai_intervention']:g}"))
    elif isinstance(suivi, dict):
        # AMOT83 (D-ACI-12=a) — nommé, sans délai inventé.
        lignes.append(libelle(doc, "ci_suivi_production_inclus",
                              "Suivi de production inclus"))
    if isinstance(services.get("raccordement"), dict):
        # AMOT83 (D-ACI-11=a) — phrase fixe, au nom de la société émettrice.
        from ..residential import theme
        lignes.append(libelle(
            doc, "ci_dossier_raccordement", "Raccordement et autorisations "
            "du site&#160;: dossier monté et suivi par {societe}",
            societe=theme.company_identity(doc or {})["brand_name"]))
    if not lignes:
        return ""
    items = "".join(f'<div style="margin-top:2px;">{li}</div>'
                    for li in lignes)
    return (f'<div class="{prefixe}-svc" style="margin-top:12px;'
            f'font-size:8pt;color:{couleur_texte};line-height:1.4;">'
            f'<div style="font-size:9pt;font-weight:700;'
            f'color:{couleur_titre};">'
            f'{libelle(doc, "ci_services", "Services")}</div>{items}</div>')


# ── CIQ320 — « Bon pour accord — pour la société » + cachet ────────────────

#: ``(champ, clé du catalogue, littéral français)``.
LIBELLES_ACCEPTATION = (
    ("raison_sociale", "ci_raison_sociale", "Raison sociale"),
    ("signataire", "ci_signataire", "Nom et qualité du signataire"),
    ("ice", None, "ICE"), ("date", "bpa_date", "Date"))


def _date_signature(valeur):
    """« 24/10/2026 » pour une date ISO servie, sinon la valeur telle quelle."""
    from ..agricole.mentions import _date_jjmmaaaa
    return _date_jjmmaaaa(valeur) or _txt(valeur)


def _options_accord(d, fmt_mad=None):
    """CPDF4 — ``[(clé, total TTC formaté)]`` des deux options d'un devis à
    DEUX options non encore accepté ; ``[]`` sinon (mono-option, accepté).
    Totaux SERVIS (offre réseau : ``totaux_all.ttc`` ; option avec :
    ``option_batterie.totaux.ttc``), aucun recalcul."""
    if d.get("deux_options") is False:
        return []
    if (_txt(d.get("accepte_par_nom")) or _txt(d.get("date_acceptation"))
            or (isinstance(d.get("signature_entreprise"), dict)
                and d["signature_entreprise"])):
        return []
    ob = d.get("option_batterie")
    tot_avec = (_num_bloc(((ob or {}).get("totaux") or {}).get("ttc"))
                if isinstance(ob, dict) else 0.0)
    tot_sans = (_num_bloc((d.get("totaux_all") or {}).get("ttc"))
                or _num_bloc(d.get("_invest_ttc")))
    if tot_avec <= 0 or tot_sans <= 0 or d.get("avec_batterie_differee"):
        return []
    fmt = fmt_mad or _montant
    return [("sans", fmt(tot_sans)), ("avec", fmt(tot_avec))]


def bloc_acceptation(d, prefixe, couleur_texte="#1F2937",
                     couleur_ligne="#E5E7EB", fmt_mad=None):
    """Contenu de la case client « Bon pour accord — pour la société »
    (D-CIQ-11) : titre et mention éditables (``doc_texts``, CIQ311).

    * devis non signé → lignes à remplir « Raison sociale », « Nom et qualité
      du signataire », « ICE », « Date », un cadre « Signature » et un cadre
      « Cachet de la société » ;
    * devis signé en ligne → les valeurs de ``signature_entreprise``
      (CIQ319, déjà échappées par le builder) et la date ; le cadre
      « Cachet » reste VIDE pour le tampon physique."""
    titre, mention = textes_bpa(d)
    sig = d.get("signature_entreprise")
    sig = sig if isinstance(sig, dict) else {}
    valeurs = {
        "raison_sociale": _txt(sig.get("raison_sociale")),
        "signataire": ", ".join(v for v in (_txt(sig.get("signataire_nom")),
                                            _txt(sig.get("signataire_qualite")))
                                if v),
        "ice": _txt(sig.get("ice")),
        # Date de signature servie en ISO (« 2026-10-24 ») : imprimée
        # jj/mm/aaaa comme le « Le 24/10/2026 » voisin.
        "date": _date_signature(sig.get("date")),
    }
    lignes = "".join(
        f'<div style="margin-top:3px;">'
        f'{libelle(d, cat, fr) if cat else fr}&#160;: '
        + (f'<b>{valeurs[cle]}</b>' if valeurs[cle]
           else f'<span style="display:inline-block;width:45mm;'
                f'border-bottom:1px dotted {couleur_ligne};">&#160;</span>')
        + '</div>'
        for cle, cat, fr in LIBELLES_ACCEPTATION)
    cadre = (f'display:table-cell;width:50%;height:16mm;vertical-align:top;'
             f'border:1px dashed {couleur_ligne};border-radius:6px;'
             f'padding:3px 6px;font-size:6.5pt;')
    cadres = (f'<div style="display:table;width:100%;border-spacing:4px 0;'
              f'margin-top:5px;"><div style="{cadre}">'
              f'{libelle(d, "ci_signature", "Signature")}</div>'
              f'<div style="{cadre}">'
              f'{libelle(d, "ci_cachet", "Cachet de la société")}'
              f'</div></div>')
    # CPDF4 — l'option retenue : deux cases à cocher sur un devis à deux options.
    cases = "".join(
        f'<div style="margin-top:3px;"><span style="display:inline-block;'
        f'width:3mm;height:3mm;border:1px solid {couleur_texte};'
        f'vertical-align:middle;margin-right:2mm;">&#160;</span>'
        + libelle(d, f"ci_bpa_option_{cle}",
                  {"sans": "Sans batterie — {total} MAD TTC",
                   "avec": "Avec batterie — {total} MAD TTC"}[cle],
                  total=total)
        + '</div>' for cle, total in _options_accord(d, fmt_mad))
    lignes = cases + lignes
    pour = libelle(d, "ci_pour_la_societe", "pour la société")
    return (f'<div class="{prefixe}-sign-h">{titre} — {pour}</div>'
            f'<div class="{prefixe}-acc" style="font-size:7pt;'
            f'color:{couleur_texte};line-height:1.3;">{lignes}{cadres}'
            f'<div style="margin-top:3px;font-style:italic;">{mention}'
            f'</div></div>')


# ── CIQ331 — échéancier en N jalons ─────────────────────────────────────────

TITRE_ECHEANCIER = "Échéancier de paiement"


def _pct(valeur):
    """« 40 » / « 33,5 » — le pourcentage servi, sans arrondi propre."""
    if isinstance(valeur, (int, float)):
        return decimale(f"{valeur:g}")
    return _txt(valeur)


def _libelle_jalon(doc, jalon):
    """Le libellé d'un jalon dans la langue du document : un jalon CONNU
    (``ci_jalon_<jalon>``) est traduit ; un libellé saisi reste tel quel."""
    from .. import i18n_labels
    cle = f"ci_jalon_{jalon.get('jalon')}"
    libelle_servi = _txt(jalon.get("libelle"))
    if cle in i18n_labels.LIBELLES and \
            libelle_servi == i18n_labels.LIBELLES[cle]["fr"]:
        return libelle(doc, cle, libelle_servi)
    return libelle_servi


def bloc_echeancier(synthese, prefixe, couleur_titre="#0F1E35",
                    couleur_texte="#1F2937", couleur_ligne="#E5E7EB",
                    doc=None):
    """``<div>`` de l'échéancier servi par ``synthese_ci['echeancier']``
    (N jalons, D-CIQ-13) : libellé, pourcentage et montant TTC au CENTIME
    (montants du builder — le dernier jalon porte le reliquat, la somme
    égale le total). Montant non servi ⇒ le pourcentage seul, jamais un
    « 0 ». '' sans jalon."""
    jalons = synthese.get("echeancier") if isinstance(synthese, dict) \
        else None
    jalons = [j for j in jalons or [] if isinstance(j, dict)]
    if not jalons:
        return ""
    ttc = libelle(doc, "ci_ttc", "TTC")
    cellules = []
    for j in jalons:
        montant = j.get("montant_ttc")
        montant_html = (
            f'<div class="{prefixe}-ech-m" style="font-weight:700;'
            f'color:{couleur_titre};margin-top:2px;">{_montant(montant)}'
            f'&#160;MAD {ttc}</div>' if montant is not None else "")
        cellules.append(
            f'<td class="{prefixe}-ech-c" style="vertical-align:top;'
            f'border:1px solid {couleur_ligne};border-radius:8px;'
            f'padding:6px 8px;"><div style="font-size:11pt;'
            f'color:{couleur_titre};">{_pct(j.get("pct"))}&#160;%</div>'
            f'<div style="margin-top:1px;">{_libelle_jalon(doc, j)}</div>'
            f'{montant_html}</td>')
    titre = libelle(doc, "ci_cpdf_echeancier", TITRE_ECHEANCIER)
    return (f'<div class="{prefixe}-ech" style="margin-top:12px;'
            f'font-size:7.5pt;color:{couleur_texte};line-height:1.3;">'
            f'<div style="font-size:9pt;font-weight:700;'
            f'color:{couleur_titre};">{titre}</div>'
            f'<table style="width:100%;border-collapse:separate;'
            f'border-spacing:5px 0;margin:4px -5px 0 -5px;table-layout:fixed;">'
            f'<tr>{"".join(cellules)}</tr></table></div>')


# ── CIQ318 — bloc « Offre de financement » ──────────────────────────────────

TITRE_FINANCEMENT = "Offre de financement"


def bloc_financement(synthese, prefixe="ci", couleur_titre="#0F1E35",
                     couleur_texte="#1F2937", doc=None):
    """``<div>`` de l'offre de financement telle que ``economie_ci`` la
    sert (``synthese_ci['argent']['financement']``, D-CIQ-15), ou ''.

    Construit SEULEMENT depuis l'offre écrite saisie par le vendeur : le
    libellé (organisme et référence quand l'offre les porte), l'échéance,
    la durée, et l'économie mensuelle moyenne sur la MÊME base HT/TTC
    (``argent.base``). Aucun taux inventé, aucun recalcul ; le mot
    « crédit-bail » ne vient que du libellé servi (gardé par le réglage
    juridique, CIQ211) — ce bloc ne l'écrit jamais lui-même."""
    argent = synthese.get("argent") if isinstance(synthese, dict) else None
    offre = argent.get("financement") if isinstance(argent, dict) else None
    if not isinstance(offre, dict) or offre.get("echeance_mad") is None:
        return ""
    base = argent.get("base")
    suffixe = {"ht": " " + libelle(doc, "ci_ht", "HT"),
               "ttc": " " + libelle(doc, "ci_ttc", "TTC")}.get(base, "")
    titre = libelle(doc, "ci_offre_financement", TITRE_FINANCEMENT)
    lignes = [_txt(offre.get("libelle_client")) or titre]
    duree = offre.get("duree_mois")
    echeance = (libelle(doc, "ci_echeance_mensuelle", "Échéance mensuelle")
                + f"&#160;: {_montant(offre['echeance_mad'])}"
                f"&#160;MAD{suffixe}")
    if duree:
        echeance += " " + libelle(doc, "ci_sur_mois", "sur {mois} mois",
                                  mois=f"{duree:g}")
    lignes.append(echeance)
    mensuelle = offre.get("economie_mensuelle_moyenne_mad")
    if mensuelle is not None:
        lignes.append(libelle(doc, "ci_economie_mensuelle",
                              "Économie mensuelle moyenne estimée")
                      + f"&#160;: {_montant(mensuelle)}&#160;MAD{suffixe}")
    ecart = offre.get("ecart_mensuel_mad")
    if ecart is not None:
        lignes.append(libelle(doc, "ci_ecart_mensuel", "Écart mensuel")
                      + f"&#160;: {_montant(ecart)}&#160;MAD{suffixe}")
    lignes.extend(_lignes_offre_cec15(doc, offre))
    source = _txt(offre.get("source"))
    if source:
        lignes.append(libelle(doc, "ci_source", "Source")
                      + f"&#160;: {source}")
    items = "".join(f'<div style="margin-top:2px;">{li}</div>'
                    for li in lignes)
    return (f'<div class="{prefixe}-fin" style="margin-top:10px;'
            f'font-size:8pt;color:{couleur_texte};line-height:1.4;">'
            f'<div style="font-size:9pt;font-weight:700;'
            f'color:{couleur_titre};">{titre}</div>{items}</div>')


def _lignes_offre_cec15(doc, offre):
    """CEC15 (affichage) — « Apport à la signature » et « Frais de l'offre »
    quand ils sont servis > 0, puis « Retour sur l'offre » lu sur
    ``retour_offre_ans`` (au dixième) ; omis quand la clé est absente ou
    nulle — jamais recalculé ici (règle #4)."""
    from .couverture import unite_ans
    lignes = []
    for cle, lib, fr in (("apport_mad", "ci_fin_apport",
                          "Apport à la signature"),
                         ("frais_mad", "ci_fin_frais", "Frais de l'offre")):
        v = offre.get(cle)
        if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0:
            lignes.append(libelle(doc, lib, fr)
                          + f"&#160;: {_montant(v)}&#160;MAD")
    retour = offre.get("retour_offre_ans")
    if isinstance(retour, (int, float)) and not isinstance(retour, bool):
        texte = decimale(f"{float(retour):.1f}")
        lignes.append(libelle(doc, "ci_fin_retour", "Retour sur l'offre")
                      + f"&#160;: {texte}" + unite_ans(doc, texte))
    return lignes


# ── CIQ311 — bloc « Conditions » ────────────────────────────────────────────

TITRE_CGV_DEFAUT = "Conditions générales du devis"


#: Fondateur 26/10/2026 — libellés du bloc « option avec batterie » C&I.
LIBELLES_OPTION_AVEC = {
    "titre": {"fr": "Option avec batterie", "en": "Battery option",
              "ar": "خيار مع بطارية"},
    "equipements": {"fr": "&Eacute;quipements propres &agrave; cette option",
                    "en": "Equipment specific to this option",
                    "ar": "معدات خاصة بهذا الخيار"},
    "economie": {"fr": "&Eacute;conomie annuelle HT", "en": "Annual saving excl. VAT",
                 "ar": "التوفير السنوي دون ضريبة"},
    "retour": {"fr": "Retour sur investissement", "en": "Payback",
               "ar": "مدة استرداد الاستثمار"},
    "ans": {"fr": "ans", "en": "years", "ar": "سنوات"},
}


def _num_bloc(valeur):
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return 0.0


def textes_non_rentable(valeur, lg):
    """D-CI-BATTERIE-NON-RENTABLE — ``(badge, ligne)`` échappés dans la
    langue ``lg`` quand la valeur chiffrée marque l'option « avec »
    ``batterie_rentable: false`` (``mentions.non_rentable_option_avec``) ;
    ``('', '')`` sinon."""
    import html
    valeur = valeur if isinstance(valeur, dict) else {}
    if valeur.get("batterie_rentable") is not False:
        return "", ""

    def dans(cle):
        textes = valeur.get(cle) if isinstance(valeur.get(cle), dict) else {}
        return html.escape(str(textes.get(lg) or textes.get("fr") or ""), quote=False)
    return dans("textes_badge"), dans("textes_non_rentable")


def bloc_option_avec(d, L, fmt_mad, couleurs):
    """Fondateur 26/10/2026 — un C&I à DEUX options imprime, sous le tableau
    de l'offre réseau, l'option « avec batterie » comme le résidentiel : ses
    équipements propres (les lignes de l'option absentes de l'offre réseau),
    SA chaîne de totaux (Total HT, TVA, Total TTC du builder, aucun
    recalcul) et l'économie / le retour chiffrés par le moteur C&I (le
    retour : total HT ÷ économie HT). Sans option « avec » au document ⇒ ''."""
    from .mentions import valeur_option_avec
    bloc = d.get("option_batterie")
    tot = (bloc or {}).get("totaux") if isinstance(bloc, dict) else None
    if not isinstance(tot, dict) or _num_bloc(tot.get("ttc")) <= 0:
        return ""
    navy, muted, line_soft, wash = couleurs
    lg = langue(d)

    def t(cle):
        return LIBELLES_OPTION_AVEC[cle].get(lg) or LIBELLES_OPTION_AVEC[cle]["fr"]

    from .installation import lignes_client
    # « Installation clé en main » regroupée PAR option (même règle que le
    # tableau de l'offre réseau).
    reseau = {(it.get("designation"), _num_bloc(it.get("quantite")))
              for it in lignes_client(d.get("all_items") or [], d) if isinstance(it, dict)}
    rows = "".join(
        f'<tr><td class="c2-d">{it.get("designation") or ""}</td>'
        f'<td class="c2-q">{_num_bloc(it.get("quantite")):g}</td></tr>'
        for it in lignes_client(bloc.get("lignes") or [], d) if isinstance(it, dict)
        and _num_bloc(it.get("quantite")) > 0
        and (it.get("designation"), _num_bloc(it.get("quantite"))) not in reseau)
    valeur = valeur_option_avec(d) or {}
    lignes_valeur = ""
    if valeur.get("economie_annuelle_mad"):
        lignes_valeur += (f'<tr><td>{t("economie")}</td>'
                          f'<td>{fmt_mad(valeur["economie_annuelle_mad"])} MAD</td></tr>')
    if valeur.get("retour_simple_ans"):
        lignes_valeur += (f'<tr><td>{t("retour")}</td><td>'
                          f'{decimale(str(valeur["retour_simple_ans"]))} {t("ans")}</td></tr>')
    badge, ligne_nr = textes_non_rentable(valeur, lg)
    if ligne_nr:
        # D-CI-BATTERIE-NON-RENTABLE — la raison, sous les chiffres réels.
        lignes_valeur += (f'<tr><td colspan="2" style="font-weight:400;font-size:7.5pt;'
                          f'color:{muted};white-space:normal;">{ligne_nr}</td></tr>')
    titre = t("titre") + (f' &mdash; <span style="font-weight:400;">{badge}</span>'
                          if badge else "")
    return (
        f'<div style="margin-top:12px;border:1px solid {line_soft};border-radius:12px;'
        f'background:{wash};padding:9px 12px;"><div class="c2-kicker">{titre}</div>'
        + (f'<table class="c2-tbl"><tr><th>{t("equipements")}</th>'
           f'<th class="c2-rr">{L("qte", "Qté")}</th></tr>{rows}</table>' if rows else "")
        + '<table class="c2-tot-tbl" style="margin-top:6px;">'
        f'<tr><td>{L("total_ht", "Total HT")}</td><td>{fmt_mad(_num_bloc(tot.get("ht_net")))} MAD</td></tr>'
        f'<tr><td>{L("tva", "TVA")}</td><td>{fmt_mad(_num_bloc(tot.get("tva")))} MAD</td></tr>'
        f'<tr class="c2-tot-ttc"><td>{L("total_ttc", "Total TTC")}</td>'
        f'<td>{fmt_mad(_num_bloc(tot.get("ttc")))} MAD</td></tr>'
        f'{lignes_valeur}</table></div>')


def _doc_texts(d):
    textes = d.get("doc_texts")
    return textes if isinstance(textes, dict) else {}


def textes_bpa(d):
    """``(titre, mention)`` du « Bon pour accord » : les textes ÉDITABLES de
    la société (``doc_texts`` › ``bpa_titre`` / ``bpa_mention``), sinon les
    libellés par défaut du moteur — la même voie que le legacy."""
    from ..generate_devis_premium import DEFAULT_DOC_TEXTS
    textes = _doc_texts(d)
    # CIQ333 — un texte SAISI par la société reste tel quel ; le libellé
    # par défaut du moteur suit la langue du document.
    titre = _txt(textes.get("bpa_titre")) or libelle(
        d, "bon_pour_accord", DEFAULT_DOC_TEXTS["bpa_titre"])
    mention = (_txt(textes.get("bpa_mention"))
               or libelle(d, "ci_bpa_mention",
                          DEFAULT_DOC_TEXTS["bpa_mention"]))
    return titre, mention


def puces_conditions(d):
    """Les puces des conditions générales que le document IMPRIME.

    APDF12 — lues de LA source ``clauses_cgv.cgv_imprimees`` :
    la variante C&I du mode (``cgv_ci``, gelée ou vive, marqueurs
    substitués), sinon les puces société gelées ou vives. Jamais ``cpq``
    (parqué)."""
    from ..clauses_cgv import cgv_imprimees
    puces = [_txt(p) for p in cgv_imprimees(d)["puces"] if _txt(p)]
    # AMOT36 — troncature DÉCLARÉE posée par ``commercial.equip.
    # pdf_adaptatif`` quand le contrat de pages ne tient pas : les premières
    # puces restent, la suite est renvoyée à la proposition en ligne.
    garder = d.get("_cgv_max")
    if isinstance(garder, int) and 0 <= garder < len(puces):
        puces = puces[:garder] + [libelle(
            d, "ci_cgv_suite",
            "Suite des conditions : proposition en ligne")]
    return puces


_PUCE_ECHEANCIER = re.compile(
    r"\s*(?:échéancier de paiement|payment schedule|جدول الأداء|جدول الدفع)",
    re.IGNORECASE)


def _echeancier_imprime(d):
    synthese = d.get("com_synthese") or d.get("ind_synthese") or {}
    return any(isinstance(j, dict) for j in synthese.get("echeancier") or [])


def bloc_conditions(d, prefixe, couleur_titre, couleur_texte):
    """``<div>`` « Conditions » : puces CGV (gelées) et note de TVA
    multi-taux (``tva_note``, si les puces ne la portent pas déjà) — styles
    en ligne, compact, pour tenir dans la page EXISTANTE (D-QJR5-12)."""
    puces = puces_conditions(d)
    if _echeancier_imprime(d):
        # CPDF10 — l'échéancier est imprimé en cartes (montants au centime,
        # dernier jalon = reliquat) : la puce CGV qui le répète (« Acompte :
        # 50 % ; … ; Solde : 10 % ») n'est pas imprimée une seconde fois.
        puces = [p for p in puces if not _PUCE_ECHEANCIER.match(p)]
    tva_note = _txt(d.get("tva_note"))
    if tva_note and not any(tva_note in p for p in puces):
        puces.append(tva_note)
    if not puces:
        return ""
    # APDF12 — titre de ``cgv_imprimees`` (celui de la variante C&I, sinon
    # la surcharge société) ; le défaut garde son libellé du catalogue.
    from .. import i18n_labels
    from ..clauses_cgv import cgv_imprimees
    titre = _txt(cgv_imprimees(d)["titre"])
    if titre in (TITRE_CGV_DEFAUT, i18n_labels.libelle(
            "ci_cgv_titre", d.get("langue_sortie"))):
        titre = libelle(d, "ci_cgv_titre", TITRE_CGV_DEFAUT)
    items = "".join(f'<li style="margin-top:1px;">{p}</li>' for p in puces)
    return (
        f'<div class="{prefixe}-cond" style="margin-top:10px;'
        f'font-size:6.8pt;color:{couleur_texte};line-height:1.35;">'
        f'<div style="font-size:8pt;font-weight:700;color:{couleur_titre};">'
        f'{titre}</div>'
        f'<ul style="margin:3px 0 0 0;padding-left:12px;">{items}</ul></div>')
