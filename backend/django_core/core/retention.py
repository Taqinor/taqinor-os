"""YOPSB10 — Registre de rétention partagé + sweep unifié.

Généralise la rétention réinventée par app (FG26 audit, XRH24 candidats,
XKB32 conversations) : un registre EN MÉMOIRE, en fondation pure (aucune
importation d'app domaine), que chaque app peuple dans son ``apps.py
ready()`` avec sa PROPRE logique de purge.

Conception
----------

* ``register_retention_policy(name, sweep_callable)`` — enregistre une
  politique nommée. ``sweep_callable`` reçoit ``now`` (``datetime``) et
  ``apply_`` (bool) et renvoie un ``int`` (compte d'éléments
  supprimés/anonymisés). Chaque app appelle CETTE fonction dans son
  ``ready()`` avec SA propre fonction de purge (définie dans son
  ``services.py``, jamais importée par ``core``) — ``core`` ne connaît que
  le NOM et le CALLABLE, jamais la logique métier.
* ``run_all_policies(now=None, apply_=False)`` — exécute TOUTES les
  politiques enregistrées, journalise chaque exécution en
  ``core.RetentionRun`` (company=None — balayage système, transverse à
  toutes les sociétés ; chaque politique reste responsable de scoper ELLE-
  MÊME par société en interne). DRY-RUN par défaut (``apply_=False``) : les
  politiques reçoivent ``apply_=False`` et NE DOIVENT rien supprimer (c'est
  la responsabilité de CHAQUE politique de respecter ce contrat) ;
  ``core`` journalise le compte renvoyé quel que soit le mode.

``core`` reste fondation : ce module n'importe AUCUNE app domaine (contrat
import-linter ``core-foundation-is-a-base-layer``). Le registre vit en
mémoire du process (pas de persistance de la LISTE des politiques — seule
l'HISTORIQUE d'exécution est persisté via ``RetentionRun``).
"""
from __future__ import annotations

import logging

from django.utils import timezone

logger = logging.getLogger(__name__)

# Registre en mémoire : {name: sweep_callable}. Réinitialisé à chaque
# démarrage process — chaque app le repeuple dans son ``ready()``.
_REGISTRY: dict = {}


def register_retention_policy(name, sweep_callable):
    """Enregistre une politique de rétention nommée.

    ``sweep_callable(now, apply_)`` doit renvoyer un ``int`` (compte
    d'éléments traités). Ré-enregistrer le même ``name`` REMPLACE l'entrée
    (idempotent au rechargement de l'app registry — utile en test)."""
    _REGISTRY[name] = sweep_callable


def unregister_retention_policy(name):
    """Retire une politique (surtout utile en test pour isoler le registre)."""
    _REGISTRY.pop(name, None)


def list_retention_policies():
    """Noms des politiques actuellement enregistrées (triés)."""
    return sorted(_REGISTRY.keys())


def clear_registry():
    """Vide le registre (test uniquement — jamais appelé en usage normal)."""
    _REGISTRY.clear()


def run_all_policies(now=None, apply_=False):
    """Exécute TOUTES les politiques enregistrées et journalise chacune en
    ``core.RetentionRun``. DRY-RUN par défaut : ``apply_=False`` est transmis
    tel quel à chaque politique (c'est à ELLE de ne rien supprimer). Renvoie
    la liste des résultats ``[{name, count, statut, erreur}]``."""
    from .models import RetentionRun

    now = now or timezone.now()
    results = []
    for name in sorted(_REGISTRY.keys()):
        sweep = _REGISTRY[name]
        try:
            count = sweep(now, apply_)
            statut = RetentionRun.STATUT_OK
            erreur = ''
        except Exception as exc:  # noqa: BLE001 — une politique en échec
            # n'arrête jamais les autres ; journalisée en échec.
            logger.exception('run_retention: politique %r a échoué', name)
            count = 0
            statut = RetentionRun.STATUT_ECHEC
            erreur = str(exc)

        RetentionRun.objects.create(
            policy_name=name, dry_run=not apply_, count=count,
            statut=statut, erreur=erreur, executed_at=now,
        )
        results.append({
            'name': name, 'count': count, 'statut': statut, 'erreur': erreur,
        })
    return results
