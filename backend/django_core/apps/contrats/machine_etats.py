"""CONTRAT12 — Machine d'états du cycle de vie d'un ``Contrat`` + transitions
gardées.

Le ``Contrat.statut`` suit un cycle de vie strict :

    brouillon ──▶ en_approbation ──▶ signe ──▶ actif ──▶ suspendu
        ▲              │                          │  ▲       │
        └──────────────┘                          │  └───────┘
                                                  ▼
                                            resilie / expire

Règles (gardes) :

- Seules les transitions listées dans ``TRANSITIONS_AUTORISEES`` sont permises ;
  toute autre lève ``TransitionInterdite``.
- ``brouillon → en_approbation`` (finalisation pour approbation) et
  ``en_approbation → signe`` exigent qu'un contrat ait **au moins deux parties**
  (``Contrat.valider_parties``) — on ne soumet/signe pas un contrat à une seule
  partie.
- Les états ``resilie`` et ``expire`` sont **terminaux** : aucune transition
  sortante.

Ce module ne dépend que des modèles de l'app `contrats` (foundation interne) et
n'effectue qu'une seule écriture (``Contrat.save`` du seul champ ``statut``).
"""
from django.core.exceptions import ValidationError


class TransitionInterdite(Exception):
    """Levée quand une transition de statut n'est pas autorisée."""


def _statuts():
    """Import paresseux du modèle pour éviter les imports circulaires."""
    from .models import Contrat

    return Contrat.Statut


def _transitions():
    """Graphe d'états : statut courant → ensemble des statuts cibles permis."""
    S = _statuts()
    return {
        S.BROUILLON: {S.EN_APPROBATION, S.RESILIE},
        S.EN_APPROBATION: {S.SIGNE, S.BROUILLON, S.RESILIE},
        S.SIGNE: {S.ACTIF, S.RESILIE},
        S.ACTIF: {S.SUSPENDU, S.RESILIE, S.EXPIRE},
        S.SUSPENDU: {S.ACTIF, S.RESILIE, S.EXPIRE},
        # États terminaux : aucune transition sortante.
        S.RESILIE: set(),
        S.EXPIRE: set(),
    }


# Exposé comme attribut de module via une propriété paresseuse : on ne peut pas
# évaluer les choices au chargement (l'app doit être prête), donc on fournit un
# proxy fonction. Pour un usage simple, appeler ``_transitions()``.
class _TransitionsProxy:
    """Proxy dict-like, résolu paresseusement au premier accès."""

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


# Transitions qui exigent au moins deux parties (finalisation / signature).
def _transitions_gardees_parties():
    S = _statuts()
    return {
        (S.BROUILLON, S.EN_APPROBATION),
        (S.EN_APPROBATION, S.SIGNE),
    }


def statuts_suivants(contrat):
    """Liste des statuts cibles autorisés depuis le statut courant du contrat."""
    return sorted(_transitions().get(contrat.statut, set()))


def transition_permise(statut_courant, statut_cible):
    """``True`` si ``statut_courant → statut_cible`` est dans le graphe."""
    return statut_cible in _transitions().get(statut_courant, set())


def changer_statut(contrat, statut_cible, *, persister=True):
    """Applique une transition de statut GARDÉE sur ``contrat``.

    - Refuse (``TransitionInterdite``) toute transition hors du graphe.
    - Pour les transitions de finalisation/signature, exige au moins deux
      parties (``Contrat.valider_parties``) — sinon ``TransitionInterdite``.
    - Une transition vers le même statut est un no-op (autorisé, sans écriture).
    - Si ``persister`` (défaut), sauvegarde le seul champ ``statut``.

    Renvoie le contrat (statut mis à jour).
    """
    statut_courant = contrat.statut
    if statut_cible == statut_courant:
        return contrat

    if not transition_permise(statut_courant, statut_cible):
        raise TransitionInterdite(
            f"Transition de statut interdite : "
            f"« {statut_courant} » → « {statut_cible} »."
        )

    if (statut_courant, statut_cible) in _transitions_gardees_parties():
        try:
            contrat.valider_parties()
        except ValidationError as exc:
            # Reformule en TransitionInterdite pour un point d'échec unique.
            message = exc.messages[0] if exc.messages else str(exc)
            raise TransitionInterdite(message)

    contrat.statut = statut_cible
    if persister:
        contrat.save(update_fields=["statut"])
    return contrat
