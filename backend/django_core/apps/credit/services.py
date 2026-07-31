"""apps.credit.services — écritures/orchestration métier crédit.

WIR93 — DÉCISION CONSIGNÉE : COEXISTENCE DOCUMENTÉE ET VERROUILLÉE
------------------------------------------------------------------
Deux moteurs de limite/hold crédit existent dans le dépôt :

  A. ``apps.credit`` — ``LimiteCredit`` / ``ReglageCredit`` +
     ``verifier_hold_credit`` (NTCRD6), encours via
     ``apps.credit.selectors.encours_client`` → point d'entrée cross-app
     ``apps.ventes.selectors.encours_ouvert_par_tiers`` (NTCRD4).
  B. ``crm.Client.plafond_credit`` / ``CompanyProfile.credit_hold_actif`` —
     ``apps.ventes.services.verifier_credit_hold`` (FG41/XFAC28), encours
     calculé en ligne par ``apps.crm.selectors.client_credit_warning``.

État réel au moment de la décision : le moteur A n'a AUCUN appelant de
production (les hooks NTCRD7/NTCRD8 sont ``[BLOCKED: hors périmètre]``) ; seul
le moteur B est branché (acceptation de devis + génération de tranches). Il n'y
a donc PAS de double-décision en production aujourd'hui.

Décision retenue (option « coexistence documentée + testée non-divergente » de
WIR93 ; la bascule vers une source unique reste ouverte au fondateur) :

  1. ``apps.ventes.selectors.encours_ouvert_par_tiers`` est le calcul d'encours
     de RÉFÉRENCE (le seul point d'entrée cross-app sanctionné vers les
     factures). Le moteur A le consomme déjà.
  2. Le moteur B assume une assiette VOLONTAIREMENT PLUS ÉTROITE : uniquement
     les factures ``emise`` / ``en_retard``. C'est le seul écart autorisé.
  3. ``ecart_encours_moteurs()`` (ci-dessous) matérialise ce contrat et est
     verrouillé par ``apps/credit/tests/test_wir93_encours_non_divergence.py`` :
     hors factures ``brouillon``, les deux moteurs DOIVENT renvoyer le même
     encours au centime. Toute dérive future (nouveau statut, changement
     d'assiette d'un seul côté) rend ce test rouge.
"""
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


def ecart_encours_moteurs(client):
    """WIR93 — compare les deux calculs d'encours et matérialise le SEUL écart
    autorisé entre les deux moteurs de crédit (voir la décision en tête de
    module). Lecture pure, aucune écriture, borné au client fourni.

    Renvoie ::

        {
          'encours_credit': Decimal,   # moteur A (apps.credit / NTCRD4)
          'encours_ventes': Decimal,   # moteur B (FG41/XFAC28)
          'ecart': Decimal,            # A − B
          'ecart_attendu': Decimal,    # reste dû des factures « brouillon »
          'divergent': bool,           # True si l'écart n'est PAS expliqué
        }

    ``divergent=True`` signifie qu'un des deux moteurs a changé d'assiette sans
    l'autre — c'est exactement ce que le test de non-divergence interdit.
    """
    from apps.crm.selectors import client_credit_warning
    from apps.ventes.selectors import reste_du_factures_brouillon
    from .selectors import encours_client

    encours_credit = Decimal(encours_client(client) or 0)
    encours_ventes = Decimal(
        client_credit_warning(client).get('encours') or 0)
    ecart = encours_credit - encours_ventes
    ecart_attendu = Decimal(reste_du_factures_brouillon(client.company, client.pk) or 0)
    return {
        'encours_credit': encours_credit,
        'encours_ventes': encours_ventes,
        'ecart': ecart,
        'ecart_attendu': ecart_attendu,
        'divergent': ecart != ecart_attendu,
    }


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
    _log_decision_derogation(derogation, user, 'approuvée')
    return derogation


def _log_decision_derogation(derogation, user, verbe):
    """NTCRD43 — journalise la décision de dérogation dans le chatter records
    UNIFIÉ, rattaché au CLIENT (une seule source d'enregistrement, visible dans
    le fil d'activité générique du client). Best-effort, jamais bloquant.
    NTCRD44 — trace aussi l'action dans ``audit.AuditLog``."""
    try:
        from apps.crm.selectors import get_company_client
        from apps.records.services import log_note

        client = get_company_client(derogation.company, derogation.client_id)
        if client is not None:
            log_note(
                client, user,
                f'Dérogation crédit {verbe} : {derogation.montant_demande} MAD.',
                company=derogation.company)
    except Exception:  # pragma: no cover - journalisation best-effort
        pass
    audit_credit(
        derogation, f'Dérogation crédit {verbe}', user=user,
        company=derogation.company)


def audit_credit(instance, detail, *, user=None, company=None):
    """NTCRD44 — écrit une entrée ``audit.AuditLog`` pour une action sensible
    crédit (best-effort, jamais bloquant) — réutilise le service d'audit
    existant, jamais un log applicatif parallèle."""
    try:
        from apps.audit.models import AuditLog
        from apps.audit.recorder import record

        record(
            AuditLog.Action.STATUS, instance=instance, detail=detail,
            user=user, company=company)
    except Exception:  # pragma: no cover - audit best-effort
        pass


def rejeter_derogation(derogation, user):
    """NTCRD9 — rejette une dérogation (statut ``rejetee`` + décideur/date)."""
    from django.utils import timezone

    from .models import DerogationCredit

    derogation.statut = DerogationCredit.Statut.REJETEE
    derogation.approuvee_par = user
    derogation.date_decision = timezone.now()
    derogation.save(update_fields=['statut', 'approuvee_par', 'date_decision'])
    _log_decision_derogation(derogation, user, 'rejetée')
    return derogation


def _lire_lignes_limites_csv(company, file_bytes, filename):
    """Parse + valide-rapproche chaque ligne d'un import de limites de crédit,
    SANS RIEN ÉCRIRE. Partagé par l'aperçu et l'écriture (``importer_limites_csv``)
    pour qu'ils ne puissent jamais diverger sur le rapprochement.

    Renvoie ``(total_lignes, resultats, erreurs)`` où chaque élément de
    ``resultats`` est ``{'ligne', 'client', 'row', 'fields', 'existing'}`` —
    ``fields`` ne contient QUE les valeurs non vides fournies par la ligne
    (``montant_limite``/``mode_hold``) : une cellule vide n'entre jamais dans
    le diff, donc ne peut jamais écraser ni vider un champ existant.
    """
    from apps.crm.selectors import find_client_by_email, get_company_client
    from apps.dataimport.parsing import iter_rows, normalize_header

    from .models import LimiteCredit

    _headers, rows = iter_rows(file_bytes, filename)
    modes_valides = {c.value for c in LimiteCredit.ModeHold}

    resultats = []
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
            # Quantifié à la précision du champ (2 décimales) AVANT tout
            # diff : sinon un « 50000 » venu du fichier, comparé au
            # « 50000.00 » relu de la base, passerait pour un ÉCRASEMENT
            # alors que c'est la même valeur (faux positif d'aperçu, et
            # refus injustifié en mode remplissage seul).
            montant = (Decimal(montant_raw).quantize(Decimal('0.01'))
                       if montant_raw else None)
        except Exception:
            erreurs.append({'ligne': idx, 'motif': f'Montant invalide : {montant_raw!r}'})
            continue

        # Cellule vide écartée d'emblée : ``fields`` ne porte que ce que la
        # ligne renseigne réellement (jamais une valeur vide qui viderait un
        # champ déjà rempli lors du diff/écriture).
        fields = {}
        if montant_raw:
            fields['montant_limite'] = montant
        if mode in modes_valides:
            fields['mode_hold'] = mode

        existing = LimiteCredit.objects.filter(
            company=company, client=client).first()
        resultats.append({
            'ligne': idx, 'client': client, 'row': row,
            'fields': fields, 'existing': existing,
        })

    return len(rows), resultats, erreurs


def importer_limites_csv(company, file_bytes, filename, *, user=None,
                         apercu=False, ecraser=False):
    """NTCRD39 — import CSV/XLSX en masse de limites de crédit.

    Réutilise le PARSEUR de ``apps.dataimport`` (``parsing.iter_rows`` —
    importable, jamais une édition de ``dataimport.services``). Colonnes
    attendues : ``client`` (email OU id), ``montant_limite``, ``mode_hold``
    (optionnel). Validation LIGNE À LIGNE : un client introuvable met la ligne
    en erreur sans bloquer le batch.

    GARDE-FOU ÉCRASEMENT — réutilise la primitive PLATEFORME
    ``apps.dataimport.services`` (``diff_import``/``appliquer_maj_import``/
    ``enregistrer_job``), jamais un diff/journal maison :

    * une ligne visant un client SANS ``LimiteCredit`` existante CRÉE une
      nouvelle fiche — jamais destructeur, comportement historique inchangé ;
    * une ligne visant un client AVEC une ``LimiteCredit`` déjà existante
      passe par ``appliquer_maj_import`` : ``ecraser=False`` (DÉFAUT) =
      REMPLISSAGE SEUL, un champ déjà rempli (``montant_limite``/
      ``mode_hold``) n'est JAMAIS remplacé — la valeur entrante repart dans
      ``refuses`` ; ``ecraser=True`` (opt-in explicite de l'appelant) applique
      aussi les remplacements, et la valeur PRÉCÉDENTE de chaque champ écrit
      est journalisée (une ligne ``AuditLog`` par fiche via
      ``appliquer_maj_import``, + le lot complet via ``enregistrer_job`` —
      consultable comme n'importe quel ``ImportJob``/``ImportJobRow``) ;
    * ``apercu=True`` (dry-run) rejoue EXACTEMENT le même rapprochement
      (``_lire_lignes_limites_csv``) et le même diff (``diff_import``) SANS
      RIEN ÉCRIRE : pour chaque fiche existante touchée, quel champ serait
      remplacé (ancienne → nouvelle valeur) ;
    * une cellule vide n'écrase ni ne vide jamais un champ déjà rempli
      (écartée avant tout diff par ``_lire_lignes_limites_csv``).

    Renvoie, mode écriture (rétro-compatible) : ``{'crees': int, 'erreurs':
    [{ligne, motif}], 'maj': int, 'ecraser': bool, 'ecrasements': [...],
    'refuses': [...], 'job_id': int}``. Mode ``apercu`` : ``{'apercu': True,
    'ecraser': bool, 'total_lignes': int, 'creations': int, 'maj': int,
    'erreurs': [...], 'conflits': [{ligne, client_id, client, ecrasements,
    remplissages}]}``.
    """
    from apps.dataimport.services import (
        appliquer_maj_import, diff_import, enregistrer_job)

    total_lignes, resultats, erreurs = _lire_lignes_limites_csv(
        company, file_bytes, filename)

    if apercu:
        creations = 0
        maj = 0
        conflits = []
        for r in resultats:
            if r['existing'] is None:
                creations += 1
                continue
            maj += 1
            ecrasements, remplissages = diff_import(r['existing'], r['fields'])
            if ecrasements or remplissages:
                conflits.append({
                    'ligne': r['ligne'],
                    'client_id': r['client'].pk,
                    'client': str(r['client']),
                    'ecrasements': ecrasements,
                    'remplissages': [rp['champ'] for rp in remplissages],
                })
        return {
            'apercu': True, 'ecraser': bool(ecraser),
            'total_lignes': total_lignes, 'creations': creations, 'maj': maj,
            'erreurs': erreurs, 'conflits': conflits,
        }

    from .models import LimiteCredit

    crees = 0
    maj = 0
    ecrasements = []
    refuses = []
    lignes_job = [{'ligne': e['ligne'], 'statut': 'erreur', 'motif': e['motif']}
                  for e in erreurs]

    for r in resultats:
        client, fields, existing = r['client'], r['fields'], r['existing']

        if existing is None:
            defaults = {'company': company, 'cree_par': user, **fields}
            limite = LimiteCredit.objects.create(client=client, **defaults)
            crees += 1
            lignes_job.append({
                'ligne': r['ligne'], 'statut': 'ok',
                'cible': 'credit.limitecredit', 'cible_id': limite.pk,
            })
            continue

        # Compte comme ``_commit_raw`` (dataimport) : une fiche RAPPROCHÉE
        # compte en mise à jour même si le garde-fou a fini par tout refuser
        # (cohérent avec l'aperçu, qui compte de la même façon).
        maj += 1
        _changed, modifications, row_refuses = appliquer_maj_import(
            existing, fields, company, user=user, filename=filename,
            skip_keys=('company', 'client', 'cree_par'), ecraser=ecraser)
        for m in modifications:
            if m['ecrasement']:
                ecrasements.append(dict(m, ligne=r['ligne'], client_id=client.pk))
        for ref in row_refuses:
            refuses.append(dict(ref, ligne=r['ligne'], client_id=client.pk))
        lignes_job.append({
            'ligne': r['ligne'], 'statut': 'ok',
            'cible': 'credit.limitecredit', 'cible_id': existing.pk,
            'modifications': modifications, 'refuses': row_refuses,
        })

    job = enregistrer_job(
        company, 'limites_credit', filename, user=user,
        mode='maj' if maj and not crees else 'creer', ecraser=ecraser,
        total_lignes=total_lignes, created=crees, updated=maj, lignes=lignes_job)

    return {
        'crees': crees, 'erreurs': erreurs, 'maj': maj, 'ecraser': bool(ecraser),
        'ecrasements': ecrasements, 'refuses': refuses, 'job_id': job.pk,
    }


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
