"""CIQ307 — morceaux HTML COMMUNS aux couvertures commerciale (``c1c``) et
industrielle (``i1``), lus sur ``synthese_ci`` (via ``chiffres_cles``).

Un seul endroit pour : le bandeau « Estimation sous réserve de la visite
technique » + la liste ``a_confirmer`` (D-CIQ-5, W4-22), la ligne de
méthode des taux (C3-07), la tuile payback, la note sur la pointe (CIQ305)
et le motif quand l'argent n'est pas chiffré. Rendu seul — aucun calcul,
aucun statut touché (règle #4).

CIQ333 — chaque libellé STRUCTUREL suit la langue du document
(``ci.blocs.libelle`` : catalogue ``i18n_labels``) ; un document français
garde ses littéraux d'hier, octet pour octet.
"""
from __future__ import annotations

import html
import re

from .blocs import langue, libelle
from .mentions import TEXTES_POINTE_SANS, TEXTES_VISITE, texte

#: Bandeau (sans le point final de la phrase de la table des mentions).
BANDEAU_RESERVE = TEXTES_VISITE["fr"].rstrip(".")

#: Le texte MT historique (QXMT), gardé tel quel pour un site MT non chiffré.
TEXTE_MT_NON_CHIFFRE = (
    "Dossier raccordé en MOYENNE TENSION : les économies et le retour sur "
    "investissement ne sont pas chiffrés au barème basse tension. "
    "Communiquez-nous {motif} et nous les calculons sur le barème MT.")
TEXTE_NON_CHIFFRE = (
    "Économies et retour sur investissement non chiffrés à ce stade : "
    "communiquez-nous {motif}.")

#: CIQ333 — motif d'argent servi par ``synthese_ci`` → clé du catalogue.
MOTIFS_ARGENT = {
    "vos 12 dernières factures": "ci_motif_argent_bt",
    ("vos 12 dernières factures MT : prix des trois postes, prime fixe, "
     "puissance souscrite"): "ci_motif_argent_mt",
}


#: AMOT80 — sources / motifs INTERNES servis par le moteur C&I → clé du
#: libellé CLIENT (``i18n_labels``). Hors table : les codes internes
#: résiduels (décisions, fichiers, clés de module) sont retirés.
SOURCES_CLIENT = {
    "economie_ci.economie_annee1 (valorisation horaire au tarif du poste)":
        "ci_src_economie",
    "etude_ci.bilan (moteur C&I)": "ci_src_production",
    "etude_ci.bilan": "ci_src_production",
    "D-CIQ-10 : 25 ans": "ci_src_horizon",
    # AMOT88 — chemin d'écran interne : jamais imprimé au client.
    "réglage société — Paramètres › Tarification & ROI":
        "ci_src_reglage_societe",
    "conventions Groupe CIQ": "ci_src_methode",
    ("remplacement à mi-vie (principe IEA PVPS, décision Q1 du 20/08/2026), "
     "au montant réel de la ligne onduleur du devis"): "ci_src_onduleur",
    # AMOT84 — motif de sensibilité servi par ``economie_ci``.
    ("charge horaire déclarée absente : production non recalculable heure "
     "par heure — scénario non chiffré"): "ci_ind_sens_motif_sans_charge",
}
#: AMOT84 — motifs de réserve de visite (``etude_ci.sous_reserve_visite``,
#: séparés par « ; », codes internes déjà retirés) → clé du catalogue.
RESERVES_CLIENT = {
    "site MT : visite avant le devis final": "ci_reserve_site_mt",
    "tension de raccordement inconnue": "ci_reserve_tension",
    "puissance souscrite inconnue": "ci_reserve_puissance",
    "surface disponible inconnue": "ci_reserve_surface",
    "profil horaire non déclaré : estimation sous réserve de visite":
        "ci_reserve_profil",
}
_CODES_INTERNES = re.compile(
    r"\s*\((?:D-[A-Z]+-\d+(?:\s*,\s*)?)+\)"
    r"|\bD-[A-Z]+-\d+\s*:\s*"
    r"|,?\s*décision Q\d+ du [\d/]+"
    r"|\b[\w.]+\.json\s*(?:—\s*)?"
    r"|\b(?:saisies_economie_ci|economie_ci|etude_ci)\.[\w.]+\s*"
    # AMOT91 — un nom de champ interne entre parenthèses
    # (« (taux_actualisation_client) »).
    r"|\s*\([a-z]+(?:_[a-z]+)+\)")


def texte_client(d, texte):
    """AMOT80 — un texte SERVI par le moteur (source d'hypothèse, motif)
    dans les mots du client : la table ``SOURCES_CLIENT`` (traduite), sinon
    le texte sans ses codes internes (« D-CIQ-10 », « economie_ci. »…)."""
    brut = str(texte or "").strip()
    if brut in SOURCES_CLIENT:
        from .. import i18n_labels
        cle = SOURCES_CLIENT[brut]
        return libelle(d, cle, i18n_labels.LIBELLES[cle]["fr"])
    return _CODES_INTERNES.sub("", brut).strip(" —")


def motif_investissement(d, cle):
    """AMOT80 (D-ACI-8=a) — « Investissement non encore chiffré (N articles
    sans prix) » quand le bloc servi omet l'investissement (ADEV81), ou
    None. Lu sur ``synthese_ci`` — aucun calcul."""
    from .synthese import chiffres_cles
    motif = chiffres_cles(d.get(f"{cle}_synthese") or {})[
        "motif_investissement"]
    visite = re.search(r"\((\d+) postes? hors total\)", motif or "")
    if visite is not None:
        # AMOT85 — seuls des postes hors total (visite) manquent.
        if visite.group(1) == "1":
            return libelle(d, "ci_invest_apres_visite_1", "Investissement à "
                           "compléter après la visite technique (1 poste hors total)")
        return libelle(d, "ci_invest_apres_visite_n", "Investissement à compléter "
                       "après la visite technique ({n} postes hors total)",
                       n=visite.group(1))
    n = re.search(r"\((\d+) articles? sans prix\)", motif or "")
    if not motif or n is None:
        return motif and libelle(d, "ci_invest_non_chiffre",
                                 "Investissement non encore chiffré")
    if n.group(1) == "1":
        return libelle(d, "ci_invest_non_chiffre_1", "Investissement non "
                       "encore chiffré (1 article sans prix)")
    return libelle(d, "ci_invest_non_chiffre_n", "Investissement non encore "
                   "chiffré ({n} articles sans prix)", n=n.group(1))


def _a_confirmer(d, cle):
    """Les points « à confirmer » dans la langue du document : un libellé
    connu du moteur (``ci_confirmer_<clé>``) est traduit ; un motif propre
    au dossier reste tel quel."""
    from .. import i18n_labels
    cles = d.get(f"{cle}_a_confirmer_cles") or []
    # AMOT88 — les postes hors total ont leur propre ligne du bandeau
    # (``bandeau_reserve``) : jamais « À confirmer : À chiffrer… ».
    paires = [(texte_client(d, a), cles[i] if i < len(cles) else "")
              for i, a in enumerate(d.get(f"{cle}_a_confirmer") or []) if a]
    paires = [(t, c) for t, c in paires if c != "a_chiffrer_visite"]
    libelles = [t for t, _c in paires]
    cles = [c for _t, c in paires]
    if langue(d) == "fr":
        return libelles
    sortie = []
    for i, texte_fr in enumerate(libelles):
        cat = f"ci_confirmer_{cles[i]}" if i < len(cles) else ""
        if cat in i18n_labels.LIBELLES and \
                texte_fr == i18n_labels.LIBELLES[cat]["fr"]:
            sortie.append(libelle(d, cat, texte_fr))
        else:
            # AMOT84 — chaque motif connu du moteur dans la langue du
            # document ; un motif propre au dossier reste tel quel.
            sortie.append("; ".join(
                libelle(d, RESERVES_CLIENT[m.strip()], m.strip())
                if m.strip() in RESERVES_CLIENT else m.strip()
                for m in texte_fr.split(";")))
    return sortie


def bandeau_reserve(d, cle, prefixe):
    """``<div>`` du bandeau quand l'étude est « sous réserve », sinon ''."""
    if not d.get(f"{cle}_sous_reserve"):
        return ""
    a_confirmer = _a_confirmer(d, cle)
    liste = (f'<div class="{prefixe}-reserve-l">'
             + libelle(d, "ci_a_confirmer", "À confirmer : ")
             + " · ".join(a_confirmer) + "</div>") if a_confirmer else ""
    postes = postes_hors_total(d.get(f"{cle}_synthese"))
    if postes:
        # AMOT88 — chaque poste dit son rôle en mots simples (« câble DC —
        # <article> », « structure de fixation »), dans la langue du document.
        from .synthese import texte_postes
        liste = (f'<div class="{prefixe}-reserve-l">'
                 + libelle(d, "ci_a_chiffrer_hors_total", "À chiffrer après "
                           "la visite technique (hors total) : ")
                 + html.escape(texte_postes(postes, roles_client(d)),
                               quote=False) + "</div>") + liste
    bandeau = (BANDEAU_RESERVE if langue(d) == "fr"
               else texte(TEXTES_VISITE, langue(d)).rstrip("."))
    return (f'<div class="{prefixe}-reserve"><b>{bandeau}</b>'
            f'{liste}</div>')


def css_bandeau(prefixe, gold, ink, muted):
    return (
        f".{prefixe}-reserve{{margin-bottom:8px;border:1px solid {gold};"
        f"border-radius:10px;background:#FFF9EC;padding:7px 12px;"
        f"font-size:8pt;color:{ink};line-height:1.35;}}"
        f".{prefixe}-reserve-l{{font-size:7pt;color:{muted};margin-top:2px;}}")


def ligne_methode(d, cle, prefixe):
    """Ligne de méthode des taux sous la rangée KPI, ou ''."""
    methode = d.get(f"{cle}_methode")
    if methode and d.get(f"{cle}_methode_cle"):
        methode = libelle(d, f"ci_methode_{d[f'{cle}_methode_cle']}",
                          methode)
    return f'<div class="{prefixe}-mtsrc">{methode}</div>' if methode else ""


def _argent_mt(d, cle):
    """Le motif MT s'applique-t-il ? ``synthese_ci`` le dit quand elle existe
    (``<cle>_motif_argent`` posé). Sans synthèse (aucun motif servi), le masque
    ne vient que de la garde QXMT du builder — un dossier dont la tension de
    raccordement DÉCLARÉE est MT : il garde sa mention MOYENNE TENSION."""
    if d.get(f"{cle}_motif_argent"):
        return bool(d.get(f"{cle}_argent_mt"))
    etude = d.get("etude") if isinstance(d.get("etude"), dict) else {}
    # AMOT81 — ``tension`` : la clé d'un brouillon auto C&I.
    tension = str(etude.get("tension_raccordement") or etude.get("tension")
                  or "").strip().lower()
    return tension in ("mt", "ht")


def ligne_non_chiffre(d, cle, prefixe):
    """Le motif quand l'argent n'est pas chiffré (``masquer_economies``).

    AMOT80 — investissement non chiffré ⇒ SON motif ; argent servi sans
    motif client ⇒ aucune demande de factures (la consommation est là)."""
    phrase = motif_investissement(d, cle)
    if phrase is None and not d.get(f"{cle}_motif_argent") and \
            (d.get(f"{cle}_synthese") or {}).get("argent"):
        phrase = libelle(d, "ci_non_chiffre_sans_motif", "Économies et "
                         "retour sur investissement non chiffrés à ce stade.")
    if phrase:
        return f'<div class="{prefixe}-mtsrc">{phrase}</div>'
    motif = d.get(f"{cle}_motif_argent") or "vos 12 dernières factures"
    if motif in MOTIFS_ARGENT:
        motif = libelle(d, MOTIFS_ARGENT[motif], motif)
    if _argent_mt(d, cle):
        phrase = libelle(d, "ci_non_chiffre_mt", TEXTE_MT_NON_CHIFFRE,
                         motif=motif)
    else:
        phrase = libelle(d, "ci_non_chiffre", TEXTE_NON_CHIFFRE, motif=motif)
    return f'<div class="{prefixe}-mtsrc">{phrase}</div>'


def note_pointe(d, cle):
    """La note sur la pointe selon la composition servie (CIQ305)."""
    if langue(d) != "fr":
        synthese = d.get(f"{cle}_synthese") or {}
        pointe = next((h for h in synthese.get("hypotheses") or []
                       if isinstance(h, dict) and h.get("cle") == "pointe"),
                      None)
        textes = (pointe or {}).get("textes") or TEXTES_POINTE_SANS
        return texte(textes, langue(d))
    return d.get(f"{cle}_note_pointe") or TEXTES_POINTE_SANS["fr"]


def ans(valeur):
    """« 3 » / « 3,4 » — le payback servi, sans arrondi propre."""
    texte_ans = (f"{valeur:g}" if isinstance(valeur, (int, float))
                 else str(valeur))
    return texte_ans.replace(".", ",")


#: CIQ315 — jamais un avantage fiscal promis : la récupération dépend du
#: régime du client (une clinique est exonérée sans droit à déduction).
NOTE_TVA_RECUPERABLE = ("TVA récupérable selon votre régime fiscal — à "
                        "confirmer avec votre comptable.")

#: AMOT86 (D-ACI-2=a) — titre du bloc investissement par base servie :
#: ``(clé, littéral)`` « clé en main » d'hier, puis la version « hors postes
#: à chiffrer après la visite » quand des postes restent hors total.
TITRES_INVESTISSEMENT = {
    "ht": (("ci_invest_ht", "Investissement HT (clé en main)"),
           ("ci_invest_ht_hv", "Investissement HT hors postes à chiffrer "
                               "après la visite")),
    "deux": (("ci_invest", "Investissement (clé en main)"),
             ("ci_invest_hv", "Investissement hors postes à chiffrer après "
                              "la visite")),
    "ttc": (("ci_invest_ttc", "Investissement (TTC, clé en main)"),
            ("ci_invest_ttc_hv", "Investissement TTC hors postes à chiffrer "
                                 "après la visite")),
}


def postes_hors_total(synthese):
    """AMOT86 — les postes « à chiffrer après la visite » restés hors total
    (``chiffres_cles(synthese)['postes_hors_total']``), ou []."""
    from .synthese import chiffres_cles
    return chiffres_cles(synthese if isinstance(synthese, dict) else {})[
        "postes_hors_total"]


def roles_client(d):
    """AMOT88 — la table « rôle → mots du client » dans la langue du
    document (``ci_role_<rôle>``), pour ``synthese.libelle_poste``."""
    from .synthese import ROLES_POSTES_CLIENT
    return {role: libelle(d, f"ci_role_{role}", fr)
            for role, fr in ROLES_POSTES_CLIENT.items()}


def titre_investissement(d, synthese, base):
    """AMOT86 — le titre du bloc investissement : jamais « clé en main »
    quand des postes sont hors total (« Investissement hors postes à chiffrer
    après la visite »). ``base`` : ``ht`` / ``deux`` / ``ttc``."""
    sans_reserve, hors_visite = TITRES_INVESTISSEMENT.get(
        base, TITRES_INVESTISSEMENT["ttc"])
    cle, fr = hors_visite if postes_hors_total(synthese) else sans_reserve
    return libelle(d, cle, fr)


def bloc_investissement(d, synthese, prefixe, fmt_mad, ancre, invest=None):
    """CIQ315 — le bloc « Investissement » de la couverture, sur la base de
    ``synthese_ci.argent.base`` (D-CIQ-3) :

    * ``ht`` (TVA récupérable déclarée) → « Investissement HT », le TTC en
      petit et la note « à confirmer avec votre comptable » ;
    * ``deux`` (récupération inconnue) → HT ET TTC (présentation D2) ;
    * ``ttc`` ou argent absent → le libellé TTC d'hier, octet pour octet.

    Jamais un HT déduit de l'ICE ou de la catégorie ; les montants sont ceux
    de la chaîne canonique (``totaux_all.ht_net``, ``_invest_ttc``)."""
    if invest is None:
        invest = d.get("_invest_ttc") or 0
    argent = (synthese or {}).get("argent") if isinstance(synthese, dict) \
        else None
    base = argent.get("base") if isinstance(argent, dict) else None
    ht = (d.get("totaux_all") or {}).get("ht_net")
    ttc_txt = fmt_mad(invest)
    l_ht = libelle(d, "ci_ht", "HT")
    l_ttc = libelle(d, "ci_ttc", "TTC")
    l_soit = libelle(d, "ci_soit", "soit")
    note_tva = libelle(d, "ci_note_tva_recuperable", NOTE_TVA_RECUPERABLE)
    if base in ("ht", "deux") and ht is not None:
        ht_txt = fmt_mad(ht)
        if base == "ht":
            return _html_investissement(
                prefixe, titre_investissement(d, synthese, "ht"), ht_txt,
                l_ht, ancre("total_ht", ht_txt),
                f'{l_soit} {ttc_txt}&nbsp;MAD&nbsp;{l_ttc}'
                f'{ancre("total_affiche", ttc_txt)} · {note_tva}')
        return _html_investissement(
            prefixe, titre_investissement(d, synthese, "deux"), ttc_txt,
            l_ttc, ancre("total_affiche", ttc_txt),
            f'{l_soit} {ht_txt}&nbsp;MAD&nbsp;{l_ht}'
            f'{ancre("total_ht", ht_txt)} · {note_tva}')
    return _html_investissement(
        prefixe, titre_investissement(d, synthese, "ttc"), ttc_txt, "",
        ancre("total_affiche", ttc_txt))


def _html_investissement(prefixe, titre, montant, base, ancre_html, note=""):
    """AMOT87 — le titre et le montant sur UNE rangée (montant et unité
    insécables : jamais « TTC » seul à la ligne), la note « soit … · TVA
    récupérable… » sur sa PROPRE rangée pleine largeur sous le montant —
    plus jamais une cellule anonyme qui écrase le montant."""
    unite = f"&nbsp;{base}" if base else ""
    note_html = (f'\n      <div class="{prefixe}-inv-n">{note}</div>'
                 if note else "")
    return (
        f'<div class="{prefixe}-inv">\n'
        f'      <div class="{prefixe}-inv-r">'
        f'<div class="{prefixe}-inv-l">{titre}</div>'
        f'<div class="{prefixe}-inv-v">{montant}<span>&nbsp;MAD{unite}'
        f'</span></div></div>{ancre_html}{note_html}\n'
        f'    </div>')


def css_investissement(prefixe, couleurs, police, taille_pt, marge_px,
                       padding):
    """AMOT87 — la feuille du bloc investissement, UNE définition pour les
    deux couvertures. ``couleurs`` = (line, wash, muted, navy, ink)."""
    line, wash, muted, navy, ink = couleurs
    return (
        f".{prefixe}-inv{{margin-top:{marge_px}px;border:1px solid {line};"
        f"border-radius:12px;background:{wash};padding:{padding};}}"
        f".{prefixe}-inv-r{{display:table;width:100%;}}"
        f".{prefixe}-inv-l{{display:table-cell;vertical-align:middle;"
        f"font-size:8.5pt;color:{muted};padding-right:10px;}}"
        f".{prefixe}-inv-v{{display:table-cell;vertical-align:middle;"
        f"text-align:right;white-space:nowrap;font-family:{police};"
        f"font-size:{taille_pt}pt;color:{navy};}}"
        f".{prefixe}-inv-v span{{font-size:10pt;color:{muted};}}"
        f".{prefixe}-inv-n{{margin-top:4px;font-size:7.5pt;color:{ink};"
        f"line-height:1.35;}}")


def tuiles_taux(d, cle, kpi):
    """Tuiles « Autoconsommation » et « Couverture conso » (taux du moteur
    C&I lus sur ``synthese_ci``), ou [] — UNE définition pour les deux
    couvertures (CIQ333 : libellés dans la langue du document)."""
    tuiles = []
    # AMOT89 — la définition SERVIE de chaque taux (``synthese_ci.energie.
    # definitions``, IEA PVPS T1-28) en légende sous la tuile.
    from .synthese import chiffres_cles
    definitions = chiffres_cles(d.get(f"{cle}_synthese") or {})["definitions"]
    autoconso = d.get(f"{cle}_autoconso")
    if autoconso is not None:
        tuiles.append(kpi(f"{round(autoconso)}", "&nbsp;%", _avec_definition(
            d, libelle(d, "ci_autoconsommation", "Autoconsommation"),
            definitions.get("autoconso")), "autoconsommation_pct"))
    couverture = d.get(f"{cle}_couverture")
    if couverture is not None:
        tuiles.append(kpi(f"{round(couverture)}", "&nbsp;%", _avec_definition(
            d, libelle(d, "ci_part_conso_couverte",
                       "Part de votre consommation couverte"),
            definitions.get("couverture")), "couverture_pct"))
    return tuiles


def _avec_definition(d, libelle_tuile, definition):
    """AMOT89 — le libellé d'une tuile de taux suivi de la définition SERVIE
    (petite ligne, isolée en arabe) — sauf quand le libellé la dit déjà
    (« Part de votre consommation couverte » : la définition n'ajouterait
    qu'une redite)."""
    texte_def = html.escape(str(definition or "").strip(), quote=False)
    brut = re.sub(r"<[^>]+>", "", libelle_tuile).strip()
    if not texte_def or texte_def.casefold().startswith(brut.casefold()):
        return libelle_tuile
    if langue(d) == "ar":
        texte_def = f'<span class="i18n-rtl" dir="rtl">{texte_def}</span>'
    return (f'{libelle_tuile}<div style="font-size:6.2pt;margin-top:1px;'
            f'line-height:1.25;">{texte_def}</div>')


def ligne_surplus(d, cle, prefixe):
    """AMOT89 — « Surplus non valorisé : ≈ N kWh/an (M % de la production) »
    lu sur le bilan servi (``synthese_ci.energie.surplus``), dit selon la
    règle 82-21 (``constants_82_21``) : en basse tension, aucune revente
    ouverte ; en MT/HT avec revente, la part valorisée sous le plafond légal
    puis le reste. '' sans surplus servi ou sans surplus du tout."""
    from ..constants_82_21 import PLAFOND_INJECTION_PCT
    from .synthese import chiffres_cles, est_site_mt
    surplus = chiffres_cles(d.get(f"{cle}_synthese") or {})["surplus"]
    if not surplus or not surplus.get("kwh_an"):
        return ""
    from ..residential.theme import fmt
    reste = {"kwh": fmt(round(surplus["non_valorise_kwh_an"])),
             "pct": f"{surplus['non_valorise_pct_production']:g}"}
    if surplus.get("valorise_kwh_an"):
        phrase = libelle(
            d, "ci_surplus_injecte_kwh", "Surplus injecté : ≈ {kwh} kWh/an "
            "valorisés (plafond légal : {plafond} % de la production "
            "annuelle, loi 82-21 art. 12)",
            kwh=fmt(round(surplus["valorise_kwh_an"])),
            plafond=PLAFOND_INJECTION_PCT)
        if surplus["non_valorise_kwh_an"]:
            phrase += libelle(d, "ci_surplus_reste", " ; ≈ {kwh} kWh/an non "
                              "valorisés ({pct} % de la production).", **reste)
        else:
            phrase += "."
    else:
        phrase = libelle(d, "ci_surplus_non_valorise", "Surplus non valorisé "
                         ": ≈ {kwh} kWh/an ({pct} % de la production)",
                         **reste)
        phrase += (libelle(d, "ci_surplus_bt", " — revente non ouverte en "
                           "basse tension à ce jour (ANRE, décision 04/26).")
                   if not est_site_mt(d) else
                   libelle(d, "ci_surplus_sans_revente",
                           " — revente du surplus non retenue."))
    return f'<div class="{prefixe}-mtsrc">{phrase}</div>'


def tuiles_argent(d, cle, kpi, fmt):
    """Tuiles « Économies estimées / an (base) » et « Retour estimé », ou []
    (argent non servi ⇒ tuiles OMISES, jamais un « 0 », QJR119)."""
    if d.get(f"{cle}_masquer_economies"):
        return []
    tuiles = []
    economies = d.get(f"{cle}_economies")
    if economies is not None:
        base = d.get(f"{cle}_economie_base")
        if base in ("HT", "TTC"):
            base = libelle(d, f"ci_{base.lower()}", base)
        libelle_eco = (libelle(d, "ci_economies_estimees",
                               "Économies estimées / an")
                       + (f" ({base})" if base else ""))
        if postes_hors_total(d.get(f"{cle}_synthese")):
            # AMOT86 (D-ACI-2=a) — postes hors total : le retour n'est pas
            # imprimé, la légende dit sur quel prix il le sera.
            libelle_eco += (
                '<div style="font-size:6.3pt;margin-top:1px;">'
                + libelle(d, "ci_retour_prix_complet", "retour calculé sur "
                          "le prix complet, après la visite") + "</div>")
        tuiles.append(kpi(fmt(economies), "&nbsp;MAD", libelle_eco,
                          "economie_annuelle"))
    payback = d.get(f"{cle}_payback")
    if payback is not None:
        # AMOT80 — la tuile retour dit sa base (celle du flux servi).
        argent = (d.get(f"{cle}_synthese") or {}).get("argent") or {}
        base = libelle(d, "ci_ttc", "TTC") if argent.get("base") == "ttc" \
            else libelle(d, "ci_ht", "HT")
        tuiles.append(kpi(ans(payback),
                          libelle(d, "ci_unite_ans", "&nbsp;ans"),
                          libelle(d, "ci_retour_estime_base",
                                  "Retour estimé ({base})", base=base)
                          if argent else
                          libelle(d, "ci_retour_estime", "Retour estimé"),
                          "payback_ans"))
    elif motif_investissement(d, cle):
        # AMOT80 (D-ACI-8=a) — investissement non chiffré : le MOTIF à la
        # place du retour, jamais « 0 an » ni « 1 an ».
        tuiles.append(kpi(
            f'<span style="font-size:9pt;">'
            f'{motif_investissement(d, cle)}</span>', "",
            libelle(d, "ci_retour_estime", "Retour estimé")))
    return tuiles


# ── AMOT92 — la couverture est le PROJET du client ─────────────────────────

def format_telephone(brut):
    """« 212661234590 » / « 0661234590 » → « +212 6 61 23 45 90 » (numéro
    marocain, mise en forme seule) ; tout autre numéro reste tel quel."""
    texte = str(brut or "").strip()
    chiffres = re.sub(r"\D", "", texte)
    if chiffres.startswith("00212"):
        chiffres = chiffres[2:]
    if len(chiffres) == 10 and chiffres.startswith("0"):
        chiffres = "212" + chiffres[1:]
    if len(chiffres) != 12 or not chiffres.startswith("212"):
        return texte
    reste = chiffres[4:]
    return (f"+212 {chiffres[3]} "
            + " ".join(reste[i:i + 2] for i in range(0, 8, 2)))


def titre_projet(d, cle, kwc_txt, nom_client):
    """« Centrale solaire 90 kWc — Hôtel Atlas Riad SARL, Marrakech » : la
    raison sociale servie (``entreprise_client``), sinon le nom du client
    imprimé ; la ville du devis quand elle est connue."""
    entreprise = (d.get(f"{cle}_synthese") or {}).get("entreprise_client")
    raison = str((entreprise or {}).get("raison_sociale") or "").strip() \
        if isinstance(entreprise, dict) else ""
    ville = str(d.get("client_ville_libelle") or d.get("client_city")
                or "").strip()
    titre = libelle(d, "ci_titre_projet", "Centrale solaire {kwc} kWc — "
                    "{client}", kwc=kwc_txt, client=raison or nom_client)
    return titre + (f", {ville}" if ville else "")


def ligne_interlocuteur(d, prefixe):
    """« Votre interlocuteur : Yassine Cherkaoui · +212 6 12 34 56 78 » — le
    créateur du devis servi par le builder (``seller``, QG7) ; '' sans nom
    (jamais un nom inventé, jamais le seul numéro de la société)."""
    vendeur = d.get("seller") if isinstance(d.get("seller"), dict) else {}
    nom = str(vendeur.get("nom") or "").strip()
    if not nom:
        return ""
    contact = " · ".join(x for x in (
        nom, format_telephone(vendeur.get("telephone")),
        str(vendeur.get("email") or "").strip()) if x)
    return (f'<div class="{prefixe}-int" style="margin-top:1.5mm;'
            f'font-size:7.5pt;">'
            + libelle(d, "ci_votre_interlocuteur", "Votre interlocuteur")
            + f"&#160;: <b>{contact}</b></div>")


def qr_proposition(d):
    """``(data-uri, lien affiché)`` du QR vers la proposition en ligne quand
    le builder sert un vrai lien de partage (``links.signer`` contenant
    « /proposition/ », QX6), sinon ``("", "")`` — même règle que la
    couverture résidentielle (jamais un QR vers un 404)."""
    from ..residential import theme
    lien = str((d.get("links") or {}).get("signer") or "").strip()
    if "/proposition/" not in lien:
        return "", ""
    uri = theme.qr_data_uri(theme.normaliser_lien(lien), logo=False,
                            correction="M", box_size=10, border=4)
    return (uri, theme.lien_affiche(lien)) if uri else ("", "")


def rangee_bas(d, graphique, etapes, prefixe):
    """AMOT92 — la rangée basse de la couverture : l'énergie mois par mois à
    gauche (AMOT90), les prochaines étapes et le QR à droite ; sans
    graphique servi, les étapes seules. Toute la rangée est CÉDABLE
    (``data-graphique``) : le rendu adaptatif la retire en entier
    (``_sans_graphiques``) plutôt que de pousser une page de plus."""
    if d.get("_sans_graphiques"):
        return ""
    if not graphique:
        return (f'<div data-graphique="etapes" style="margin-top:10px;">'
                f'{etapes}</div>')
    return (f'<table class="{prefixe}-bas" data-graphique="etapes"><tr>'
            f'<td>{graphique}</td><td class="{prefixe}-bas-d">{etapes}</td>'
            f'</tr></table>')


#: AMOT92 — les prochaines étapes, sans date promise.
ETAPES_SUIVANTES = (
    ("ci_etape_suivante_visite", "Visite technique de votre site"),
    ("ci_etape_suivante_validation", "Validation de l'offre définitive"),
    ("ci_etape_suivante_pose", "Pose et mise en service"))


def bloc_etapes(d, prefixe, couleurs, en_ligne=False):
    """« Prochaines étapes » (visite technique, validation de l'offre
    définitive, pose et mise en service — sans date promise) et, quand un
    lien de partage existe, le QR de la proposition en ligne.
    ``couleurs`` = (navy, muted, gold) ; ``en_ligne`` : les étapes sur une
    ligne et le QR à droite (couverture industrielle, plus dense)."""
    navy, muted, gold = couleurs
    puces = [f'<span style="color:{gold};font-weight:700;">{i}</span>&#160;'
             f'{libelle(d, cle, fr)}'
             for i, (cle, fr) in enumerate(ETAPES_SUIVANTES, start=1)]
    corps = (" &#160;·&#160; ".join(puces) if en_ligne else "".join(
        f'<div style="margin-top:2px;">{p}</div>' for p in puces))
    uri, lien = qr_proposition(d)
    legende = (f'<div style="font-size:6.5pt;color:{muted};margin-top:2px;">'
               + libelle(d, "ci_proposition_en_ligne",
                         "Votre proposition en ligne")
               + f' · {html.escape(lien)}</div>') if uri else ""
    image = (f'<img src="{uri}" alt="QR" style="width:19mm;height:19mm;'
             f'display:block;">') if uri else ""
    titre = (f'<div style="font-size:8.5pt;font-weight:700;color:{navy};'
             f'margin-bottom:2px;">'
             + libelle(d, "ci_prochaines_etapes", "Prochaines étapes")
             + "</div>")
    if en_ligne:
        return (f'<table class="{prefixe}-etapes" style="width:100%;'
                f'border-collapse:collapse;font-size:7.5pt;"><tr>'
                f'<td style="vertical-align:middle;">{titre}{corps}{legende}'
                f'</td><td style="width:21mm;vertical-align:middle;">{image}'
                f'</td></tr></table>')
    return (f'<div class="{prefixe}-etapes" style="font-size:7.5pt;'
            f'line-height:1.35;">{titre}{corps}'
            + (f'<div style="margin-top:6px;">{image}{legende}</div>'
               if uri else "") + "</div>")
