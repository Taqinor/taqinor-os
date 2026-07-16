"""apps.credit.services — écritures/orchestration métier crédit."""
from decimal import Decimal


def verifier_hold_credit(client, montant_transaction=None):
    """NTCRD6 — verdict de hold crédit pour ``client`` face à une transaction
    proposée (devis à accepter, BC à créer) de ``montant_transaction`` (TTC).

    Combine la ``LimiteCredit`` active du client + son encours réel
    (``selectors.encours_client``) + le montant de la transaction proposée.
    En mode ``avertissement`` (défaut), ``autorise`` reste TOUJOURS ``True`` —
    jamais bloquant sans opt-in explicite. Sans ``LimiteCredit`` (ou
    ``montant_limite`` non défini), toujours autorisé (illimité — comportement
    historique inchangé).

    Renvoie ``{'autorise': bool, 'mode': str, 'depassement': Decimal,
    'disponible': Decimal|None}``.
    """
    from .models import LimiteCredit

    montant_transaction = Decimal(montant_transaction or 0)
    limite_obj = LimiteCredit.objects.filter(client=client, actif=True).first()

    if limite_obj is None or limite_obj.montant_limite is None:
        return {
            'autorise': True, 'mode': LimiteCredit.ModeHold.AUCUN,
            'depassement': Decimal('0'), 'disponible': None,
        }

    from .selectors import encours_client

    encours = encours_client(client)
    disponible = limite_obj.montant_limite - encours
    depassement_apres = (encours + montant_transaction) - limite_obj.montant_limite
    depassement = depassement_apres if depassement_apres > 0 else Decimal('0')
    mode = limite_obj.mode_hold

    if mode == LimiteCredit.ModeHold.BLOCAGE:
        autorise = depassement <= 0
    else:
        # 'aucun' et 'avertissement' : jamais bloquant.
        autorise = True

    return {
        'autorise': autorise, 'mode': mode, 'depassement': depassement,
        'disponible': disponible,
    }
