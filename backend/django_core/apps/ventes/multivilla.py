"""QJ29 / ERR-QAC-MULTIVILLA-TOTAL-XN — aides PURES du devis « ×N villas
identiques » (aucun import de l'app : ``models.py`` les appelle sans tirer
``selectors`` et ses dépendances inter-apps — contrat import-linter M1).
``selectors`` les ré-exporte."""


def nombre_proprietes(devis) -> int:
    """QJ29 (A) — multiplicateur ×N villas identiques stocké dans
    ``etude_params['nombre_proprietes']`` (défaut 1, jamais < 1). N=1 = chemin
    mono-système inchangé."""
    try:
        n = int((devis.etude_params or {}).get('nombre_proprietes', 1) or 1)
    except (TypeError, ValueError, AttributeError):
        n = 1
    return max(1, n)


def puissance_kwc_projet(devis):
    """ERR-QAC-MULTIVILLA-TOTAL-XN — le kWc du PROJET entier.

    ``etude_params['puissance_kwc']`` reste le cache de
    ``domain.scenario.puissance_kwc_du_devis`` : il est DÉRIVÉ DES LIGNES, qui
    décrivent UNE villa, et le moteur en tire la production d'une villa (qu'il
    multiplie ensuite par N lui-même — le multiplier dans la clé doublerait
    l'échelle). La puissance du projet, celle qui s'apparie au total ×N
    (``prix_par_kwc`` = TTC(×N) ÷ kWc total), est donc kWc × N, lue ICI.
    ``None`` quand aucun kWc lisible (pompage, devis sans étude).
    """
    from decimal import Decimal, InvalidOperation
    etude = devis.etude_params if isinstance(devis.etude_params, dict) else {}
    kwc = etude.get('puissance_kwc')
    try:
        kwc_val = Decimal(str(kwc)) if kwc else Decimal('0')
    except (InvalidOperation, TypeError, ValueError):
        kwc_val = Decimal('0')
    if kwc_val <= 0:
        return None
    return kwc_val * nombre_proprietes(devis)
