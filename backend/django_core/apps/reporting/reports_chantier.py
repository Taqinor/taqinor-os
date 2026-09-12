"""CHT27 — Cockpit KPI chantier (`reports/chantier/`), INSTRUMENTÉ.

Trois sélecteurs, lecture seule, multi-tenant (même patron que `reports_field.py`/
`sav_sla.py` : imports LOCAUX de `apps.installations.models`, jamais au
chargement du module — aucune arête d'import statique cross-app depuis
`reporting`) :

  * `cycle_time_chantiers`  — durées médianes/moyennes (jours) entre les
    transitions canoniques SIGNE→PLANIFIE→EN_COURS→INSTALLE→RECEPTIONNE,
    dérivées du CHATTER `installations.InstallationActivity` (jamais des
    champs de dates milestone : `date_pose_prevue` et consorts sont à DOUBLE
    EMPLOI — posés soit manuellement par un utilisateur, soit auto-stampés à
    l'entrée dans le statut correspondant SI VIDE — donc inutilisables comme
    horodatage fiable de transition). `old_value`/`new_value` du chatter sont
    des LIBELLÉS FRANÇAIS AFFICHÉS (voir `apps.installations.activity._display`) :
    on les re-résout en CLÉS canoniques via `Installation.canonical_statut`,
    JAMAIS un parsing du français.
  * `taux_reprise_post_mes` — taux de chantiers ayant subi une intervention
    DEPANNAGE dans les N jours suivant la mise en service. DISTINCT de
    `sav.Ticket.est_recidive` (signal PAR-TICKET, réservé au module SAV) :
    ceci est un indicateur CHANTIER agrégé, ne duplique aucune logique SAV.
  * `chantiers_en_retard` — chantiers dont `date_pose_prevue` est dépassée
    alors que la pose n'a pas encore eu lieu (ce champ EST le bon usage ici :
    contexte de planification, à la différence du sélecteur ci-dessus).

AUCUN prix d'achat / marge d'achat n'entre dans ce module (règle fondateur).
Adjacence : NTDATA4 (dataset BI chantiers, `core.data_explorer`) reste au plan
plateforme — ce module ne crée aucun `bi_datasets.py`.
"""
import statistics
from datetime import timedelta

from authentication.permissions import IsResponsableOrAdmin
from core.dates import aujourd_hui_local
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

# Chaîne canonique INSTRUMENTÉE (volontairement hors MATERIEL_COMMANDE et
# CLOTURE — voir le programme CHT27 : seuls ces 5 jalons sont mesurés).
_CANONICAL_CHAIN = ['signe', 'planifie', 'en_cours', 'installe', 'receptionne']
_SEGMENTS = list(zip(_CANONICAL_CHAIN, _CANONICAL_CHAIN[1:]))
_SEGMENT_LABELS = {
    ('signe', 'planifie'): 'Signé → Planifié',
    ('planifie', 'en_cours'): 'Planifié → En cours',
    ('en_cours', 'installe'): 'En cours → Installé',
    ('installe', 'receptionne'): 'Installé → Réceptionné',
}


def _pct(numerator, denominator):
    if not denominator:
        return None
    return round(numerator / denominator * 100, 1)


def _median(values):
    vals = [v for v in values if v is not None]
    return round(statistics.median(vals), 1) if vals else None


def _mean(values):
    vals = [v for v in values if v is not None]
    return round(sum(vals) / len(vals), 1) if vals else None


def _segment_result(deltas_par_segment):
    """Met en forme {n, jours_median, jours_moyen} par segment canonique,
    dans l'ordre de la chaîne — `deltas_par_segment` peut être un dict
    partiel ou vide (aucun chantier mesurable)."""
    out = []
    for seg in _SEGMENTS:
        vals = deltas_par_segment.get(seg, [])
        out.append({
            'de': seg[0], 'vers': seg[1], 'label': _SEGMENT_LABELS[seg],
            'n': len(vals),
            'jours_median': _median(vals),
            'jours_moyen': _mean(vals),
        })
    return out


def _label_to_statut_key_map():
    """Inverse de `Installation.Statut.choices` : libellé affiché → clé
    stockée (couvre AUSSI les libellés hérités, ex. « Posé » → 'pose')."""
    from apps.installations.models import Installation
    return {str(label): value for value, label in Installation.Statut.choices}


def _first_reached_map(installations, label_to_key):
    """Pour chaque chantier, l'instant (datetime) de PREMIÈRE entrée dans
    chaque statut CANONIQUE, dérivé du chatter — jamais des dates milestone.

    Le point de départ (statut dans lequel le chantier a été créé) est déduit
    de l'`old_value` de la toute première ligne de chatter 'statut' (elle
    précède le premier changement enregistré) ; `Installation.date_creation`
    sert d'horodatage à ce point de départ — c'est un timestamp d'audit
    (auto_now_add), jamais réécrit, donc AUCUN double emploi contrairement
    aux champs `date_*` milestone. Un chantier sans aucune ligne de chatter
    'statut' (jamais transitionné) n'a qu'un statut de départ et aucun
    segment n'est calculable pour lui — c'est correct (0 mesure)."""
    from apps.installations.models import Installation, InstallationActivity

    ids = [inst.id for inst in installations]
    acts = list(
        InstallationActivity.objects
        .filter(installation_id__in=ids,
                kind=InstallationActivity.Kind.MODIFICATION, field='statut')
        .order_by('installation_id', 'created_at', 'id'))
    par_installation = {}
    for act in acts:
        par_installation.setdefault(act.installation_id, []).append(act)

    out = {}
    for inst in installations:
        events = []
        acts_inst = par_installation.get(inst.id, [])
        if acts_inst:
            old_key = label_to_key.get(acts_inst[0].old_value)
            if old_key is not None:
                events.append(
                    (inst.date_creation, Installation.canonical_statut(old_key)))
        for act in acts_inst:
            new_key = label_to_key.get(act.new_value)
            if new_key is not None:
                events.append(
                    (act.created_at, Installation.canonical_statut(new_key)))

        first_reached = {}
        for ts, canon in events:
            if canon not in first_reached:
                first_reached[canon] = ts
        out[inst.id] = first_reached
    return out


def cycle_time_chantiers(company, debut=None, fin=None):
    """CHT27 — durées médianes/moyennes (jours) entre transitions canoniques,
    globalement puis groupées par `type_installation` et par équipe terrain
    (dérivée de la première intervention du chantier portant une `equipe_ref`
    — le chantier lui-même ne porte pas d'équipe propre ; sans intervention
    équipée, le chantier tombe dans le seau « Sans équipe »).

    `debut`/`fin` (dates, optionnelles) filtrent la POPULATION de chantiers
    sur `date_creation` (fenêtre d'ouverture) — chaque chantier retenu garde
    son historique de chatter COMPLET et non tronqué, pour ne jamais casser
    une chaîne de transitions au bord de la fenêtre demandée.

    Renvoie {segments, par_type_installation, par_equipe} — jamais aucun prix
    d'achat ni marge d'achat."""
    from apps.installations.models import Installation, Intervention

    qs = Installation.objects.filter(company=company, annule=False)
    if debut is not None:
        qs = qs.filter(date_creation__date__gte=debut)
    if fin is not None:
        qs = qs.filter(date_creation__date__lte=fin)
    installations = list(
        qs.only('id', 'date_creation', 'statut', 'type_installation'))

    if not installations:
        return {
            'segments': _segment_result({}),
            'par_type_installation': [],
            'par_equipe': [],
        }

    label_to_key = _label_to_statut_key_map()
    first_reached_map = _first_reached_map(installations, label_to_key)

    def deltas_pour(subset):
        out = {seg: [] for seg in _SEGMENTS}
        for inst in subset:
            fr = first_reached_map.get(inst.id, {})
            for seg in _SEGMENTS:
                de, vers = seg
                if de in fr and vers in fr:
                    delta = (fr[vers] - fr[de]).total_seconds() / 86400
                    if delta > 0:
                        out[seg].append(delta)
        return out

    segments = _segment_result(deltas_pour(installations))

    # ── Groupé par type d'installation ──────────────────────────────────
    type_labels = dict(Installation.TypeInstallation.choices)
    par_type_buckets = {}
    for inst in installations:
        par_type_buckets.setdefault(inst.type_installation, []).append(inst)
    par_type_installation = [
        {
            'type_installation': type_value,
            'label': type_labels.get(type_value, 'Non renseigné'),
            'segments': _segment_result(deltas_pour(subset)),
        }
        for type_value, subset in par_type_buckets.items()
    ]

    # ── Groupé par équipe terrain (via les interventions du chantier) ────
    ids = [inst.id for inst in installations]
    equipe_par_installation = {}
    rows = (
        Intervention.objects
        .filter(installation_id__in=ids, equipe_ref__isnull=False)
        .order_by('installation_id', 'date_prevue', 'id')
        .values('installation_id', 'equipe_ref_id', 'equipe_ref__nom'))
    for row in rows:
        equipe_par_installation.setdefault(
            row['installation_id'],
            (row['equipe_ref_id'], row['equipe_ref__nom']))

    par_equipe_buckets = {}
    for inst in installations:
        key = equipe_par_installation.get(inst.id, (None, 'Sans équipe'))
        par_equipe_buckets.setdefault(key, []).append(inst)
    par_equipe = [
        {
            'equipe_id': equipe_id,
            'equipe': equipe_nom,
            'segments': _segment_result(deltas_pour(subset)),
        }
        for (equipe_id, equipe_nom), subset in par_equipe_buckets.items()
    ]

    return {
        'segments': segments,
        'par_type_installation': par_type_installation,
        'par_equipe': par_equipe,
    }


def taux_reprise_post_mes(company, fenetre_jours=30):
    """CHT27 — proportion des chantiers réceptionnés (MES connue, fenêtre
    ENTIÈREMENT écoulée) ayant subi au moins une intervention DEPANNAGE
    RÉALISÉE (`date_realisee`) dans les `fenetre_jours` suivant
    `date_mise_en_service`. Un chantier dont la fenêtre n'est pas encore
    écoulée est exclu du dénominateur (sinon il compterait à tort comme
    « sans reprise »). DISTINCT de `sav.Ticket.est_recidive` (signal
    par-ticket) — aucune duplication de cette logique ici."""
    from apps.installations.models import Installation, Intervention

    aujourd_hui = aujourd_hui_local()
    seuil = aujourd_hui - timedelta(days=fenetre_jours)
    eligibles = list(
        Installation.objects.filter(
            company=company, annule=False,
            date_mise_en_service__isnull=False,
            date_mise_en_service__lte=seuil,
        ).only('id', 'date_mise_en_service'))

    if not eligibles:
        return {
            'fenetre_jours': fenetre_jours, 'nb_eligibles': 0,
            'nb_avec_reprise': 0, 'taux_pct': None,
        }

    ids = [inst.id for inst in eligibles]
    mes_par_installation = {inst.id: inst.date_mise_en_service for inst in eligibles}

    depannages = (
        Intervention.objects
        .filter(installation_id__in=ids,
                type_intervention=Intervention.Type.DEPANNAGE,
                date_realisee__isnull=False)
        .values('installation_id', 'date_realisee'))

    avec_reprise = set()
    for row in depannages:
        mes = mes_par_installation.get(row['installation_id'])
        if mes is None:
            continue
        delta_jours = (row['date_realisee'] - mes).days
        if 0 <= delta_jours <= fenetre_jours:
            avec_reprise.add(row['installation_id'])

    return {
        'fenetre_jours': fenetre_jours,
        'nb_eligibles': len(eligibles),
        'nb_avec_reprise': len(avec_reprise),
        'taux_pct': _pct(len(avec_reprise), len(eligibles)),
    }


def chantiers_en_retard(company):
    """CHT27 — chantiers dont `date_pose_prevue` est dépassée alors que la
    pose n'a pas encore eu lieu (statut canonique strictement avant INSTALLE
    dans `Installation.STATUT_ORDER` — couvre aussi les alias hérités, ex.
    'pose_en_cours'/'raccordement_onee' → EN_COURS canonique). Ici
    `date_pose_prevue` est le bon usage du champ (planification), à la
    différence de `cycle_time_chantiers` qui l'évite pour les transitions."""
    from apps.installations.models import Installation

    seuil_index = Installation.STATUT_ORDER.index(Installation.Statut.INSTALLE)
    statuts_avant_pose = [
        value for value, _label in Installation.Statut.choices
        if Installation.STATUT_ORDER.index(
            Installation.canonical_statut(value)) < seuil_index
    ]

    aujourd_hui = aujourd_hui_local()
    qs = (
        Installation.objects
        .filter(company=company, annule=False,
                date_pose_prevue__isnull=False,
                date_pose_prevue__lt=aujourd_hui,
                statut__in=statuts_avant_pose)
        .select_related('client')
        .order_by('date_pose_prevue'))

    items = [
        {
            'installation_id': inst.id,
            'reference': inst.reference,
            'client': getattr(inst.client, 'nom', None),
            'date_pose_prevue': str(inst.date_pose_prevue),
            'jours_retard': (aujourd_hui - inst.date_pose_prevue).days,
        }
        for inst in qs
    ]
    return {'total': len(items), 'items': items}


@api_view(['GET'])
@permission_classes([IsResponsableOrAdmin])
def pilotage_chantiers_report(request):
    """CHT27 — Cockpit KPI chantier (`reports/chantier/`). Filtres optionnels
    `?from=&to=` (fenêtre de création des chantiers pour le cycle time) et
    `?fenetre_jours=` (fenêtre de reprise post-MES, défaut 30). Réservé
    responsable/admin. Renvoie {cycle_time, taux_reprise_post_mes,
    chantiers_en_retard} — jamais aucun prix d'achat ni marge d'achat."""
    if not request.user.company_id:
        if not request.user.is_superuser:
            return Response({'detail': 'Accès refusé.'}, status=403)
        return Response({
            'cycle_time': {
                'segments': _segment_result({}),
                'par_type_installation': [], 'par_equipe': [],
            },
            'taux_reprise_post_mes': {
                'fenetre_jours': 30, 'nb_eligibles': 0,
                'nb_avec_reprise': 0, 'taux_pct': None,
            },
            'chantiers_en_retard': {'total': 0, 'items': []},
        })

    company = request.user.company
    debut = request.query_params.get('from')
    fin = request.query_params.get('to')
    try:
        fenetre_jours = int(request.query_params.get('fenetre_jours', 30))
    except (TypeError, ValueError):
        fenetre_jours = 30

    return Response({
        'cycle_time': cycle_time_chantiers(company, debut=debut, fin=fin),
        'taux_reprise_post_mes': taux_reprise_post_mes(
            company, fenetre_jours=fenetre_jours),
        'chantiers_en_retard': chantiers_en_retard(company),
    })
