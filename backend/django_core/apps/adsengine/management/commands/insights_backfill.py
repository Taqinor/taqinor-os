"""ADSDEEP3 — Backfill HISTORIQUE des insights niveau ad.

    python manage.py insights_backfill [--company <slug|id>] [--max-polls N]

Rejoue l'historique complet des insights (``date_preset=maximum``,
``time_increment=1``, ``level=ad``) via l'API asynchrone de Meta (jobs
``report_run_id`` + polling) et upserte un ``InsightSnapshot`` par (ad, jour) —
IDEMPOTENT : re-run sans doublon (clé datée ``sync.upsert_insight``). Si le job
échoue (« Job Failed » — trop de cardinalité/plage), on retombe sur un pull
SYNCHRONE mois par mois (dossier insights-api §4). NO-OP propre sans connexion
Meta active + token.

Ne modifie AUCUN comportement de synchro quotidienne (ENG6/ADSDEEP2) : cette
commande est une passe de rattrapage ponctuelle, lancée à la main.

FIXPUB3 — le CŒUR par connexion (``backfill_insights_for_connection``) est
extrait au niveau module pour être réutilisé par la tâche async « rattrapage
complet » (``adsengine.tasks.backfill_complet``) sans dupliquer la logique.
"""
import datetime
import time

from django.core.management.base import BaseCommand

from apps.adsengine.tasks import AD_INSIGHT_FIELDS

# Champs demandés à l'edge compte, niveau ad — colonnes ADSDEEP1 + l'id d'ad.
BACKFILL_FIELDS = AD_INSIGHT_FIELDS + ('ad_id',)
# Statuts terminaux d'un job async Meta.
_DONE = 'Job Completed'
_FAILED = 'Job Failed'
_SKIPPED = 'Job Skipped'


def _account_node(conn):
    acct = str(conn.ad_account_id or '').strip()
    if not acct:
        return ''
    return acct if acct.startswith('act_') else f'act_{acct}'


def _month_ranges(start, end):
    """Découpe [start, end] en tranches mensuelles [(since, until), …]."""
    ranges = []
    cur = datetime.date(start.year, start.month, 1)
    while cur <= end:
        if cur.month == 12:
            nxt = datetime.date(cur.year + 1, 1, 1)
        else:
            nxt = datetime.date(cur.year, cur.month + 1, 1)
        since = max(cur, start)
        until = min(nxt - datetime.timedelta(days=1), end)
        ranges.append((since, until))
        cur = nxt
    return ranges


# ── Cycle async report_run_id (fonctions module — réutilisables) ─────────────
def _start_report(client, node, params):
    payload = client._request('POST', f'{node}/insights', data=params)
    return (payload or {}).get('report_run_id')


def _poll_report(client, report_run_id, *, max_polls, interval):
    for _ in range(max(1, max_polls)):
        payload = client._request('GET', f'{report_run_id}') or {}
        status = payload.get('async_status')
        if status in (_DONE, _FAILED, _SKIPPED):
            return status
        if interval:
            time.sleep(interval)
    return None  # timeout — traité comme un échec pour retomber sur mois


def _fetch_report(client, report_run_id):
    return client.get_insights(report_run_id)


def _upsert_rows(company, rows, mirrors):
    from apps.adsengine import sync
    from apps.adsengine.platforms.base import normalize_insight_row

    today = datetime.date.today()
    written = 0
    for row in rows or []:
        ad_id = str(row.get('ad_id') or '').strip()
        mirror = mirrors.get(ad_id)
        if mirror is None:
            continue
        try:
            day = datetime.date.fromisoformat(str(row.get('date_start')))
        except (ValueError, TypeError):
            day = today
        norm = normalize_insight_row(row)
        sync.upsert_insight(
            company, mirror, date=day,
            spend=norm['spend'], results=norm['results'],
            frequency=norm['frequency'], cpl=norm['cpl'],
            impressions=norm['impressions'], reach=norm['reach'],
            clicks=norm['clicks'], link_clicks=norm['link_clicks'],
            conversations=norm['conversations'],
            leads_count=norm['leads_count'],
            video_metrics=norm['video_metrics'])
        written += 1
    return written


def _backfill_monthly(client, node, company, mirrors, *, months=48):
    """Repli SYNCHRONE mois par mois quand le job async échoue."""
    today = datetime.date.today()
    start = today - datetime.timedelta(days=30 * months)
    written = 0
    for since, until in _month_ranges(start, today):
        rows = client.get_insights(
            node, fields=BACKFILL_FIELDS,
            params={'level': 'ad', 'time_increment': 1,
                    'time_range': {'since': since.isoformat(),
                                   'until': until.isoformat()}})
        written += _upsert_rows(company, rows, mirrors)
    return written


def backfill_insights_for_connection(conn, *, max_polls=60, poll_interval=2.0,
                                     warn=None):
    """FIXPUB3 — CŒUR du backfill historique pour UNE connexion Meta.

    Extraction module-niveau de l'ancienne méthode privée du Command : lance le
    job async ``date_preset=maximum`` (level=ad), sonde, et upserte un
    ``InsightSnapshot`` par (ad, jour) ; retombe sur le repli mensuel synchrone
    si le job échoue/expire. ``warn`` (callable optionnel) reçoit un message FR
    quand le repli mensuel s'active (le Command y branche ``self.stdout``).
    Renvoie le nombre de snapshots upsertés (0 sans ``ad_account_id``)."""
    from apps.adsengine.meta_client import MetaClient
    from apps.adsengine.models import AdMirror

    company = conn.company
    node = _account_node(conn)
    if not node:
        return 0
    client = MetaClient.from_connection(conn)
    mirrors = {m.meta_id: m
               for m in AdMirror.objects.filter(company=company)}

    params = {
        'level': 'ad', 'time_increment': 1, 'date_preset': 'maximum',
        'fields': ','.join(BACKFILL_FIELDS),
    }
    report_run_id = _start_report(client, node, params)
    status = None
    if report_run_id:
        status = _poll_report(
            client, report_run_id, max_polls=max_polls, interval=poll_interval)
    if status == _DONE:
        rows = _fetch_report(client, report_run_id)
        return _upsert_rows(company, rows, mirrors)
    # Job Failed / Skipped / timeout → repli mensuel (chunk par mois).
    if warn is not None:
        warn(f"job async « {status or 'timeout'} » — repli mois par mois.")
    return _backfill_monthly(client, node, company, mirrors)


class Command(BaseCommand):
    help = ("Backfill historique des insights niveau ad (jobs async + polling, "
            "date_preset=maximum, upsert idempotent par date).")

    def add_arguments(self, parser):
        parser.add_argument('--company', dest='company', default=None,
                            help="Slug ou id (défaut : toutes les sociétés "
                                 "avec une connexion Meta active).")
        parser.add_argument('--max-polls', dest='max_polls', type=int,
                            default=60, help="Nombre max de sondages du job.")
        parser.add_argument('--poll-interval', dest='poll_interval',
                            type=float, default=2.0,
                            help="Secondes entre deux sondages.")

    def _connections(self, raw):
        from authentication.models import Company

        from apps.adsengine.models import MetaConnection

        qs = MetaConnection.objects.filter(enabled=True)
        if raw is not None:
            company = Company.objects.filter(slug=raw).first()
            if company is None and str(raw).isdigit():
                company = Company.objects.filter(pk=int(raw)).first()
            qs = qs.filter(company=company) if company else qs.none()
        return [c for c in qs if c.is_live]

    def handle(self, *args, **options):
        conns = self._connections(options.get('company'))
        if not conns:
            self.stdout.write(self.style.WARNING(
                "Aucune connexion Meta active + tokenisée — no-op propre."))
            return
        total = 0
        for conn in conns:
            name = getattr(conn.company, 'nom', conn.company_id)
            self.stdout.write(f"Backfill société « {name} »…")
            try:
                written = backfill_insights_for_connection(
                    conn, max_polls=options['max_polls'],
                    poll_interval=options['poll_interval'],
                    warn=lambda msg: self.stdout.write(
                        self.style.WARNING(f"  {msg}")))
            except Exception as exc:  # noqa: BLE001 — isolation société
                self.stdout.write(self.style.ERROR(
                    f"  échec : {exc}"))
                continue
            total += written
            self.stdout.write(f"  {written} snapshot(s) upsertés.")
        self.stdout.write(self.style.SUCCESS(
            f"Backfill terminé — {total} snapshot(s) au total."))
