"""Copilote vague 2 (BRF) — blocs ajoutés au point du matin et au dossier d'un lead.

Chaque bloc vient d'UN sélecteur public de l'app propriétaire (visites,
calepinage, installations, ventes, sav) : ce module ne lit jamais leurs modèles.
Un sélecteur rend ``None`` quand le compte n'a pas la lecture du module : la clé
est alors ABSENTE de la réponse (jamais vide, jamais une erreur). L'interrupteur
du copilote reste décidé par l'appelant (``copilote_allume_pour``).

Formes servies : ``contract_samples/assistant_digest_matin.json`` (``vague2``)
et ``contract_samples/assistant_lead_resume.json`` (``vague2``).
"""
import json

#: Taille maximale (caractères) du point du matin servi au copilote : le modèle
#: n'en voit pas davantage.
LIMITE_CARACTERES = 5000


def _bloc_calepinages(user, aujourdhui, voit_les_leads):
    from apps.calepinage.selectors import brief_calepinage

    return brief_calepinage(user, aujourdhui)


def blocs_du_matin(user, aujourdhui, voit_les_leads):
    """Les blocs de la vague 2 du point du matin de ``user`` :
    ``{clé: bloc}`` sans les clés dont le sélecteur rend ``None``.
    ``voit_les_leads`` : le compte lit le CRM (ligne « visite validée sans
    calepinage », qui parle de leads)."""
    from apps.installations.selectors_assistant import brief_chantiers
    from apps.sav.selectors_assistant import brief_sav
    from apps.ventes.selectors_assistant import brief_ventes
    from apps.visites.selectors import brief_visites

    blocs = {
        'visites_equipe': brief_visites(user, aujourdhui),
        'calepinages': _bloc_calepinages(user, aujourdhui, voit_les_leads),
        'chantiers': brief_chantiers(user, aujourdhui),
        'impayes': brief_ventes(user, aujourdhui),
        'tickets': brief_sav(user, aujourdhui),
    }
    return {cle: bloc for cle, bloc in blocs.items() if bloc is not None}


def _listes_lignes(noeud):
    """Toutes les listes servies sous une clé ``lignes`` dans ``noeud``."""
    trouvees = []
    if isinstance(noeud, dict):
        for cle, valeur in noeud.items():
            if cle == 'lignes' and isinstance(valeur, list):
                trouvees.append(valeur)
            trouvees.extend(_listes_lignes(valeur))
    return trouvees


def _taille(reponse):
    return len(json.dumps(reponse, ensure_ascii=False, default=str))


def borner_taille(reponse, limite=LIMITE_CARACTERES):
    """Ramène ``reponse`` à ``limite`` caractères en retirant des LIGNES (la
    dernière de la liste la plus lourde, tant qu'il le faut) ; les compteurs
    (``total``, ``ouverts``, …) ne sont jamais touchés. Rend ``reponse``."""
    while _taille(reponse) > limite:
        listes = [liste for liste in _listes_lignes(reponse) if liste]
        if not listes:
            break
        max(listes, key=_taille).pop()
    return reponse
