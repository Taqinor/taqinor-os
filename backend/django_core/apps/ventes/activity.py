"""Chatter d'un devis (N25) — même patron que apps/installations/activity.py.

Notes manuelles + trace d'acceptation. Utilisateur et société toujours posés
côté serveur.
"""
from .models import DevisActivity


def log_devis_note(devis, user, body):
    return DevisActivity.objects.create(
        company=devis.company, devis=devis, user=user,
        kind=DevisActivity.Kind.NOTE, body=body,
    )


def log_devis_acceptance(devis, user, nom, date_acceptation, option=''):
    """Consigne l'acceptation du devis (qui + quand + option) dans son chatter.

    ``option`` est la valeur OptionAcceptee retenue (A1) ; on l'affiche en clair
    (« Sans batterie » / « Avec batterie ») quand elle est renseignée.
    """
    from .models import Devis
    qui = (nom or '').strip() or getattr(user, 'username', '?')
    opt_label = dict(Devis.OptionAcceptee.choices).get(option or '', '')
    suffixe = f" — option : {opt_label}" if opt_label else ''
    return DevisActivity.objects.create(
        company=devis.company, devis=devis, user=user,
        kind=DevisActivity.Kind.MODIFICATION,
        field='statut', field_label='Acceptation',
        old_value='',
        new_value=f"Accepté le {date_acceptation} par {qui}{suffixe}",
        body=f"Devis accepté le {date_acceptation} par {qui}{suffixe}.",
    )
