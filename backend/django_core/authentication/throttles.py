from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    """Max 5 tentatives de connexion par minute par IP."""
    scope = 'login'


class RegisterRateThrottle(AnonRateThrottle):
    """Max 3 inscriptions par heure par IP."""
    scope = 'register'


class GesteSecuriteParUtilisateurThrottle(UserRateThrottle):
    """ASEC5 — max 5 gestes de sécurité par heure et par UTILISATEUR
    (désactivation 2FA, changement de mot de passe) : borne le devinement du
    mot de passe/du code depuis une session volée, quelle que soit l'IP.

    Taux posé ici (pas dans ``DEFAULT_THROTTLE_RATES``) : aucun réglage à
    toucher. Un compteur par vue (``scope`` distinct) pour que l'un ne
    consomme pas le quota de l'autre."""
    rate = '5/hour'

    def get_rate(self):
        return self.rate


class Desactivation2FAThrottle(GesteSecuriteParUtilisateurThrottle):
    scope = 'asec5_desactivation_2fa'


class ChangementMotDePasseThrottle(GesteSecuriteParUtilisateurThrottle):
    scope = 'asec5_changement_mdp'
