"""YDOCF1 — Machine d'états GARDÉE du cycle de vie d'un ``Ticket`` SAV, même
patron que ``apps/contrats/machine_etats.py``.

Le ``Ticket.statut`` suit un cycle de vie strict :

    nouveau ──▶ planifie ──▶ en_cours ──▶ resolu ──▶ cloture
       │            │            │           ▲
       └────────────┴────────────┴───────────┘   (réouverture — XSAV11)

Règles (gardes) :

- Seules les transitions listées dans ``TRANSITIONS_AUTORISEES`` sont permises ;
  toute autre lève ``TransitionInterdite``.
- Un saut direct NOUVEAU → CLOTURE (ou tout saut hors du graphe) est refusé —
  contrairement au PATCH libre d'avant YDOCF1.
- Une réouverture (RESOLU/CLOTURE → un statut ouvert) reste permise : c'est le
  chemin XSAV11 existant, comptabilisé par ``Ticket.reopen_count`` côté vue.
- ``cloture`` est un état sans transition sortante dans CE graphe (la
  réouverture est gérée explicitement, pas comme une transition « normale »).

Ce module ne dépend que du modèle ``Ticket`` de cette même app (foundation
interne, aucun import cross-app) et n'effectue qu'une seule écriture
(``Ticket.save`` du seul champ ``statut``) — la vue reste responsable du
chatter (``activity.log_changes``), du recalcul SLA et des notifications.
"""


class TransitionInterdite(Exception):
    """Levée quand une transition de statut de ticket n'est pas autorisée."""


def _statuts():
    """Import paresseux du modèle pour éviter les imports circulaires."""
    from .models import Ticket

    return Ticket.Statut


def _transitions():
    """Graphe d'états : statut courant → ensemble des statuts cibles permis.

    XSAV11 — la réouverture (resolu/cloture → un statut ouvert) est incluse
    ici comme transition permise ; c'est la vue qui distingue une
    « réouverture » (incrémente ``reopen_count``) d'une progression normale."""
    S = _statuts()
    return {
        S.NOUVEAU: {S.PLANIFIE, S.EN_COURS},
        S.PLANIFIE: {S.EN_COURS, S.NOUVEAU},
        S.EN_COURS: {S.RESOLU, S.PLANIFIE},
        S.RESOLU: {S.CLOTURE, S.EN_COURS, S.NOUVEAU, S.PLANIFIE},
        S.CLOTURE: {S.EN_COURS, S.NOUVEAU, S.PLANIFIE},
    }


class _TransitionsProxy:
    """Proxy dict-like, résolu paresseusement au premier accès (même patron
    que ``apps/contrats/machine_etats.py``)."""

    def __getitem__(self, key):
        return _transitions()[key]

    def get(self, key, default=None):
        return _transitions().get(key, default)

    def __contains__(self, key):
        return key in _transitions()

    def __iter__(self):
        return iter(_transitions())

    def items(self):
        return _transitions().items()


TRANSITIONS_AUTORISEES = _TransitionsProxy()


def statuts_suivants(ticket):
    """Liste des statuts cibles autorisés depuis le statut courant du ticket."""
    return sorted(_transitions().get(ticket.statut, set()))


def transition_permise(statut_courant, statut_cible):
    """``True`` si ``statut_courant → statut_cible`` est dans le graphe."""
    return statut_cible in _transitions().get(statut_courant, set())


def changer_statut(ticket, statut_cible, *, persister=True):
    """Applique une transition de statut GARDÉE sur ``ticket``.

    - Refuse (``TransitionInterdite``) toute transition hors du graphe.
    - Une transition vers le même statut est un no-op (autorisé, sans écriture).
    - Si ``persister`` (défaut), sauvegarde le seul champ ``statut``.

    Renvoie le ticket (statut mis à jour). N'écrit PAS le chatter/SLA/
    notifications — laissé à l'appelant (la vue), comme pour ``Contrat``."""
    statut_courant = ticket.statut
    if statut_cible == statut_courant:
        return ticket

    if not transition_permise(statut_courant, statut_cible):
        raise TransitionInterdite(
            f"Transition de statut interdite : "
            f"« {statut_courant} » → « {statut_cible} ». "
            f"Statuts permis : {', '.join(statuts_suivants(ticket)) or 'aucun'}."
        )

    ticket.statut = statut_cible
    if persister:
        ticket.save(update_fields=["statut"])
    return ticket
