"""N85 — Vue carte : agrégation géographique (lecture seule, multi-tenant).

Rassemble en un seul appel tous les enregistrements géolocalisables de l'OS pour
les afficher sur une carte (Leaflet côté front) afin de planifier les visites
sans routage lourd :

  - ``lead``     : prospects CRM avec GPS (``crm.Lead.gps_lat/gps_lng``) ;
  - ``chantier`` : chantiers en cours (``installations.Installation`` dont le
    statut CANONIQUE n'est pas encore « installé ») avec GPS de site ;
  - ``installe`` : systèmes installés (statut canonique Installé / Réceptionné /
    Clôturé) avec GPS de site ;
  - ``visite``   : visites/poses prévues (visite technique d'un lead, pose prévue
    d'un chantier, intervention terrain planifiée) qui portent un GPS exploitable.

La classification chantier vs installé passe par ``Installation.canonical_statut``
afin que les statuts HÉRITÉS (pose / raccordement_onee / mise_en_service…) soient
rabattus sur l'entonnoir canonique courant (Installé / Réceptionné…), sans jamais
toucher la valeur stockée.

Chaque point porte ``id`` (composite, unique sur la carte), ``type``, ``statut``
(clé + libellé), ``label``, ``lat``, ``lng`` et ``detail_path`` (route front pour
ouvrir la fiche). Tout est strictement borné à la société de l'utilisateur ; on
peut filtrer par ``?types=`` et ``?statuts=``. Aucune écriture, aucun prix
d'achat / marge exposé.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAnyRole

# Types de points exposés par la carte. Le front affiche un filtre par type.
TYPE_LEAD = 'lead'
TYPE_CHANTIER = 'chantier'
TYPE_INSTALLE = 'installe'
TYPE_VISITE = 'visite'
ALL_TYPES = {TYPE_LEAD, TYPE_CHANTIER, TYPE_INSTALLE, TYPE_VISITE}


def _co_filter(user):
    """kwargs de filtrage société, ou None si accès interdit."""
    if user.company_id:
        return {'company': user.company}
    if user.is_superuser:
        return {}
    return None


def _wanted_set(raw):
    """Découpe un paramètre CSV (``?types=lead,chantier``) en ensemble propre."""
    return {t.strip() for t in (raw or '').split(',') if t.strip()}


def _point(coord):
    """Convertit un ``Decimal`` GPS en ``float`` ou ``None`` (valeur absente)."""
    return float(coord) if coord is not None else None


@api_view(['GET'])
@permission_classes([IsAnyRole])
def geo_points(request):
    """Points géolocalisés pour la vue carte (lecture seule, borné société).

    Filtres optionnels :
      - ``?types=lead,chantier,installe,visite`` (défaut : tous) ;
      - ``?statuts=signe,en_cours,nouveau`` filtre les chantiers/installés (par
        statut chantier) et les leads (par étape du pipeline).

    Réponse : ``{points: [{id, type, type_label, statut, statut_label, label,
    lat, lng, detail_path}], counts: {<type>: n, total: n}}``.
    """
    co = _co_filter(request.user)
    if co is None:
        return Response({'detail': 'Accès refusé.'}, status=403)

    wanted = _wanted_set(request.query_params.get('types'))

    def want(type_key):
        return not wanted or type_key in wanted

    statuts = _wanted_set(request.query_params.get('statuts'))

    from apps.crm.models import Lead
    from apps.installations.models import Installation, Intervention

    points = []

    # ── Leads géolocalisés (prospects) ────────────────────────────────────
    if want(TYPE_LEAD):
        leads = (Lead.objects.filter(**co, is_archived=False)
                 .exclude(gps_lat__isnull=True).exclude(gps_lng__isnull=True))
        for le in leads:
            # Filtre statut optionnel : pour un lead, le « statut » est l'étape.
            if statuts and le.stage not in statuts:
                continue
            nom = f"{le.nom} {le.prenom or ''}".strip() or le.societe or '—'
            points.append({
                'id': f'lead-{le.id}',
                'type': TYPE_LEAD,
                'type_label': 'Lead',
                'statut': le.stage,
                'statut_label': le.get_stage_display(),
                'label': nom,
                'lat': _point(le.gps_lat),
                'lng': _point(le.gps_lng),
                'detail_path': f'/crm/leads?lead={le.id}',
            })

    # ── Chantiers + systèmes installés (un seul parcours) ─────────────────
    # « installé » = système physiquement posé/réceptionné/clôturé. On classe
    # via le statut CANONIQUE (les statuts hérités sont rabattus), sans jamais
    # altérer la valeur stockée.
    installed_canonical = {
        Installation.Statut.INSTALLE,
        Installation.Statut.RECEPTIONNE,
        Installation.Statut.CLOTURE,
    }
    if want(TYPE_CHANTIER) or want(TYPE_INSTALLE):
        inst_qs = (Installation.objects.filter(**co)
                   .exclude(gps_lat__isnull=True).exclude(gps_lng__isnull=True))
        for inst in inst_qs:
            canonical = Installation.canonical_statut(inst.statut)
            point_type = (TYPE_INSTALLE if canonical in installed_canonical
                          else TYPE_CHANTIER)
            if not want(point_type):
                continue
            # Le filtre statut compare la valeur STOCKÉE (clé exacte de l'enum).
            if statuts and inst.statut not in statuts:
                continue
            points.append({
                'id': f'inst-{inst.id}',
                'type': point_type,
                'type_label': ('Système installé'
                               if point_type == TYPE_INSTALLE else 'Chantier'),
                'statut': inst.statut,
                'statut_label': inst.get_statut_display(),
                'label': inst.reference,
                'lat': _point(inst.gps_lat),
                'lng': _point(inst.gps_lng),
                'detail_path': f'/chantiers?chantier={inst.id}',
            })

    # ── Visites / poses prévues (planification terrain) ───────────────────
    # On n'expose que les visites portant un GPS exploitable, pour pouvoir les
    # situer sur la carte. Sources : visite technique du lead, pose prévue du
    # chantier, intervention terrain planifiée (GPS hérité du chantier).
    if want(TYPE_VISITE):
        # Visite technique d'un lead (non effectuée) avec GPS.
        lead_visits = (
            Lead.objects.filter(
                **co, is_archived=False, visite_effectuee=False)
            .exclude(visite_prevue_le__isnull=True)
            .exclude(gps_lat__isnull=True)
            .exclude(gps_lng__isnull=True))
        for le in lead_visits:
            nom = f"{le.nom} {le.prenom or ''}".strip() or le.societe or '—'
            points.append({
                'id': f'visite-lead-{le.id}',
                'type': TYPE_VISITE,
                'type_label': 'Visite technique',
                'statut': 'visite_technique',
                'statut_label': 'Visite technique',
                'label': f"Visite — {nom}",
                'lat': _point(le.gps_lat),
                'lng': _point(le.gps_lng),
                'date': le.visite_prevue_le.isoformat(),
                'detail_path': f'/crm/leads?lead={le.id}',
            })

        # Pose prévue d'un chantier avec GPS.
        poses = (Installation.objects.filter(**co)
                 .exclude(date_pose_prevue__isnull=True)
                 .exclude(gps_lat__isnull=True).exclude(gps_lng__isnull=True))
        for inst in poses:
            points.append({
                'id': f'visite-pose-{inst.id}',
                'type': TYPE_VISITE,
                'type_label': 'Pose prévue',
                'statut': 'pose_prevue',
                'statut_label': 'Pose prévue',
                'label': f"Pose — {inst.reference}",
                'lat': _point(inst.gps_lat),
                'lng': _point(inst.gps_lng),
                'date': inst.date_pose_prevue.isoformat(),
                'detail_path': f'/chantiers?chantier={inst.id}',
            })

        # Interventions terrain planifiées — GPS hérité du chantier lié.
        inter = (Intervention.objects.filter(**co)
                 .exclude(date_prevue__isnull=True)
                 .select_related('installation')
                 .exclude(installation__gps_lat__isnull=True)
                 .exclude(installation__gps_lng__isnull=True))
        for iv in inter:
            inst = iv.installation
            points.append({
                'id': f'visite-inter-{iv.id}',
                'type': TYPE_VISITE,
                'type_label': 'Intervention',
                'statut': 'intervention',
                'statut_label': iv.get_type_intervention_display(),
                'label': f"{iv.get_type_intervention_display()} — "
                         f"{inst.reference}",
                'lat': _point(inst.gps_lat),
                'lng': _point(inst.gps_lng),
                'date': iv.date_prevue.isoformat(),
                'detail_path': f'/chantiers?chantier={inst.id}',
            })

    counts = {}
    for p in points:
        counts[p['type']] = counts.get(p['type'], 0) + 1
    counts['total'] = len(points)

    return Response({'points': points, 'counts': counts})
