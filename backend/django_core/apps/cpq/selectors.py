"""Sélecteurs (lectures) de l'app CPQ.

Fonctions de lecture pures, scopées société. Aucun import des modèles des
autres apps domaine (string-FK uniquement)."""
from .models import ContrainteCompatibilite


def violations_compatibilite(*, company, produit_ids):
    """NTCPQ1 — Évalue les contraintes de compatibilité pour une sélection.

    ``produit_ids`` : itérable d'IDs de ``stock.Produit`` sélectionnés. Renvoie
    une liste de dicts ``{type, produit_a, produit_b, message, bloquante}`` pour
    chaque contrainte de la société qui est violée par la sélection :

      * ``INCOMPATIBLE`` : les deux produits sont présents → violation bloquante.
      * ``REQUIERT`` : ``produit_a`` présent sans ``produit_b`` → bloquante.
      * ``RECOMMANDE`` : ``produit_a`` présent sans ``produit_b`` → avertissement.
    """
    ids = {int(p) for p in produit_ids if p is not None}
    if not ids:
        return []
    qs = ContrainteCompatibilite.objects.filter(
        company=company, produit_a__in=ids)
    violations = []
    for c in qs:
        a_present = c.produit_a_id in ids
        b_present = c.produit_b_id in ids
        if not a_present:
            continue
        if c.type == ContrainteCompatibilite.TypeContrainte.INCOMPATIBLE:
            if b_present:
                violations.append(_violation(c))
        else:  # REQUIERT / RECOMMANDE : a présent, b manquant → déclenche.
            if not b_present:
                violations.append(_violation(c))
    return violations


def _violation(contrainte):
    return {
        'type': contrainte.type,
        'produit_a': contrainte.produit_a_id,
        'produit_b': contrainte.produit_b_id,
        'message': contrainte.message_utilisateur,
        'bloquante': contrainte.bloquante,
    }
