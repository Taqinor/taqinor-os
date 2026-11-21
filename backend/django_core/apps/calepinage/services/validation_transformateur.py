"""ACAL642 — la forme de la déclaration de transformateur (validation).

Extraite de ``services/electrique.py`` : ``electrique`` ré-importe
``valider_transformateur`` sous son ancien nom ``_valider_transformateur``.
"""
from .valeurs import nombre as _nombre


def valider_transformateur(saisie):
    """ACAL151 — la FORME du transformateur : ``{declare, 3 grandeurs}``.

    Chaque grandeur est ``{valeur, source, reference}`` : une valeur sans
    source n'est pas une saisie (D-CALX 7) et le refus NOMME le champ. La
    lecture de l'étape (``services/etapes/transformateur.py``) reste LA
    règle de calcul ; ici, on refuse seulement ce qu'elle ignorerait en
    silence.
    """
    from .electrique import EntreeInvalide, _fini
    from .etapes.transformateur import (
        CHAMP_A_VIDE, CHAMP_EN_CHARGE, CHAMP_NOMINAL, CLE_TRANSFORMATEUR,
    )

    if saisie is None:
        return
    if not isinstance(saisie, dict):
        raise EntreeInvalide(
            "« transformateur » doit être un objet {declare, %s, %s, %s} "
            "(reçu : %s)." % (CHAMP_A_VIDE, CHAMP_EN_CHARGE, CHAMP_NOMINAL,
                              type(saisie).__name__),
            champ=CLE_TRANSFORMATEUR)
    grandeurs = (CHAMP_A_VIDE, CHAMP_EN_CHARGE, CHAMP_NOMINAL)
    inconnues = sorted(set(saisie) - {'declare', *grandeurs})
    if inconnues:
        raise EntreeInvalide(
            "Champ du transformateur inconnu : « %s »." % inconnues[0],
            champ='%s.%s' % (CLE_TRANSFORMATEUR, inconnues[0]))
    if not isinstance(saisie.get('declare'), bool):
        raise EntreeInvalide(
            "Répondez à la question « transformateur » : declare vaut vrai "
            "(un transformateur est déclaré) ou faux (pas de transformateur).",
            champ='%s.declare' % CLE_TRANSFORMATEUR)
    for champ in grandeurs:
        brut = saisie.get(champ)
        if brut is None:
            continue
        chemin = '%s.%s' % (CLE_TRANSFORMATEUR, champ)
        if not isinstance(brut, dict):
            raise EntreeInvalide(
                "« %s » doit être un objet {valeur, source, reference}."
                % champ, champ=chemin)
        valeur = _nombre(brut.get('valeur'))
        if not _fini(valeur) or valeur < 0:
            raise EntreeInvalide(
                "« %s » : valeur illisible ou négative (« %s »)."
                % (champ, brut.get('valeur')), champ='%s.valeur' % chemin)
        if not str(brut.get('source') or '').strip():
            raise EntreeInvalide(
                "« %s » est saisi sans sa source : une valeur sans source "
                "n'est pas une saisie (fiche, plaque, procès-verbal…)."
                % champ, champ='%s.source' % chemin)
