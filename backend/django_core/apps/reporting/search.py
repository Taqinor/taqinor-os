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

    def add(type_key, label_fr, qs, mapper):
        """Ajoute un groupe à partir d'un queryset.

        N83 — on tronque à PER côté vue ; quand le groupe atteint PER on compte
        le total réel pour exposer un lien « voir tout / +N autres » côté front
        (clé ``more``/``more_count``). Le ``.count()`` n'est fait QUE quand le
        groupe est plein, pour ne pas surcharger les petits résultats.
        """
        rows = list(qs[:PER])
        items = [mapper(obj) for obj in rows]
        if not items:
            return
        group = {'type': type_key, 'label': label_fr, 'results': items}
        if len(items) >= PER:
            total = qs.count()
            if total > len(items):
                group['more'] = True
                group['more_count'] = total - len(items)
        groups.append(group)

    # ── Leads ────────────────────────────────────────────────────────────
    from apps.crm.models import Client, Lead
    leads = Lead.objects.filter(**co).filter(
        Q(nom__icontains=q) | Q(prenom__icontains=q) | Q(societe__icontains=q)
        | Q(email__icontains=q) | Q(telephone__icontains=q) | Q(ville__icontains=q)
    ).order_by('-date_creation')
    add('lead', 'Leads', leads, lambda le: {
        'id': le.id,
        'label': f"{le.nom} {le.prenom or ''}".strip() or le.societe or '—',
        'sublabel': le.societe or le.ville or le.telephone or ''})

    # ── Clients ──────────────────────────────────────────────────────────
    clients = Client.objects.filter(**co).filter(
        Q(nom__icontains=q) | Q(prenom__icontains=q)
        | Q(email__icontains=q) | Q(telephone__icontains=q)
    ).order_by('nom')
    add('client', 'Clients', clients, lambda c: {
        'id': c.id,
        'label': f"{c.nom} {c.prenom or ''}".strip() or '—',
        'sublabel': c.email or c.telephone or ''})

    # ── Devis / Factures ─────────────────────────────────────────────────
    from apps.ventes.models import Devis, Facture
    devis = Devis.objects.filter(**co).filter(
        Q(reference__icontains=q) | Q(client__nom__icontains=q)
    ).select_related('client').order_by('-id')
    add('devis', 'Devis', devis, lambda d: {
        'id': d.id, 'label': d.reference,
        'sublabel': getattr(d.client, 'nom', '') or ''})
    factures = Facture.objects.filter(**co).filter(
        Q(reference__icontains=q) | Q(client__nom__icontains=q)
    ).select_related('client').order_by('-id')
    add('facture', 'Factures', factures, lambda f: {
        'id': f.id, 'label': f.reference,
        'sublabel': getattr(f.client, 'nom', '') or ''})

    # ── Chantiers / Équipements ──────────────────────────────────────────
    from apps.installations.models import Installation
    from apps.sav.models import Equipement, Ticket
    chantiers = Installation.objects.filter(**co).filter(
        Q(reference__icontains=q)
    ).order_by('-id')
    add('chantier', 'Chantiers', chantiers,
        lambda i: {'id': i.id, 'label': i.reference, 'sublabel': ''})

    equipements = Equipement.objects.filter(**co).filter(
        Q(numero_serie__icontains=q) | Q(produit__nom__icontains=q)
    ).select_related('produit').order_by('-id')
    add('equipement', 'Équipements', equipements, lambda e: {
        'id': e.id, 'label': e.numero_serie or f"#{e.id}",
        'sublabel': getattr(e.produit, 'nom', '') or ''})

    tickets = Ticket.objects.filter(**co).filter(
        Q(reference__icontains=q) | Q(description__icontains=q)
    ).order_by('-id')
    add('ticket', 'Tickets SAV', tickets, lambda t: {
        'id': t.id, 'label': t.reference,
        'sublabel': (t.description or '')[:40]})

    # ── Bons de commande (devis → BC) ────────────────────────────────────
    from apps.ventes.models import BonCommande
    bons = BonCommande.objects.filter(**co).filter(
        Q(reference__icontains=q) | Q(client__nom__icontains=q)
    ).select_related('client').order_by('-id')
    add('bon_commande', 'Bons de commande', bons, lambda b: {
        'id': b.id, 'label': b.reference,
        'sublabel': getattr(b.client, 'nom', '') or ''})

    # ── Contrats de maintenance ──────────────────────────────────────────
    from apps.sav.models import ContratMaintenance
    contrats = ContratMaintenance.objects.filter(**co).filter(
        Q(client__nom__icontains=q) | Q(notes__icontains=q)
    ).select_related('client').order_by('-id')
    add('contrat', 'Contrats de maintenance', contrats, lambda c: {
        'id': c.id,
        'label': f"Contrat #{c.id}",
        'sublabel': getattr(c.client, 'nom', '') or ''})

    # ── Dossiers réglementaires (référence/opérateur sur le chantier) ─────
    dossiers = Installation.objects.filter(**co).filter(
        Q(dossier_reference__icontains=q) | Q(dossier_operateur__icontains=q)
    ).exclude(dossier_reference__isnull=True).exclude(
        dossier_reference=''
    ).order_by('-id')
    add('dossier', 'Dossiers réglementaires', dossiers, lambda i: {
        'id': i.id,
        'label': i.dossier_reference or i.reference,
        'sublabel': i.dossier_operateur or i.reference})

    return Response({'query': q, 'groups': groups})


@api_view(['GET'])
@permission_classes([IsAnyRole])
def notifications(request):
    """Cloche de notifications in-app (aucun email). Compte + liste cliquable
    des éléments demandant une action, calculés à la volée et bornés société."""
    co = _co_filter(request.user)
    if co is None:
        return Response({'detail': 'Accès refusé.'}, status=403)
    today = date.today()

    # ── Activités en retard (records.Activity ouvertes, échéance passée) ──
    from apps.records.models import Activity
    overdue_acts = (Activity.objects
                    .filter(**co, done=False, due_date__lt=today)
                    .select_related('assigned_to')
                    .order_by('due_date')[:20])
    activites = [
        {'id': a.id, 'label': a.summary or 'Activité',
         'date': a.due_date.isoformat() if a.due_date else None,
         'lead_id': (a.object_id if a.content_type_id == _lead_ct_id() else None)}
        for a in overdue_acts
    ]

    # ── Garanties expirant sous 90 jours ─────────────────────────────────
    from apps.sav.models import Equipement
    horizon = today + timedelta(days=90)
    eq_qs = (Equipement.objects
             .filter(**co, date_fin_garantie__gte=today,
                     date_fin_garantie__lte=horizon)
             .select_related('produit')
             .order_by('date_fin_garantie')[:20])
    garanties = [
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
    factures = [
        {'id': f.id, 'label': f.reference,
         'sublabel': getattr(f.client, 'nom', '') or '',
         # `date` = échéance (sert au tri par urgence côté cloche).
         'date': f.date_echeance.isoformat() if f.date_echeance else None,
         'overdue': bool(f.date_echeance and f.date_echeance < today)}
        for f in fac_qs
    ]

    # ── N83 — signaux maintenance : contrats à renouveler ≤ 90 j + visites
    #    dues. Le « dû » et la prochaine visite sont calculés À LA LECTURE sur
    #    le modèle (pas de planificateur), cohérent avec ContratMaintenance.
    from apps.sav.models import ContratMaintenance
    contrats_actifs = (ContratMaintenance.objects
                       .filter(**co, actif=True)
                       .select_related('client')
                       .order_by('date_renouvellement', 'derniere_visite'))
    renouvellements = []
    visites_dues = []
    for c in contrats_actifs:
        client_nom = str(c.client) if c.client_id else f"Contrat #{c.id}"
        # Renouvellement à échéance dans ≤ 90 jours (incluant déjà dépassée).
        if c.date_renouvellement and c.date_renouvellement <= horizon:
            renouvellements.append({
                'id': c.id, 'label': f"Renouvellement — {client_nom}",
                'date': c.date_renouvellement.isoformat(),
                'overdue': c.date_renouvellement < today})
        # Visite due : prochaine visite calculée déjà atteinte.
        if c.is_due(today):
            prochaine = c.prochaine_visite()
            visites_dues.append({
                'id': c.id, 'label': f"Visite due — {client_nom}",
                'date': prochaine.isoformat() if prochaine else None,
                'overdue': True})
    renouvellements = renouvellements[:20]
    visites_dues = visites_dues[:20]

    return Response({
        'total': (len(activites) + len(garanties) + len(factures)
                  + len(renouvellements) + len(visites_dues)),
        'activites_en_retard': activites,
        'garanties_expirantes': garanties,
        'factures_impayees': factures,
        'contrats_a_renouveler': renouvellements,
        'visites_dues': visites_dues,
    })


def _lead_ct_id():
    from apps.crm.models import Lead
    return ContentType.objects.get_for_model(Lead).id
