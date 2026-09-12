"""N79 — Envoi par email programmé des rapports sauvegardés (Celery Beat).

Une tâche unique (`reporting.email_saved_reports`) décide, à chaque exécution, des
rapports DUS : ceux dont `schedule` correspond à la cadence courante (quotidienne
le matin, hebdomadaire le lundi) et qui ont au moins un destinataire. Pour chacun,
elle rend le rapport ciblé en .xlsx (builder partagé `apps.records.xlsx`) et
l'envoie via le backend email configuré.

Principes (règles fondatrices) :
  - NO-OP sûr : sans email configuré (clé Brevo/SMTP), AUCUN envoi réseau — la
    tâche se contente de ne rien envoyer (comportement actuel préservé). On
    réutilise `apps.ventes.email_service.is_email_configured`.
  - MULTI-TENANT : chaque rapport est rendu DANS la portée de sa société (jamais
    de fuite inter-société) ; le rendu est borné par `company`.
  - DÉFENSIF/IDEMPOTENT : chaque rapport est traité isolément (try/except) ; une
    erreur n'arrête pas les suivants. Aucune donnée métier n'est mutée (seul
    `last_sent_at` du rapport envoyé est horodaté).
  - Aucun prix d'achat / marge n'est jamais exposé (rapports client-safe).
  Texte utilisateur en FRANÇAIS ; code/identifiants en anglais.
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)

CASABLANCA_TZ = 'Africa/Casablanca'


def _casablanca_now():
    from django.utils import timezone
    try:
        from zoneinfo import ZoneInfo
        return timezone.now().astimezone(ZoneInfo(CASABLANCA_TZ))
    except Exception:  # pragma: no cover - zoneinfo absent (très improbable)
        return timezone.localtime()


def _is_email_configured():
    """Réutilise l'helper de configuration email des ventes (Brevo/SMTP)."""
    try:
        from apps.ventes.email_service import is_email_configured
        return is_email_configured()
    except Exception:  # pragma: no cover - défensif
        return False


# ── Rendu d'un rapport → (en-têtes, lignes). Borné à la société. ─────────────

def _company_filter(company):
    return {'company': company} if company is not None else {}


def render_sales(report):
    """Funnel des leads par étape (miroir léger de reports.sales_report)."""
    from apps.crm import stages as stage_mod
    from apps.crm.models import Lead

    co = _company_filter(report.company)
    leads = Lead.objects.filter(is_archived=False, **co)
    rows = []
    for key in stage_mod.STAGES:
        rows.append([
            stage_mod.STAGE_LABELS.get(key, key),
            leads.filter(stage=key).count(),
        ])
    return ['Étape', 'Leads'], rows


def render_stock(report):
    """Produits + quantités en stock (jamais de prix d'achat)."""
    from apps.stock.models import Produit

    co = _company_filter(report.company)
    rows = []
    for p in Produit.objects.filter(**co).order_by('nom'):
        rows.append([
            getattr(p, 'nom', '') or '',
            getattr(p, 'sku', '') or '',
            getattr(p, 'quantite_stock', 0) or 0,
        ])
    return ['Produit', 'Référence', 'Quantité en stock'], rows


def render_service(report):
    """Tickets SAV par statut (vue service)."""
    from apps.sav.models import Ticket

    co = _company_filter(report.company)
    tickets = Ticket.objects.filter(**co)
    labels = dict(Ticket.Statut.choices)
    rows = []
    for value, _label in Ticket.Statut.choices:
        rows.append([
            labels.get(value, value),
            tickets.filter(statut=value).count(),
        ])
    return ['Statut', 'Tickets'], rows


_RENDERERS = {
    'sales': render_sales,
    'stock': render_stock,
    'service': render_service,
}


# ── NTDATA37 — cibles CONSTRUITES par l'utilisateur (dashboard / requête) ───
#
# Les 3 rapports ci-dessus sont FIGÉS : leur contenu est écrit en Python. Un
# abonnement doit aussi pouvoir viser ce que l'utilisateur a bâti lui-même —
# un tableau de bord (NTDATA32) ou une requête sauvegardée (FG382).
#
# DEUX FORMATS, choisis par la NATURE de la cible et pas par une préférence :
# un tableau de bord est une MISE EN PAGE (plusieurs blocs, des titres) → PDF ;
# une requête est un TABLEAU (des lignes, des colonnes) → XLSX, qu'on ouvre et
# qu'on retrie.
#
# RIEN N'EST INVENTÉ : les deux rendus rejouent la cible via
# `core.data_explorer` / `core.dashboard_data`, avec le scoping société et la
# liste blanche de champs que ces moteurs imposent déjà. Un widget en erreur
# est RENDU COMME TEL dans le PDF — jamais remplacé par un tableau vide qui
# laisserait croire qu'il n'y avait rien à voir.

MIME_XLSX = ('application/vnd.openxmlformats-officedocument'
             '.spreadsheetml.sheet')
MIME_PDF = 'application/pdf'

#: Feuille de style du PDF de tableau de bord. CONSTANTE séparée (et jamais
#: interpolée) : elle contient des « % » — `width:100%` — qui casseraient un
#: formatage `%`, exactement ce que flake8 F509/F507 a attrapé ici.
_STYLE_PDF = (
    'body{font-family:sans-serif;font-size:11px}'
    'h1{font-size:16px}h2{font-size:13px;margin:12px 0 4px}'
    'table{border-collapse:collapse;width:100%}'
    'th,td{border:1px solid #ccc;padding:3px 5px;text-align:left}'
    '.erreur{color:#a00}.vide{color:#666;font-style:italic}'
)


def _echappe(valeur):
    """Échappe une valeur pour l'insérer dans le HTML du PDF."""
    from django.utils.html import escape
    return escape('' if valeur is None else str(valeur))


def rendre_dashboard_html(report, dashboard):
    """Le HTML du PDF d'un tableau de bord (fonction PURE, testable seule).

    Un widget en ERREUR est affiché AVEC son message : un tableau de bord qui
    tait un widget cassé ment par omission. Un widget sans ligne affiche
    « aucune donnée » plutôt qu'un cadre vide.
    """
    from core.dashboard_data import executer_dashboard

    donnees = executer_dashboard(dashboard, report.company, report.owner)
    blocs = []
    for widget in donnees['widgets']:
        titre = _echappe(widget.get('titre') or widget.get('id') or '')
        if widget.get('erreur'):
            blocs.append(
                '<section><h2>%s</h2><p class="erreur">%s</p></section>'
                % (titre, _echappe(widget['erreur'])))
            continue
        lignes = widget.get('rows') or []
        if not lignes:
            blocs.append(
                '<section><h2>%s</h2><p class="vide">Aucune donnée sur la '
                'période.</p></section>' % titre)
            continue
        colonnes = list(lignes[0].keys())
        entete = ''.join('<th>%s</th>' % _echappe(c) for c in colonnes)
        corps = ''.join(
            '<tr>%s</tr>' % ''.join(
                '<td>%s</td>' % _echappe(ligne.get(c)) for c in colonnes)
            for ligne in lignes)
        blocs.append(
            '<section><h2>%s</h2><table><thead><tr>%s</tr></thead>'
            '<tbody>%s</tbody></table></section>' % (titre, entete, corps))
    titre_page = _echappe(dashboard.titre or report.name)
    return ('<html><head><meta charset="utf-8"><style>' + _STYLE_PDF
            + '</style></head><body><h1>' + titre_page + '</h1>'
            + ''.join(blocs) + '</body></html>')


def _rendre_dashboard(report):
    """``(bytes, titre, filename, content_type)`` du PDF d'un dashboard."""
    dashboard = report.resoudre_cible()
    if dashboard is None:
        return None, None, None, None
    html = rendre_dashboard_html(report, dashboard)
    try:
        from core.pdf import render_pdf
        contenu = render_pdf(html=html, company=report.company)
    except Exception:  # pragma: no cover - dépend de WeasyPrint
        logger.warning('email_saved_reports: rendu PDF du dashboard %s en '
                       'échec (rapport %s)', dashboard.pk, report.pk,
                       exc_info=True)
        return None, None, None, None
    titre = dashboard.titre or report.name
    return contenu, titre, f'{_nom_fichier(titre)}.pdf', MIME_PDF


def _rendre_saved_query(report):
    """``(bytes, titre, filename, content_type)`` du XLSX d'une requête."""
    from core import data_explorer

    requete = report.resoudre_cible()
    if requete is None:
        return None, None, None, None
    try:
        lignes = data_explorer.run_query(
            requete.dataset, report.company, report.owner,
            requete.spec or {})
    except Exception:
        logger.warning('email_saved_reports: exécution de la requête %s en '
                       'échec (rapport %s)', requete.pk, report.pk,
                       exc_info=True)
        return None, None, None, None
    entetes = list(lignes[0].keys()) if lignes else []
    tableau = [[ligne.get(c, '') for c in entetes] for ligne in lignes]
    titre = requete.titre or report.name
    try:
        from apps.records.xlsx import workbook_bytes
        contenu = workbook_bytes(entetes, tableau, sheet_title=titre[:31])
    except Exception:  # pragma: no cover - dépend d'openpyxl
        logger.warning('email_saved_reports: sérialisation xlsx en échec '
                       '(rapport %s)', report.pk, exc_info=True)
        return None, None, None, None
    return contenu, titre, f'{_nom_fichier(titre)}.xlsx', MIME_XLSX


def _nom_fichier(base):
    """Nom de fichier sûr dérivé d'un titre (jamais vide)."""
    sur = ''.join(c for c in (base or '') if c.isalnum() or c in ('-', '_'))
    return sur or 'rapport'


def _rendre_legacy(report):
    """Les 3 rapports FIGÉS — rendu inchangé, au format .xlsx."""
    renderer = _RENDERERS.get(report.target_kind)
    if renderer is None:
        return None, None, None, None
    try:
        headers, rows = renderer(report)
    except Exception:  # pragma: no cover - défensif (modèle/requête)
        logger.warning('email_saved_reports: rendu %r en échec (rapport %s)',
                       report.target_kind, report.pk, exc_info=True)
        return None, None, None, None
    try:
        from apps.records.xlsx import workbook_bytes
        title = report.get_target_kind_display()
        return (workbook_bytes(headers, rows, sheet_title=title), title,
                f'{report.target_kind}.xlsx', MIME_XLSX)
    except Exception:  # pragma: no cover - dépend d'openpyxl
        logger.warning('email_saved_reports: sérialisation xlsx en échec '
                       '(rapport %s)', report.pk, exc_info=True)
        return None, None, None, None


def rendre_rapport(report):
    """NTDATA37 — rend N'IMPORTE QUELLE cible : ``(bytes, titre, nom, mime)``.

    ``(None, None, None, None)`` quand la cible est introuvable ou le rendu
    impossible — l'appelant journalise alors un envoi en échec AVEC son motif,
    plutôt que d'envoyer une pièce jointe vide.
    """
    from .models import SavedReport

    if report.target_kind == SavedReport.TargetKind.DASHBOARD:
        return _rendre_dashboard(report)
    if report.target_kind == SavedReport.TargetKind.QUERY:
        return _rendre_saved_query(report)
    return _rendre_legacy(report)


def render_report_xlsx(report):
    """Rend un SavedReport en octets .xlsx (builder partagé). None si échec.

    CONTRAT HISTORIQUE CONSERVÉ (deux valeurs, format .xlsx) pour les appelants
    d'avant NTDATA37. Les nouvelles cibles passent par :func:`rendre_rapport`,
    qui rend AUSSI le nom de fichier et le type MIME — un PDF de dashboard
    servi en .xlsx ne s'ouvrirait nulle part.
    """
    contenu, titre, _nom, _mime = _rendre_legacy(report)
    return contenu, titre


def _send_report_email(report, content, title, filename=None,
                       content_type=None):
    """Envoie la pièce jointe aux destinataires via le backend configuré.

    NO-OP (renvoie False) si l'email n'est pas configuré ou sans destinataire.
    Best-effort : toute exception est capturée, jamais propagée.

    NTDATA37 — ``filename``/``content_type`` sont facultatifs et retombent sur
    le .xlsx historique : un appelant d'avant ce lot obtient EXACTEMENT le même
    message. Un PDF de tableau de bord servi sous un nom .xlsx ne s'ouvrirait
    nulle part, d'où ces deux paramètres."""
    recipients = report.recipient_list()
    if not recipients or not _is_email_configured():
        return False
    try:
        from django.conf import settings
        from django.core.mail import EmailMessage, get_connection

        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', '') or 'noreply@erp.local'
        subject = f'Rapport : {report.name}'[:300]
        body = (f'Bonjour,\n\nVeuillez trouver ci-joint le rapport « {report.name} » '
                f'({title}).\n\nCordialement.')
        connection = get_connection(fail_silently=True)
        msg = EmailMessage(
            subject=subject, body=body, from_email=from_email,
            to=recipients, connection=connection)
        msg.attach(
            filename or f'{report.target_kind}.xlsx', content,
            content_type or MIME_XLSX)
        msg.send(fail_silently=True)
        return True
    except Exception:  # pragma: no cover - dépend du backend réel
        logger.warning('email_saved_reports: envoi en échec (rapport %s)',
                       report.pk, exc_info=True)
        return False


def journaliser_envoi(report, canal, destinataires, statut, erreur=''):
    """NTDATA40 — trace UNE tentative de diffusion (réussie ou non).

    ``company`` est reprise DU RAPPORT (côté serveur, jamais d'un corps de
    requête). Best-effort : un journal qui échoue ne doit jamais empêcher — ni
    faire croire à — un envoi ; il est simplement logué."""
    from .models import EnvoiRapport
    try:
        return EnvoiRapport.objects.create(
            company=report.company,
            saved_report=report,
            canal=canal,
            destinataires=', '.join(destinataires or []),
            statut=statut,
            erreur=(erreur or '')[:2000],
        )
    except Exception:  # pragma: no cover - défensif
        logger.warning('journaliser_envoi: écriture impossible (rapport %s)',
                       getattr(report, 'pk', None), exc_info=True)
        return None


def _due_schedules(now):
    """Cadences dues à l'instant `now` (Casablanca).

    La tâche est planifiée chaque jour (06:00) et le lundi (06:00). Pour rester
    robuste quelle que soit l'horloge réelle d'invocation, on considère « daily »
    toujours dû, « weekly » dû uniquement le lundi (weekday() == 0), et
    « monthly » (NTDATA38) dû les jours du mois pouvant porter un envoi."""
    due = {'daily'}
    if now.weekday() == 0:  # lundi
        due.add('weekly')
    due.add('monthly')  # affiné par rapport dans `_rapport_est_du`.
    return due


def _heure_ok(report, now):
    """Fenêtre horaire du rapport (NTDATA38).

    `heure_envoi` NULL = comportement HISTORIQUE : aucune contrainte d'heure,
    le rapport part au passage du planificateur. Renseignée, l'envoi n'a lieu
    que lorsque l'heure locale correspond."""
    heure = getattr(report, 'heure_envoi', None)
    return heure is None or now.hour == int(heure)


def _deja_envoye_ce_mois(report, now):
    """Anti-doublon de la cadence mensuelle : un mois = un envoi.

    Le jour d'envoi peut voir le planificateur passer plusieurs fois ;
    `last_sent_at` (déjà horodaté à chaque envoi réussi) suffit à ne pas
    renvoyer le même rapport mensuel deux fois."""
    dernier = getattr(report, 'last_sent_at', None)
    if dernier is None:
        return False
    try:
        local = dernier.astimezone(now.tzinfo) if now.tzinfo else dernier
    except (ValueError, TypeError):  # pragma: no cover - défensif
        local = dernier
    return (local.year, local.month) == (now.year, now.month)


def _rapport_est_du(report, now):
    """Vrai si CE rapport doit partir à l'instant `now` (Casablanca).

    Affine la sélection grossière par cadence : fenêtre horaire (`heure_envoi`)
    et, pour le mensuel, jour du mois + anti-doublon. Les cadences historiques
    (`daily`/`weekly`) restent INCHANGÉES tant qu'aucune heure n'est posée."""
    cadence = report.schedule
    if cadence == 'none':
        return False
    if cadence == 'weekly' and now.weekday() != 0:
        return False
    if cadence == 'monthly':
        jour = getattr(report, 'jour_du_mois', 1) or 1
        if now.day != int(jour):
            return False
        if _deja_envoye_ce_mois(report, now):
            return False
    return _heure_ok(report, now)


@shared_task(name='reporting.email_saved_reports')
def email_saved_reports():
    """Envoie par email les rapports sauvegardés dus. Renvoie le nb d'envois.

    Sélectionne les rapports dont `schedule` est dû et qui ont un destinataire,
    les rend en .xlsx et les envoie. NO-OP propre si l'email n'est pas configuré
    (aucun envoi). Idempotent : seul `last_sent_at` est horodaté sur envoi réussi."""
    from .models import SavedReport

    now = _casablanca_now()
    due = _due_schedules(now)
    sent = 0
    try:
        reports = list(SavedReport.objects.filter(schedule__in=due))
    except Exception:  # pragma: no cover - défensif
        logger.warning('email_saved_reports: chargement des rapports impossible',
                       exc_info=True)
        return 0

    for report in reports:
        try:
            # NTDATA38 — fenêtre fine (heure d'envoi, jour du mois, anti-doublon
            # mensuel) par-dessus la sélection grossière par cadence.
            if not _rapport_est_du(report, now):
                continue
            # NTDATA39 — canal WhatsApp : un LIEN tokenisé, jamais la pièce
            # jointe, et un NO-OP TOTAL tant que le canal n'est pas armé.
            if getattr(report, 'canal', 'email') == 'whatsapp':
                from .diffusion_views import diffuser_whatsapp
                envoyes, detail = diffuser_whatsapp(report)
                numeros = report.whatsapp_list()
                if envoyes:
                    report.last_sent_at = now
                    report.save(update_fields=['last_sent_at'])
                    sent += 1
                    journaliser_envoi(report, 'whatsapp', numeros, 'envoye')
                elif not numeros:
                    journaliser_envoi(report, 'whatsapp', numeros,
                                      'sans_destinataire', detail)
                else:
                    journaliser_envoi(report, 'whatsapp', numeros,
                                      'non_configure', detail)
                continue
            destinataires = report.recipient_list()
            if not destinataires:
                journaliser_envoi(report, 'email', destinataires,
                                  'sans_destinataire',
                                  'Aucune adresse destinataire configurée.')
                continue
            if not _is_email_configured():
                journaliser_envoi(report, 'email', destinataires,
                                  'non_configure',
                                  "Email non configuré (aucune clé d'envoi) — "
                                  'aucun message envoyé.')
                continue
            # NTDATA37 — la cible peut être un dashboard (PDF) ou une requête
            # sauvegardée (XLSX) en plus des 3 rapports figés ; le rendu dit
            # lui-même sous quel nom et quel type MIME il part.
            content, title, filename, content_type = rendre_rapport(report)
            if content is None:
                journaliser_envoi(report, 'email', destinataires, 'echec',
                                  'Rendu du rapport impossible (cible '
                                  'introuvable, format ou données '
                                  'indisponibles).')
                continue
            if _send_report_email(report, content, title, filename,
                                  content_type):
                report.last_sent_at = now
                report.save(update_fields=['last_sent_at'])
                sent += 1
                journaliser_envoi(report, 'email', destinataires, 'envoye')
            else:
                journaliser_envoi(report, 'email', destinataires, 'echec',
                                  "Envoi refusé par le backend email.")
        except Exception:  # pragma: no cover - défensif par rapport
            logger.warning('email_saved_reports: échec sur le rapport %s',
                           getattr(report, 'pk', None), exc_info=True)
            continue
    logger.info('email_saved_reports: %s rapport(s) envoyé(s) (cadences=%s)',
                sent, ','.join(sorted(due)))
    return sent
