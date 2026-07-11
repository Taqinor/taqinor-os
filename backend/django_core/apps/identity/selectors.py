"""Sélecteurs de lecture de la fondation identité (NTSEC).

Point d'entrée LECTURE unique pour que le reste du backend (login
authentication, middleware…) interroge l'état SSO d'une société SANS importer
les modèles ``identity`` directement. Toutes les fonctions sont best-effort et
défensives : si l'app/les tables n'existent pas encore, elles retombent sur
« pas d'IdP » (comportement historique inchangé).
"""


def active_provider(company, protocol=None):
    """IdP ACTIF d'une société (optionnellement filtré par protocole), ou None.

    Ne renvoie qu'un fournisseur ``actif=True``. Sans ``protocol``, renvoie le
    premier IdP actif trouvé (l'unicité partielle garantit au plus un par
    protocole). Best-effort : toute erreur → None (login local intact)."""
    if company is None:
        return None
    try:
        from .models import IdentityProvider
        qs = IdentityProvider.objects.filter(company=company, actif=True)
        if protocol:
            qs = qs.filter(protocol=protocol)
        return qs.first()
    except Exception:  # noqa: BLE001 — best-effort : jamais bloquer le login
        return None


def is_break_glass(user):
    """True si ``user`` bénéficie d'un accès d'urgence break-glass actif (NTSEC22).

    Un compte break-glass CONTOURNE ``enforce_sso`` (NTSEC4). Tant que le modèle
    ``BreakGlassGrant`` (NTSEC22) n'est pas encore branché, cette fonction
    renvoie False (aucun contournement) et NTSEC22 la câblera sur ses octrois
    actifs non révoqués et non échus. Best-effort : toute erreur → False.
    """
    if user is None:
        return False
    try:
        from django.utils import timezone
        from .models import BreakGlassGrant
        now = timezone.now()
        return BreakGlassGrant.objects.filter(
            user_id=getattr(user, 'pk', None),
            revoque_le__isnull=True,
            active_jusqu_a__gt=now,
        ).exists()
    except Exception:  # noqa: BLE001 — modèle absent (avant NTSEC22) ou erreur
        return False


def enforce_sso_active(company):
    """True si la société a un IdP ACTIF avec ``enforce_sso=True`` (NTSEC4).

    Sert au backend de login local à décider s'il doit refuser le mot de passe.
    Fail-open : sans IdP actif enforce, renvoie False (login local autorisé)."""
    if company is None:
        return False
    try:
        from .models import IdentityProvider
        return IdentityProvider.objects.filter(
            company=company, actif=True, enforce_sso=True).exists()
    except Exception:  # noqa: BLE001 — best-effort : fail-open
        return False
