"""N58 — défauts canoniques (clé → libellé, ordre) des statuts métier.

Source de vérité UNIQUE : on lit l'ordre d'entonnoir et les libellés
directement sur les modèles ``installations.Installation`` / ``sav.Ticket`` /
``ventes.BonCommande`` — jamais une copie codée en dur ici. Ainsi, si un
statut canonique change à la source, le défaut suit automatiquement.

Ces défauts servent à :
  * fusionner avec les surcharges ``StatutConfig`` enregistrées (GET effectif) ;
  * borner les clés qu'on accepte en écriture (on ne configure QUE des statuts
    qui existent réellement).

L'entonnoir du lead (``STAGES.py``) n'est volontairement PAS exposé ici.
"""

CHANTIER = 'chantier'
SAV = 'sav'
BON_COMMANDE = 'bon_commande'

VALID_DOMAINES = (CHANTIER, SAV, BON_COMMANDE)


def _ordered_defaults(choices, order):
    """Construit [(cle, libelle, ordre)] dans l'ordre d'entonnoir donné.

    `choices` : liste (value, label) du TextChoices source.
    `order`    : liste des clés dans l'ordre d'entonnoir canonique.
    """
    labels = dict(choices)
    out = []
    for i, key in enumerate(order):
        key = str(key)
        out.append((key, labels.get(key, key), i))
    return out


def default_statuses(domaine):
    """Retourne la liste [(cle, libelle, ordre)] canonique d'un domaine.

    Lue à la volée depuis le modèle source — d'où la robustesse à un changement
    de la machine à états. Lève KeyError pour un domaine inconnu.
    """
    if domaine == CHANTIER:
        from apps.installations.models import Installation
        return _ordered_defaults(
            Installation.Statut.choices, Installation.STATUT_ORDER)
    if domaine == SAV:
        from apps.sav.models import Ticket
        return _ordered_defaults(Ticket.Statut.choices, Ticket.STATUT_ORDER)
    if domaine == BON_COMMANDE:
        from apps.ventes.models import BonCommande
        # BonCommande n'a pas de STATUT_ORDER : l'ordre de déclaration du
        # TextChoices EST l'ordre d'entonnoir (en_attente → confirmé → livré),
        # « annulé » restant en fin (drapeau, comme ailleurs).
        order = [value for value, _ in BonCommande.Statut.choices]
        return _ordered_defaults(BonCommande.Statut.choices, order)
    raise KeyError(domaine)


def default_keys(domaine):
    """Ensemble des clés canoniques valides d'un domaine (pour validation)."""
    return {cle for cle, _, _ in default_statuses(domaine)}
