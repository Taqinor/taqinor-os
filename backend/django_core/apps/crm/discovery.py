"""Recherche globale + notifications calculées à la volée (CRM).

Tout est strictement scopé à la société de l'utilisateur. Les modèles des
autres apps (ventes, installations, sav) sont lus en LECTURE SEULE — aucune
migration ni écriture ailleurs. Les imports sont locaux et tolérants : une app
absente n'empêche jamais le reste de répondre.

Les « route hints » suivent les routes front existantes (router/index.jsx) ou,
à défaut, des chemins de liste raisonnables que l'intégrateur peut ajuster.
"""
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

# Fenêtre « garantie bientôt expirée » (jours).
WARRANTY_WINDOW_DAYS = 90


def _scoped(model, company):
    """Queryset d'un modèle filtré sur la société (ou tout si superadmin sans
    société). Renvoie None si le modèle n'a pas de champ company."""
    try:
        model._meta.get_field('company')
    except Exception:
        return model.objects.all()
    if company is None:
        return model.objects.all()
    return model.objects.filter(company=company)


def global_search(user, q, limit=8):
    """Recherche multi-modèles. Renvoie une liste de groupes :
    [{type, label, items:[{id, label, route}]}] — tout scopé société."""
    q = (q or '').strip()
    company = user.company if user.company_id else None
    if not q:
        return []
    groups = []

    # ── Leads ──
    try:
        from .models import Lead
        qs = _scoped(Lead, company).filter(
            Q(nom__icontains=q) | Q(prenom__icontains=q) |
            Q(societe__icontains=q) | Q(email__icontains=q) |
            Q(telephone__icontains=q) | Q(ville__icontains=q)
        ).order_by('-date_creation')[:limit]
        items = [{
            'id': le.id,
            'label': f"{le.nom} {le.prenom or ''}".strip() + (
                f" · {le.societe}" if le.societe else ''),
            'route': f"/crm/leads?lead={le.id}",
        } for le in qs]
        if items:
            groups.append({'type': 'leads', 'label': 'Leads', 'items': items})
    except Exception:
        pass

    # ── Clients ──
    try:
        from .models import Client
        qs = _scoped(Client, company).filter(
            Q(nom__icontains=q) | Q(prenom__icontains=q) |
            Q(email__icontains=q) | Q(telephone__icontains=q)
        ).order_by('-date_creation')[:limit]
        items = [{
            'id': c.id,
            'label': f"{c.nom} {c.prenom or ''}".strip(),
            'route': f"/crm?client={c.id}",
        } for c in qs]
        if items:
            groups.append({
                'type': 'clients', 'label': 'Clients', 'items': items})
    except Exception:
        pass

    # ── Devis (ventes) ──
    try:
        from apps.ventes.models import Devis
        qs = _scoped(Devis, company).filter(
            Q(reference__icontains=q) | Q(client__nom__icontains=q)
        ).order_by('-date_creation')[:limit]
        items = [{
            'id': d.id,
            'label': f"{d.reference} · {d.client.nom if d.client_id else ''}"
                     .strip(' ·'),
            'route': f"/ventes/devis?devis={d.id}",
        } for d in qs]
        if items:
            groups.append({'type': 'devis', 'label': 'Devis', 'items': items})
    except Exception:
        pass

    # ── Factures (ventes) ──
    try:
        from apps.ventes.models import Facture
        qs = _scoped(Facture, company).filter(
            Q(reference__icontains=q) | Q(client__nom__icontains=q)
        ).order_by('-date_emission')[:limit]
        items = [{
            'id': f.id,
            'label': f"{f.reference} · {f.client.nom if f.client_id else ''}"
                     .strip(' ·'),
            'route': f"/ventes/factures?facture={f.id}",
        } for f in qs]
        if items:
            groups.append({
                'type': 'factures', 'label': 'Factures', 'items': items})
    except Exception:
        pass

    # ── Chantiers (installations) ──
    try:
        from apps.installations.models import Installation
        qs = _scoped(Installation, company).filter(
            Q(reference__icontains=q) | Q(client__nom__icontains=q)
        ).order_by('-id')[:limit]
        items = [{
            'id': i.id,
            'label': f"{i.reference} · {i.client.nom if i.client_id else ''}"
                     .strip(' ·'),
            'route': f"/chantiers?chantier={i.id}",
        } for i in qs]
        if items:
            groups.append({
                'type': 'chantiers', 'label': 'Chantiers', 'items': items})
    except Exception:
        pass

    # ── Équipements (sav) ──
    try:
        from apps.sav.models import Equipement
        qs = _scoped(Equipement, company).filter(
            Q(numero_serie__icontains=q) | Q(produit__nom__icontains=q)
        ).order_by('-id')[:limit]

        def _equip_label(e):
            base = e.numero_serie or ''
            if e.produit_id:
                base = f"{base} · {e.produit.nom}" if base else e.produit.nom
            return base
        items = [{
            'id': e.id,
            'label': _equip_label(e),
            'route': f"/equipements?equipement={e.id}",
        } for e in qs]
        items = [it for it in items if it['label'].strip(' ·')]
        if items:
            groups.append({
                'type': 'equipements', 'label': 'Équipements',
                'items': items})
    except Exception:
        pass

    # ── Tickets SAV ──
    try:
        from apps.sav.models import Ticket
        qs = _scoped(Ticket, company).filter(
            Q(reference__icontains=q) | Q(description__icontains=q) |
            Q(client__nom__icontains=q)
        ).order_by('-id')[:limit]
        items = [{
            'id': t.id,
            'label': f"{t.reference} · {t.client.nom if t.client_id else ''}"
                     .strip(' ·'),
            'route': f"/sav?ticket={t.id}",
        } for t in qs]
        if items:
            groups.append({
                'type': 'tickets', 'label': 'Tickets SAV', 'items': items})
    except Exception:
        pass

    return groups


def notifications(user, limit=10):
    """Notifications in-app calculées à la volée (aucun scheduler) :
      - activités en retard (records.Activity non faites, échéance dépassée) ;
      - garanties expirant sous 90 jours (sav.Equipement) ;
      - factures impayées / en retard (ventes.Facture).
    Renvoie {total, groups:[{type, label, count, items:[{id,label,route}]}]}.
    """
    company = user.company if user.company_id else None
    today = timezone.now().date()
    groups = []

    # ── Activités en retard ──
    try:
        from apps.records.models import Activity
        qs = _scoped(Activity, company).filter(
            done=False, due_date__isnull=False, due_date__lt=today
        ).order_by('due_date')
        count = qs.count()

        def _act_label(a):
            base = a.summary or getattr(a.activity_type, 'nom', 'Activité')
            return f"{base} · échue le {a.due_date}"
        items = [{
            'id': a.id,
            'label': _act_label(a),
            'route': '/activites',
        } for a in qs[:limit]]
        if count:
            groups.append({
                'type': 'overdue_activities',
                'label': 'Activités en retard',
                'count': count, 'items': items})
    except Exception:
        pass

    # ── Garanties expirant sous 90 jours ──
    try:
        from apps.sav.models import Equipement
        horizon = today + timedelta(days=WARRANTY_WINDOW_DAYS)
        qs = _scoped(Equipement, company).filter(
            date_fin_garantie__isnull=False,
            date_fin_garantie__gte=today,
            date_fin_garantie__lte=horizon,
        ).order_by('date_fin_garantie')
        count = qs.count()

        def _warranty_label(e):
            nom = (getattr(e.produit, 'nom', 'Équipement')
                   if e.produit_id else 'Équipement')
            return f"{nom} · garantie jusqu'au {e.date_fin_garantie}"
        items = [{
            'id': e.id,
            'label': _warranty_label(e),
            'route': f"/equipements?equipement={e.id}",
        } for e in qs[:limit]]
        if count:
            groups.append({
                'type': 'expiring_warranties',
                'label': 'Garanties bientôt expirées',
                'count': count, 'items': items})
    except Exception:
        pass

    # ── Factures impayées / en retard ──
    try:
        from apps.ventes.models import Facture
        qs = _scoped(Facture, company).filter(
            Q(statut='en_retard') |
            Q(statut='emise', date_echeance__isnull=False,
              date_echeance__lt=today)
        ).order_by('date_echeance')
        count = qs.count()
        items = [{
            'id': f.id,
            'label': f"{f.reference} · "
                     f"{f.client.nom if f.client_id else ''}".strip(' ·'),
            'route': f"/ventes/factures?facture={f.id}",
        } for f in qs[:limit]]
        if count:
            groups.append({
                'type': 'overdue_invoices',
                'label': 'Factures impayées',
                'count': count, 'items': items})
    except Exception:
        pass

    total = sum(g['count'] for g in groups)
    return {'total': total, 'groups': groups}
