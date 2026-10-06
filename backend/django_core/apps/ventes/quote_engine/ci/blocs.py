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
