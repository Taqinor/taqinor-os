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

    from .selectors import derogation_valide_pour, encours_client

    encours = encours_client(client)
    disponible = limite_obj.montant_limite - encours
    depassement_apres = (encours + montant_transaction) - limite_obj.montant_limite
    depassement = depassement_apres if depassement_apres > 0 else Decimal('0')
    mode = limite_obj.mode_hold

    if mode == LimiteCredit.ModeHold.BLOCAGE:
        # NTCRD9 — une dérogation approuvée non expirée couvrant ce montant
        # lève le hold de blocage pour cette transaction précise.
        if depassement <= 0:
            autorise = True
        else:
            autorise = derogation_valide_pour(client, montant_transaction)
    else:
        # 'aucun' et 'avertissement' : jamais bloquant.
        autorise = True

    return {
        'autorise': autorise, 'mode': mode, 'depassement': depassement,
        'disponible': disponible,
    }


def creer_demande_derogation(client, montant_demande, *, motif='', user=None,
                             devis=None, company=None):
    """NTCRD9 — crée une demande de dérogation crédit (statut ``en_attente``).

    La société est posée côté serveur (jamais lue du corps) : par défaut celle
    du client."""
    from .models import DerogationCredit

    return DerogationCredit.objects.create(
        company=company or client.company, client=client,
        montant_demande=montant_demande, motif=motif or '', demandeur=user,
        devis=devis)


def approuver_derogation(derogation, user, *, jours_validite=30):
    """NTCRD9 — approuve une dérogation : statut ``approuvee`` + fenêtre de
    validité (défaut 30 jours à compter de MAINTENANT). Réservé côté vue au
    rôle Directeur/Administrateur."""
    from datetime import timedelta

    from django.utils import timezone

    from .models import DerogationCredit

    now = timezone.now()
    derogation.statut = DerogationCredit.Statut.APPROUVEE
    derogation.approuvee_par = user
    derogation.date_decision = now
    derogation.valide_jusqu_au = now + timedelta(days=jours_validite)
    derogation.save(update_fields=[
        'statut', 'approuvee_par', 'date_decision', 'valide_jusqu_au'])
    return derogation


def rejeter_derogation(derogation, user):
    """NTCRD9 — rejette une dérogation (statut ``rejetee`` + décideur/date)."""
    from django.utils import timezone

    from .models import DerogationCredit

    derogation.statut = DerogationCredit.Statut.REJETEE
    derogation.approuvee_par = user
    derogation.date_decision = timezone.now()
    derogation.save(update_fields=['statut', 'approuvee_par', 'date_decision'])
    return derogation
