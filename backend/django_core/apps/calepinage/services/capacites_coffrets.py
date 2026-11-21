"""ACAL618 — la capacité d'entrées des coffrets DC, lue sur la fiche produit.

Extraite de ``services/electrique.py`` (fichier de plus de 4 000 lignes) pour
qu'il ne grossisse pas ; ses lecteurs (``bordereau_calepinage``) l'importent
ICI, sans ré-export par ``electrique``.
"""
from .valeurs import nombre as _nombre

#: Les clés de fiche (CALX60) sous lesquelles une capacité d'entrées de
#: coffret DC serait publiée. Liste FERMÉE : aucune fiche « coffret » n'existe
#: aujourd'hui au catalogue, donc ce chemin rend ``None`` et
#: ``coffrets_dc`` retombe sur la capacité SAISIE — ou refuse en nommant le
#: coffret. Rien n'est supposé à la place (D-CALX 7).
CLES_CAPACITE_COFFRET = ('capacite_entrees', 'entrees')


def capacites_des_coffrets(company, equipements):
    """``({id coffret: capacité}, alertes)`` — capacités lues sur LA FICHE.

    Un ``produitId`` qui ne désigne aucun produit du catalogue de la société
    est NOMMÉ (règle fondateur « erreur → champ fautif ») et la capacité reste
    absente : ``coffrets_dc`` retombera alors sur la capacité saisie, ou
    refusera le coffret en le nommant.
    """
    from apps.stock.selectors import specs_for_produit

    from .coffrets import TYPE_COFFRET_DC
    from .electrique import _produit_borne

    capacites, alertes = {}, []
    for equipement in equipements:
        if equipement.get('type') != TYPE_COFFRET_DC:
            continue
        identifiant = equipement.get('produitId')
        if identifiant in (None, ''):
            continue
        produit = _produit_borne(company, identifiant)
        if produit is None:
            alertes.append(
                "coffret DC « %s » : le produit « %s » désigné par "
                "« equipements[].produitId » est introuvable dans le "
                "catalogue de la société — capacité d'entrées NON lue sur "
                "une fiche."
                % (equipement.get('label') or equipement.get('id') or '?',
                   identifiant))
            continue
        specs = specs_for_produit(produit) or {}
        for cle in CLES_CAPACITE_COFFRET:
            valeur = _nombre(specs.get(cle))
            if valeur is not None:
                capacites[equipement.get('id')] = int(valeur)
                break
    return (capacites, alertes)
