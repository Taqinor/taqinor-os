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


def log_facture_avoir(facture, user, avoir):
    """Consigne la création d'un avoir dans le chatter de la facture.

    Acteur et société toujours posés côté serveur (jamais du corps de requête).
    """
    from .models import FactureActivity
    montant = getattr(avoir, 'total_ttc', None)
    detail = f"Avoir {avoir.reference} créé"
    if montant is not None:
        detail += f" ({montant} MAD TTC)"
    return FactureActivity.objects.create(
        company=facture.company, facture=facture, user=user,
        kind=FactureActivity.Kind.MODIFICATION,
        field='avoir', field_label='Avoir',
        new_value=avoir.reference, body=detail + '.',
    )


def log_facture_paiement(facture, user, paiement):
    """Consigne l'encaissement d'un paiement dans le chatter de la facture."""
    from .models import FactureActivity
    mode = paiement.get_mode_display() if hasattr(paiement, 'get_mode_display') \
        else (getattr(paiement, 'mode', '') or '')
    detail = f"Paiement encaissé : {paiement.montant} MAD"
    if mode:
        detail += f" ({mode})"
    return FactureActivity.objects.create(
        company=facture.company, facture=facture, user=user,
        kind=FactureActivity.Kind.MODIFICATION,
        field='paiement', field_label='Paiement',
        new_value=str(paiement.montant), body=detail + '.',
    )
