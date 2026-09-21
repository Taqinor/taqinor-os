"""CONTRAT12 — Machine d'états du cycle de vie d'un ``Contrat`` + transitions
gardées.

Le ``Contrat.statut`` suit un cycle de vie strict :

    brouillon ──▶ en_approbation ──▶ signe ──▶ actif ──▶ suspendu
        ▲              │                          │  ▲       │
        └──────────────┘                          │  └───────┘
                                                  ▼
                                            resilie / expire

NTDOC4 ajoute une dérivation AVANT l'approbation : ``brouillon →
en_negociation → en_approbation`` (round de redlines avec la contrepartie).
Le chemin direct ``brouillon → en_approbation`` reste inchangé, et
``en_negociation → brouillon`` permet d'abandonner la négociation. Les deux
portes dédiées ``demarrer-negociation`` / ``cloturer-negociation`` portent les
gardes métier (une contrepartie non traitée / tous les commentaires résolus).

Règles (gardes) :

- Seules les transitions listées dans ``TRANSITIONS_AUTORISEES`` sont permises ;
  toute autre lève ``TransitionInterdite``.
- ``brouillon → en_approbation`` (finalisation pour approbation) et
  ``en_approbation → signe`` exigent qu'un contrat ait **au moins deux parties**
  (``Contrat.valider_parties``) — on ne soumet/signe pas un contrat à une seule
  partie.
- ``expire`` est le seul état **terminal** : aucune transition sortante.
- ``resilie`` porte UNE arête sortante, ``resilie → actif``, **réservée** à
  l'action ``annuler-resiliation`` (AUD511 : annuler une résiliation saisie par
  erreur, dans la fenêtre de préavis). La porte générique ``changer-statut``
  la refuse explicitement en 400 — ressusciter un contrat n'est pas un geste
  administratif.

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
        # NTDOC4 — « brouillon → en_negociation » ouvre le round de redlines
        # avec la contrepartie ; le chemin direct « brouillon → en_approbation »
        # (sans négociation) reste inchangé.
        S.BROUILLON: {S.EN_NEGOCIATION, S.EN_APPROBATION, S.RESILIE},
        # NTDOC4 — la clôture de négociation pousse vers l'approbation
        # (``cloturer-negociation``, qui EXIGE que tous les commentaires de
        # redline soient résolus) ; le retour en brouillon reste possible si la
        # négociation est abandonnée, et la résiliation garde sa porte dédiée.
        S.EN_NEGOCIATION: {S.EN_APPROBATION, S.BROUILLON, S.RESILIE},
        S.EN_APPROBATION: {S.SIGNE, S.BROUILLON, S.RESILIE},
        S.SIGNE: {S.ACTIF, S.RESILIE},
        S.ACTIF: {S.SUSPENDU, S.RESILIE, S.EXPIRE},
        S.SUSPENDU: {S.ACTIF, S.RESILIE, S.EXPIRE},
        # AUD511 — LA MARCHE ARRIÈRE DANS LA FENÊTRE DE PRÉAVIS. `Resiliation`
        # déclarait trois statuts, mais `annulee` et `effective` étaient des
        # ÉTATS MORTS : seul `resilier_contrat` créait une Resiliation (toujours
        # en `demande`), aucun service n'écrivait les deux autres, et `RESILIE`
        # était terminal — donc même une résiliation annulée n'aurait jamais
        # rendu son contrat ACTIF. Une résiliation faite par erreur était
        # IRRATTRAPABLE. Décision fondateur : câbler une vraie annulation
        # (besoin métier réel), pas retirer les états.
        #
        # Cette arête est RÉSERVÉE à l'action `annuler-resiliation` (fenêtre de
        # préavis + passage de la Resiliation à ANNULEE). La porte générique
        # `changer-statut` la refuse explicitement (même patron qu'AUD501) :
        # ressusciter un contrat n'est pas un geste administratif.
        S.RESILIE: {S.ACTIF},
        # État terminal : aucune transition sortante.
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
        # NTDOC4 — la clôture de négociation est une FINALISATION : elle porte
        # la même garde « au moins deux parties » que le passage direct en
        # approbation (on ne soumet pas un contrat à une seule partie).
        (S.EN_NEGOCIATION, S.EN_APPROBATION),
        (S.EN_APPROBATION, S.SIGNE),
    }


def _negociation_obligatoire(contrat):
    """NTDOC29 — la société impose-t-elle un round de négociation ?

    Lecture PURE via ``selectors.reglages_clm`` (import fonction-local : ce
    module ne dépend que de ``models`` au chargement). Un contrat sans société
    résoluble, ou toute erreur de lecture, laisse passer : une garde
    OPTIONNELLE ne doit jamais bloquer une transition légitime.
    """
    company = getattr(contrat, 'company', None)
    if company is None:
        return False
    try:
        from . import selectors

        return bool(
            selectors.reglages_clm(company)
            .negociation_obligatoire_avant_signature)
    except Exception:  # pragma: no cover - défensif (garde optionnelle)
        return False


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

    # NTDOC29 — réglage société « négociation obligatoire avant approbation ».
    # DÉSACTIVÉ PAR DÉFAUT : le raccourci brouillon → en_approbation reste
    # ouvert, comportement strictement inchangé. Activé, il force le passage
    # par un round de redlines. Lecture PURE (aucune ligne créée au passage).
    S = _statuts()
    if (statut_courant, statut_cible) == (S.BROUILLON, S.EN_APPROBATION):
        if _negociation_obligatoire(contrat):
            raise TransitionInterdite(
                'Votre société exige un round de négociation avant '
                "l'approbation : ouvrez d'abord la négociation (action "
                '« demarrer-negociation »).')

    contrat.statut = statut_cible
    if persister:
        contrat.save(update_fields=["statut"])
    return contrat


# ---------------------------------------------------------------------------
# XCTR17 — Machine d'états de l'``OrdreLocation`` (location SORTANTE)
# ---------------------------------------------------------------------------
#
#   reservee ──▶ enlevee ──▶ retournee ──▶ cloturee
#      │            │
#      └────────────┴──▶ annulee
#
# États terminaux : cloturee, annulee. Complètement INDÉPENDANTE de la
# machine d'états de ``Contrat`` ci-dessus (statut LOCAL à l'ordre de
# location, jamais confondue avec ``Contrat.statut`` ni STAGES.py — rule #2).


def _statuts_ordre_location():
    from .models import OrdreLocation

    return OrdreLocation.Statut


def _transitions_ordre_location():
    S = _statuts_ordre_location()
    return {
        S.RESERVEE: {S.ENLEVEE, S.ANNULEE},
        S.ENLEVEE: {S.RETOURNEE, S.ANNULEE},
        S.RETOURNEE: {S.CLOTUREE},
        S.CLOTUREE: set(),
        S.ANNULEE: set(),
    }


class _TransitionsOrdreLocationProxy:
    """Même patron paresseux que ``_TransitionsProxy`` ci-dessus."""

    def __getitem__(self, key):
        return _transitions_ordre_location()[key]

    def get(self, key, default=None):
        return _transitions_ordre_location().get(key, default)

    def __contains__(self, key):
        return key in _transitions_ordre_location()

    def __iter__(self):
        return iter(_transitions_ordre_location())

    def items(self):
        return _transitions_ordre_location().items()


TRANSITIONS_ORDRE_LOCATION_AUTORISEES = _TransitionsOrdreLocationProxy()


def transition_ordre_location_permise(statut_courant, statut_cible):
    """``True`` si ``statut_courant → statut_cible`` est permis pour un
    ``OrdreLocation`` (XCTR17)."""
    return statut_cible in _transitions_ordre_location().get(
        statut_courant, set())


def changer_statut_ordre_location(ordre, statut_cible, *, persister=True):
    """Applique une transition de statut GARDÉE sur un ``OrdreLocation``
    (XCTR17). Une transition vers le même statut est un no-op. Lève
    ``TransitionInterdite`` si la transition n'est pas dans le graphe."""
    statut_courant = ordre.statut
    if statut_cible == statut_courant:
        return ordre

    if not transition_ordre_location_permise(statut_courant, statut_cible):
        raise TransitionInterdite(
            f"Transition de statut interdite (ordre de location) : "
            f"« {statut_courant} » → « {statut_cible} »."
        )

    ordre.statut = statut_cible
    if persister:
        ordre.save(update_fields=["statut"])
    return ordre
