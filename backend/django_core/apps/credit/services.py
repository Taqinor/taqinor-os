"""apps.credit.services — écritures/orchestration métier crédit."""
from decimal import Decimal


def role_peut_bypass_hold(user, company):
    """NTCRD31 — vrai si le rôle de ``user`` figure dans
    ``ReglageCredit.roles_bypass_hold`` de ``company`` (liste de noms de rôles),
    l'autorisant à passer outre un hold de blocage SANS dérogation formelle.
    Défaut vide = personne (comportement actuel inchangé)."""
    if user is None:
        return False
    from .models import ReglageCredit

    reglage = ReglageCredit.objects.filter(company=company).first()
    roles = (reglage.roles_bypass_hold if reglage else None) or []
    if not roles:
        return False
    role = getattr(user, 'role', None)
    return bool(role and role.nom in roles)


def verifier_hold_credit(client, montant_transaction=None, user=None):
    """NTCRD6 — verdict de hold crédit pour ``client`` face à une transaction
    proposée (devis à accepter, BC à créer) de ``montant_transaction`` (TTC).

    Combine la ``LimiteCredit`` active du client + son encours réel
    (``selectors.encours_client``) + le montant de la transaction proposée.
    En mode ``avertissement`` (défaut), ``autorise`` reste TOUJOURS ``True`` —
    jamais bloquant sans opt-in explicite. Sans ``LimiteCredit`` (ou
    ``montant_limite`` non défini), toujours autorisé (illimité — comportement
    historique inchangé).

    NTCRD30 — un dépassement inférieur au seuil de tolérance société
    (``ReglageCredit.seuil_tolerance_depassement``) n'est jamais bloquant.
    NTCRD31 — un ``user`` d'un rôle listé dans ``roles_bypass_hold`` passe
    outre un blocage sans dérogation (le champ ``bypass_role`` du verdict le
    signale à l'appelant, qui journalise — NTCRD31/44).

    Renvoie ``{'autorise': bool, 'mode': str, 'depassement': Decimal,
    'disponible': Decimal|None, 'bypass_role': bool}``.
    """
    from .models import LimiteCredit

    montant_transaction = Decimal(montant_transaction or 0)
    limite_obj = LimiteCredit.objects.filter(client=client, actif=True).first()

    if limite_obj is None or limite_obj.montant_limite is None:
        return {
            'autorise': True, 'mode': LimiteCredit.ModeHold.AUCUN,
            'depassement': Decimal('0'), 'disponible': None,
            'bypass_role': False,
        }

    from .models import ReglageCredit
    from .selectors import derogation_valide_pour, encours_client

    encours = encours_client(client)
    disponible = limite_obj.montant_limite - encours
    depassement_apres = (encours + montant_transaction) - limite_obj.montant_limite
    depassement = depassement_apres if depassement_apres > 0 else Decimal('0')
    mode = limite_obj.mode_hold

    reglage = ReglageCredit.objects.filter(company=client.company).first()
    tolerance = (
        reglage.seuil_tolerance_depassement if reglage else Decimal('0')
    ) or Decimal('0')

    bypass_role = False
    if mode == LimiteCredit.ModeHold.BLOCAGE:
        if depassement <= 0:
            autorise = True
        elif depassement <= tolerance:
            # NTCRD30 — grâce automatique petits montants.
            autorise = True
        elif derogation_valide_pour(client, montant_transaction):
            # NTCRD9 — dérogation approuvée non expirée.
            autorise = True
        elif role_peut_bypass_hold(user, client.company):
            # NTCRD31 — bypass rôle (tracé par l'appelant).
            autorise = True
            bypass_role = True
        else:
            autorise = False
    else:
        # 'aucun' et 'avertissement' : jamais bloquant.
        autorise = True

    return {
        'autorise': autorise, 'mode': mode, 'depassement': depassement,
        'disponible': disponible, 'bypass_role': bypass_role,
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


def importer_limites_csv(company, file_bytes, filename, *, user=None):
    """NTCRD39 — import CSV/XLSX en masse de limites de crédit initiales.

    Réutilise le PARSEUR de ``apps.dataimport`` (``parsing.iter_rows`` —
    importable, jamais une édition de ``dataimport.services``). Colonnes
    attendues : ``client`` (email OU id), ``montant_limite``, ``mode_hold``
    (optionnel). Validation LIGNE À LIGNE : un client introuvable met la ligne
    en erreur sans bloquer le batch. Idempotent par (company, client) —
    ``update_or_create``. Renvoie ``{'crees': int, 'erreurs': [{ligne, motif}]}``.
    """
    from apps.crm.selectors import find_client_by_email, get_company_client
    from apps.dataimport.parsing import iter_rows, normalize_header

    from .models import LimiteCredit

    _headers, rows = iter_rows(file_bytes, filename)
    modes_valides = {c.value for c in LimiteCredit.ModeHold}

    crees = 0
    erreurs = []
    for idx, row in enumerate(rows, start=1):
        norm = {normalize_header(k): v for k, v in row.items()}
        ref = (norm.get('client') or '').strip()
        montant_raw = (norm.get('montant_limite') or norm.get('montant') or '').strip()
        mode = (norm.get('mode_hold') or '').strip().lower()

        client = None
        if ref.isdigit():
            client = get_company_client(company, int(ref))
        if client is None and '@' in ref:
            client = find_client_by_email(ref, company)
        if client is None:
            erreurs.append({'ligne': idx, 'motif': f'Client introuvable : {ref!r}'})
            continue

        try:
            montant = Decimal(montant_raw) if montant_raw else None
        except Exception:
            erreurs.append({'ligne': idx, 'motif': f'Montant invalide : {montant_raw!r}'})
            continue

        defaults = {'company': company, 'montant_limite': montant, 'cree_par': user}
        if mode in modes_valides:
            defaults['mode_hold'] = mode
        LimiteCredit.objects.update_or_create(client=client, defaults=defaults)
        crees += 1

    return {'crees': crees, 'erreurs': erreurs}


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
