"""XSAV8 — Rapport de conformité SLA + KPI SAV avancés.

`reports/service/` ne donne que des comptes par statut. Ce module ajoute un
agrégat dédié : % première réponse et % résolution dans les délais (par
priorité et par technicien), temps moyens, backlog vieilli, % préventif vs
correctif, ponctualité des visites préventives, taux de réouverture (si
disponible), avec drill-down (ids de tickets) et export xlsx.

Lecture seule, multi-tenant (même patron que `reports.py`/`insights.py` :
import LOCAL de `apps.sav.models`, jamais au chargement du module — aucune
arête d'import statique vers `sav`). Réservé responsable/admin.
"""
from datetime import date

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsResponsableOrAdmin
from apps.crm.exports import build_xlsx_response


def _co(user):
    if user.company_id:
        return {'company': user.company}
    if user.is_superuser:
        return {}
    return None


def _maybe_xlsx(request, filename, headers, rows, title):
    if request.query_params.get('export') == 'xlsx':
        return build_xlsx_response(filename, headers, rows, sheet_title=title)
    return None


def _pct(numerator, denominator):
    if not denominator:
        return None
    return round(numerator / denominator * 100, 1)


def _avg_days(values):
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return round(sum(vals) / len(vals), 1)


@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def sav_sla_insight(request):
    """XSAV8 — SLA compliance + KPI avancés SAV (`insights/sav-sla/`).

    Filtres optionnels : `?from=&to=` (fenêtre sur `date_creation`),
    `?technicien=<id>`, `?priorite=<code>`. `?export=xlsx` renvoie un tableau
    récapitulatif par priorité.
    """
    co = _co(request.user)
    if co is None:
        return Response({'detail': 'Accès refusé.'}, status=403)

    from apps.sav.models import Ticket

    qs = Ticket.objects.filter(**co, annule=False)

    start = request.query_params.get('from')
    end = request.query_params.get('to')
    if start:
        qs = qs.filter(date_creation__date__gte=start)
    if end:
        qs = qs.filter(date_creation__date__lte=end)
    technicien_id = request.query_params.get('technicien')
    if technicien_id:
        qs = qs.filter(technicien_responsable_id=technicien_id)
    priorite = request.query_params.get('priorite')
    if priorite:
        qs = qs.filter(priorite=priorite)

    tickets = list(qs.select_related('technicien_responsable'))

    # ── % première réponse / résolution dans les délais, par priorité ──────
    par_priorite = {}
    for choice_val, choice_label in Ticket.Priorite.choices:
        subset = [t for t in tickets if t.priorite == choice_val]
        if not subset:
            continue
        reponse_ok = [
            t for t in subset
            if t.date_premiere_reponse and t.sla_due_at
            and t.date_premiere_reponse.date() <= t.sla_due_at
        ]
        reponse_total = [t for t in subset if t.date_premiere_reponse]
        resolution_ok = [
            t for t in subset
            if t.date_resolution and t.sla_due_at
            and t.date_resolution <= t.sla_due_at
        ]
        resolution_total = [t for t in subset if t.date_resolution]
        par_priorite[choice_val] = {
            'priorite': choice_val,
            'label': str(choice_label),
            'total': len(subset),
            'pct_premiere_reponse_ok': _pct(
                len(reponse_ok), len(reponse_total)),
            'pct_resolution_ok': _pct(
                len(resolution_ok), len(resolution_total)),
        }

    # ── % première réponse / résolution dans les délais, par technicien ────
    par_technicien = {}
    for t in tickets:
        tech = t.technicien_responsable
        key = tech.id if tech else None
        label = (tech.get_full_name() or tech.username) if tech else 'Non affecté'
        entry = par_technicien.setdefault(key, {
            'technicien_id': key, 'technicien': label,
            'total': 0, 'reponse_total': 0, 'reponse_ok': 0,
            'resolution_total': 0, 'resolution_ok': 0,
            'reouvertures': 0,
        })
        entry['total'] += 1
        if t.date_premiere_reponse:
            entry['reponse_total'] += 1
            if t.sla_due_at and t.date_premiere_reponse.date() <= t.sla_due_at:
                entry['reponse_ok'] += 1
        if t.date_resolution:
            entry['resolution_total'] += 1
            if t.sla_due_at and t.date_resolution <= t.sla_due_at:
                entry['resolution_ok'] += 1
        # XSAV11 — taux de réouverture, seulement si le champ existe déjà.
        reopen_count = getattr(t, 'reopen_count', None)
        if reopen_count:
            entry['reouvertures'] += reopen_count

    par_technicien_out = []
    for entry in par_technicien.values():
        par_technicien_out.append({
            'technicien_id': entry['technicien_id'],
            'technicien': entry['technicien'],
            'total': entry['total'],
            'pct_premiere_reponse_ok': _pct(
                entry['reponse_ok'], entry['reponse_total']),
            'pct_resolution_ok': _pct(
                entry['resolution_ok'], entry['resolution_total']),
            'reouvertures': entry['reouvertures'],
        })
    par_technicien_out.sort(key=lambda e: e['technicien'].lower())

    # ── Temps moyens (première réponse, résolution), en jours ──────────────
    delais_reponse = []
    delais_resolution = []
    for t in tickets:
        if t.date_premiere_reponse and t.date_creation:
            delta = (t.date_premiere_reponse.date()
                     - t.date_creation.date()).days
            delais_reponse.append(max(delta, 0))
        if t.date_resolution and t.date_creation:
            delta = (t.date_resolution - t.date_creation.date()).days
            delais_resolution.append(max(delta, 0))

    # ── Backlog vieilli (tickets encore ouverts) ────────────────────────────
    today = date.today()
    ouverts = [t for t in tickets if t.statut in Ticket.OPEN_STATUTS]
    backlog = {'0_2j': 0, '3_7j': 0, 'plus_7j': 0}
    backlog_ids = {'0_2j': [], '3_7j': [], 'plus_7j': []}
    for t in ouverts:
        age = (today - t.date_creation.date()).days if t.date_creation else 0
        if age <= 2:
            bucket = '0_2j'
        elif age <= 7:
            bucket = '3_7j'
        else:
            bucket = 'plus_7j'
        backlog[bucket] += 1
        backlog_ids[bucket].append(t.id)

    # ── % préventif vs correctif ────────────────────────────────────────────
    nb_preventif = sum(1 for t in tickets if t.type == Ticket.Type.PREVENTIF)
    nb_correctif = sum(1 for t in tickets if t.type == Ticket.Type.CORRECTIF)
    total_types = nb_preventif + nb_correctif

    # ── Visites préventives à l'heure vs en retard ──────────────────────────
    # `date_tournee` = date planifiée (FG88) ; `date_resolution` = date réelle
    # de clôture. Une visite est « en retard » quand la résolution dépasse la
    # tournée planifiée. Seuls les tickets préventifs avec les deux dates
    # renseignées entrent dans ce calcul (sinon indéterminé, exclu).
    preventives = [
        t for t in tickets
        if t.type == Ticket.Type.PREVENTIF and t.date_tournee
        and t.date_resolution
    ]
    preventives_a_heure = sum(
        1 for t in preventives if t.date_resolution <= t.date_tournee)
    preventives_en_retard = len(preventives) - preventives_a_heure

    # ── Taux de réouverture (si XSAV11 `reopen_count` présent) ──────────────
    reouverture = None
    if tickets and hasattr(tickets[0], 'reopen_count'):
        total_reouvertures = sum(
            getattr(t, 'reopen_count', 0) or 0 for t in tickets)
        reouverture = {
            'total_reouvertures': total_reouvertures,
            'taux_pour_100_tickets': round(
                total_reouvertures / len(tickets) * 100, 1) if tickets else 0,
        }

    result = {
        'total_tickets': len(tickets),
        'par_priorite': list(par_priorite.values()),
        'par_technicien': par_technicien_out,
        'delai_moyen_premiere_reponse_jours': _avg_days(delais_reponse),
        'delai_moyen_resolution_jours': _avg_days(delais_resolution),
        'backlog_vieilli': {
            'buckets': backlog,
            'ids': backlog_ids,
        },
        'preventif_vs_correctif': {
            'nb_preventif': nb_preventif,
            'nb_correctif': nb_correctif,
            'pct_preventif': _pct(nb_preventif, total_types),
        },
        'visites_preventives': {
            'total_evaluees': len(preventives),
            'a_heure': preventives_a_heure,
            'en_retard': preventives_en_retard,
            'pct_a_heure': _pct(preventives_a_heure, len(preventives)),
        },
        'reouverture': reouverture,
    }

    if request.query_params.get('export') == 'xlsx':
        rows = [
            [p['label'], p['total'], p['pct_premiere_reponse_ok'],
             p['pct_resolution_ok']]
            for p in result['par_priorite']
        ]
        x = _maybe_xlsx(
            request, 'rapport-sav-sla.xlsx',
            ['Priorité', 'Total', '% 1ère réponse OK', '% résolution OK'],
            rows, 'SLA SAV')
        if x:
            return x

    return Response(result)
