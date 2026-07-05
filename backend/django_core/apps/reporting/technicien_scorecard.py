"""XFSM17 — Scorecard technicien (coaching).

Combine en UNE vue par technicien les briques déjà existantes, jamais
regroupées ensemble :
  * interventions terminées + durée réelle vs estimée (F15, XFSM22)
  * récidives (XFSM15, `sav.Ticket.est_recidive`)
  * ponctualité (XFSM5, `installations.selectors.taux_ponctualite`)
  * NPS des chantiers livrés (FG238, `compta.services.score_nps`) — agrégé
    sur les chantiers où le technicien est intervenu (`EnqueteNPS.chantier_id`
    résolu via les interventions du technicien).
  * utilisation (FG299, `installations.selectors.plan_de_charge_equipes`)

Lecture seule, multi-tenant. Réservé responsable/admin — JAMAIS visible par
le technicien lui-même, et n'expose AUCUN coût interne (prix d'achat,
marge). Compare le technicien à la moyenne de l'équipe (tous les
techniciens actifs sur la période).
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


def _technicien_nps(company, chantier_ids):
    """NPS (FG238) agrégé sur un sous-ensemble de chantiers (`chantier_id`).

    Import local de `apps.compta.models.EnqueteNPS` (même patron que les
    autres lectures cross-app de `reporting` — jamais au chargement du
    module). `None` si aucune enquête répondue sur ces chantiers."""
    from apps.compta.models import EnqueteNPS
    if not chantier_ids:
        return {'nps': None, 'total': 0, 'promoteurs': 0, 'passifs': 0,
                'detracteurs': 0}
    reponses = EnqueteNPS.objects.filter(
        company=company, chantier_id__in=chantier_ids,
        statut=EnqueteNPS.Statut.REPONDUE, score__isnull=False)
    total = reponses.count()
    if total == 0:
        return {'nps': None, 'total': 0, 'promoteurs': 0, 'passifs': 0,
                'detracteurs': 0}
    promoteurs = reponses.filter(score__gte=9).count()
    detracteurs = reponses.filter(score__lte=6).count()
    passifs = total - promoteurs - detracteurs
    nps = round((promoteurs - detracteurs) * 100 / total)
    return {'nps': nps, 'total': total, 'promoteurs': promoteurs,
            'passifs': passifs, 'detracteurs': detracteurs}


def _technicien_stats(company, technicien, *, start=None, end=None):
    """Statistiques brutes d'UN technicien sur la fenêtre [start, end]."""
    from apps.installations import selectors as installations_selectors
    from apps.installations.field_capture import labour_days_for_intervention
    from apps.installations.models import Intervention
    from apps.sav.models import Ticket

    interv_qs = Intervention.objects.filter(
        company=company, technicien=technicien, annulee=False)
    if start:
        interv_qs = interv_qs.filter(date_prevue__gte=start)
    if end:
        interv_qs = interv_qs.filter(date_prevue__lte=end)
    interventions = list(interv_qs.select_related('installation'))

    terminees = [
        i for i in interventions
        if i.statut in (Intervention.Statut.TERMINEE, Intervention.Statut.VALIDEE)
    ]
    durees_reelles = []
    for i in terminees:
        jours = labour_days_for_intervention(i)
        if jours is not None:
            durees_reelles.append(float(jours))

    chantier_ids = {
        i.installation_id for i in interventions if i.installation_id}

    ticket_qs = Ticket.objects.filter(
        company=company, technicien_responsable=technicien)
    if start:
        ticket_qs = ticket_qs.filter(date_creation__date__gte=start)
    if end:
        ticket_qs = ticket_qs.filter(date_creation__date__lte=end)
    tickets = list(ticket_qs)
    recidives = sum(1 for t in tickets if t.est_recidive)

    ponctualite = installations_selectors.taux_ponctualite(
        company, debut=start, fin=end, technicien_id=technicien.id)

    nps = _technicien_nps(company, chantier_ids)

    utilisation_pct = None
    if start and end:
        plan = installations_selectors.plan_de_charge_equipes(
            company, start, end)
        entry = next(
            (t for t in plan['techniciens'] if t['technicien_id'] == technicien.id),
            None)
        if entry:
            utilisation_pct = entry['charge_pct']

    return {
        'technicien_id': technicien.id,
        'technicien': technicien.get_full_name() or technicien.username,
        'interventions_total': len(interventions),
        'interventions_terminees': len(terminees),
        'duree_reelle_moyenne_jours': _avg(durees_reelles),
        'nb_recidives': recidives,
        'taux_recidive_pct': _pct(recidives, len(tickets)),
        'ponctualite_pct': ponctualite['taux_pct'],
        'nps': nps['nps'],
        'nps_total_reponses': nps['total'],
        'utilisation_pct': utilisation_pct,
    }


@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def technicien_scorecard(request):
    """XFSM17 — Scorecard technicien (`insights/technicien-scorecard/`).

    `?technicien=<id>` (requis) et `?periode=&from=&to=` (fenêtre optionnelle
    sur `date_prevue`/`date_creation`). Renvoie le scorecard du technicien
    ainsi que la MOYENNE ÉQUIPE (tous les techniciens de la société ayant au
    moins une intervention sur la fenêtre) pour comparaison. Jamais de coût
    interne. `?export=xlsx` renvoie un tableau récapitulatif technicien vs
    moyenne équipe."""
    co = _co(request.user)
    if co is None:
        return Response({'detail': 'Accès refusé.'}, status=403)

    from django.contrib.auth import get_user_model
    from apps.installations.models import Intervention

    technicien_id = request.query_params.get('technicien')
    if not technicien_id:
        return Response({'detail': '?technicien est requis.'}, status=400)

    User = get_user_model()
    try:
        technicien = User.objects.get(id=technicien_id, company=request.user.company)
    except (User.DoesNotExist, ValueError):
        return Response({'detail': 'Technicien introuvable.'}, status=404)

    start = request.query_params.get('from')
    end = request.query_params.get('to')

    scorecard = _technicien_stats(
        request.user.company, technicien, start=start, end=end)

    # ── Moyenne équipe : tous les techniciens ayant au moins une intervention
    # sur la fenêtre (même bassin que XFSM2 `_techniciens_eligibles`). ──
    equipe_qs = Intervention.objects.filter(
        company=request.user.company, technicien__isnull=False, annulee=False)
    if start:
        equipe_qs = equipe_qs.filter(date_prevue__gte=start)
    if end:
        equipe_qs = equipe_qs.filter(date_prevue__lte=end)
    equipe_ids = list(
        equipe_qs.values_list('technicien_id', flat=True).distinct())

    stats_equipe = []
    for uid in equipe_ids:
        try:
            u = User.objects.get(id=uid)
        except User.DoesNotExist:
            continue
        stats_equipe.append(
            _technicien_stats(request.user.company, u, start=start, end=end))

    def _moyenne_equipe(key):
        return _avg([s[key] for s in stats_equipe])

    moyenne_equipe = {
        'nb_techniciens': len(stats_equipe),
        'interventions_terminees': _moyenne_equipe('interventions_terminees'),
        'duree_reelle_moyenne_jours': _moyenne_equipe('duree_reelle_moyenne_jours'),
        'taux_recidive_pct': _moyenne_equipe('taux_recidive_pct'),
        'ponctualite_pct': _moyenne_equipe('ponctualite_pct'),
        'nps': _moyenne_equipe('nps'),
        'utilisation_pct': _moyenne_equipe('utilisation_pct'),
    }

    result = {
        'scorecard': scorecard,
        'moyenne_equipe': moyenne_equipe,
    }

    if request.query_params.get('export') == 'xlsx':
        rows = [
            ['Technicien', scorecard['interventions_terminees'],
             scorecard['duree_reelle_moyenne_jours'],
             scorecard['taux_recidive_pct'], scorecard['ponctualite_pct'],
             scorecard['nps'], scorecard['utilisation_pct']],
            ['Moyenne équipe', moyenne_equipe['interventions_terminees'],
             moyenne_equipe['duree_reelle_moyenne_jours'],
             moyenne_equipe['taux_recidive_pct'],
             moyenne_equipe['ponctualite_pct'], moyenne_equipe['nps'],
             moyenne_equipe['utilisation_pct']],
        ]
        return build_xlsx_response(
            'scorecard-technicien.xlsx',
            ['', 'Interventions terminées', 'Durée réelle moy. (j)',
             '% récidive', '% ponctualité', 'NPS', '% utilisation'],
            rows, sheet_title='Scorecard')

    return Response(result)
