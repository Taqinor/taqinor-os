"""Copilote vague 2 — lectures COMPACTES du SAV servies à l'assistant.

Trois lectures (le parc d'un client, les tickets, la fiche d'un ticket) et le
bloc du point du matin (``brief_sav``). Lecture seule, bornée à la SOCIÉTÉ de
l'utilisateur et à la PORTÉE des écrans SAV (tickets : créés par soi, dont on
est technicien, ou de l'équipe ; équipements : parc d'un chantier visible,
D-ACSV-2). Jamais un coût, un prix, une adresse ni un e-mail ; le téléphone ne
sort que pour un rôle qui a ``client_pii_voir`` (même règle que les
sérialiseurs SAV). Les formes sont celles des échantillons
``contract_samples/assistant_*.json`` de l'app.

Un client se retrouve par les sélecteurs du CRM (téléphone, nom) — jamais par
ses modèles.
"""
import re

from django.db.models import Q
from django.utils import timezone

from core.scoping import scope_client_queryset, scope_queryset, visible_user_ids

from .selectors_libelles import _equipements_visibles as equipements_visibles

#: Parc : 5 clients par défaut, 10 au plus ; au plus 20 équipements par client.
LIMITE_PARC_DEFAUT = 5
LIMITE_PARC_MAX = 10
MAX_EQUIPEMENTS_PAR_CLIENT = 20
MAX_CHANTIERS_PAR_CLIENT = 10
MAX_TICKETS_PAR_CLIENT = 5
#: Clients candidats lus avant le filtre de portée (une recherche par nom).
MAX_CANDIDATS = 50

LIEN_FICHE_CLIENT = '/crm?id={}'
LIEN_TICKET = '/sav?id={}'

_TELEPHONE = re.compile(r'^\+?[\d\s.\-()]{6,}$')


def tickets_visibles(user):
    """Tickets de la société de ``user`` dans sa portée — la même que la liste
    de ``TicketViewSet`` (jamais ``Ticket.objects.filter(company=…)`` nu)."""
    from .models import Ticket

    return scope_queryset(
        Ticket.objects.filter(company_id=user.company_id), user,
        ['technicien_responsable', 'created_by'])


def nom_du_client(client):
    """« Nadia Chraibi » : nom puis prénom, comme les sérialiseurs SAV."""
    return f"{client.nom or ''} {client.prenom or ''}".strip()


def _client_de_l_equipement(equipement):
    """Identifiant du client d'un équipement : celui de son chantier, à défaut
    le client de la vente directe (comptoir)."""
    if equipement.installation_id:
        return equipement.installation.client_id
    return equipement.client_vente_id


def _clients_hors_portee_retires(user, ids):
    """``ids`` réduits aux clients que ``user`` voit : portée « tous » = aucun
    retrait ; sinon un client visible côté CRM, OU porteur d'un ticket ou d'un
    équipement visible (ce que l'écran SAV lui montre déjà)."""
    from apps.crm.selectors import client_base_qs

    if not ids or visible_user_ids(user) is None:
        return ids
    visibles = set(scope_client_queryset(
        client_base_qs(user.company).filter(pk__in=ids), user
    ).values_list('pk', flat=True))
    visibles |= set(tickets_visibles(user).filter(
        client_id__in=ids).values_list('client_id', flat=True))
    for equipement in equipements_visibles(user).filter(
            Q(installation__client_id__in=ids) | Q(client_vente_id__in=ids)
    ).select_related('installation'):
        visibles.add(_client_de_l_equipement(equipement))
    return [pk for pk in ids if pk in visibles]


def clients_pour_recherche(user, q):
    """Identifiants (ordonnés) des clients visibles que ``q`` désigne :
    téléphone (``crm.selectors.find_client_by_phone``), sinon numéro de série
    exact d'un équipement visible, sinon nom ou prénom (chaque mot doit
    figurer)."""
    from apps.crm.selectors import client_base_qs, find_client_by_phone

    texte = (q or '').strip()
    ids = []
    if _TELEPHONE.match(texte) and len(re.sub(r'\D', '', texte)) >= 6:
        client = find_client_by_phone(user.company, texte)
        if client is not None:
            ids = [client.pk]
    if not ids:
        equipement = (equipements_visibles(user)
                      .filter(numero_serie__iexact=texte)
                      .select_related('installation').first())
        if equipement is not None and _client_de_l_equipement(equipement):
            ids = [_client_de_l_equipement(equipement)]
    if not ids:
        qs = client_base_qs(user.company).filter(is_anonymized=False)
        for mot in texte.split()[:4]:
            qs = qs.filter(Q(nom__icontains=mot) | Q(prenom__icontains=mot))
        ids = list(qs.order_by('nom', 'prenom', 'id')
                   .values_list('pk', flat=True)[:MAX_CANDIDATS])
    return _clients_hors_portee_retires(user, ids)


def _chantiers_par_client(user, ids):
    from apps.installations.selectors import chantiers_visibles

    par_client = {}
    lignes = (chantiers_visibles(user).filter(client_id__in=ids)
              .order_by('-id').values('pk', 'reference', 'statut', 'client_id'))
    for ligne in lignes:
        liste = par_client.setdefault(ligne['client_id'], [])
        if len(liste) < MAX_CHANTIERS_PAR_CLIENT:
            liste.append({'installation_id': ligne['pk'],
                          'reference': ligne['reference'] or '',
                          'statut': ligne['statut'] or ''})
    return par_client


def _ligne_equipement(equipement, aujourdhui):
    fin = equipement.date_fin_garantie_effective
    produit = equipement.produit
    return {
        'equipement_id': equipement.pk,
        'produit': produit.nom or '',
        'marque': produit.marque or '',
        'numero_serie': equipement.numero_serie or '',
        'statut': equipement.statut,
        'date_pose': equipement.date_pose.isoformat() if equipement.date_pose else None,
        'fin_garantie_effective': fin.isoformat() if fin else None,
        'sous_garantie': bool(fin and aujourdhui < fin),
        'installation_id': equipement.installation_id,
    }


def _equipements_par_client(user, ids, aujourdhui):
    """Équipements encore posés (ni remplacés ni mis au rebut : fermés à tout
    nouveau ticket) de chaque client, en service d'abord."""
    par_client = {}
    qs = (equipements_visibles(user)
          .filter(Q(installation__client_id__in=ids) | Q(client_vente_id__in=ids))
          .exclude(mis_au_rebut=True).exclude(statut='remplace')
          .select_related('produit', 'installation').order_by('produit__nom', 'id'))
    for equipement in qs:
        liste = par_client.setdefault(_client_de_l_equipement(equipement), [])
        if len(liste) < MAX_EQUIPEMENTS_PAR_CLIENT:
            liste.append(_ligne_equipement(equipement, aujourdhui))
    return par_client


def _tickets_ouverts_par_client(user, ids):
    from .models import Ticket

    par_client = {}
    lignes = (tickets_visibles(user)
              .filter(client_id__in=ids, statut__in=Ticket.OPEN_STATUTS, annule=False)
              .order_by('-date_creation')
              .values('pk', 'reference', 'statut', 'equipement_id', 'client_id'))
    for ligne in lignes:
        liste = par_client.setdefault(ligne['client_id'], [])
        if len(liste) < MAX_TICKETS_PAR_CLIENT:
            liste.append({'ticket_id': ligne['pk'], 'reference': ligne['reference'],
                          'statut': ligne['statut'],
                          'equipement_id': ligne['equipement_id'],
                          'lien': LIEN_TICKET.format(ligne['pk'])})
    return par_client


def _contrats_actifs_par_client(user, ids, aujourdhui):
    """``{client_id: {id, fin}}`` du contrat de maintenance ACTIF (début, échéance
    et grâce compris : ``est_actif``) le plus récent de chaque client."""
    from .models import ContratMaintenance

    par_client = {}
    for contrat in ContratMaintenance.objects.filter(
            company_id=user.company_id, client_id__in=ids,
            actif=True).order_by('-date_creation'):
        if contrat.client_id not in par_client and contrat.est_actif(aujourdhui):
            fin = contrat.date_expiration()
            par_client[contrat.client_id] = {
                'id': contrat.pk, 'fin': fin.isoformat() if fin else None}
    return par_client


def parc_clients(user, q, limite=LIMITE_PARC_DEFAUT, aujourdhui=None):
    """``(total, clients)`` : les clients désignés par ``q`` (``total`` = tous,
    ``clients`` = les ``limite`` premiers) avec chantiers, équipements (garantie
    effective), tickets ouverts et contrat actif. Le téléphone est vide sans
    ``client_pii_voir``. UNE requête par bloc, jamais une par client."""
    from apps.crm.selectors import client_base_qs

    aujourdhui = aujourdhui or timezone.localdate()
    ids = clients_pour_recherche(user, q)
    page = ids[:limite]
    if not page:
        return len(ids), []
    clients = {c.pk: c for c in client_base_qs(user.company).filter(pk__in=page)}
    chantiers = _chantiers_par_client(user, page)
    equipements = _equipements_par_client(user, page, aujourdhui)
    tickets = _tickets_ouverts_par_client(user, page)
    contrats = _contrats_actifs_par_client(user, page, aujourdhui)
    voit_le_telephone = getattr(user, 'can_view_client_pii', True)
    lignes = []
    for pk in page:
        client = clients.get(pk)
        if client is None:
            continue
        ouverts = tickets.get(pk, [])
        lignes.append({
            'client_id': pk,
            'nom': nom_du_client(client),
            'telephone': (client.telephone or '') if voit_le_telephone else '',
            'chantiers': chantiers.get(pk, []),
            'equipements': equipements.get(pk, []),
            'tickets_ouverts': ouverts,
            'contrat_actif': contrats.get(pk),
            'a_faire': 'suivre_ticket' if ouverts else 'rien',
            'lien': LIEN_FICHE_CLIENT.format(pk),
        })
    return len(ids), lignes
