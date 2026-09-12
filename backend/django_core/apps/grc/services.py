"""Services d'écriture/orchestration du module GRC & Conformité (NTGRC).

Point d'entrée UNIQUE pour les autres apps : une app métier qui doit tracer
une destruction/anonymisation appelle ``journaliser_destruction`` (import
FONCTION-LOCAL depuis son propre ``services``/``dsr_provider``) — jamais un
import des modèles de ``grc``.
"""
from __future__ import annotations

import hashlib
import logging

logger = logging.getLogger(__name__)


def empreinte_avant(valeurs):
    """SHA-256 hexadécimal d'un instantané AVANT destruction (ou '').

    ``valeurs`` est un dict (ou toute valeur ``repr``-able) des champs
    personnels sur le point d'être effacés. On ne stocke JAMAIS la valeur
    elle-même — seulement son empreinte, qui permet de prouver a posteriori
    « c'est bien cette donnée-là qui a été détruite » sans la conserver.
    """
    if not valeurs:
        return ''
    if isinstance(valeurs, dict):
        canon = '|'.join(
            f'{cle}={valeurs[cle]}' for cle in sorted(valeurs) if valeurs[cle])
    else:
        canon = str(valeurs)
    if not canon:
        return ''
    return hashlib.sha256(canon.encode('utf-8')).hexdigest()


def journaliser_destruction(company, *, type_objet, objet_ref, action,
                            politique_ref='', demande_droit_ref='',
                            executee_par='', motif='', empreinte=''):
    """Écrit UNE ligne immuable au journal de destruction (NTGRC5).

    Appelée par les fournisseurs DSR (NTGRC1) et par les politiques de
    rétention (NTGRC4) à CHAQUE purge/anonymisation réelle. Best-effort
    absolu : une erreur de journalisation ne doit JAMAIS faire échouer
    l'effacement légal lui-même (la demande resterait bloquée). Renvoie la
    ligne créée, ou ``None`` si la journalisation n'a pas pu avoir lieu.

    Aucune donnée personnelle n'est écrite : seuls un type d'objet, un
    identifiant technique, un motif et une EMPREINTE (SHA-256) sont tracés.
    """
    if company is None:
        return None
    try:
        from .models import JournalDestruction
    except ImportError:  # pragma: no cover - le modèle arrive avec NTGRC5
        return None
    try:
        return JournalDestruction.objects.create(
            company=company,
            type_objet=(type_objet or '')[:60],
            objet_ref=str(objet_ref or '')[:64],
            action=action,
            politique_ref=str(politique_ref or '')[:64],
            demande_droit_ref=str(demande_droit_ref or '')[:64],
            executee_par=(executee_par or '')[:150],
            motif=motif or '',
            empreinte_avant=(empreinte or '')[:64],
        )
    except Exception:  # noqa: BLE001 - jamais bloquant pour l'effacement
        logger.exception(
            'grc: journalisation de destruction impossible (%s/%s)',
            type_objet, objet_ref)
        return None
