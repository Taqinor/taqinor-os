"""Sélecteurs (lectures) de l'app CPQ.

Fonctions de lecture pures, scopées société. Aucun import des modèles des
autres apps domaine (string-FK uniquement)."""
from decimal import Decimal

from core.rules import evaluate_condition_group
from .models import ContrainteCompatibilite, RegleProduitCPQ, SeuilMargeFamille


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


def evaluer_regles_produit(*, company, context):
    """NTCPQ2 — Évalue les règles produit actives de la société contre un
    ``context`` (dict plat construit par l'appelant depuis les lignes/champs du
    devis) via ``core.rules.evaluate_condition_group``.

    Renvoie la liste des règles déclenchées :
    ``[{regle_id, nom, actions}, ...]``."""
    if not isinstance(context, dict):
        context = {}
    declenchees = []
    for regle in RegleProduitCPQ.objects.filter(company=company, actif=True):
        if evaluate_condition_group(regle.condition_group, context):
            declenchees.append({
                'regle_id': regle.id,
                'nom': regle.nom,
                'actions': regle.actions,
            })
    return declenchees


def devis_marge_sous_seuil(devis):
    """NTCPQ6 — INTERNE : une ligne du devis est-elle sous le seuil de marge
    minimale de sa famille (catégorie) ?

    Marge ligne = ``(prix_unitaire - produit.prix_achat) / prix_unitaire`` en %.
    Comparée à ``SeuilMargeFamille.marge_min_pct`` de la catégorie du produit.
    Renvoie ``True`` dès qu'une ligne passe sous son seuil. Aucun seuil
    configuré ⇒ ``False``. JAMAIS exposé côté client (règle #4)."""
    company_id = getattr(devis, 'company_id', None)
    if company_id is None:
        return False
    seuils = {
        s.categorie_id: s.marge_min_pct
        for s in SeuilMargeFamille.objects.filter(company_id=company_id)}
    if not seuils:
        return False
    for ligne in devis.lignes.all():
        produit = ligne.produit
        if produit is None or ligne.prix_unitaire is None:
            continue
        seuil = seuils.get(produit.categorie_id)
        if seuil is None:
            continue
        pv = Decimal(str(ligne.prix_unitaire))
        if pv <= 0:
            continue
        pa = Decimal(str(produit.prix_achat or 0))
        marge_pct = (pv - pa) / pv * Decimal('100')
        if marge_pct < Decimal(str(seuil)):
            return True
    return False
