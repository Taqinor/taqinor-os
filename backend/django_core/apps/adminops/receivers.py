"""apps.adminops.receivers — récepteurs internes (best-effort, jamais
bloquants), câblés depuis `apps.py::ready()`.

NTADM8 — alerte de franchissement du quota de sièges : à chaque création d'un
CustomUser ACTIF, si le nombre de sièges utilisés atteint/dépasse
``CompanyProfile.nb_sieges_max``, notifie chaque Administrateur actif de la
société. JAMAIS BLOQUANT : la création du compte a déjà réussi quand ce
récepteur s'exécute (``post_save``) — aucune exception ici ne peut l'annuler.
``authentication`` est une app de FONDATION (exempte de la frontière
cross-app inter-domaines métier) : l'import direct de son modèle est
autorisé."""
from django.db.models.signals import post_save


def _statut_sieges(company):
    from apps.parametres.models import CompanyProfile
    from authentication.services import sieges_utilises

    profile = CompanyProfile.get(company=company)
    max_sieges = profile.nb_sieges_max
    if not max_sieges:
        return None  # illimité (défaut) — rien à signaler
    utilises = sieges_utilises(company)
    if utilises < max_sieges:
        return None  # sous le quota — rien à signaler
    return utilises, max_sieges


def _alerter_administrateurs(company, utilises, max_sieges):
    try:
        from authentication.models import CustomUser
        from apps.notifications.models import EventType
        from apps.notifications.services import notify_many
        admins = list(CustomUser.admins_actifs_qs(company))
        notify_many(
            admins, EventType.DIGEST, 'Quota de sièges atteint',
            body=(f'Vous avez atteint votre quota de {max_sieges} sièges — '
                  'contactez-nous pour l\'augmenter.'),
            company=company)
    except Exception:  # noqa: BLE001 — jamais bloquant
        pass


def user_post_save_quota_sieges(sender, instance, created, **kwargs):
    if not created or not instance.is_active:
        return
    company = getattr(instance, 'company', None)
    if company is None:
        return
    try:
        resultat = _statut_sieges(company)
    except Exception:  # noqa: BLE001 — jamais bloquant
        return
    if resultat is None:
        return
    utilises, max_sieges = resultat
    _alerter_administrateurs(company, utilises, max_sieges)


def connect():
    """Branche tous les récepteurs. Appelé depuis AppConfig.ready()."""
    from authentication.models import CustomUser
    post_save.connect(
        user_post_save_quota_sieges, sender=CustomUser,
        dispatch_uid='adminops_quota_sieges')
