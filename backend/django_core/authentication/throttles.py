from rest_framework.throttling import AnonRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    """Max 5 tentatives de connexion par minute par IP."""
    scope = 'login'


class RegisterRateThrottle(AnonRateThrottle):
    """Max 3 inscriptions par heure par IP."""
    scope = 'register'
