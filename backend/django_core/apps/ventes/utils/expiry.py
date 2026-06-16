"""T7 — expiration des devis calculée À LA VOLÉE (aucun planificateur).

Un devis est « expiré » quand la date du jour dépasse sa date de validité ET
qu'il est encore en attente (brouillon/envoyé). Un devis accepté, refusé ou
déjà marqué expiré n'est jamais recalculé. La date de validité = `date_validite`
si renseignée, sinon `date_creation + quote_validity_days` (réglage société).
On ne PERSISTE rien et on ne touche jamais à l'étape du lead.
"""
from datetime import timedelta

# Statuts encore « ouverts » : seuls ceux-ci peuvent devenir expirés à la volée.
PENDING_STATUTS = ('brouillon', 'envoye')


def _validity_days(company):
    try:
        from apps.parametres.models import CompanyProfile
        prof = CompanyProfile.get(company)
        return int(prof.quote_validity_days or 30)
    except Exception:
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
    """Vrai si le devis est expiré à la volée (statut en attente + date passée)."""
    if devis.statut not in PENDING_STATUTS:
        return False
    exp = date_expiration(devis)
    if exp is None:
        return False
    from datetime import date as _date
    return (today or _date.today()) > exp
