"""Blocs HTML COMMUNS aux documents commercial (``c1c``/``c3c``) et
industriel (``i1``/``i4``), lus sur la charge utile du builder ou sur
``synthese_ci``.

Rendu SEUL : aucun calcul d'argent, aucun accès base, aucun statut touché
(règle #4). Les textes client arrivent DÉJÀ échappés une fois
(``builder.echapper_textes_client``, QJR30) : ces blocs ne les échappent pas
une seconde fois.
"""
from __future__ import annotations


def _txt(valeur):
    return str(valeur).strip() if valeur is not None else ""


# ── CIQ309 — bloc client entreprise ─────────────────────────────────────────

#: Champs d'identité légale imprimés, dans l'ordre (clé de
#: ``entreprise_client`` → libellé). Champ vide ⇒ OMIS, jamais un tiret.
CHAMPS_LEGAUX = (("ice", "ICE"), ("rc", "RC"), ("if_fiscal", "IF"))


def bloc_client(entreprise, prefixe, nom_affiche=""):
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
        morceaux.append(f"Raison sociale&#160;: {raison}")
    for cle, libelle in CHAMPS_LEGAUX:
        valeur = _txt(entreprise.get(cle))
        if valeur:
            morceaux.append(f"{libelle}&#160;: {valeur}")
    siege = _txt(entreprise.get("siege"))
    if siege:
        morceaux.append(f"Siège&#160;: {siege}")
    interlocuteur = _txt(entreprise.get("interlocuteur"))
    fonction = _txt(entreprise.get("fonction"))
    if interlocuteur:
        morceaux.append("À l'attention de " + interlocuteur
                        + (f", {fonction}" if fonction else ""))
    elif fonction:
        morceaux.append(f"À l'attention de la fonction&#160;: {fonction}")
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


def _montant(valeur):
    from ..montants import fmt_centimes
    return fmt_centimes(valeur)


def bloc_services(synthese, prefixe, couleur_titre, couleur_texte):
    """``<div>`` des services RÉELLEMENT portés par le devis
    (``synthese_ci['services']``) : la ligne O&M nommée et son prix (ou
    « prix à renseigner »), le délai d'intervention saisi. Rien d'autre :
    aucune « supervision », aucune « performance garantie » (D-CIQ-12).
    '' quand le devis ne porte aucun service."""
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
            prix = (f"{_montant(ht)} MAD HT" if ht and ht > 0
                    else "prix à renseigner")
            detail.append(f"{nom} — {prix}")
        statut = om.get("statut")
        suffixe = (" (proposé, non inclus dans le total)"
                   if statut == "propose" else "")
        lignes.append("Maintenance (O&amp;M)&#160;: " + " ; ".join(detail)
                      + suffixe)
    suivi = services.get("suivi_production")
    if isinstance(suivi, dict) and suivi.get("delai_intervention"):
        lignes.append("Suivi de production&#160;: intervention sous "
                      f"{suivi['delai_intervention']:g}&#160;h")
    if not lignes:
        return ""
    items = "".join(f'<div style="margin-top:2px;">{li}</div>'
                    for li in lignes)
    return (f'<div class="{prefixe}-svc" style="margin-top:12px;'
            f'font-size:8pt;color:{couleur_texte};line-height:1.4;">'
            f'<div style="font-size:9pt;font-weight:700;'
            f'color:{couleur_titre};">Services</div>{items}</div>')


# ── CIQ318 — bloc « Offre de financement » ──────────────────────────────────

TITRE_FINANCEMENT = "Offre de financement"


def bloc_financement(synthese, prefixe="ci", couleur_titre="#0F1E35",
                     couleur_texte="#1F2937"):
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
    suffixe = {"ht": " HT", "ttc": " TTC"}.get(base, "")
    libelle = _txt(offre.get("libelle_client")) or TITRE_FINANCEMENT
    lignes = [libelle]
    duree = offre.get("duree_mois")
    echeance = (f"Échéance mensuelle&#160;: {_montant(offre['echeance_mad'])}"
                f"&#160;MAD{suffixe}")
    if duree:
        echeance += f" sur {duree:g} mois"
    lignes.append(echeance)
    mensuelle = offre.get("economie_mensuelle_moyenne_mad")
    if mensuelle is not None:
        lignes.append("Économie mensuelle moyenne estimée&#160;: "
                      f"{_montant(mensuelle)}&#160;MAD{suffixe}")
    ecart = offre.get("ecart_mensuel_mad")
    if ecart is not None:
        lignes.append(f"Écart mensuel&#160;: {_montant(ecart)}&#160;MAD"
                      f"{suffixe}")
    source = _txt(offre.get("source"))
    if source:
        lignes.append(f"Source&#160;: {source}")
    items = "".join(f'<div style="margin-top:2px;">{li}</div>'
                    for li in lignes)
    return (f'<div class="{prefixe}-fin" style="margin-top:10px;'
            f'font-size:8pt;color:{couleur_texte};line-height:1.4;">'
            f'<div style="font-size:9pt;font-weight:700;'
            f'color:{couleur_titre};">{TITRE_FINANCEMENT}</div>{items}</div>')


# ── CIQ311 — bloc « Conditions » ────────────────────────────────────────────

TITRE_CGV_DEFAUT = "Conditions générales du devis"


def _doc_texts(d):
    textes = d.get("doc_texts")
    return textes if isinstance(textes, dict) else {}


def textes_bpa(d):
    """``(titre, mention)`` du « Bon pour accord » : les textes ÉDITABLES de
    la société (``doc_texts`` › ``bpa_titre`` / ``bpa_mention``), sinon les
    libellés par défaut du moteur — la même voie que le legacy."""
    from ..generate_devis_premium import DEFAULT_DOC_TEXTS
    textes = _doc_texts(d)
    titre = _txt(textes.get("bpa_titre")) or DEFAULT_DOC_TEXTS["bpa_titre"]
    mention = (_txt(textes.get("bpa_mention"))
               or DEFAULT_DOC_TEXTS["bpa_mention"])
    return titre, mention


def puces_conditions(d):
    """Les puces des conditions générales que le document IMPRIME.

    * ``cgv_ci`` (CIQ218) : la variante C&I du mode, GELÉE à l'envoi,
      marqueurs substitués par le builder ;
    * sinon ``cgv_bullets_remplies(data)`` (QJR668) : les puces société
      gelées à l'envoi (``doc_texts``), la fonction unique que la page
      publique appelle déjà. Jamais ``cpq`` (parqué)."""
    cgv_ci = d.get("cgv_ci")
    if isinstance(cgv_ci, list):
        puces = [_txt(p) for p in cgv_ci if _txt(p)]
        if puces:
            return puces
    from ..generate_devis_premium import cgv_bullets_remplies
    return [p for p in cgv_bullets_remplies(d) if _txt(p)]


def bloc_conditions(d, prefixe, couleur_titre, couleur_texte):
    """``<div>`` « Conditions » : puces CGV (gelées) et note de TVA
    multi-taux (``tva_note``, si les puces ne la portent pas déjà) — styles
    en ligne, compact, pour tenir dans la page EXISTANTE (D-QJR5-12)."""
    puces = puces_conditions(d)
    tva_note = _txt(d.get("tva_note"))
    if tva_note and not any(tva_note in p for p in puces):
        puces.append(tva_note)
    if not puces:
        return ""
    titre = _txt(_doc_texts(d).get("cgv_titre")) or TITRE_CGV_DEFAUT
    items = "".join(f'<li style="margin-top:1px;">{p}</li>' for p in puces)
    return (
        f'<div class="{prefixe}-cond" style="margin-top:10px;'
        f'font-size:6.8pt;color:{couleur_texte};line-height:1.35;">'
        f'<div style="font-size:8pt;font-weight:700;color:{couleur_titre};">'
        f'{titre}</div>'
        f'<ul style="margin:3px 0 0 0;padding-left:12px;">{items}</ul></div>')
