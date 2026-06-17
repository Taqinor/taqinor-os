"""T5 — Recherche globale + notifications in-app (lecture seule, multi-tenant).

Tout est borné à la société de l'utilisateur. La recherche balaie les entités
clés (leads, clients, devis, factures, chantiers, équipements, tickets SAV) ;
les notifications agrègent ce qui demande une action (activités en retard,
garanties expirant sous 90 j, factures impayées/en retard). Aucune écriture.
"""
from datetime import date, timedelta

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAnyRole


def _co_filter(user):
    """kwargs de filtrage société, ou None si accès interdit."""
    if user.company_id:
        return {'company': user.company}
    if user.is_superuser:
        return {}
    return None


@api_view(['GET'])
@permission_classes([IsAnyRole])
def global_search(request):
    """Recherche transverse. ?q=<terme> → résultats groupés par type.

    Chaque résultat porte type / id / label / sublabel ; le front mappe le
    type vers sa route pour ouvrir l'enregistrement. Limité par type pour
    rester rapide et lisible."""
    co = _co_filter(request.user)
    if co is None:
        return Response({'detail': 'Accès refusé.'}, status=403)
    q = (request.query_params.get('q') or '').strip()
    if len(q) < 2:
        return Response({'query': q, 'groups': []})

    PER = 6
    groups = []

    def add(type_key, label_fr, items):
        if items:
            groups.append({'type': type_key, 'label': label_fr, 'results': items})

    # ── Leads ────────────────────────────────────────────────────────────
    from apps.crm.models import Client, Lead
    leads = Lead.objects.filter(**co).filter(
        Q(nom__icontains=q) | Q(prenom__icontains=q) | Q(societe__icontains=q)
        | Q(email__icontains=q) | Q(telephone__icontains=q) | Q(ville__icontains=q)
    ).order_by('-date_creation')[:PER]
    add('lead', 'Leads', [
        {'id': le.id,
         'label': f"{le.nom} {le.prenom or ''}".strip() or le.societe or '—',
         'sublabel': le.societe or le.ville or le.telephone or ''}
        for le in leads
    ])

    # ── Clients ──────────────────────────────────────────────────────────
    clients = Client.objects.filter(**co).filter(
        Q(nom__icontains=q) | Q(prenom__icontains=q)
        | Q(email__icontains=q) | Q(telephone__icontains=q)
    ).order_by('nom')[:PER]
    add('client', 'Clients', [
        {'id': c.id,
         'label': f"{c.nom} {c.prenom or ''}".strip() or '—',
         'sublabel': c.email or c.telephone or ''}
        for c in clients
    ])

    # ── Devis / Factures ─────────────────────────────────────────────────
    from apps.ventes.models import Devis, Facture
    devis = Devis.objects.filter(**co).filter(
        Q(reference__icontains=q) | Q(client__nom__icontains=q)
    ).select_related('client').order_by('-id')[:PER]
    add('devis', 'Devis', [
        {'id': d.id, 'label': d.reference,
         'sublabel': getattr(d.client, 'nom', '') or ''}
        for d in devis
    ])
    factures = Facture.objects.filter(**co).filter(
        Q(reference__icontains=q) | Q(client__nom__icontains=q)
    ).select_related('client').order_by('-id')[:PER]
    add('facture', 'Factures', [
        {'id': f.id, 'label': f.reference,
         'sublabel': getattr(f.client, 'nom', '') or ''}
        for f in factures
    ])

    # ── Chantiers / Équipements ──────────────────────────────────────────
    from apps.installations.models import Installation
    from apps.sav.models import Equipement, Ticket
    chantiers = Installation.objects.filter(**co).filter(
        Q(reference__icontains=q)
    ).order_by('-id')[:PER]
    add('chantier', 'Chantiers',
        [{'id': i.id, 'label': i.reference, 'sublabel': ''} for i in chantiers])

    equipements = Equipement.objects.filter(**co).filter(
        Q(numero_serie__icontains=q) | Q(produit__nom__icontains=q)
    ).select_related('produit').order_by('-id')[:PER]
    add('equipement', 'Équipements', [
        {'id': e.id, 'label': e.numero_serie or f"#{e.id}",
         'sublabel': getattr(e.produit, 'nom', '') or ''}
        for e in equipements
    ])

    tickets = Ticket.objects.filter(**co).filter(
        Q(reference__icontains=q) | Q(description__icontains=q)
    ).order_by('-id')[:PER]
    add('ticket', 'Tickets SAV', [
        {'id': t.id, 'label': t.reference,
         'sublabel': (t.description or '')[:40]}
        for t in tickets
    ])

    return Response({'query': q, 'groups': groups})


def _notification_categories(co, today):
    """Calcule, à la volée et borné société, chaque catégorie d'évènement de la
    cloche. Renvoie {event_type: [items]}. N75 — moteur in-app unifié."""
    cats = {}

    # ── Activités en retard (records.Activity ouvertes, échéance passée) ──
    from apps.records.models import Activity
    overdue_acts = (Activity.objects
                    .filter(**co, done=False, due_date__lt=today)
                    .select_related('assigned_to')
                    .order_by('due_date')[:20])
    cats['activites_en_retard'] = [
        {'id': a.id, 'label': a.summary or 'Activité',
         'date': a.due_date.isoformat() if a.due_date else None,
         'lead_id': (a.object_id if a.content_type_id == _lead_ct_id() else None)}
        for a in overdue_acts
    ]

    # ── Garanties expirant sous 90 jours ─────────────────────────────────
    from apps.sav.models import Equipement, Ticket
    horizon = today + timedelta(days=90)
    eq_qs = (Equipement.objects
             .filter(**co, date_fin_garantie__gte=today,
                     date_fin_garantie__lte=horizon)
             .select_related('produit')
             .order_by('date_fin_garantie')[:20])
    cats['garanties_expirantes'] = [
        {'id': e.id, 'label': (getattr(e.produit, 'nom', None) or e.numero_serie
                               or f"#{e.id}"),
         'date': e.date_fin_garantie.isoformat()}
        for e in eq_qs
    ]

    # ── Factures impayées / en retard ────────────────────────────────────
    from apps.ventes.models import Facture
    fac_qs = (Facture.objects
              .filter(**co, statut__in=[Facture.Statut.EMISE,
                                        Facture.Statut.EN_RETARD])
              .select_related('client')
              .order_by('date_echeance')[:20])
    cats['factures_impayees'] = [
        {'id': f.id, 'label': f.reference,
         'sublabel': getattr(f.client, 'nom', '') or '',
         'overdue': bool(f.date_echeance and f.date_echeance < today)}
        for f in fac_qs
    ]

    # ── Chantiers à planifier / poser sous 14 jours (N75) ─────────────────
    from apps.installations.models import Installation
    not_done = [Installation.Statut.SIGNE, Installation.Statut.MATERIEL_COMMANDE,
                Installation.Statut.PLANIFIE, Installation.Statut.EN_COURS,
                Installation.Statut.A_PLANIFIER,
                Installation.Statut.POSE_EN_COURS,
                Installation.Statut.RACCORDEMENT_ONEE]
    cht_qs = (Installation.objects
              .filter(**co, annule=False, statut__in=not_done,
                      date_pose_prevue__isnull=False,
                      date_pose_prevue__lte=today + timedelta(days=14))
              .order_by('date_pose_prevue')[:20])
    cats['chantiers_a_planifier'] = [
        {'id': i.id, 'label': i.reference,
         'date': i.date_pose_prevue.isoformat() if i.date_pose_prevue else None}
        for i in cht_qs
    ]

    # ── Visites de maintenance dues (N75 — calculées à la volée, cf. T16) ──
    from apps.sav.models import ContratMaintenance
    maintenance = []
    for c in (ContratMaintenance.objects
              .filter(**co, actif=True).select_related('client')[:50]):
        if c.is_due(today):
            maintenance.append(
                {'id': c.id, 'label': getattr(c.client, 'nom', '') or f"Contrat #{c.id}",
                 'date': c.prochaine_visite().isoformat()})
        if len(maintenance) >= 20:
            break
    cats['maintenance_due'] = maintenance

    # ── Tickets SAV ouverts ───────────────────────────────────────────────
    tk_qs = (Ticket.objects
             .filter(**co, annule=False, statut__in=Ticket.OPEN_STATUTS)
             .select_related('client')
             .order_by('-date_creation')[:20])
    cats['tickets_ouverts'] = [
        {'id': t.id, 'label': t.reference,
         'sublabel': getattr(t.client, 'nom', '') or ''}
        for t in tk_qs
    ]

    # ── Stock bas (quantité ≤ seuil d'alerte, seuil renseigné) ────────────
    from django.db.models import F
    from apps.stock.models import Produit
    prod_qs = (Produit.objects
               .filter(**co, seuil_alerte__gt=0,
                       quantite_stock__lte=F('seuil_alerte'))
               .order_by('quantite_stock')[:20])
    cats['stock_bas'] = [
        {'id': p.id, 'label': p.nom,
         'sublabel': f"{p.quantite_stock} ≤ {p.seuil_alerte}"}
        for p in prod_qs
    ]
    return cats


def _resolve_prefs(user):
    """Carte {event_type: in_app bool} pour l'utilisateur ; manquant = activé."""
    from .models import NOTIF_EVENT_KEYS, NotificationPreference
    prefs = {k: True for k in NOTIF_EVENT_KEYS}
    for p in NotificationPreference.objects.filter(user=user):
        if p.event_type in prefs:
            prefs[p.event_type] = p.in_app
    return prefs


@api_view(['GET'])
@permission_classes([IsAnyRole])
def notifications(request):
    """Cloche de notifications in-app (aucun email). Compte + liste cliquable
    des éléments demandant une action, calculés à la volée et bornés société.

    N75 — moteur unifié : couvre activités en retard, garanties expirantes,
    factures impayées, chantiers à planifier/poser, visites de maintenance dues,
    tickets SAV ouverts et stock bas. Chaque type respecte la préférence in-app
    de l'utilisateur (un type désactivé n'est pas compté ni listé ; défaut =
    tout activé → comportement historique inchangé). L'envoi sortant
    WhatsApp/email/SMS reste gated (G1/G2/G9)."""
    co = _co_filter(request.user)
    if co is None:
        return Response({'detail': 'Accès refusé.'}, status=403)
    today = date.today()
    cats = _notification_categories(co, today)
    prefs = _resolve_prefs(request.user)

    total = sum(len(items) for key, items in cats.items() if prefs.get(key, True))
    payload = {'total': total, 'preferences': prefs}
    # Un type désactivé renvoie une liste vide (ne pollue pas la cloche).
    for key, items in cats.items():
        payload[key] = items if prefs.get(key, True) else []
    return Response(payload)


@api_view(['GET', 'POST'])
@permission_classes([IsAnyRole])
def notification_preferences(request):
    """Préférences in-app de notification de l'utilisateur (N75).

    GET  → {event_type: {label, in_app}} (défauts activés pour les manquants).
    POST → upsert {event_type, in_app} (borné aux types connus + à la société
            de l'utilisateur ; jamais d'autre utilisateur)."""
    from .models import NOTIF_EVENT_TYPES, NOTIF_EVENT_KEYS, NotificationPreference
    user = request.user
    if request.method == 'POST':
        event_type = request.data.get('event_type')
        if event_type not in NOTIF_EVENT_KEYS:
            return Response({'detail': 'Type inconnu.'}, status=400)
        in_app = bool(request.data.get('in_app', True))
        NotificationPreference.objects.update_or_create(
            user=user, event_type=event_type,
            defaults={'in_app': in_app, 'company': user.company})
    prefs = _resolve_prefs(user)
    labels = dict(NOTIF_EVENT_TYPES)
    return Response({
        'preferences': [
            {'event_type': k, 'label': labels[k], 'in_app': prefs[k]}
            for k in NOTIF_EVENT_KEYS
        ],
    })


def _lead_ct_id():
    from apps.crm.models import Lead
    return ContentType.objects.get_for_model(Lead).id
