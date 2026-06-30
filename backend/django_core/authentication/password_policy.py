"""FG22 — politique de mot de passe & verrouillage de compte, par société.

La politique vit sur ``parametres.CompanyProfile`` (longueur min., complexité,
verrouillage après N échecs, expiration). Tous les défauts sont INERTES :
``min_length=8`` (= Django), ``require_complexity=False``, ``lockout=0`` (off),
``expiry=0`` (jamais). Tant qu'une société n'édite rien, la connexion et le
changement de mot de passe se comportent EXACTEMENT comme avant.

Ces fonctions sont des helpers de fondation (``authentication``) ; elles lisent
le profil via un import paresseux pour ne créer aucun cycle au chargement.
"""
import re

from django.utils import timezone


def get_policy(company):
    """Renvoie le ``CompanyProfile`` (politique) pour une société, ou None.

    Best-effort : ne lève jamais (un profil manquant → None → défauts inertes).
    """
    if company is None:
        return None
    try:
        from apps.parametres.models import CompanyProfile
        return CompanyProfile.objects.filter(company=company).first()
    except Exception:
        return None


def validate_password_policy(password, company):
    """Valide ``password`` contre la politique de ``company``.

    Retourne une liste de messages d'erreur (vide si conforme). Sans profil ou
    avec les défauts inertes, ne renvoie aucune erreur supplémentaire au-delà
    des validateurs Django appelés ailleurs."""
    errors = []
    profile = get_policy(company)
    if profile is None:
        return errors
    min_len = profile.password_min_length or 0
    if min_len and len(password or '') < min_len:
        errors.append(
            f'Le mot de passe doit comporter au moins {min_len} caractères.')
    if profile.password_require_complexity:
        checks = [
            (r'[a-z]', 'une minuscule'),
            (r'[A-Z]', 'une majuscule'),
            (r'[0-9]', 'un chiffre'),
            (r'[^A-Za-z0-9]', 'un caractère spécial'),
        ]
        missing = [label for pattern, label in checks
                   if not re.search(pattern, password or '')]
        if missing:
            errors.append(
                'Le mot de passe doit contenir ' + ', '.join(missing) + '.')
    return errors


def is_locked(user):
    """True si le compte est temporairement verrouillé (FG22)."""
    locked_until = getattr(user, 'locked_until', None)
    return bool(locked_until and locked_until > timezone.now())


def register_failed_login(user):
    """Incrémente le compteur d'échecs et verrouille si le seuil société est
    atteint. No-op si la société n'active pas le verrouillage (seuil 0)."""
    if user is None:
        return
    profile = get_policy(getattr(user, 'company', None))
    max_attempts = getattr(profile, 'lockout_max_attempts', 0) or 0
    if max_attempts <= 0:
        return  # verrouillage désactivé → comportement historique
    user.failed_login_count = (user.failed_login_count or 0) + 1
    fields = ['failed_login_count']
    reached = user.failed_login_count >= max_attempts
    if reached:
        minutes = getattr(profile, 'lockout_duration_minutes', 15) or 15
        user.locked_until = timezone.now() + timezone.timedelta(
            minutes=minutes)
        user.failed_login_count = 0
        fields = ['failed_login_count', 'locked_until']
    try:
        user.save(update_fields=fields)
    except Exception:
        pass
    # FG23 — alerte de sécurité quand le seuil d'échecs consécutifs est atteint
    # (et que le compte vient d'être verrouillé). Best-effort : journalisée dans
    # le Journal d'activité (action SECURITY_ALERT), visible dans l'onglet
    # « Sécurité » réservé au Directeur. N'élève jamais.
    if reached:
        try:
            from apps.audit.recorder import record
            from apps.audit.models import AuditLog
            record(
                AuditLog.Action.SECURITY_ALERT, user=user,
                actor_username=user.username,
                company=getattr(user, 'company', None),
                detail=(f'Compte verrouillé après {max_attempts} échecs de '
                        'connexion consécutifs.'))
        except Exception:
            pass


def reset_failed_login(user):
    """Remet le compteur à 0 et lève le verrou (connexion réussie)."""
    if user is None:
        return
    if (user.failed_login_count or 0) == 0 and user.locked_until is None:
        return
    user.failed_login_count = 0
    user.locked_until = None
    try:
        user.save(update_fields=['failed_login_count', 'locked_until'])
    except Exception:
        pass


def password_expired(user):
    """True si le mot de passe a dépassé la fenêtre d'expiration de la société.

    0 jour = jamais (défaut). Sans ``password_changed_at`` connu, on ne force
    rien (on ne verrouille jamais un compte historique par ancienneté)."""
    profile = get_policy(getattr(user, 'company', None))
    days = getattr(profile, 'password_expiry_days', 0) or 0
    if days <= 0:
        return False
    changed_at = getattr(user, 'password_changed_at', None)
    if changed_at is None:
        return False
    return changed_at < timezone.now() - timezone.timedelta(days=days)
