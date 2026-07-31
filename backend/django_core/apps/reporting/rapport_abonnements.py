"""NTEXT12 — envoi PLANIFIÉ des rapports sauvegardés (abonnements).

Une tâche Celery Beat unique (``reporting.envoyer_rapports_planifies``) parcourt
les ``RapportAbonnement`` ACTIFS, garde ceux qui sont DUS, rejoue leur
``RapportDefinition`` (NTEXT10 : ``core.data_explorer.run_query`` + éventuel
``core.pivot.build_pivot``) et envoie le résultat par email.

Principes (règles fondatrices), calqués sur ``reporting.email_saved_reports`` et
``core.scheduled_export`` :
  * NO-OP SÛR — sans canal email configuré, AUCUN envoi réseau : le run est
    journalisé ``non_configure`` sur la ligne, rien d'autre ne se passe ;
  * MULTI-TENANT — chaque rapport est exécuté DANS la société de l'abonnement,
    et les destinataires ``users`` sont résolus dans CETTE société uniquement ;
  * DÉFENSIF / IDEMPOTENT — un abonnement en échec n'arrête pas les suivants, et
    un abonnement déjà exécuté dans l'HEURE courante n'est jamais renvoyé
    (``acks_late`` peut rejouer la tâche après un crash worker) ;
  * aucun texte n'est exécuté : ``cron`` est parsé par un matcheur pur.

GRAIN DE PLANIFICATION = L'HEURE. Le beat tourne à chaque heure pile ; le champ
MINUTE du cron n'entre donc PAS dans la décision « dû ou pas » (« 0 8 * * 1 » et
« 30 8 * * 1 » sont tous deux dus le lundi entre 8 h et 9 h). Les quatre autres
champs (heure, jour du mois, mois, jour de semaine) sont respectés à la lettre.
"""
import csv
import io
import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)

CASABLANCA_TZ = 'Africa/Casablanca'


# ── Cron : matcheur PUR (aucune exécution de texte) ────────────────────────

def _champ_valeurs(champ, borne_min, borne_max):
    """Ensemble des valeurs couvertes par UN champ cron (``*``, ``a,b``,
    ``a-b``, ``*/n``, ``a-b/n``). ``None`` si le champ est illisible."""
    champ = (champ or '').strip()
    if not champ:
        return None
    valeurs = set()
    for morceau in champ.split(','):
        morceau = morceau.strip()
        if not morceau:
            return None
        pas = 1
        if '/' in morceau:
            morceau, _, brut_pas = morceau.partition('/')
            if not brut_pas.isdigit() or int(brut_pas) < 1:
                return None
            pas = int(brut_pas)
            morceau = morceau.strip() or '*'
        if morceau == '*':
            debut, fin = borne_min, borne_max
        elif '-' in morceau:
            brut_debut, _, brut_fin = morceau.partition('-')
            if not (brut_debut.strip().isdigit() and brut_fin.strip().isdigit()):
                return None
            debut, fin = int(brut_debut), int(brut_fin)
        elif morceau.isdigit():
            debut = fin = int(morceau)
        else:
            return None
        if debut > fin or debut < borne_min or fin > borne_max:
            return None
        valeurs.update(range(debut, fin + 1, pas))
    return valeurs


def cron_du(expression, now):
    """L'expression cron 5 champs est-elle DUE à ``now`` (grain = heure) ?

    Champs : ``minute heure jour_du_mois mois jour_de_semaine``. Le champ MINUTE
    est accepté puis IGNORÉ (cf. docstring du module). ``jour_de_semaine`` suit
    la convention cron : 0 = dimanche (7 accepté comme dimanche aussi).
    Expression vide ou illisible → JAMAIS due (aucun envoi surprise).
    """
    champs = (expression or '').split()
    if len(champs) != 5:
        return False
    _minute, heure, jour_mois, mois, jour_semaine = champs
    heures = _champ_valeurs(heure, 0, 23)
    jours_mois = _champ_valeurs(jour_mois, 1, 31)
    moiss = _champ_valeurs(mois, 1, 12)
    jours_semaine = _champ_valeurs(jour_semaine, 0, 7)
    if None in (heures, jours_mois, moiss, jours_semaine):
        return False
    if 7 in jours_semaine:
        jours_semaine = set(jours_semaine) | {0}
    return (now.hour in heures
            and now.day in jours_mois
            and now.month in moiss
            and (now.isoweekday() % 7) in jours_semaine)


def _now_casablanca():
    try:
        from zoneinfo import ZoneInfo
        return timezone.now().astimezone(ZoneInfo(CASABLANCA_TZ))
    except Exception:  # pragma: no cover - zoneinfo absent (très improbable)
        return timezone.localtime()


def _dans_le_fuseau_de(valeur, reference):
    """``valeur`` ramenée dans le fuseau de ``reference`` (tolère le naïf)."""
    if timezone.is_aware(valeur):
        fuseau = (reference.tzinfo if timezone.is_aware(reference)
                  else timezone.get_current_timezone())
        valeur = valeur.astimezone(fuseau)
    return valeur


def _deja_execute_cette_heure(abonnement, now):
    """Idempotence : l'abonnement a-t-il déjà tourné dans l'HEURE courante ?"""
    dernier = abonnement.derniere_execution_le
    if dernier is None:
        return False
    dernier = _dans_le_fuseau_de(dernier, now)
    return (dernier.year, dernier.month, dernier.day, dernier.hour) == (
        now.year, now.month, now.day, now.hour)


def est_du(abonnement, now):
    """L'abonnement doit-il partir maintenant ? (actif + cron dû + pas déjà fait)"""
    if not abonnement.actif:
        return False
    if not cron_du(abonnement.cron, now):
        return False
    return not _deja_execute_cette_heure(abonnement, now)


# ── Destinataires ─────────────────────────────────────────────────────────

def destinataires_emails(abonnement):
    """Adresses email de l'abonnement, dédupliquées et ORDONNÉES.

    Les ``users`` sont résolus DANS la société de l'abonnement : un id d'un
    autre tenant ne résout rien (jamais de fuite cross-société)."""
    brut = abonnement.destinataires or {}
    if isinstance(brut, list):
        brut = {'emails': brut}
    if not isinstance(brut, dict):
        return []

    adresses = []
    for valeur in (brut.get('emails') or []):
        adresse = str(valeur or '').strip()
        if adresse:
            adresses.append(adresse)

    ids = [i for i in (brut.get('users') or []) if i not in (None, '')]
    if ids:
        from django.contrib.auth import get_user_model
        try:
            qs = get_user_model().objects.filter(
                pk__in=ids, company=abonnement.company)
            adresses.extend(
                a for a in qs.values_list('email', flat=True) if a)
        except Exception:  # pragma: no cover - défensif (ids illisibles)
            logger.warning(
                'envoyer_rapports_planifies: destinataires users illisibles '
                '(abonnement %s)', abonnement.pk, exc_info=True)

    vus = set()
    ordonnees = []
    for adresse in adresses:
        if adresse not in vus:
            vus.add(adresse)
            ordonnees.append(adresse)
    return ordonnees


# ── Rendu : rejoue la RapportDefinition puis sérialise ──────────────────────

def executer_definition(rapport_def):
    """Rejoue la définition (NTEXT10) et renvoie ``(lignes, pivot|None)``."""
    from core import data_explorer
    from core.pivot import PivotSpec, build_pivot

    lignes = data_explorer.run_query(
        rapport_def.dataset, rapport_def.company, rapport_def.owner,
        rapport_def.spec or {})
    pivot_spec = rapport_def.pivot_spec or {}
    if not pivot_spec:
        return lignes, None
    return lignes, build_pivot(lignes, PivotSpec(**pivot_spec))


def _lignes_pivot(pivot):
    """Aplatit un tableau croisé en ``(en-têtes, lignes)`` lisibles."""
    colonnes = [','.join(ck) for ck in pivot['col_keys']]
    entetes = ['Ligne'] + colonnes + ['Total']
    lignes = []
    for rk in pivot['row_keys']:
        cle = ','.join(rk)
        cellules = pivot['cells'].get(cle, {})
        lignes.append([cle] + [cellules.get(c, 0) for c in colonnes]
                      + [pivot['row_totals'].get(cle, 0)])
    return entetes, lignes


def _lignes_plates(rows):
    if not rows:
        return [], []
    entetes = list(rows[0].keys())
    return entetes, [[r.get(c, '') for c in entetes] for r in rows]


def rendre_abonnement(abonnement):
    """Rend le rapport de l'abonnement : ``(filename, bytes, content_type)``.

    ``xlsx`` best-effort : si le constructeur partagé n'est pas disponible, on
    dégrade proprement en CSV (jamais d'exception ni de dépendance dure) —
    même politique que ``core.scheduled_export.rendre_extrait`` pour parquet.
    """
    from .models import RapportAbonnement

    rapport_def = abonnement.rapport_def
    rows, pivot = executer_definition(rapport_def)
    entetes, lignes = (_lignes_pivot(pivot) if pivot
                       else _lignes_plates(rows))

    base = rapport_def.titre or rapport_def.dataset or 'rapport'
    sur = ''.join(c for c in base if c.isalnum() or c in ('-', '_')) or 'rapport'

    if abonnement.format == RapportAbonnement.Format.XLSX:
        try:
            from apps.records.xlsx import workbook_bytes
            contenu = workbook_bytes(entetes, lignes, sheet_title=base[:31])
            return (f'{sur}.xlsx', contenu,
                    'application/vnd.openxmlformats-officedocument'
                    '.spreadsheetml.sheet')
        except Exception:  # pragma: no cover - dépend d'openpyxl
            logger.warning(
                'envoyer_rapports_planifies: xlsx indisponible, repli CSV '
                '(abonnement %s)', abonnement.pk, exc_info=True)

    tampon = io.StringIO()
    writer = csv.writer(tampon)
    if entetes:
        writer.writerow(entetes)
    writer.writerows(lignes)
    return f'{sur}.csv', tampon.getvalue().encode('utf-8'), 'text/csv'


# ── Envoi ─────────────────────────────────────────────────────────────────

def _email_configure():
    """Réutilise l'helper de configuration email existant (Brevo/SMTP)."""
    try:
        from apps.ventes.email_service import is_email_configured
        return is_email_configured()
    except Exception:  # pragma: no cover - défensif
        return False


def _envoyer(abonnement, adresses, filename, contenu, content_type):
    from django.conf import settings
    from django.core.mail import EmailMessage, get_connection

    titre = abonnement.rapport_def.titre
    from_email = (getattr(settings, 'DEFAULT_FROM_EMAIL', '')
                  or 'noreply@erp.local')
    message = EmailMessage(
        subject=f'Rapport : {titre}'[:300],
        body=(f'Bonjour,\n\nVeuillez trouver ci-joint le rapport '
              f'« {titre} ».\n\nCordialement.'),
        from_email=from_email, to=adresses,
        connection=get_connection(fail_silently=True))
    message.attach(filename, contenu, content_type)
    message.send(fail_silently=True)


def executer_abonnement(abonnement, now=None):
    """Exécute UN abonnement et journalise le résultat SUR la ligne.

    Ne lève jamais : toute erreur devient un statut ``erreur`` journalisé.
    """
    from .models import RapportAbonnement

    now = now or _now_casablanca()
    statut = RapportAbonnement.Statut.OK
    detail = {}
    try:
        adresses = destinataires_emails(abonnement)
        if not adresses:
            statut = RapportAbonnement.Statut.SANS_DESTINATAIRE
            detail = {'detail': 'Aucun destinataire résolu : envoi ignoré.'}
        elif not _email_configure():
            statut = RapportAbonnement.Statut.NON_CONFIGURE
            detail = {'detail': 'Canal email non configuré : envoi ignoré.',
                      'destinataires': len(adresses)}
        else:
            filename, contenu, content_type = rendre_abonnement(abonnement)
            _envoyer(abonnement, adresses, filename, contenu, content_type)
            detail = {'detail': 'Rapport envoyé.', 'fichier': filename,
                      'destinataires': len(adresses)}
    except Exception as exc:  # défensif : jamais de propagation
        logger.warning(
            'envoyer_rapports_planifies: échec sur l\'abonnement %s',
            getattr(abonnement, 'pk', None), exc_info=True)
        statut = RapportAbonnement.Statut.ERREUR
        detail = {'detail': str(exc)[:500]}

    abonnement.dernier_statut = statut
    abonnement.dernier_detail = detail
    abonnement.derniere_execution_le = now
    abonnement.save(update_fields=[
        'dernier_statut', 'dernier_detail', 'derniere_execution_le',
        'updated_at'])
    return statut


@shared_task(name='reporting.envoyer_rapports_planifies')
def envoyer_rapports_planifies():
    """Exécute les abonnements DUS. Renvoie le nombre d'abonnements traités."""
    from .models import RapportAbonnement

    now = _now_casablanca()
    try:
        abonnements = list(
            RapportAbonnement.objects.filter(actif=True)
            .select_related('rapport_def'))
    except Exception:  # pragma: no cover - défensif
        logger.warning('envoyer_rapports_planifies: chargement impossible',
                       exc_info=True)
        return 0

    traites = 0
    for abonnement in abonnements:
        try:
            if not est_du(abonnement, now):
                continue
            executer_abonnement(abonnement, now)
            traites += 1
        except Exception:  # pragma: no cover - défensif par abonnement
            logger.warning(
                'envoyer_rapports_planifies: abonnement %s en échec',
                getattr(abonnement, 'pk', None), exc_info=True)
            continue
    logger.info('envoyer_rapports_planifies: %s abonnement(s) traité(s)',
                traites)
    return traites
