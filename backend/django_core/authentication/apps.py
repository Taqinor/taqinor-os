from django.apps import AppConfig


class AuthenticationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'authentication'
    verbose_name = 'Authentification'
    module_manifest = {
        'key': 'authentication',
        'label': 'Authentification',
        'icone': 'key',
        'depends': [],
        'installable': False,
        'description': 'Comptes, sociétés et authentification.',
        'categorie': 'Technique',
    }

    def ready(self):
        # SCA20 — enregistre les hooks de seed « nouvelle société » (types
        # d'activité + niveaux de relance) migrés depuis les seeds INLINE de
        # RegisterCompanyView. Import local : jamais d'effet de bord à l'import.
        from .signup_seeds import register_authentication_signup_hooks
        register_authentication_signup_hooks()
