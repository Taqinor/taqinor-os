"""Services d'écriture/orchestration du module GRC & Conformité (NTGRC).

Point d'entrée UNIQUE pour les autres apps : une app métier qui doit tracer
une destruction/anonymisation appelle ``journaliser_destruction`` (import
FONCTION-LOCAL depuis son propre ``services``/``dsr_provider``) — jamais un
import des modèles de ``grc``.
"""
from __future__ import annotations

import hashlib
import logging
import secrets

from django.utils import timezone

logger = logging.getLogger(__name__)

#: NTGRC2/NTGRC3 — délai légal de réponse à une demande de droit (loi 09-08).
DELAI_LEGAL_JOURS = 30


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
    from .models import JournalDestruction
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


# ── NTGRC2 — portail public de dépôt / suivi d'une demande de droit ─────────

def _nouveau_token_suivi():
    """Jeton de suivi OPAQUE (32 octets d'entropie, URL-safe).

    Distinct de l'identifiant réel : le déposant suit sa demande sans qu'aucun
    identifiant interne ne fuite et sans énumération possible.
    """
    return secrets.token_urlsafe(32)[:64]


def creer_demande_publique(slug_societe, identifiant, type_demande, *,
                           ip='', user_agent=''):
    """Crée une ``core.DataSubjectRequest`` déposée PUBLIQUEMENT.

    Renvoie ``(demande, None)`` en cas de succès, ``(None, {champ: message})``
    sinon — le message NOMME toujours le champ fautif, en français.

    La preuve (horodatage SERVEUR, IP, user-agent) est posée côté serveur et
    JAMAIS lue du corps de la requête. La société est résolue par son slug :
    la demande naît donc déjà bornée à un tenant.
    """
    from authentication.models import Company
    from core.models import DataSubjectRequest

    company = Company.objects.filter(slug=slug_societe).first()
    if company is None:
        return None, {'societe': 'Société inconnue.'}

    valides = {c for c, _ in DataSubjectRequest.KIND_CHOICES}
    if type_demande not in valides:
        return None, {
            'type': 'Type de demande invalide : choisissez « accès », '
                    '« rectification » ou « effacement ».'}

    maintenant = timezone.now()
    demande = DataSubjectRequest(
        company=company,
        subject_identifier=identifiant[:255],
        kind=type_demande,
        statut=DataSubjectRequest.STATUT_RECUE,
        token_suivi=_nouveau_token_suivi(),
        preuve={
            'depose_le': maintenant.isoformat(),
            'ip': ip or '',
            'user_agent': user_agent or '',
            'canal': 'portail_public',
        },
    )
    demande.save()
    return demande, None


def suivi_demande_publique(token):
    """État public d'une demande, résolu par son jeton OPAQUE.

    Renvoie un dict SANS aucune donnée personnelle d'autrui ni identifiant
    interne, ou ``None`` si le jeton ne correspond à rien.
    """
    from core.models import DataSubjectRequest

    if not token:
        return None
    demande = DataSubjectRequest.objects.filter(token_suivi=token).first()
    if demande is None:
        return None

    echeance = getattr(demande, 'date_echeance', None)
    if echeance is None:
        echeance = demande.created_at + timezone.timedelta(
            days=DELAI_LEGAL_JOURS)
    return {
        'statut': demande.statut,
        'type': demande.kind,
        'depose_le': demande.created_at.isoformat(),
        'echeance_legale': echeance.isoformat(),
        'delai_legal_jours': DELAI_LEGAL_JOURS,
        'traitee_le': (demande.traitee_le.isoformat()
                       if demande.traitee_le else None),
    }
