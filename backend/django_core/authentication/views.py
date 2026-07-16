from django.conf import settings
from django.http import HttpResponse
from django.utils.text import slugify
from rest_framework import generics, permissions, viewsets, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from .models import CustomUser, Company, UserSession
from .serializers import (
    RegisterSerializer,
    UserSerializer,
    CompanySerializer,
    CustomTokenObtainPairSerializer,
    UserSessionSerializer,
)
from .throttles import LoginRateThrottle, RegisterRateThrottle
from authentication.permissions import IsAdminRole, IsAdminOrResponsableTier

# ── Stratégie CSRF des cookies d'authentification (ERR45) ────────────────────
# Les jetons JWT sont posés en cookies ``httpOnly`` (jamais lisibles par JS, ce
# qui neutralise le vol de jeton par XSS). La protection CSRF des mutations
# authentifiées par cookie repose sur DEUX barrières complémentaires :
#   1. ``SameSite=Lax`` — le navigateur n'attache PAS ces cookies aux requêtes
#      cross-site qui changent l'état (POST/PUT/PATCH/DELETE déclenchés depuis un
#      autre site), ce qui bloque les CSRF classiques. Notre API n'expose AUCUNE
#      mutation en GET, donc Lax offre la même barrière anti-CSRF que Strict pour
#      les écritures, tout en envoyant le cookie sur les navigations top-level.
#      MOTIF DU PASSAGE STRICT→LAX (bug iOS connu) : WebKit n'attache PAS les
#      cookies ``SameSite=Strict`` à la requête de DÉMARRAGE quand on lance la PWA
#      depuis l'écran d'accueil (cold-launch). Conséquence avec Strict : l'app
#      s'ouvrait déconnectée ET le refresh silencieux (cookie ``refresh_token``)
#      ne partait pas non plus → re-login forcé à chaque ouverture sur iPhone.
#      Lax corrige ce comportement (le cookie part sur la navigation de lancement)
#      sans rouvrir de fenêtre CSRF sur les écritures. NE PAS repasser à 'None'
#      sans un flux de jeton CSRF explicite (double-submit / X-CSRFToken).
#   2. ``Secure`` en production (cookies HTTPS uniquement) — posé via
#      ``_COOKIE_SECURE`` ci-dessous, renforcé par ``SESSION/CSRF_COOKIE_SECURE``
#      et ``SECURE_SSL_REDIRECT`` dans settings/prod.py.
# Le frontend est servi depuis le même site eTLD+1 que l'API en production. Le
# test ``tests_hardening.test_auth_cookies_are_samesite_lax_and_httponly``
# verrouille cette valeur pour qu'un relâchement silencieux casse la CI.
_COOKIE_SECURE = not settings.DEBUG
_COOKIE_SAMESITE = 'Lax'
_ACCESS_MAX_AGE = int(
    settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'].total_seconds()
)
_REFRESH_MAX_AGE = int(
    settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds()
)


def _set_auth_cookies(response, access, refresh=None):
    """Positionne les cookies httpOnly sur la reponse Django."""
    response.set_cookie(
        'access_token', access,
        max_age=_ACCESS_MAX_AGE,
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite=_COOKIE_SAMESITE,
        path='/',
    )
    if refresh:
        response.set_cookie(
            'refresh_token', refresh,
            max_age=_REFRESH_MAX_AGE,
            httponly=True,
            secure=_COOKIE_SECURE,
            samesite=_COOKIE_SAMESITE,
            path='/',
        )


def _clear_auth_cookies(response):
    """Supprime les cookies d'authentification."""
    response.delete_cookie('access_token', path='/')
    response.delete_cookie('refresh_token', path='/')


# NTSEC14 — durée par défaut de confiance d'un appareil (« se souvenir 30 j »).
_DEVICE_TRUST_DAYS = 30


def _maybe_trust_device(user, request, response):
    """NTSEC14 — si la connexion demande « faire confiance à cet appareil » et
    que la société l'autorise (``CompanyProfile.allow_device_trust``), enregistre
    un ``TrustedDevice`` (jeton opaque tiré au sort) et pose le cookie httpOnly
    ``device_trust_id``. Best-effort : n'échoue jamais le login. Inerte tant que
    la société n'a pas activé l'option (défaut) ou que rien n'est demandé."""
    try:
        if user is None:
            return
        data = getattr(request, 'data', {}) or {}
        if not data.get('trust_device'):
            return
        company = getattr(user, 'company', None)
        if company is None:
            return
        from apps.parametres.models_company import CompanyProfile
        profile = (
            CompanyProfile.objects
            .filter(company=company)
            .only('allow_device_trust')
            .first()
        )
        if not (profile and profile.allow_device_trust):
            return
        import secrets
        from datetime import timedelta
        from django.utils import timezone as _tz
        from apps.identity.models import TrustedDevice

        token = secrets.token_urlsafe(48)
        now = _tz.now()
        max_age = _DEVICE_TRUST_DAYS * 24 * 3600
        TrustedDevice.objects.create(
            user=user,
            company=company,
            device_fingerprint=token,
            approuve_le=now,
            expire_le=now + timedelta(days=_DEVICE_TRUST_DAYS),
            approuve_par=user,
            label=(request.META.get('HTTP_USER_AGENT', '') or '')[:200],
        )
        response.set_cookie(
            'device_trust_id', token,
            max_age=max_age,
            httponly=True,
            secure=_COOKIE_SECURE,
            samesite=_COOKIE_SAMESITE,
            path='/',
        )
    except Exception:
        pass


def _client_ip(request):
    """Adresse IP du client (premier saut X-Forwarded-For, sinon REMOTE_ADDR)."""
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR') or None


def _refresh_jti(refresh_raw):
    """Extrait le claim ``jti`` d'un jeton de rafraîchissement brut (ou None)."""
    if not refresh_raw:
        return None
    try:
        return RefreshToken(refresh_raw).get('jti')
    except TokenError:
        return None


def _record_session(user, refresh_raw, request):
    """Crée (best-effort) une ligne ``UserSession`` pour une connexion réussie.

    Tracée par le ``jti`` du jeton de rafraîchissement, scopée à l'utilisateur et
    à sa société (jamais depuis le corps de la requête). N'échoue jamais la
    connexion : toute erreur est avalée."""
    try:
        jti = _refresh_jti(refresh_raw)
        if not jti or user is None:
            return
        # NTSEC9 — si la connexion a franchi un second facteur (2FA TOTP actif),
        # la MFA vient d'être vérifiée : on horodate la session pour le step-up.
        from django.utils import timezone as _tz
        mfa_at = _tz.now() if getattr(user, 'totp_enabled', False) else None
        session = UserSession.objects.create(
            user=user,
            company=getattr(user, 'company', None),
            jti=jti,
            user_agent=(request.META.get('HTTP_USER_AGENT', '') or '')[:400],
            ip_address=_client_ip(request),
            last_mfa_at=mfa_at,
        )
        # NTSEC13 — empreinte d'appareil + alerte « appareil inconnu » à la
        # première apparition (best-effort, jamais bloquant).
        try:
            from .device import note_login_device
            note_login_device(user, session, request)
        except Exception:
            pass
        # NTSEC10 — limite de sessions concurrentes : au-delà du plafond
        # société, évincer la (les) session(s) la (les) plus ancienne(s).
        try:
            from .session_policy import enforce_concurrent_limit
            enforce_concurrent_limit(user)
        except Exception:
            pass
    except Exception:
        pass


def _blacklist_refresh_jti(jti):
    """Blackliste le jeton de rafraîchissement portant ``jti`` (best-effort).

    S'appuie sur l'app ``token_blacklist`` (présente dans INSTALLED_APPS) : on
    retrouve l'``OutstandingToken`` émis pour ce jti et on crée son entrée
    blacklistée. Sans correspondance (jeton jamais sorti via la voie standard),
    la révocation repose alors uniquement sur la suppression de la session."""
    try:
        from rest_framework_simplejwt.token_blacklist.models import (
            OutstandingToken, BlacklistedToken,
        )
        outstanding = OutstandingToken.objects.filter(jti=jti).first()
        if outstanding is not None:
            BlacklistedToken.objects.get_or_create(token=outstanding)
    except Exception:
        pass


# ── Login ──────────────────────────────────────────────────────
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = [LoginRateThrottle]

    def post(self, request, *args, **kwargs):
        from rest_framework.exceptions import ValidationError
        from .password_policy import (
            is_locked, register_failed_login, reset_failed_login,
        )
        # FG22 — verrouillage de compte (par société, opt-in). Résout le compte
        # par username (insensible à la casse) pour vérifier l'état de verrou
        # AVANT de tenter l'authentification. Inerte si la société n'a pas armé
        # ``lockout_max_attempts`` (aucun compte n'a alors de ``locked_until``).
        raw_uname0 = (request.data.get('username') or '').strip()
        locked_user = CustomUser.objects.filter(
            username__iexact=raw_uname0).first() if raw_uname0 else None
        if locked_user is not None and is_locked(locked_user):
            return Response(
                {'detail': 'Compte temporairement verrouillé après trop de '
                           'tentatives. Réessayez plus tard.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        # NTSEC4 — enforce-SSO : si la société de ce compte a un IdP actif avec
        # ``enforce_sso``, le login par mot de passe local est interdit (le
        # membre doit passer par le SSO). Fail-open (aucun IdP → inchangé) ;
        # super-admin et comptes break-glass (NTSEC22) restent exemptés. On
        # bloque AVANT toute tentative de mot de passe (pas de fuite d'état).
        if locked_user is not None:
            try:
                from apps.identity.selectors import (
                    local_password_login_blocked,
                )
                if local_password_login_blocked(locked_user):
                    return Response(
                        {'detail': 'Connexion via SSO obligatoire pour cette '
                                   'société.', 'sso_required': True},
                        status=status.HTTP_403_FORBIDDEN,
                    )
            except Exception:
                pass
        # Double authentification (2FA, N96) : si le mot de passe est bon mais
        # qu'un code TOTP est requis/invalide, on renvoie une réponse 401 au
        # contour stable (`otp_required: true`) que le frontend sait gérer —
        # sans divulguer l'état 2FA d'un compte avant que le mot de passe soit
        # validé.
        try:
            response = super().post(request, *args, **kwargs)
        except ValidationError as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {}
            if detail.get('otp_required'):
                msg = detail.get('detail')
                if isinstance(msg, (list, tuple)):
                    msg = msg[0] if msg else None
                msg = str(msg) if msg else 'Double authentification requise.'
                return Response(
                    {'otp_required': True, 'detail': msg},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            # FG22 — échec d'identifiants : compte le tentative ratée et
            # verrouille au seuil société. No-op si le verrouillage est off.
            if locked_user is not None:
                register_failed_login(locked_user)
            raise
        if response.status_code == 200:
            access = response.data.pop('access', None)
            refresh = response.data.pop('refresh', None)
            _set_auth_cookies(response, access, refresh)
            # ERR92 — sur un login RÉUSSI, résoudre l'objet utilisateur depuis
            # le username (insensible à la casse), source d'autorité.
            raw_uname = (request.data.get('username') or '').strip()
            u = CustomUser.objects.filter(username__iexact=raw_uname).first()
            # FG22 — connexion réussie : remet à zéro le compteur d'échecs et
            # lève tout verrou éventuel. No-op si rien n'était posé.
            reset_failed_login(u)
            # FG22 — expiration du mot de passe : si dépassée (société l'a
            # activée), on arme la rotation forcée à cette session (le frontend
            # lit must_change_password dans /auth/me/). Inerte si expiry=0.
            try:
                from .password_policy import password_expired
                if u is not None and not u.must_change_password \
                        and password_expired(u):
                    u.must_change_password = True
                    u.save(update_fields=['must_change_password'])
            except Exception:
                pass
            # Sessions actives (N96) — tracer cette connexion par le jti du
            # jeton de rafraîchissement. Best-effort, ne bloque jamais le login.
            _record_session(u, refresh, request)
            # NTSEC14 — device trust (« se souvenir de cet appareil »), opt-in
            # société. Best-effort ; inerte sans demande ni opt-in.
            _maybe_trust_device(u, request, response)
            # Journal d'activité (Feature G) — connexion réussie. Best-effort.
            try:
                from apps.audit.recorder import record
                from apps.audit.models import AuditLog
                actor = u.username if u is not None else raw_uname
                record(AuditLog.Action.LOGIN, user=u, actor_username=actor,
                       company=getattr(u, 'company', None), detail='Connexion')
            except Exception:
                pass
            # NTSEC12 — détection « impossible travel » (best-effort, jamais
            # bloquant ; inerte sans base géo GeoLite2).
            try:
                from apps.identity.anomaly import detect_impossible_travel
                detect_impossible_travel(u, _client_ip(request))
            except Exception:
                pass
        return response


# ── Refresh cookie ──────────────────────────────────────────────
class CookieTokenRefreshView(APIView):
    """
    Renouvelle le access_token depuis le cookie refresh_token.
    Le client n'a pas besoin d'envoyer quoi que ce soit dans le body.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        refresh_raw = request.COOKIES.get('refresh_token')
        if not refresh_raw:
            return Response(
                {'detail': 'Refresh token manquant.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        try:
            token = RefreshToken(refresh_raw)
            # SCA18 — un tenant suspendu/en fermeture ne peut plus rafraîchir un
            # jeton émis avant sa suspension : on rejette au refresh (message FR).
            # Superuser (support) exempté. Tenant actif inchangé.
            try:
                uid = token.get('user_id')
                u = CustomUser.objects.select_related('company').filter(
                    pk=uid).first() if uid else None
                if (u is not None and not u.is_superuser
                        and u.company is not None
                        and not u.company.est_operationnel):
                    resp = Response(
                        {'detail': 'Ce compte société est suspendu.'},
                        status=status.HTTP_403_FORBIDDEN,
                    )
                    _clear_auth_cookies(resp)
                    return resp
            except Exception:
                pass
            # NTSEC10 — politique de session : refuser le refresh au-delà de la
            # durée absolue / d'inactivité configurée par la société (inerte si
            # non configurée). La session dépassée est révoquée côté serveur.
            try:
                from .session_policy import refresh_allowed
                if not refresh_allowed(refresh_raw, u):
                    resp = Response(
                        {'detail': 'Session expirée par la politique de '
                                   'sécurité. Reconnectez-vous.'},
                        status=status.HTTP_401_UNAUTHORIZED,
                    )
                    _clear_auth_cookies(resp)
                    return resp
            except Exception:
                pass
            access_token = token.access_token
            # XPLT19 — le claim ``active_company_id`` du refresh n'est PAS recopié
            # d'office sur l'access dérivé (simplejwt ne propage que les claims
            # enregistrés). On le reporte explicitement pour que la société active
            # choisie survive au rafraîchissement transparent (sinon elle
            # retomberait sur la société d'attache toutes les 30 min).
            from authentication.active_company import ACTIVE_COMPANY_CLAIM
            active = token.get(ACTIVE_COMPANY_CLAIM)
            if active is not None:
                access_token[ACTIVE_COMPANY_CLAIM] = active
            access = str(access_token)
            new_refresh = str(token) if settings.SIMPLE_JWT.get(
                'ROTATE_REFRESH_TOKENS', False
            ) else None
            response = Response({'detail': 'Token rafraichi.'})
            _set_auth_cookies(response, access, new_refresh)
            return response
        except TokenError:
            resp = Response(
                {'detail': 'Refresh token invalide ou expire.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )
            _clear_auth_cookies(resp)
            return resp


# ── XPLT19 — Bascule de société active (accès multi-sociétés) ──────
class SwitchCompanyView(APIView):
    """POST /api/django/auth/switch-company/ — change la société ACTIVE.

    Corps : ``{"company_id": <id>}``. Autorisé UNIQUEMENT si l'utilisateur est
    membre de la société cible (société d'attache OU ``societes_autorisees``).
    Un compte mono-société ne peut donc PAS switcher (403). Sur succès, on
    réémet des jetons (access + refresh) portant le claim ``active_company_id``
    de la société choisie, et on journalise la bascule dans l'audit. Toutes les
    requêtes ultérieures sont alors bornées à la nouvelle société active."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        company_id = request.data.get('company_id')
        if company_id in (None, ''):
            return Response(
                {'detail': 'Le champ « company_id » est requis.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            company_id = int(company_id)
        except (TypeError, ValueError):
            return Response(
                {'detail': 'Identifiant de société invalide.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Garde d'appartenance STRICTE : jamais de switch vers une société non
        # autorisée (défense contre l'escalade cross-tenant).
        if not user.peut_operer_societe(company_id):
            return Response(
                {'detail': "Vous n'êtes pas membre de cette société."},
                status=status.HTTP_403_FORBIDDEN,
            )
        cible = Company.objects.filter(pk=company_id).first()
        if cible is None:
            return Response(
                {'detail': 'Société introuvable.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        # Réémet des jetons portant le claim de société active choisie. On passe
        # par le même ``get_token`` que le login (mêmes claims), puis on écrase
        # le claim de société active sur le refresh ET l'access (l'access dérivé
        # ne recopie pas les claims personnalisés tout seul).
        from authentication.active_company import ACTIVE_COMPANY_CLAIM
        refresh = CustomTokenObtainPairSerializer.get_token(user)
        refresh[ACTIVE_COMPANY_CLAIM] = company_id
        access = refresh.access_token
        access[ACTIVE_COMPANY_CLAIM] = company_id
        response = Response({
            'detail': 'Société active changée.',
            'company_id': company_id,
            'company_nom': cible.nom,
        })
        _set_auth_cookies(response, str(access), str(refresh))
        # Sessions actives (N96) — le nouveau refresh est tracé/révocable comme
        # une connexion. Best-effort, ne bloque jamais le switch.
        _record_session(user, str(refresh), request)
        # Journal d'activité — bascule de société active (best-effort).
        try:
            from apps.audit.recorder import record
            from apps.audit.models import AuditLog
            record(
                AuditLog.Action.SWITCH_COMPANY, user=user,
                company=cible,
                detail=f'Société active → {cible.nom} (#{company_id}).',
            )
        except Exception:
            pass
        return response


# ── Inscription d'un utilisateur dans une entreprise existante ─
class RegisterView(generics.CreateAPIView):
    """Admin cree un utilisateur dans sa propre entreprise."""
    queryset = CustomUser.objects.all()
    permission_classes = [IsAdminRole]
    serializer_class = RegisterSerializer
    throttle_classes = [RegisterRateThrottle]

    def get_serializer_context(self):
        from apps.roles.models import Role
        ctx = super().get_serializer_context()
        ctx['company'] = self.request.user.company
        role_id = self.request.data.get('role')
        if role_id and self.request.user.company:
            try:
                ctx['role'] = Role.objects.get(
                    pk=role_id,
                    company=self.request.user.company,
                )
            except Role.DoesNotExist:
                ctx['role'] = None
        return ctx


def _create_system_roles(company):
    """Create the canonical system roles for a newly created company (Feature D).

    Seeds the seven roles + the two legacy ones; returns {nom: Role}.

    Idempotent ET auto-réparateur (N103) : si une ligne du même nom préexiste
    avec ``est_systeme=False`` (rôle personnalisé qui a heurté le nom canonique),
    on la promeut en rôle système. Sans cela, un « Directeur »/« Administrateur »
    laissé ``est_systeme=False`` résoudrait à tort au palier limité et perdrait
    l'accès aux écrans Utilisateurs/Rôles. Additif : ne supprime jamais une ligne
    et ne touche pas aux permissions déjà posées."""
    from apps.roles.models import Role, CANONICAL_SYSTEM_ROLES
    roles = {}
    for nom, perms in CANONICAL_SYSTEM_ROLES:
        role, created = Role.objects.get_or_create(
            company=company,
            nom=nom,
            defaults={'permissions': list(perms), 'est_systeme': True},
        )
        if not created and not role.est_systeme:
            role.est_systeme = True
            role.save(update_fields=['est_systeme'])
        roles[nom] = role
    return roles


# ── Creation d'une nouvelle entreprise (onboarding SaaS) ───────
class RegisterCompanyView(generics.GenericAPIView):
    """
    POST /api/django/auth/register-company/
    Cree une nouvelle entreprise + un administrateur.
    Endpoint public pour l'onboarding SaaS.
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [RegisterRateThrottle]
    serializer_class = RegisterSerializer  # requis par DRF GenericAPIView

    def post(self, request):
        company_nom = request.data.get('company_nom', '').strip()
        username = request.data.get('username', '').strip()
        password = request.data.get('password', '')
        email = request.data.get('email', '').strip()

        errors = {}
        if not company_nom:
            errors['company_nom'] = ["Ce champ est requis."]
        if not username:
            errors['username'] = ["Ce champ est requis."]
        if not password:
            errors['password'] = ["Ce champ est requis."]
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        if CustomUser.objects.filter(username=username).exists():
            return Response(
                {'username': ["Ce nom d'utilisateur est deja utilise."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        slug_base = slugify(company_nom) or 'company'
        slug = slug_base
        i = 1
        while Company.objects.filter(slug=slug).exists():
            slug = f"{slug_base}-{i}"
            i += 1

        company = Company.objects.create(nom=company_nom, slug=slug)

        from apps.parametres.models import CompanyProfile
        CompanyProfile.objects.get_or_create(
            company=company,
            defaults={'nom': company_nom},
        )

        roles = _create_system_roles(company)
        # Le propriétaire fondateur de la nouvelle société est Directeur (accès
        # total + Journal d'activité), pour qu'il y ait au moins un Directeur.
        admin_role = roles['Directeur']

        user = CustomUser.objects.create_user(
            username=username,
            email=email,
            password=password,
            role_legacy=CustomUser.ROLE_ADMIN,
            role=admin_role,
            company=company,
        )
        # XPLT19 — la société d'attache est aussi la première société autorisée
        # (membre). Un compte mono-société démarre donc avec {sa société}.
        user.societes_autorisees.add(company)

        # SCA20 — seeds « à la création d'une société » migrés en HOOKS
        # idempotents (types d'activité + niveaux de relance historiques, PLUS
        # le catalogue produit désormais seedé). Chaque app enregistre son hook
        # dans son apps.py ready() ; la vue ne les connaît pas. Best-effort : un
        # hook KO n'empêche jamais la création de la société.
        from core.signup_hooks import run_signup_hooks
        run_signup_hooks(company, user=user)

        return Response({
            'detail': 'Entreprise creee avec succes.',
            'company_id': company.id,
            'company_nom': company.nom,
            'username': user.username,
        }, status=status.HTTP_201_CREATED)


# ── Profil courant ─────────────────────────────────────────────
class MeView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


# ── Logout securise ────────────────────────────────────────────
class LogoutView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        refresh_raw = (
            request.COOKIES.get('refresh_token')
            or request.data.get('refresh')
        )
        if refresh_raw:
            try:
                token = RefreshToken(refresh_raw)
                token.blacklist()
            except TokenError:
                pass
        # Journal d'activité (Feature G) — déconnexion. Best-effort.
        try:
            from apps.audit.recorder import record
            from apps.audit.models import AuditLog
            record(AuditLog.Action.LOGOUT, user=request.user,
                   detail='Déconnexion')
        except Exception:
            pass
        response = Response({'detail': 'Deconnexion reussie.'})
        _clear_auth_cookies(response)
        return response


# ── Gestion utilisateurs (admin) ───────────────────────────────
class UserViewSet(viewsets.ModelViewSet):
    """Gestion des utilisateurs — Administrateur et Responsable, scoped company."""
    serializer_class = UserSerializer

    def get_permissions(self):
        # Le proxy de lecture des photos de profil (avatar_image) est consommé
        # par un <img> de N'IMPORTE quel écran (sélecteur de responsable côté
        # Commerciale, cartes kanban, entête…), pas seulement l'écran admin :
        # il suffit d'être authentifié. Tout le RESTE de l'écran Utilisateurs
        # reste réservé à l'Administrateur/Responsable promu.
        if getattr(self, 'action', None) == 'avatar_image':
            return [permissions.IsAuthenticated()]
        return [IsAdminOrResponsableTier()]

    def get_queryset(self):
        user = self.request.user
        if user.company_id:
            return (
                CustomUser.objects
                .filter(company=user.company)
                .select_related('role')
                .order_by('date_joined')
            )
        if user.is_superuser:
            return CustomUser.objects.all().order_by('date_joined')
        return CustomUser.objects.none()

    def _audit_user(self, field, label, old, new):
        """FG18 — écrit une ligne au Journal d'audit des paramètres
        (section='utilisateurs') pour un changement de gestion d'utilisateur.

        Best-effort : ne casse jamais l'écriture utilisateur. Réutilise le
        mécanisme ``SettingsAuditLog`` existant des Paramètres (acteur + société
        posés côté serveur)."""
        try:
            from apps.parametres.models import SettingsAuditLog
            actor = self.request.user
            SettingsAuditLog.log_change(
                company=getattr(actor, 'company', None), user=actor,
                section='utilisateurs', field=field, field_label=label,
                old=old, new=new,
            )
        except Exception:
            pass

    def _role_label(self, role_id):
        """Libellé lisible d'un rôle (nom) à partir de son id, ou son id brut."""
        if role_id in (None, '', 'null'):
            return '—'
        try:
            from apps.roles.models import Role
            role = Role.objects.filter(pk=role_id).first()
            return role.nom if role else str(role_id)
        except Exception:
            return str(role_id)

    def perform_create(self, serializer):
        instance = serializer.save(company=self.request.user.company)
        self._audit_user(
            field=f'user:{instance.username}', label='Utilisateur créé',
            old=None,
            new=f'{instance.username} (rôle {self._role_label(instance.role_id)})',
        )

    def perform_update(self, serializer):
        # FG18 — journaliser les changements de rôle / activation / superviseur.
        target = serializer.instance
        old_role_id = target.role_id
        old_active = target.is_active
        old_sup_id = target.supervisor_id
        instance = serializer.save()
        uname = instance.username
        if instance.role_id != old_role_id:
            self._audit_user(
                field=f'user:{uname}:role', label='Rôle de l\'utilisateur',
                old=self._role_label(old_role_id),
                new=self._role_label(instance.role_id))
        if instance.is_active != old_active:
            self._audit_user(
                field=f'user:{uname}:actif', label='Compte actif',
                old='actif' if old_active else 'désactivé',
                new='actif' if instance.is_active else 'désactivé')
        if instance.supervisor_id != old_sup_id:
            self._audit_user(
                field=f'user:{uname}:superviseur', label='Superviseur',
                old=old_sup_id, new=instance.supervisor_id)

    def perform_destroy(self, instance):
        uname = instance.username
        super().perform_destroy(instance)
        self._audit_user(
            field=f'user:{uname}', label='Utilisateur supprimé',
            old=uname, new=None)

    @action(detail=True, methods=['post'], url_path='avatar',
            parser_classes=[MultiPartParser])
    def avatar(self, request, pk=None):
        """Téléverse/remplace la photo de profil d'un employé (admin).

        Stockée dans MinIO (bucket erp-uploads) via boto3, comme le logo
        d'entreprise. La photo appartient à l'employé : elle apparaît ensuite
        sur tous ses leads (responsable)."""
        from .avatars import store_avatar
        target = self.get_object()
        file = request.FILES.get('file')
        if not file:
            return Response({'detail': 'Aucun fichier fourni.'},
                            status=status.HTTP_400_BAD_REQUEST)
        # SCA42 — clé préfixée par société pour le NOUVEL objet
        # (avatars/{company_id}/…). L'ancienne clé (supprimée) garde sa forme.
        key, err = store_avatar(file, target.avatar_key, company=target.company)
        if err:
            return Response({'detail': err},
                            status=status.HTTP_400_BAD_REQUEST)
        target.avatar_key = key
        target.save(update_fields=['avatar_key'])
        return Response(
            UserSerializer(target, context={'request': request}).data)

    @action(detail=False, methods=['get'], url_path='avatar-image',
            permission_classes=[permissions.IsAuthenticated])
    def avatar_image(self, request):
        """T-U13 — relaie la photo de profil via Django (MÊME ORIGINE).

        ``presign_avatar`` renvoyait jadis une URL présignée pointant sur l'hôte
        INTERNE MinIO (``minio:9000``), injoignable depuis le navigateur → la
        photo ne s'affichait jamais (seules les initiales). On streame ici les
        octets côté serveur, comme le proxy des pièces jointes
        (apps.records.views.AttachmentViewSet.download).

        Authentifié par le cookie ; la clé est bornée au préfixe ``avatars/``
        (``is_avatar_key``) pour ne jamais relayer un objet arbitraire du
        bucket. Servi en ligne (inline) pour s'afficher dans un ``<img>``."""
        from .avatars import avatar_mime_for_key, fetch_avatar, is_avatar_key
        key = request.query_params.get('key', '')
        if not is_avatar_key(key):
            return Response({'detail': 'Photo introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        data = fetch_avatar(key)
        if data is None:
            return Response({'detail': 'Photo introuvable.'},
                            status=status.HTTP_404_NOT_FOUND)
        resp = HttpResponse(data, content_type=avatar_mime_for_key(key))
        resp['Content-Disposition'] = 'inline'
        resp['X-Content-Type-Options'] = 'nosniff'
        # Photo immuable (clé = uuid) → cache navigateur privé court.
        resp['Cache-Control'] = 'private, max-age=300'
        return resp

    def _role_grants_admin(self, target, role_id):
        """L'utilisateur serait-il admin avec ce nouveau rôle ?"""
        if target.is_superuser:
            return True
        if role_id in (None, '', 'null'):
            # Rôle vidé → on retombe sur le legacy.
            return target.role_legacy == CustomUser.ROLE_ADMIN
        from apps.roles.models import Role
        role = Role.objects.filter(pk=role_id).first()
        return bool(role and 'roles_gerer' in (role.permissions or []))

    def update(self, request, *args, **kwargs):
        target = self.get_object()
        data = request.data
        # Détecte une rétrogradation (perte du rôle admin) ou une
        # désactivation du compte.
        retro = False
        if 'role' in data and target.is_admin_role \
                and not self._role_grants_admin(target, data.get('role')):
            retro = True
        if 'is_active' in data and \
                str(data.get('is_active')).lower() in ('false', '0', ''):
            retro = True
        if retro:
            if target.is_protected:
                return Response(
                    {'detail': 'Ce compte propriétaire est protégé : il ne '
                               'peut pas être rétrogradé ni désactivé.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if target.est_dernier_proprietaire():
                return Response(
                    {'detail': 'Impossible de rétrograder le dernier '
                               'propriétaire : le système doit toujours '
                               'garder un administrateur.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        target = self.get_object()
        if target == request.user:
            return Response(
                {'detail': 'Vous ne pouvez pas supprimer votre propre compte.'},  # noqa: E501
                status=status.HTTP_400_BAD_REQUEST,
            )
        if target.is_protected:
            return Response(
                {'detail': 'Ce compte propriétaire est protégé : il ne peut '
                           'pas être supprimé.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if target.is_superuser:
            return Response(
                {'detail': 'Ce compte ne peut pas être supprimé via l\'ERP.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if target.est_dernier_proprietaire():
            return Response(
                {'detail': 'Impossible de supprimer le dernier propriétaire : '
                           'le système doit toujours garder un administrateur.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)


# ── Gestion des entreprises (superuser uniquement) ─────────────
def _run_demo_reset(slug):
    """NTDMO7 — lance ``reset_demo_company`` en tâche Celery best-effort, avec
    repli SYNCHRONE si Celery est absent/non configuré. Ne lève jamais côté
    requête pour une erreur d'enqueue : dans ce cas on exécute en synchrone."""
    from django.core.management import call_command
    try:
        from authentication.tasks import reset_demo_company_task
        reset_demo_company_task.delay(slug)
        return
    except Exception:
        # Pas de Celery (ou pas de task) → exécution synchrone immédiate.
        pass
    call_command('reset_demo_company', slug=slug, force=True, verbosity=0)


class CompanyViewSet(viewsets.ModelViewSet):
    queryset = Company.objects.all().order_by('date_creation')
    serializer_class = CompanySerializer
    permission_classes = [permissions.IsAdminUser]

    def perform_update(self, serializer):
        # NTDMO10 — le mode présentation ne peut être activé/modifié QUE sur une
        # société de démonstration (jamais sur une société réelle, même par un
        # admin). ``est_demo`` reste read-only côté sérialiseur (NTDMO8).
        company = self.get_object()
        if ('mode_presentation_actif' in serializer.validated_data
                and not company.est_demo):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied(
                "Le mode présentation n'est disponible que sur une société de "
                "démonstration.")
        serializer.save()

    @action(detail=True, methods=['post'], url_path='reset-demo')
    def reset_demo(self, request, pk=None):
        """NTDMO7 — réinitialise les données de démonstration d'une société.

        403 si la société n'est pas une société de DÉMONSTRATION
        (``est_demo=False``). Invoque ``reset_demo_company`` (best-effort en
        tâche Celery, sinon synchrone) puis notifie l'utilisateur in-app.
        """
        company = self.get_object()
        if not company.est_demo:
            return Response(
                {'detail': "Cette société n'est pas une société de "
                           "démonstration."},
                status=status.HTTP_403_FORBIDDEN)

        _run_demo_reset(company.slug)

        # Notification in-app de confirmation (best-effort, ne bloque jamais).
        try:
            from apps.notifications.services import notify
            from apps.notifications.models import EventType
            notify(
                request.user, EventType.SECURITY_CHANGE,
                'Données de démonstration réinitialisées',
                body=f'La société « {company.nom} » a été réinitialisée '
                     'avec un nouveau jeu de données de démonstration.',
                company=company)
        except Exception:
            pass
        return Response({'detail': 'Données de démonstration réinitialisées.',
                         'slug': company.slug})


# ── Double authentification (2FA TOTP) — opt-in par utilisateur (N96) ──────
_TOTP_ISSUER = 'TAQINOR OS'


def _generate_recovery_codes(n=8):
    """Génère ``n`` codes de secours en clair (8 caractères base32 lisibles).

    Retourne (codes_en_clair, codes_hachés). On ne montre les codes en clair
    qu'UNE seule fois, à l'activation ; en base on ne garde que les hachages."""
    import secrets
    from django.contrib.auth.hashers import make_password
    alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    plain = [
        ''.join(secrets.choice(alphabet) for _ in range(8))
        for _ in range(n)
    ]
    hashed = [make_password(c) for c in plain]
    return plain, hashed


class TwoFactorSetupView(APIView):
    """POST — démarre la configuration 2FA pour l'utilisateur connecté.

    Génère un nouveau secret TOTP et l'URI otpauth (pour le QR code), persiste
    le secret SANS activer le 2FA (``totp_enabled`` reste False). Tant que le
    secret n'est pas vérifié, la connexion n'est jamais bloquée."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        import pyotp
        # VX120 — le QR est rendu ICI, côté serveur (SVG inline, réutilise le
        # générateur QR maison déjà vendored pour les étiquettes stock), au lieu
        # d'envoyer l'URI otpauth:// (qui CONTIENT la graine TOTP en clair) à un
        # service tiers non contrôlé (api.qrserver.com). `otpauth_uri` reste dans
        # la réponse pour compat (saisie manuelle/anciens clients) mais n'est
        # plus utilisé pour le QR par le frontend.
        from apps.stock.labels import qr_svg
        user = request.user
        if user.totp_enabled:
            return Response(
                {'detail': 'La double authentification est déjà activée.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        secret = pyotp.random_base32()
        user.totp_secret = secret
        user.totp_enabled = False
        user.save(update_fields=['totp_secret', 'totp_enabled'])
        label = user.email or user.username
        uri = pyotp.TOTP(secret).provisioning_uri(
            name=label, issuer_name=_TOTP_ISSUER,
        )
        return Response({
            'secret': secret,
            'otpauth_uri': uri,
            'qr_svg': qr_svg(uri),
            'issuer': _TOTP_ISSUER,
            'label': label,
        })


class TwoFactorEnableView(APIView):
    """POST — vérifie un premier code et active le 2FA.

    Corps : ``{"code": "123456"}``. Sur succès : ``totp_enabled=True`` et
    renvoie une liste de codes de secours à usage unique (montrés une seule
    fois)."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        import pyotp
        user = request.user
        if user.totp_enabled:
            return Response(
                {'detail': 'La double authentification est déjà activée.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not user.totp_secret:
            return Response(
                {'detail': "Aucune configuration en cours. Démarrez d'abord "
                           "la configuration de la double authentification."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        code = str(request.data.get('code', '')).strip().replace(' ', '')
        if not pyotp.TOTP(user.totp_secret).verify(code, valid_window=1):
            return Response(
                {'detail': 'Code invalide. Vérifiez le code à 6 chiffres de '
                           'votre application d\'authentification.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        plain, hashed = _generate_recovery_codes()
        user.totp_enabled = True
        user.totp_recovery_codes = hashed
        user.save(update_fields=['totp_enabled', 'totp_recovery_codes'])
        # NTSEC30 — notification obligatoire de changement de sécurité.
        try:
            from apps.notifications.services import notify_security_change
            notify_security_change(
                user, 'Double authentification activée',
                'La double authentification (2FA) a été activée sur votre '
                'compte.')
        except Exception:
            pass
        return Response({
            'detail': 'Double authentification activée.',
            'recovery_codes': plain,
        })


class TwoFactorDisableView(APIView):
    """POST — désactive le 2FA. Exige un code TOTP/secours valide OU le mot de
    passe du compte. Efface le secret et les codes de secours."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        if not user.totp_enabled:
            return Response(
                {'detail': 'La double authentification n\'est pas activée.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        code = request.data.get('code', '')
        password = request.data.get('password', '')
        ok = False
        if code and user.verify_totp(code):
            ok = True
        elif password and user.check_password(password):
            ok = True
        if not ok:
            return Response(
                {'detail': 'Vérification requise : fournissez un code valide '
                           'ou votre mot de passe pour désactiver la double '
                           'authentification.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.totp_enabled = False
        user.totp_secret = None
        user.totp_recovery_codes = []
        user.save(update_fields=[
            'totp_enabled', 'totp_secret', 'totp_recovery_codes'])
        # NTSEC30 — notification obligatoire de changement de sécurité.
        try:
            from apps.notifications.services import notify_security_change
            notify_security_change(
                user, 'Double authentification désactivée',
                'La double authentification (2FA) a été désactivée sur votre '
                'compte.')
        except Exception:
            pass
        return Response({'detail': 'Double authentification désactivée.'})


class TwoFactorStatusView(APIView):
    """GET — état du 2FA pour l'utilisateur connecté (affichage Paramètres)."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({
            'enabled': bool(user.totp_enabled),
            'recovery_codes_remaining': len(user.totp_recovery_codes or []),
        })


# ── Sessions actives & révocation (N96) ────────────────────────────────────
class SessionListView(generics.ListAPIView):
    """GET — liste les sessions actives (non révoquées) de l'utilisateur
    connecté, scopées à sa société. La session courante (déduite du cookie
    refresh) est marquée ``is_current`` pour l'affichage « cet appareil »."""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserSessionSerializer
    pagination_class = None

    def get_queryset(self):
        user = self.request.user
        qs = UserSession.objects.filter(user=user, revoked=False)
        # Garde multi-tenant : ne jamais sortir de la société de l'utilisateur.
        if user.company_id:
            qs = qs.filter(company=user.company)
        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['current_jti'] = _refresh_jti(
            self.request.COOKIES.get('refresh_token'))
        return ctx


class SessionRevokeView(APIView):
    """POST /auth/sessions/<pk>/revoke/ — révoque une session de l'utilisateur
    connecté : marque la ligne ``revoked`` ET blackliste son jeton de
    rafraîchissement pour qu'il ne puisse plus rafraîchir d'accès."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        user = request.user
        session = UserSession.objects.filter(
            pk=pk, user=user, revoked=False).first()
        # Scope multi-tenant supplémentaire.
        if session is not None and user.company_id \
                and session.company_id != user.company_id:
            session = None
        if session is None:
            return Response(
                {'detail': 'Session introuvable.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        _blacklist_refresh_jti(session.jti)
        session.revoked = True
        session.save(update_fields=['revoked'])
        # Si l'utilisateur révoque SA session courante, on efface ses cookies
        # pour le déconnecter immédiatement de cet appareil.
        current_jti = _refresh_jti(request.COOKIES.get('refresh_token'))
        response = Response({'detail': 'Session révoquée.'})
        if current_jti and current_jti == session.jti:
            _clear_auth_cookies(response)
        return response


# ── Changement / rotation du mot de passe (N96) ────────────────────────────
class ChangePasswordView(APIView):
    """POST — change le mot de passe de l'utilisateur connecté.

    Corps : ``{"current_password": "...", "new_password": "..."}``. Vérifie le
    mot de passe courant, applique les validateurs Django, pose le nouveau,
    horodate ``password_changed_at`` et efface le drapeau de rotation forcée
    ``must_change_password``. Sert aussi bien au changement volontaire qu'au
    flux de rotation forcée déclenché par un administrateur."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError as DjValidationError
        from django.utils import timezone
        user = request.user
        current = request.data.get('current_password', '')
        new = request.data.get('new_password', '')
        if not user.check_password(current):
            return Response(
                {'detail': 'Mot de passe actuel incorrect.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not new:
            return Response(
                {'detail': 'Le nouveau mot de passe est requis.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            validate_password(new, user=user)
        except DjValidationError as exc:
            return Response(
                {'detail': ' '.join(exc.messages)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # FG22 — politique par société (longueur/complexité) en plus des
        # validateurs Django. Inerte tant que la société n'a rien durci.
        from .password_policy import validate_password_policy
        policy_errors = validate_password_policy(
            new, getattr(user, 'company', None))
        if policy_errors:
            return Response(
                {'detail': ' '.join(policy_errors)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.set_password(new)
        user.must_change_password = False
        user.password_changed_at = timezone.now()
        user.save(update_fields=[
            'password', 'must_change_password', 'password_changed_at'])
        # NTSEC30 — notification obligatoire de changement de sécurité.
        try:
            from apps.notifications.services import notify_security_change
            notify_security_change(
                user, 'Mot de passe modifié',
                'Le mot de passe de votre compte vient d\'être modifié. Si '
                'vous n\'êtes pas à l\'origine de ce changement, contactez '
                'immédiatement votre administrateur.')
        except Exception:
            pass
        # VX242 — un changement de mot de passe doit révoquer toute AUTRE
        # session active (blackliste son jeton de rafraîchissement) : sans
        # cela, un attaquant qui a compromis le compte garde son refresh
        # jusqu'à expiration (jusqu'à 7 j) alors que la machinerie de
        # révocation existe déjà (SessionRevokeView / _blacklist_refresh_jti),
        # simplement jamais invoquée depuis ce chemin. La session COURANTE
        # (celle qui vient de changer le mot de passe) reste active.
        current_jti = _refresh_jti(request.COOKIES.get('refresh_token'))
        other_sessions = UserSession.objects.filter(user=user, revoked=False)
        if current_jti:
            other_sessions = other_sessions.exclude(jti=current_jti)
        sessions_revoked = 0
        for session in other_sessions:
            _blacklist_refresh_jti(session.jti)
            session.revoked = True
            session.save(update_fields=['revoked'])
            sessions_revoked += 1
        detail = 'Mot de passe mis à jour.'
        if sessions_revoked:
            detail += (
                f' {sessions_revoked} autre'
                f'{"s" if sessions_revoked > 1 else ""} session'
                f'{"s" if sessions_revoked > 1 else ""} déconnectée'
                f'{"s" if sessions_revoked > 1 else ""}.'
            )
        return Response({
            'detail': detail,
            'sessions_revoked': sessions_revoked,
        })
