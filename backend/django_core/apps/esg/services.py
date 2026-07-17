"""Services d'écriture / orchestration de l'app ESG (Groupe NTESG).

``figer_periode`` (NTESG1) est la seule opération qui MUTE une
``PeriodeReportingESG`` : elle calcule ``selectors.agreger_indicateurs_
periode`` une fois et gèle le résultat dans ``SnapshotESG`` — même logique de
verrouillage que ``compta.services.cloturer_periode``. Refuse (lève
``ValidationError``) si la période n'est plus en ``brouillon`` : le figeage
n'est PAS ré-exécutable (contrairement à une simple clôture idempotente) —
une période déjà figée/publiée ne recalcule jamais ses chiffres.

``alerter_derive_trajectoire`` (NTESG10) est appelée UNE SEULE FOIS, à la fin
de ``figer_periode`` — puisque ``figer_periode`` lui-même refuse toute
ré-exécution sur une période déjà figée, l'alerte hérite naturellement de
cette garantie « une seule fois par période » sans champ de déduplication
supplémentaire.
"""
import logging

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

# NTESG10 — seuil par défaut (% d'écart défavorable) déclenchant l'alerte de
# dérive trajectoire. « Configurable par société » (spec NTESG10) attend le
# réglage dédié ``ParametresESG.seuil_alerte_derive_pct`` (NTESG20, hors
# périmètre de ce lane — Files listées ne portent pas models.py) : ce
# module expose donc un défaut fixe, substituable par un futur appelant via
# le paramètre ``seuil_pct`` de ``alerter_derive_trajectoire`` sans changer
# sa signature.
SEUIL_ALERTE_DERIVE_PCT_DEFAUT = 10


@transaction.atomic
def figer_periode(periode, *, user=None):
    """Fige une ``PeriodeReportingESG`` : gèle son ``SnapshotESG`` (NTESG1).

    Refuse (``ValidationError``) si la période est déjà ``figee`` ou
    ``publiee`` — le figeage ne recalcule/n'écrase JAMAIS un snapshot
    existant, pour garantir qu'une période figée renvoie exactement les
    mêmes chiffres indéfiniment, même si les données sources QHSE ont changé
    depuis. Renvoie la période (rafraîchie).

    À la clôture, tente une alerte de dérive trajectoire (NTESG10,
    ``alerter_derive_trajectoire``) — best-effort, JAMAIS bloquant : une
    erreur de notification ne doit jamais empêcher le figeage lui-même.
    """
    from .models import PeriodeReportingESG, SnapshotESG
    from .selectors import agreger_indicateurs_periode

    if periode.statut != PeriodeReportingESG.Statut.BROUILLON:
        raise ValidationError(
            'Cette période est déjà figée ou publiée — le figeage est '
            'refusé (les chiffres figés ne sont jamais recalculés).')

    donnees = agreger_indicateurs_periode(
        periode.company, periode.date_debut, periode.date_fin)
    SnapshotESG.objects.create(
        company=periode.company, periode=periode, donnees=donnees)
    periode.statut = PeriodeReportingESG.Statut.FIGEE
    periode.figee_le = timezone.now()
    periode.figee_par = user
    periode.save(update_fields=['statut', 'figee_le', 'figee_par'])

    try:
        alerter_derive_trajectoire(periode)
    except Exception:  # noqa: BLE001 - best-effort, jamais bloquant
        logger.warning(
            'esg.figer_periode: alerte de dérive trajectoire échouée '
            'pour la période %s', periode.pk, exc_info=True)

    return periode


def _ecart_est_defavorable(objectif, ecart_pct, seuil_pct):
    """Un écart (NTESG7, ``trajectoire_vs_realise``) est-il défavorable au-delà
    du seuil (NTESG10) ?

    Le sens de « défavorable » dépend de la direction visée par l'objectif :
      * trajectoire DÉCROISSANTE (``valeur_cible < valeur_reference``, ex.
        réduction d'émissions) : défavorable si le réel DÉPASSE la
        trajectoire théorique de plus de ``seuil_pct`` (``ecart_pct`` positif) ;
      * trajectoire CROISSANTE/STABLE (``valeur_cible >= valeur_reference``,
        ex. hausse d'un taux de valorisation) : défavorable si le réel est EN
        RETARD de plus de ``seuil_pct`` (``ecart_pct`` négatif).
    """
    if ecart_pct is None:
        return False
    if objectif.valeur_cible < objectif.valeur_reference:
        return ecart_pct >= seuil_pct
    return ecart_pct <= -seuil_pct


def _dernier_point_reel(points, annee_limite):
    """Dernier point (année, réel, écart) connu à ``annee_limite`` inclus."""
    candidats = [
        p for p in points
        if (annee_limite is None or p['annee'] <= annee_limite)
        and p['reel'] is not None and p['ecart_pct'] is not None
    ]
    if not candidats:
        return None
    return max(candidats, key=lambda p: p['annee'])


def alerter_derive_trajectoire(periode, *, seuil_pct=None):
    """Alerte de dérive trajectoire ESG (NTESG10).

    Pour chaque ``ObjectifESGTrajectoire`` actif de la société de ``periode``,
    compare le dernier point réel disponible (à la date de fin de ``periode``
    incluse) à sa trajectoire théorique (NTESG7, ``trajectoire_vs_realise``).
    Un écart défavorable dépassant ``seuil_pct`` (défaut
    ``SEUIL_ALERTE_DERIVE_PCT_DEFAUT``, 10 %) déclenche une notification
    (réutilise ``notifications.notify_many``) vers les administrateurs actifs
    de la société — en attendant qu'un ``pilote_esg`` dédié (NTESG20) affine
    le destinataire. Best-effort : une source indisponible (qhse absent,
    erreur de calcul) dégrade silencieusement cet objectif, jamais toute
    l'alerte. Renvoie la liste des ``Notification`` effectivement créées
    (peut être vide).
    """
    from .models import ObjectifESGTrajectoire
    from .selectors import trajectoire_vs_realise

    seuil = seuil_pct if seuil_pct is not None else SEUIL_ALERTE_DERIVE_PCT_DEFAUT
    company = periode.company
    if company is None:
        return []
    annee_limite = periode.date_fin.year if periode.date_fin else None

    objectifs_en_derive = []
    for objectif in ObjectifESGTrajectoire.objects.filter(
            company=company, actif=True):
        try:
            points = trajectoire_vs_realise(objectif)
        except Exception:  # noqa: BLE001 - dégrade cet objectif uniquement
            continue
        dernier = _dernier_point_reel(points, annee_limite)
        if dernier is None:
            continue
        if _ecart_est_defavorable(objectif, dernier['ecart_pct'], seuil):
            objectifs_en_derive.append((objectif, dernier))

    if not objectifs_en_derive:
        return []

    from authentication.models import CustomUser
    from apps.notifications.models import EventType
    from apps.notifications.services import notify_many

    destinataires = list(CustomUser.admins_actifs_qs(company))
    notifications = []
    for objectif, point in objectifs_en_derive:
        title = f'Dérive trajectoire ESG — {objectif.indicateur_code}'
        body = (
            f'{objectif.libelle or objectif.indicateur_code} : écart de '
            f"{point['ecart_pct']} % par rapport à la trajectoire théorique "
            f"en {point['annee']} (seuil {seuil} %) — période « "
            f'{periode.libelle} ».')
        notifications.extend(notify_many(
            destinataires, EventType.DIGEST, title, body=body,
            company=company))
    return notifications
