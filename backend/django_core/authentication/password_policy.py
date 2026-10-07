"""FG22 — politique de mot de passe & verrouillage de compte, par société.

La politique vit sur ``parametres.CompanyProfile`` (longueur min., complexité,
verrouillage après N échecs, expiration). Tous les défauts sont INERTES :
``min_length=8`` (= Django), ``require_complexity=False``, ``lockout=0`` (off),
``expiry=0`` (jamais). Tant qu'une société n'édite rien, la connexion et le
changement de mot de passe se comportent EXACTEMENT comme avant.

Ces fonctions sont des helpers de fondation (``authentication``) ; elles lisent
le profil via un import paresseux pour ne créer aucun cycle au chargement.
"""
import hashlib
import re

from django.conf import settings
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


def validate_new_password(password, company, user=None):
    """AUD402 — point d'entrée UNIQUE pour valider un mot de passe NEUF.

    Combine les validateurs Django (``AUTH_PASSWORD_VALIDATORS``, qui n'étaient
    câblés QUE dans ``ChangePasswordView`` — jamais à la création d'un compte)
    et la politique de société FG22 (``validate_password_policy``). Les trois
    points d'entrée d'un mot de passe neuf (``RegisterCompanyView``,
    ``RegisterSerializer``, ``ChangePasswordView``) passent par ici pour qu'une
    4e divergence ne puisse plus s'installer.

    ``company`` peut être ``None`` (signup public : la société n'existe pas
    encore) → seuls les validateurs Django s'appliquent, ce qui suffit à
    refuser un mot de passe d'un caractère.

    Retourne une LISTE de messages (vide si conforme) ; ne lève jamais, pour
    que chaque appelant rende sa propre 400 dans son format.
    """
    from django.contrib.auth.password_validation import validate_password
    from django.core.exceptions import ValidationError as DjValidationError

    if not password:
        return ['Le mot de passe est requis.']
    errors = []
    try:
        validate_password(password, user=user)
    except DjValidationError as exc:
        errors.extend(exc.messages)
    errors.extend(validate_password_policy(password, company))
    return errors


def _cle_plancher(user, ip, nature):
    """ASEC4-revue — clé de cache du plancher pour le couple (compte, IP).

    L'IP (lue par ``core.throttling.ip_de_requete`` chez l'appelant) n'est
    jamais écrite en clair dans le cache : empreinte SHA-256 tronquée. Une IP
    inconnue (appel hors requête) forme son propre seau ``inconnue``."""
    empreinte = hashlib.sha256(
        (ip or 'inconnue').encode('utf-8')).hexdigest()[:32]
    return f'asec4:{nature}:{user.pk}:{empreinte}'


def _plancher_verrouille(user, ip):
    from django.core.cache import cache
    try:
        return bool(cache.get(_cle_plancher(user, ip, 'verrou')))
    except Exception:  # noqa: BLE001 — cache en panne : pas de verrou
        return False


def is_locked(user, ip=None):
    """True si le compte est verrouillé pour cette connexion.

    * verrou SOCIÉTÉ (FG22, ``lockout_max_attempts`` > 0) : sur le COMPTE,
      quelle que soit l'IP (``locked_until``) ;
    * plancher PLATEFORME (ASEC4, décision fondateur « verrou par compte+IP »)
      : sur le couple (compte, ``ip``) seulement — le titulaire qui se
      connecte depuis une autre IP n'est pas gêné."""
    locked_until = getattr(user, 'locked_until', None)
    if locked_until and locked_until > timezone.now():
        return True
    if user is None or getattr(user, 'pk', None) is None:
        return False
    return _plancher_verrouille(user, ip)


def _plancher_echec(user, ip):
    """ASEC4-revue — compte un échec du couple (compte, IP) ; True si le
    plancher vient de verrouiller ce couple. Cache Django (Redis en prod,
    comme les throttles) ; panne du cache = pas de verrou (dégradé ouvert,
    comme les throttles)."""
    from django.core.cache import cache
    plancher = int(getattr(settings, 'LOGIN_PLANCHER_ECHECS', 10) or 0)
    if plancher <= 0:
        return False
    minutes = int(getattr(settings, 'LOGIN_PLANCHER_VERROU_MINUTES', 15) or 15)
    cle = _cle_plancher(user, ip, 'echecs')
    try:
        # Échecs CONSÉCUTIFS : remis à 0 au succès (``reset_failed_login``) ;
        # la fenêtre d'un jour borne seulement la durée de vie de la clé.
        if cache.add(cle, 1, timeout=86400):
            compte = 1
        else:
            compte = cache.incr(cle)
        if compte < plancher:
            return False
        cache.set(_cle_plancher(user, ip, 'verrou'), 1, timeout=minutes * 60)
        cache.delete(cle)
        return True
    except Exception:  # noqa: BLE001
        return False


def register_failed_login(user, ip=None):
    """Compte un échec de connexion.

    * verrou SOCIÉTÉ (FG22) — inchangé : au seuil ``lockout_max_attempts``
      (si > 0), le COMPTE est verrouillé ``lockout_duration_minutes`` ;
    * plancher PLATEFORME (ASEC4) — même quand la société n'a pas armé son
      verrou : ``LOGIN_PLANCHER_ECHECS`` échecs CONSÉCUTIFS depuis la MÊME IP
      verrouillent le couple (compte, IP) ``LOGIN_PLANCHER_VERROU_MINUTES``.
      Aucune exemption (superuser compris)."""
    if user is None:
        return
    profile = get_policy(getattr(user, 'company', None))
    societe = getattr(profile, 'lockout_max_attempts', 0) or 0
    user.failed_login_count = (user.failed_login_count or 0) + 1
    fields = ['failed_login_count']
    verrou_societe = societe > 0 and user.failed_login_count >= societe
    if verrou_societe:
        minutes = getattr(profile, 'lockout_duration_minutes', 15) or 15
        user.locked_until = timezone.now() + timezone.timedelta(
            minutes=minutes)
        user.failed_login_count = 0
        fields = ['failed_login_count', 'locked_until']
    try:
        user.save(update_fields=fields)
    except Exception:
        pass
    verrou_plancher = _plancher_echec(user, ip)
    # FG23 — alerte de sécurité quand un verrou vient d'être posé.
    # Best-effort : journalisée dans le Journal d'activité (action
    # SECURITY_ALERT), visible dans l'onglet « Sécurité » réservé au
    # Directeur. N'élève jamais.
    if verrou_societe or verrou_plancher:
        if verrou_societe:
            detail = (f'Compte verrouillé après {societe} échecs de '
                      'connexion consécutifs.')
        else:
            plancher = int(getattr(settings, 'LOGIN_PLANCHER_ECHECS', 10) or 0)
            detail = (f'Compte verrouillé pour une adresse IP après '
                      f'{plancher} échecs de connexion consécutifs.')
        try:
            from apps.audit.recorder import record
            from apps.audit.models import AuditLog
            record(
                AuditLog.Action.SECURITY_ALERT, user=user,
                actor_username=user.username,
                company=getattr(user, 'company', None), detail=detail)
        except Exception:
            pass


def reset_failed_login(user, ip=None):
    """Remet le compteur à 0 et lève le verrou (connexion réussie) ; efface
    aussi le compteur plancher du couple (compte, IP)."""
    if user is None:
        return
    try:
        from django.core.cache import cache
        cache.delete(_cle_plancher(user, ip, 'echecs'))
    except Exception:  # noqa: BLE001
        pass
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
