"""T7 — expiration des devis calculée À LA VOLÉE (aucun planificateur).

Un devis est « expiré » quand la date du jour dépasse sa date de validité ET
qu'il est encore en attente (brouillon/envoyé). Un devis accepté, refusé ou
déjà marqué expiré n'est jamais recalculé. La date de validité = `date_validite`
si renseignée, sinon `date_creation + quote_validity_days` (réglage société).
On ne PERSISTE rien et on ne touche jamais à l'étape du lead.
"""
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

# Statuts encore « ouverts » : seuls ceux-ci peuvent devenir expirés à la volée.
PENDING_STATUTS = ('brouillon', 'envoye')


def _validity_days(company):
    try:
        from apps.parametres.models import CompanyProfile
        prof = CompanyProfile.lire(company)
        return int(prof.quote_validity_days or 30)
    except Exception:
        logger.warning("expiry._validity_days : erreur ignorée (mode dégradé)", exc_info=True)
        return 30


def date_expiration(devis):
    """Date d'expiration effective du devis (date), ou None si indéterminable."""
    if devis.date_validite:
        return devis.date_validite
    if not devis.date_creation:
        return None
    return (devis.date_creation.date()
            + timedelta(days=_validity_days(devis.company)))


def is_expired(devis, today=None):
    """Vrai si le devis est expiré à la volée (statut en attente + date passée).

    ADEV52 (C-ADEV-019) — UNE règle : l'offre vaut jusqu'à la FIN de son
    dernier jour de validité, à l'heure du MAROC (``timezone.localdate()``,
    ``TIME_ZONE = 'Africa/Casablanca'``) — jamais le jour du serveur (UTC dans
    le conteneur) ni « 12:00 UTC » comme le calculait la page. La page lit
    ce verdict (``offre_expiree``), l'acceptation client l'applique."""
    if devis.statut not in PENDING_STATUTS:
        return False
    exp = date_expiration(devis)
    if exp is None:
        return False
    if today is None:
        from django.utils import timezone
        today = timezone.localdate()
    return today > exp


def q_expiration(company, apres=None, avant=None):
    """T4-X4-005 — la JUMELLE SQL de :func:`date_expiration` : les devis dont
    la date d'expiration tombe entre ``apres`` et ``avant`` (bornes incluses,
    ``None`` = ouverte), pour filtrer et compter la liste côté serveur sans
    charger les devis. Même règle : ``date_validite`` si renseignée, sinon
    le jour (UTC, comme ``date_creation.date()``) de création + la validité
    de la société."""
    from datetime import datetime, time, timezone as tz_utc
    from django.db.models import Q

    jours = _validity_days(company)

    def minuit(jour):
        return datetime.combine(jour - timedelta(days=jours), time.min,
                                tzinfo=tz_utc.utc)

    par_validite = Q(date_validite__isnull=False)
    par_creation = Q(date_validite__isnull=True, date_creation__isnull=False)
    if apres is not None:
        par_validite &= Q(date_validite__gte=apres)
        par_creation &= Q(date_creation__gte=minuit(apres))
    if avant is not None:
        par_validite &= Q(date_validite__lte=avant)
        par_creation &= Q(date_creation__lt=minuit(avant + timedelta(days=1)))
    return par_validite | par_creation


def q_expire_a_la_volee(company, today):
    """La jumelle SQL de :func:`is_expired` (statut en attente + date passée)."""
    from django.db.models import Q
    return Q(statut__in=PENDING_STATUTS) & q_expiration(
        company, avant=today - timedelta(days=1))
