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
