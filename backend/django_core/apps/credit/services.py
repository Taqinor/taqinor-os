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


def _html_position_credit(client):
    """NTCRD25 — construit le fragment HTML du rapport interne « Position
    crédit client » (filigrane USAGE INTERNE). AUCUNE donnée ``prix_achat``/
    marge — document de contrôle interne réservé Direction/Finance. Testable
    sans WeasyPrint (rendu HTML pur)."""
    from html import escape

    from apps.ventes.selectors import encours_clients_par_tiers

    from .selectors import fiche_credit

    fiche = fiche_credit(client)
    nom = escape(f"{client.prenom or ''} {client.nom}".strip())

    # Détail des factures ouvertes (references) — via le sélecteur ventes
    # existant (jamais un import de ventes.models).
    factures_lignes = ''
    for entry in encours_clients_par_tiers(client.company):
        if entry['tiers_id'] == client.id:
            for ref in entry['references']:
                factures_lignes += f'<li>{escape(str(ref))}</li>'

    def _mad(value):
        if value is None:
            return '—'
        return f'{value} MAD'

    derogations_html = ''.join(
        f"<li>{_mad(d['montant_demande'])} — {escape(str(d['statut']))}</li>"
        for d in fiche['derogations']
    ) or '<li>Aucune</li>'

    return f"""
    <html><head><meta charset="utf-8">
    <style>
      .filigrane {{ color:#c00; font-weight:bold; letter-spacing:2px; }}
      body {{ font-family: sans-serif; font-size: 12px; }}
      h1 {{ font-size: 18px; }}
    </style></head>
    <body>
      <p class="filigrane">USAGE INTERNE</p>
      <h1>Position crédit — {nom}</h1>
      <p>Limite : {_mad(fiche['limite'])}</p>
      <p>Encours : {_mad(fiche['encours'])}</p>
      <p>Disponible : {_mad(fiche['disponible'])}</p>
      <p>Lettre de score : {escape(str(fiche['lettre_score']))}</p>
      <p>Mode de hold : {escape(str(fiche['mode_hold'] or 'aucun'))}</p>
      <h2>Factures ouvertes</h2>
      <ul>{factures_lignes or '<li>Aucune</li>'}</ul>
      <h2>Dérogations</h2>
      <ul>{derogations_html}</ul>
    </body></html>
    """


def generer_pdf_position_credit(client):
    """NTCRD25 — rend le PDF interne « Position crédit client » via le service
    PDF partagé (``core.pdf.render_pdf`` — moteur WeasyPrint legacy, JAMAIS
    ``/proposal``/quote_engine : ce n'est pas un document client). Renvoie des
    bytes."""
    from core.pdf import render_pdf

    return render_pdf(html=_html_position_credit(client))
