"""AMSG61 (C-AMSG-010) — enveloppe de destinataires autour du backend e-mail RÉEL.

Le seul goulot commun à tous les envois (notify, automatisations, ventes, ``send_mail``
directs) est ``settings.EMAIL_BACKEND`` : il désigne cette enveloppe, qui délègue à
``settings.EMAIL_BACKEND_REEL``. Hors production (``DEBUG``) ou dès qu'une liste
``EMAIL_DESTINATAIRES_AUTORISES`` est posée, seuls ses destinataires sont remis ; un
domaine réservé (RFC 2606 / 6761) ne l'est jamais. Un destinataire écarté laisse une
ligne de journal sans contenu, l'adresse masquée.
"""
import copy
import logging
from email.utils import parseaddr

from django.conf import settings
from django.core.mail import get_connection
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

ENVELOPPE_EMAIL = 'core.email_backends.EnveloppeEmailBackend'
_TLD_RESERVES = {'invalid', 'test', 'local', 'localhost', 'example'}
_DOMAINES_RESERVES = ('example.com', 'example.net', 'example.org')


def backend_reel(backend=None):
    """Le backend qui remet VRAIMENT : sous l'enveloppe, ``EMAIL_BACKEND_REEL``."""
    if backend is None:
        backend = getattr(settings, 'EMAIL_BACKEND', '') or ''
    backend = str(backend).strip()
    if backend == ENVELOPPE_EMAIL:
        return str(getattr(settings, 'EMAIL_BACKEND_REEL', '') or '').strip()
    return backend


def destinataire_permis(adresse):
    """Faux pour un domaine réservé ; en mode restreint, vrai seulement pour la liste."""
    adresse = parseaddr(str(adresse or ''))[1].strip().lower()
    domaine = adresse.rpartition('@')[2].rstrip('.')
    if not domaine or domaine.rsplit('.', 1)[-1] in _TLD_RESERVES \
            or any(domaine == d or domaine.endswith('.' + d) for d in _DOMAINES_RESERVES):
        return False
    liste = {str(a).strip().lower() for a in getattr(settings, 'EMAIL_DESTINATAIRES_AUTORISES', ()) or ()}
    if liste or settings.DEBUG:
        return adresse in liste
    return True


def _masque(adresse):
    nom, _, domaine = parseaddr(str(adresse or ''))[1].partition('@')
    return f'{nom[:1]}***@{domaine}'


class EnveloppeEmailBackend(BaseEmailBackend):
    """Filtre ``to`` / ``cc`` / ``bcc`` puis délègue au backend réel."""

    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently)
        reel = backend_reel(ENVELOPPE_EMAIL)
        if not reel or reel == ENVELOPPE_EMAIL:  # jamais d'enveloppe dans l'enveloppe
            reel = 'django.core.mail.backends.console.EmailBackend'
        self.reel = get_connection(reel, fail_silently=fail_silently, **kwargs)

    def open(self):
        return self.reel.open()

    def close(self):
        return self.reel.close()

    def send_messages(self, email_messages):
        remis = []
        for message in email_messages or []:
            message = copy.copy(message)
            for champ in ('to', 'cc', 'bcc'):
                gardes = []
                for adresse in getattr(message, champ, None) or []:
                    if destinataire_permis(adresse):
                        gardes.append(adresse)
                    else:
                        logger.warning('E-mail non remis (destinataire hors liste autorisée) : %s',
                                       _masque(adresse))
                setattr(message, champ, gardes)
            if message.recipients():
                remis.append(message)
        return self.reel.send_messages(remis) if remis else 0
