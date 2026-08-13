"""Sélecteurs (lectures) de l'app CPQ.

Fonctions de lecture pures, scopées société. Aucun import des modèles des
autres apps domaine (string-FK uniquement)."""
from decimal import Decimal

from core.rules import evaluate_condition_group
from .models import (
    ContrainteCompatibilite, RegleProduitCPQ, SeuilMargeFamille,
    EtapeApprobationDevis, ClauseCGV,
)


def contexte_session_configurateur(session):
    """NTCPQ9 — Contexte plat {champ: valeur} construit depuis les réponses
    d'une session de configurateur (pour l'évaluation des règles NTCPQ2)."""
    context = {}
    for rep in session.reponses.select_related('question').all():
        context[rep.question.champ] = rep.valeur
    return context


def resoudre_configurateur(session):
    """NTCPQ9 — Résout les produits/bundles d'une session via les règles
    produit NTCPQ2. Renvoie ``{context, actions_declenchees}``."""
    context = contexte_session_configurateur(session)
    actions = evaluer_regles_produit(
        company=session.company, context=context)
    return {'context': context, 'actions_declenchees': actions}


def premiere_etape_en_attente(devis):
    """NTCPQ7 — Première étape d'approbation de remise encore ``en_attente``
    pour un devis (ordre ``niveau``), ou ``None`` si aucune. Sert au blocage
    de l'envoi/PDF tant qu'une approbation est requise."""
    return EtapeApprobationDevis.objects.filter(
        devis_id=devis.id,
        statut=EtapeApprobationDevis.Statut.EN_ATTENTE,
    ).order_by('niveau', 'id').first()


def etapes_approbation_devis(devis):
    """NTCPQ8 — Étapes d'approbation de remise d'un devis, en dicts JSON-safe
    (pour l'écran « Approbation » du devis)."""
    etapes = EtapeApprobationDevis.objects.filter(
        devis_id=devis.id).select_related('approbateur').order_by(
            'niveau', 'id')
    return [{
        'id': e.id,
        'niveau': e.niveau,
        'niveau_approbation': e.niveau_approbation,
        'statut': e.statut,
        'approbateur': (
            getattr(e.approbateur, 'username', None) if e.approbateur_id
            else None),
        'decision_le': e.decision_le.isoformat() if e.decision_le else None,
        'commentaire': e.commentaire,
    } for e in etapes]


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


def clause_sapplique(clause, context):
    """NTCPQ11 — Une clause s'applique-t-elle à ce contexte de devis ?

    Deux filtres cumulés : ``type_deal`` (référentiel libre, vide = tous types,
    comparaison insensible à la casse/aux espaces) puis ``applicable_si``
    (arbre ET/OU/NON évalué par ``core.rules`` ; vide = toujours vrai)."""
    if not isinstance(context, dict):
        context = {}
    attendu = (clause.type_deal or '').strip().lower()
    if attendu:
        recu = str(context.get('type_deal') or '').strip().lower()
        if recu != attendu:
            return False
    arbre = clause.applicable_si
    if not arbre:
        return True
    return evaluate_condition_group(arbre, context)


_OPERATEURS_LISIBLES = {
    'eq': '=', 'ne': '≠', 'gt': '>', 'gte': '≥', 'lt': '<', 'lte': '≤',
    'in': 'parmi', 'not_in': 'hors de', 'contains': 'contient',
    'startswith': 'commence par', 'exists': 'est renseigné',
}
_GROUPES_LISIBLES = {'and': ' ET ', 'or': ' OU '}


def condition_en_clair(noeud):
    """NTCPQ12 — Traduit un arbre ``core.rules`` en français lisible.

    Ex. ``{'op': 'and', 'conditions': [{'field': 'type_deal', ...}, ...]}``
    → ``"type_deal=Industriel ET montant>500000"``. Arbre vide → « toujours »
    (une clause sans condition s'applique systématiquement). Purement
    descriptif : n'évalue rien, ne lève jamais."""
    if not noeud:
        return 'toujours'
    if not isinstance(noeud, dict):
        return str(noeud)
    op = noeud.get('op')
    if 'conditions' in noeud or op in ('and', 'or', 'not'):
        enfants = noeud.get('conditions') or []
        rendus = [condition_en_clair(e) for e in enfants if e]
        if not rendus:
            return 'toujours'
        if op == 'not':
            return f'NON ({rendus[0]})'
        joint = _GROUPES_LISIBLES.get(op or 'and', ' ET ')
        if len(rendus) == 1:
            return rendus[0]
        return joint.join(f'({r})' if ' ET ' in r or ' OU ' in r else r
                          for r in rendus)
    champ = noeud.get('field', '?')
    operateur = noeud.get('operator', 'eq')
    valeur = noeud.get('value')
    lisible = _OPERATEURS_LISIBLES.get(operateur, operateur)
    if operateur == 'exists':
        return f'{champ} {lisible}'
    if isinstance(valeur, (list, tuple)):
        valeur = ', '.join(str(v) for v in valeur)
    if lisible in ('=', '≠', '>', '≥', '<', '≤'):
        return f'{champ}{lisible}{valeur}'
    return f'{champ} {lisible} {valeur}'


def clauses_applicables(*, company, context):
    """NTCPQ11 — Clauses/CGV actives de la société qui s'appliquent au contexte.

    Renvoie une liste JSON-safe (ordonnée par ``ordre`` puis ``id``) :
    ``[{clause_id, nom, corps_texte, type_deal, ordre}, ...]``. C'est cette
    liste qui est FIGÉE sur ``Devis.clauses_appliquees`` à l'envoi."""
    clauses = ClauseCGV.objects.filter(
        company=company, actif=True).order_by('ordre', 'id')
    return [{
        'clause_id': c.id,
        'nom': c.nom,
        'corps_texte': c.corps_texte,
        'type_deal': c.type_deal,
        'ordre': c.ordre,
    } for c in clauses if clause_sapplique(c, context)]
