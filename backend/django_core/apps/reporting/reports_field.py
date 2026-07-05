"""XFSM16 — Rapport analytics field service (FTF, MTTR, ponctualité, récidive).

Consolide en UN rapport des briques déjà existantes mais jamais agrégées
ensemble :
  * first-time-fix (FTF)  — tickets SAV résolus en UNE seule intervention
                            liée / total de tickets résolus (`sav.Ticket` ↔
                            `installations.Intervention.ticket`).
  * MTTR                  — délai moyen création → résolution (jours),
                            même mesure que `sav_sla.py`.
  * ponctualité           — XFSM5, `installations.selectors.taux_ponctualite`.
  * récidive              — XFSM15, `est_recidive` sur `sav.Ticket`.
  * temps trajet vs sur site — F15, `installations.field_capture.crew_time`.
  * interventions par type/statut — `installations.Intervention`.

Lecture seule, multi-tenant (même patron que `sav_sla.py`/`reports.py` :
imports LOCAUX de `apps.sav.models`/`apps.installations.models`, jamais au
chargement du module — aucune arête d'import statique cross-app depuis
`reporting`). Filtrable période/technicien/équipe. Réservé responsable/admin.
Export `?export=xlsx` (tableau récapitulatif par technicien).
"""
from apps.crm.exports import build_xlsx_response
from authentication.permissions import IsResponsableOrAdmin
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response


def _co(user):
    if user.company_id:
        return {'company': user.company}
    if user.is_superuser:
        return {}
    return None


def _pct(numerator, denominator):
    if not denominator:
        return None
    return round(numerator / denominator * 100, 1)


def _avg(values):
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return round(sum(vals) / len(vals), 1)


@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def field_service_report(request):
    """XFSM16 — Rapport analytics field service (`reports/field/`).

    Filtres optionnels : `?from=&to=` (fenêtre sur `Intervention.date_prevue`
    pour les KPIs terrain, sur `Ticket.date_creation` pour FTF/récidive),
    `?technicien=<id>`, `?equipe=<id>` (équipe canonique `installations.Equipe`).
    `?export=xlsx` renvoie un tableau récapitulatif par technicien.
    """
    co = _co(request.user)
    if co is None:
        return Response({'detail': 'Accès refusé.'}, status=403)

    from apps.installations.field_capture import crew_time
    from apps.installations.models import Intervention
    from apps.sav.models import Ticket

    start = request.query_params.get('from')
    end = request.query_params.get('to')
    technicien_id = request.query_params.get('technicien')
    equipe_id = request.query_params.get('equipe')

    # ── Interventions (KPIs terrain : ponctualité amont, trajet/site, types/statuts) ──
    interv_qs = Intervention.objects.filter(**co, annulee=False)
    if start:
        interv_qs = interv_qs.filter(date_prevue__gte=start)
    if end:
        interv_qs = interv_qs.filter(date_prevue__lte=end)
    if technicien_id:
        interv_qs = interv_qs.filter(technicien_id=technicien_id)
    if equipe_id:
        interv_qs = interv_qs.filter(equipe_ref_id=equipe_id)

    interventions = list(
        interv_qs.select_related('technicien').prefetch_related('equipe'))

    par_type = {}
    for choice_val, choice_label in Intervention.Type.choices:
        count = sum(1 for i in interventions if i.type_intervention == choice_val)
        if count:
            par_type[choice_val] = {
                'type': choice_val, 'label': str(choice_label), 'total': count,
            }

    par_statut = {}
    for choice_val, choice_label in Intervention.Statut.choices:
        count = sum(1 for i in interventions if i.statut == choice_val)
        if count:
            par_statut[choice_val] = {
                'statut': choice_val, 'label': str(choice_label), 'total': count,
            }

    # ── Temps trajet vs sur site (F15), agrégé et par technicien ────────────
    trajet_minutes = []
    sur_site_minutes = []
    par_technicien_temps = {}
    for interv in interventions:
        t = crew_time(interv)
        if t['trajet_aller_min'] is not None:
            trajet_minutes.append(t['trajet_aller_min'])
        if t['duree_sur_site_min'] is not None:
            sur_site_minutes.append(t['duree_sur_site_min'])
        tech = interv.technicien
        key = tech.id if tech else None
        label = (tech.get_full_name() or tech.username) if tech else 'Non affecté'
        entry = par_technicien_temps.setdefault(key, {
            'technicien_id': key, 'technicien': label,
            'trajet_min': [], 'sur_site_min': [],
        })
        if t['trajet_aller_min'] is not None:
            entry['trajet_min'].append(t['trajet_aller_min'])
        if t['duree_sur_site_min'] is not None:
            entry['sur_site_min'].append(t['duree_sur_site_min'])

    # ── Ponctualité (XFSM5) — via le selector dédié, jamais d'import de models ──
    from apps.installations import selectors as installations_selectors
    ponctualite = installations_selectors.taux_ponctualite(
        request.user.company if request.user.company_id else None,
        debut=start, fin=end,
        technicien_id=int(technicien_id) if technicien_id else None,
    ) if request.user.company_id else {
        'nb_mesurees': 0, 'nb_a_lheure': 0, 'taux_pct': None,
    }

    # ── Tickets SAV : FTF + MTTR + récidive (XFSM15) ────────────────────────
    ticket_qs = Ticket.objects.filter(**co, annule=False)
    if start:
        ticket_qs = ticket_qs.filter(date_creation__date__gte=start)
    if end:
        ticket_qs = ticket_qs.filter(date_creation__date__lte=end)
    if technicien_id:
        ticket_qs = ticket_qs.filter(technicien_responsable_id=technicien_id)

    tickets = list(
        ticket_qs.select_related('technicien_responsable')
        .prefetch_related('interventions'))

    resolus = [t for t in tickets if t.date_resolution]
    ftf_ok = [t for t in resolus if t.interventions.count() == 1]
    mttr_jours = []
    for t in resolus:
        if t.date_creation:
            delta = (t.date_resolution - t.date_creation.date()).days
            mttr_jours.append(max(delta, 0))

    recidive_total = sum(1 for t in tickets if t.est_recidive)

    # ── Par technicien (FTF, MTTR, récidive, trajet/site) ───────────────────
    par_technicien = {}
    for t in tickets:
        tech = t.technicien_responsable
        key = tech.id if tech else None
        label = (tech.get_full_name() or tech.username) if tech else 'Non affecté'
        entry = par_technicien.setdefault(key, {
            'technicien_id': key, 'technicien': label,
            'total_tickets': 0, 'resolus': 0, 'ftf_ok': 0,
            'mttr_jours': [], 'recidives': 0,
        })
        entry['total_tickets'] += 1
        if t.est_recidive:
            entry['recidives'] += 1
        if t.date_resolution:
            entry['resolus'] += 1
            if t.interventions.count() == 1:
                entry['ftf_ok'] += 1
            if t.date_creation:
                delta = (t.date_resolution - t.date_creation.date()).days
                entry['mttr_jours'].append(max(delta, 0))

    par_technicien_out = []
    for entry in par_technicien.values():
        temps_entry = par_technicien_temps.get(entry['technicien_id'], {})
        par_technicien_out.append({
            'technicien_id': entry['technicien_id'],
            'technicien': entry['technicien'],
            'total_tickets': entry['total_tickets'],
            'pct_ftf': _pct(entry['ftf_ok'], entry['resolus']),
            'mttr_jours': _avg(entry['mttr_jours']),
            'taux_recidive_pct': _pct(entry['recidives'], entry['total_tickets']),
            'trajet_moyen_min': _avg(temps_entry.get('trajet_min', [])),
            'duree_sur_site_moyenne_min': _avg(temps_entry.get('sur_site_min', [])),
        })
    par_technicien_out.sort(key=lambda e: e['technicien'].lower())

    result = {
        'total_interventions': len(interventions),
        'par_type': list(par_type.values()),
        'par_statut': list(par_statut.values()),
        'total_tickets': len(tickets),
        'first_time_fix': {
            'nb_resolus': len(resolus),
            'nb_ftf': len(ftf_ok),
            'pct_ftf': _pct(len(ftf_ok), len(resolus)),
        },
        'mttr_jours_moyen': _avg(mttr_jours),
        'ponctualite': ponctualite,
        'recidive': {
            'total': recidive_total,
            'taux_pct': _pct(recidive_total, len(tickets)),
        },
        'temps_trajet_vs_site': {
            'trajet_moyen_min': _avg(trajet_minutes),
            'duree_sur_site_moyenne_min': _avg(sur_site_minutes),
        },
        'par_technicien': par_technicien_out,
    }

    if request.query_params.get('export') == 'xlsx':
        rows = [
            [p['technicien'], p['total_tickets'], p['pct_ftf'],
             p['mttr_jours'], p['taux_recidive_pct'],
             p['trajet_moyen_min'], p['duree_sur_site_moyenne_min']]
            for p in par_technicien_out
        ]
        return build_xlsx_response(
            'rapport-field-service.xlsx',
            ['Technicien', 'Total tickets', '% FTF', 'MTTR (j)',
             '% récidive', 'Trajet moyen (min)', 'Durée sur site moy. (min)'],
            rows, sheet_title='Field Service')

    return Response(result)
