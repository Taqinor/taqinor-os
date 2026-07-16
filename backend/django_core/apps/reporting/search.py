"""T5 — Recherche globale + notifications in-app (lecture seule, multi-tenant).

Tout est borné à la société de l'utilisateur. La recherche balaie les entités
clés (leads, clients, devis, factures, chantiers, équipements, tickets SAV) ;
les notifications agrègent ce qui demande une action (activités en retard,
garanties expirant sous 90 j, factures impayées/en retard). Aucune écriture.

ARC29 — PILOTÉE PAR LE REGISTRE (``core.platform``). Avant ARC29, les 10
modèles cherchables étaient hard-codés dans cette fonction : un modèle
importable/chatter-isé mais absent d'ici restait introuvable (``stock.Produit``,
``contrats.Contrat``). ``global_search`` itère désormais
``platform.searchable_models(company)`` (les manifestes ``apps/<x>/platform.py``
gatés ``ModuleToggle``) et résout chaque clé ``'app.model'`` dans le registre
LOCAL ``_SEARCH_SPECS`` ci-dessous — la construction de requête/mise en forme du
résultat reste PROPRE à chaque modèle (elle ne peut pas être généralisée sans
connaître les champs de recherche pertinents), mais l'ENSEMBLE des modèles
balayés vient désormais du registre plateforme : ajouter un modèle au manifeste
d'une app SANS toucher ce fichier ne le rend PAS automatiquement cherchable
(il faut aussi déclarer sa spec ici) — en revanche retirer/désactiver un module
(toggle OFF) le retire bien de la recherche sans rien changer ici. L'enveloppe
de résultat (``{'query', 'groups': [{'type','label','results':[...]}]}``) reste
BYTE-IDENTIQUE à avant ARC29 (le hook front VX13 la consomme sans changement).
"""
from datetime import date, timedelta

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from authentication.permissions import IsAnyRole
from core import platform


def _co_filter(user):
    """kwargs de filtrage société, ou None si accès interdit."""
    if user.company_id:
        return {'company': user.company}
    if user.is_superuser:
        return {}
    return None


def _spec_lead(co, q):
    from apps.crm.models import Lead
    qs = Lead.objects.filter(**co).filter(
        Q(nom__icontains=q) | Q(prenom__icontains=q) | Q(societe__icontains=q)
        | Q(email__icontains=q) | Q(telephone__icontains=q) | Q(ville__icontains=q)
    ).order_by('-date_creation')
    return 'lead', 'Leads', qs, lambda le: {
        'id': le.id,
        'label': f"{le.nom} {le.prenom or ''}".strip() or le.societe or '—',
        'sublabel': le.societe or le.ville or le.telephone or ''}


def _spec_client(co, q):
    from apps.crm.models import Client
    qs = Client.objects.filter(**co).filter(
        Q(nom__icontains=q) | Q(prenom__icontains=q)
        | Q(email__icontains=q) | Q(telephone__icontains=q)
    ).order_by('nom')
    return 'client', 'Clients', qs, lambda c: {
        'id': c.id,
        'label': f"{c.nom} {c.prenom or ''}".strip() or '—',
        'sublabel': c.email or c.telephone or ''}


def _spec_devis(co, q):
    from apps.ventes.models import Devis
    qs = Devis.objects.filter(**co).filter(
        Q(reference__icontains=q) | Q(client__nom__icontains=q)
    ).select_related('client').order_by('-id')
    return 'devis', 'Devis', qs, lambda d: {
        'id': d.id, 'label': d.reference,
        'sublabel': getattr(d.client, 'nom', '') or ''}


def _spec_facture(co, q):
    from apps.ventes.models import Facture
    qs = Facture.objects.filter(**co).filter(
        Q(reference__icontains=q) | Q(client__nom__icontains=q)
    ).select_related('client').order_by('-id')
    return 'facture', 'Factures', qs, lambda f: {
        'id': f.id, 'label': f.reference,
        'sublabel': getattr(f.client, 'nom', '') or ''}


def _spec_chantier(co, q):
    from apps.installations.models import Installation
    qs = Installation.objects.filter(**co).filter(
        Q(reference__icontains=q)
    ).order_by('-id')
    return 'chantier', 'Chantiers', qs, (
        lambda i: {'id': i.id, 'label': i.reference, 'sublabel': ''})


def _spec_equipement(co, q):
    from apps.sav.models import Equipement
    qs = Equipement.objects.filter(**co).filter(
        Q(numero_serie__icontains=q) | Q(produit__nom__icontains=q)
    ).select_related('produit').order_by('-id')
    return 'equipement', 'Équipements', qs, lambda e: {
        'id': e.id, 'label': e.numero_serie or f"#{e.id}",
        'sublabel': getattr(e.produit, 'nom', '') or ''}


def _spec_ticket(co, q):
    from apps.sav.models import Ticket
    qs = Ticket.objects.filter(**co).filter(
        Q(reference__icontains=q) | Q(description__icontains=q)
    ).order_by('-id')
    return 'ticket', 'Tickets SAV', qs, lambda t: {
        'id': t.id, 'label': t.reference,
        'sublabel': (t.description or '')[:40]}


def _spec_bon_commande(co, q):
    from apps.ventes.models import BonCommande
    qs = BonCommande.objects.filter(**co).filter(
        Q(reference__icontains=q) | Q(client__nom__icontains=q)
    ).select_related('client').order_by('-id')
    return 'bon_commande', 'Bons de commande', qs, lambda b: {
        'id': b.id, 'label': b.reference,
        'sublabel': getattr(b.client, 'nom', '') or ''}


def _spec_contrat_maintenance(co, q):
    from apps.sav.models import ContratMaintenance
    qs = ContratMaintenance.objects.filter(**co).filter(
        Q(client__nom__icontains=q) | Q(notes__icontains=q)
    ).select_related('client').order_by('-id')
    return 'contrat', 'Contrats de maintenance', qs, lambda c: {
        'id': c.id,
        'label': f"Contrat #{c.id}",
        'sublabel': getattr(c.client, 'nom', '') or ''}


def _spec_dossier_reglementaire(co, q):
    from apps.installations.models import Installation
    qs = Installation.objects.filter(**co).filter(
        Q(dossier_reference__icontains=q) | Q(dossier_operateur__icontains=q)
    ).exclude(dossier_reference__isnull=True).exclude(
        dossier_reference=''
    ).order_by('-id')
    return 'dossier', 'Dossiers réglementaires', qs, lambda i: {
        'id': i.id,
        'label': i.dossier_reference or i.reference,
        'sublabel': i.dossier_operateur or i.reference}


def _spec_produit(co, q):
    """ARC29 — trou comblé : ``stock.Produit`` était importable/customfieldable/
    records-isé mais absent de la recherche globale."""
    from apps.stock.models import Produit
    qs = Produit.objects.filter(**co, is_archived=False).filter(
        Q(nom__icontains=q) | Q(sku__icontains=q)
    ).order_by('nom')
    return 'produit', 'Produits', qs, lambda p: {
        'id': p.id, 'label': p.nom,
        'sublabel': p.sku or ''}


def _spec_contrat(co, q):
    """ARC29 — trou comblé : ``contrats.Contrat`` avait le chatter générique
    (ARC8) mais restait invisible en recherche (seul ``sav.ContratMaintenance``
    l'était). ``client_id`` est un lien LÂCHE (pas de FK dur) : pas de
    ``select_related`` possible, le sous-libellé se limite à l'objet/type."""
    from apps.contrats.models import Contrat
    qs = Contrat.objects.filter(**co).filter(
        Q(reference__icontains=q) | Q(objet__icontains=q)
    ).order_by('-id')
    return 'contrat_clm', 'Contrats', qs, lambda c: {
        'id': c.id,
        'label': c.reference or c.objet,
        'sublabel': c.get_type_contrat_display()}


# Registre LOCAL des specs de recherche, LISTE ORDONNÉE de couples
# ``('app.model', spec_builder)`` — clé minuscule, alignée sur
# ``core.platform`` / ``records.ALLOWED_TARGETS``. L'ORDRE est EXACTEMENT
# celui des 10 groupes historiques d'avant ARC29 (enveloppe ET ordre de
# groupes inchangés pour l'existant), les trous comblés (Produit, Contrat CLM)
# en fin de liste. ``installations.installation`` apparaît DEUX fois (les
# groupes « Chantiers » et « Dossiers réglementaires », historiquement
# distincts sur le même modèle et non adjacents). ``global_search`` n'itère
# QUE les clés listées ici ET présentes dans
# ``platform.searchable_models(company)`` — les deux conditions sont
# nécessaires (une clé ici sans manifeste, ou un manifeste sans spec ici, ne
# produit rien).
_SEARCH_SPECS = [
    ('crm.lead', _spec_lead),
    ('crm.client', _spec_client),
    ('ventes.devis', _spec_devis),
    ('ventes.facture', _spec_facture),
    ('installations.installation', _spec_chantier),
    ('sav.equipement', _spec_equipement),
    ('sav.ticket', _spec_ticket),
    ('ventes.boncommande', _spec_bon_commande),
    ('sav.contratmaintenance', _spec_contrat_maintenance),
    ('installations.installation', _spec_dossier_reglementaire),
    # ARC29 — trous comblés.
    ('stock.produit', _spec_produit),
    ('contrats.contrat', _spec_contrat),
]


@api_view(['GET'])
@permission_classes([IsAnyRole])
def global_search(request):
    """Recherche transverse. ?q=<terme> → résultats groupés par type.

    Chaque résultat porte type / id / label / sublabel ; le front mappe le
    type vers sa route pour ouvrir l'enregistrement. Limité par type pour
    rester rapide et lisible.

    ARC29 — pilotée par le registre plateforme : on itère
    ``platform.searchable_models(company)`` (gaté ``ModuleToggle``) et on
    résout chaque clé dans ``_SEARCH_SPECS`` ; l'ordre des groupes suit
    l'ordre historique pour rester stable côté front (les nouvelles clés
    ARC29 sont ajoutées en fin de balayage)."""
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

    # ARC29 — balayage piloté par le registre plateforme : seules les clés
    # présentes dans platform.searchable_models(company) (manifestes gatés
    # ModuleToggle) sont interrogées, dans l'ordre historique de _SEARCH_SPECS.
    cherchables = platform.searchable_models(request.user.company)
    for cle, spec_builder in _SEARCH_SPECS:
        if cle not in cherchables:
            continue
        type_key, label_fr, qs, mapper = spec_builder(co, q)
        add(type_key, label_fr, qs, mapper)

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
    # VX84 — bornées à `assigned_to=request.user` : avant ce filtre le badge
    # était company-wide pendant que « Ma file » (records.mine/ma-file) ne
    # montre QUE les activités de l'utilisateur — deux chiffres contradictoires
    # sur la même page. Même source de vérité que records.views.mine/ma_file.
    from apps.records.models import Activity
    overdue_acts = (Activity.objects
                    .filter(**co, assigned_to=request.user, done=False,
                            due_date__lt=today)
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
