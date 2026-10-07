"""ASEC12 — la connexion à l'admin Django passe par la MÊME porte que l'API.

Avant, l'admin Django (``DJANGO_ADMIN_URL``) n'exigeait que le mot de passe :
ni code TOTP pour un compte 2FA, ni compteur/verrou d'échecs (FG22/ASEC4),
ni ``UserSession`` tracée, et tout ``is_staff`` y entrait. Ce module fournit :

* ``AdminLoginForm`` — mot de passe, puis verrou (annoncé seulement après un
  mot de passe correct, ASEC14), réservé aux superusers, code TOTP exigé pour
  un compte 2FA (vérification anti-rejeu ``CustomUser.verify_totp``, ASEC5),
  chaque échec compté (``register_failed_login``, ASEC4), succès = compteur
  remis à zéro + ``UserSession`` tracée ;
* ``admin_has_permission`` — l'accès au site admin exige ``is_superuser``.

Aucune seconde implémentation : vérification TOTP, compteur et verrou sont
ceux de l'API. Posés sur ``admin.site`` depuis ``authentication/admin.py``.
"""
import uuid

from django import forms
from django.contrib.admin.forms import AdminAuthenticationForm
from django.core.exceptions import ValidationError

from .password_policy import is_locked, register_failed_login, reset_failed_login


def _compte(username):
    from .models import CustomUser
    username = (username or '').strip()
    if not username:
        return None
    return CustomUser.objects.filter(username__iexact=username).first()


class AdminLoginForm(AdminAuthenticationForm):
    otp = forms.CharField(
        label='Code de double authentification', required=False,
        widget=forms.TextInput(attrs={'autocomplete': 'one-time-code'}))

    error_messages = {
        **AdminAuthenticationForm.error_messages,
        'compte_verrouille': (
            'Compte temporairement verrouillé après trop de tentatives. '
            'Réessayez plus tard.'),
        'otp_requis': 'Code de double authentification requis ou invalide.',
    }

    def clean(self):
        compte = _compte(self.cleaned_data.get('username'))
        ip = self._ip()
        try:
            cleaned = super().clean()
        except ValidationError:
            # Mauvais identifiants (ou compte non autorisé) : échec compté,
            # même message pour un compte inconnu.
            if compte is not None:
                register_failed_login(compte, ip)
            raise
        user = self.get_user()
        if is_locked(user, ip):
            raise ValidationError(self.error_messages['compte_verrouille'],
                                  code='compte_verrouille')
        if getattr(user, 'totp_enabled', False):
            code = (self.cleaned_data.get('otp') or '').strip()
            if not code or not user.verify_totp(code):
                register_failed_login(user, ip)
                raise ValidationError(self.error_messages['otp_requis'],
                                      code='otp_requis')
        reset_failed_login(user, ip)
        self._tracer_session(user)
        return cleaned

    def _ip(self):
        """IP de la requête par LA primitive (ADOC79) ; None hors requête."""
        request = getattr(self, 'request', None)
        if request is None:
            return None
        from core.throttling import ip_de_requete
        try:
            return ip_de_requete(request)
        except Exception:  # noqa: BLE001
            return None

    def confirm_login_allowed(self, user):
        """``is_staff`` (contrôle Django) ET superuser : l'admin Django est un
        outil d'opérateur plateforme, pas un écran de gestion de société."""
        super().confirm_login_allowed(user)
        if not getattr(user, 'is_superuser', False):
            raise ValidationError(
                self.error_messages['invalid_login'], code='invalid_login',
                params={'username': self.username_field.verbose_name})

    def _tracer_session(self, user):
        """``UserSession`` de la connexion admin (best-effort, jamais
        bloquant). Identifiant préfixé ``admin-`` : il ne correspond à aucun
        jeton JWT et apparaît dans la liste des sessions du compte."""
        try:
            from .models import UserSession
            from .views import _client_ip
            request = self.request
            meta = getattr(request, 'META', {}) or {}
            UserSession.objects.create(
                user=user, company=getattr(user, 'company', None),
                jti=f'admin-{uuid.uuid4().hex}',
                user_agent=(meta.get('HTTP_USER_AGENT', '') or '')[:400],
                ip_address=_client_ip(request) if request is not None else None,
            )
        except Exception:  # noqa: BLE001 — la traçabilité ne bloque jamais
            pass


def admin_has_permission(request):
    """Accès au site admin : compte actif, ``is_staff`` ET superuser."""
    user = getattr(request, 'user', None)
    return bool(user is not None and user.is_active and user.is_staff
                and user.is_superuser)
