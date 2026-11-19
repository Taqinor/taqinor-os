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

from django.db.models import F, Q
from django.utils import timezone

from core.scoping import scope_client_queryset, scope_queryset, visible_user_ids

from . import machine_etats
from .models import ContratMaintenance, Ticket, TicketActivity
from .selectors import pieces_unifiees, ticket_en_retard_sla
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


# ── Tickets ─────────────────────────────────────────────────────────────────

LIMITE_TICKETS_DEFAUT = 10
LIMITE_TICKETS_MAX = 25
#: Lignes lues pour répondre à ``retard_sla`` (calculé en Python, jamais en SQL).
SCAN_RETARD_MAX = 500
LIEN_FILE_SAV = '/sav/action-requise'

#: Le geste que fait avancer chaque statut cible (jamais déduit du seul
#: statut courant : ``a_faire_du_ticket`` le lit de la machine d'états).
_GESTE_DU_STATUT_CIBLE = {
    Ticket.Statut.PLANIFIE: 'planifier', Ticket.Statut.EN_COURS: 'demarrer',
    Ticket.Statut.RESOLU: 'resoudre', Ticket.Statut.CLOTURE: 'cloturer',
}


def a_faire_du_ticket(ticket):
    """Le prochain geste du ticket, ensemble FERMÉ : ``planifier | demarrer |
    resoudre | cloturer | rien``. C'est, parmi les statuts suivants que
    ``machine_etats.statuts_suivants`` PERMET, le plus proche EN AVANT dans
    l'ordre d'entonnoir (``Ticket.STATUT_ORDER``) ; une réouverture n'est jamais
    un « à faire », ni un ticket annulé."""
    if ticket.annule:
        return 'rien'
    ordre = list(Ticket.STATUT_ORDER)
    courant = ordre.index(ticket.statut)
    en_avant = [s for s in machine_etats.statuts_suivants(ticket)
                if ordre.index(s) > courant]
    if not en_avant:
        return 'rien'
    return _GESTE_DU_STATUT_CIBLE.get(min(en_avant, key=ordre.index), 'rien')


def _equipement_en_clair(ticket):
    """« Onduleur Deye 8 kW — DEYE-SUN8K-2304-1182 » (vide sans équipement)."""
    equipement = ticket.equipement
    if equipement is None:
        return ''
    return ' — '.join(m for m in (equipement.produit.nom or '',
                                  equipement.numero_serie or '') if m)


def ligne_ticket(ticket, aujourdhui=None):
    """Une ligne compacte (``assistant_tickets.json``) ; ``ticket`` chargé avec
    ``select_related('client', 'equipement__produit')``. Ni texte du client, ni
    coût, ni téléphone."""
    due = ticket.sla_due_at_effectif(today=aujourdhui) if ticket.sla_due_at else None
    return {
        'ticket_id': ticket.pk,
        'reference': ticket.reference,
        'client_id': ticket.client_id,
        'client_nom': nom_du_client(ticket.client),
        'equipement': _equipement_en_clair(ticket),
        'statut': ticket.statut,
        'priorite': ticket.priorite,
        'cree_le': ticket.date_creation.isoformat(),
        'sla_due_at': due.isoformat() if due else None,
        'en_retard_sla': bool(ticket_en_retard_sla(ticket, aujourdhui)),
        'sous_garantie': ticket.sous_garantie_calcule == Ticket.SousGarantie.OUI,
        'a_faire': a_faire_du_ticket(ticket),
        'lien': LIEN_TICKET.format(ticket.pk),
    }


def _tickets_filtres(user, *, q='', statut='', priorite='', client=None,
                     equipement=None):
    """Tickets visibles NON annulés : les ouverts par défaut, ``statut`` sinon ;
    ``q`` = chaque mot dans la référence, le client ou le numéro de série ;
    les plus en retard d'abord (échéance SLA croissante, sans échéance en
    dernier)."""
    qs = tickets_visibles(user).filter(annule=False)
    qs = qs.filter(statut=statut) if statut else qs.filter(
        statut__in=Ticket.OPEN_STATUTS)
    if priorite:
        qs = qs.filter(priorite=priorite)
    if client:
        qs = qs.filter(client_id=client)
    if equipement:
        qs = qs.filter(equipement_id=equipement)
    for mot in (q or '').split()[:4]:
        qs = qs.filter(
            Q(reference__icontains=mot) | Q(client__nom__icontains=mot)
            | Q(client__prenom__icontains=mot)
            | Q(equipement__numero_serie__icontains=mot))
    return (qs.select_related('client', 'equipement__produit')
            .order_by(F('sla_due_at').asc(nulls_last=True), '-date_creation', '-id'))


def tickets_compacts(user, *, retard_sla=None, limite=LIMITE_TICKETS_DEFAUT,
                     aujourdhui=None, **filtres):
    """``(total, lignes)`` des tickets (voir :func:`_tickets_filtres`).
    ``retard_sla`` vrai/faux ne garde que les tickets en retard (ou non) selon
    ``selectors.ticket_en_retard_sla`` — la définition unique du retard — lus
    parmi les ``SCAN_RETARD_MAX`` premiers."""
    aujourdhui = aujourdhui or timezone.localdate()
    qs = _tickets_filtres(user, **filtres)
    if retard_sla is None:
        return qs.count(), [ligne_ticket(t, aujourdhui) for t in qs[:limite]]
    if retard_sla:
        qs = qs.filter(sla_due_at__lte=aujourdhui)  # tout retard a une échéance échue
    gardes = [t for t in qs[:SCAN_RETARD_MAX]
              if bool(ticket_en_retard_sla(t, aujourdhui)) == retard_sla]
    return len(gardes), [ligne_ticket(t, aujourdhui) for t in gardes[:limite]]


# ── Fiche d'un ticket ───────────────────────────────────────────────────────

#: Le texte du client (``description``) est un contenu TIERS : borné.
DESCRIPTION_MAX = 600
TEXTE_ACTIVITE_MAX = 300
NB_ACTIVITES = 5


def ticket_pour_fiche(user, pk):
    """Le ticket ``pk`` de la société de ``user`` dans sa portée, chargé pour
    la fiche — ``None`` s'il n'existe pas, est d'une autre société ou hors
    portée (le même 404 que l'écran)."""
    return (tickets_visibles(user).filter(pk=pk)
            .select_related('client', 'installation', 'technicien_responsable',
                            'equipement__produit').first())


def bloc_client(ticket):
    return {'id': ticket.client_id, 'nom': nom_du_client(ticket.client)}


def bloc_installation(ticket):
    if ticket.installation_id is None:
        return None
    return {'id': ticket.installation_id,
            'reference': ticket.installation.reference or ''}


def bloc_equipement(ticket):
    """L'équipement du ticket et sa garantie, jugée à l'OUVERTURE du ticket
    (D-ASAV-6), jamais un coût."""
    equipement = ticket.equipement
    if equipement is None:
        return None
    fin = equipement.date_fin_garantie_effective
    return {
        'id': equipement.pk,
        'produit': equipement.produit.nom or '',
        'numero_serie': equipement.numero_serie or '',
        'fin_garantie_effective': fin.isoformat() if fin else None,
        'sous_garantie': ticket.sous_garantie_calcule == Ticket.SousGarantie.OUI,
    }


def bloc_sla(ticket, aujourdhui=None):
    aujourdhui = aujourdhui or timezone.localdate()
    reponse, due = ticket.sla_reponse_due_at, (
        ticket.sla_due_at_effectif(today=aujourdhui) if ticket.sla_due_at else None)
    return {'reponse_due_at': reponse.isoformat() if reponse else None,
            'due_at': due.isoformat() if due else None,
            'en_retard': bool(ticket_en_retard_sla(ticket, aujourdhui))}


def nom_du_technicien(ticket):
    """Nom complet du technicien responsable — jamais son identifiant de
    connexion ; ``None`` sans technicien."""
    technicien = ticket.technicien_responsable
    if technicien is None:
        return None
    return (technicien.get_full_name() or '').strip() or None


def _texte_activite(activite):
    """Une ligne de chatter en une phrase bornée : la note ou le message tels
    qu'écrits ; un champ modifié « Priorité : Normale → Haute » (le CONTENU de
    la description n'est pas recopié)."""
    if activite.kind != TicketActivity.Kind.MODIFICATION:
        texte = activite.body or ''
    elif activite.field == 'description':
        texte = 'Description modifiée'
    else:
        texte = (f'{activite.field_label or activite.field} : '
                 f'{activite.old_value or "—"} → {activite.new_value or "—"}')
    return texte[:TEXTE_ACTIVITE_MAX]


def dernieres_activites(ticket):
    """Les ``NB_ACTIVITES`` dernières entrées du chatter, plus récente d'abord.
    Sont écartées : les lignes du COÛT (interne) et les notes VISIBLES du
    client (écrites pour lui, pas pour l'équipe)."""
    activites = (ticket.activites.exclude(field='cout').exclude(visible_client=True)
                 .select_related('user').order_by('-created_at', '-id')[:NB_ACTIVITES])
    return [{
        'type': a.kind,
        'le': a.created_at.isoformat(),
        'par': (a.user.get_full_name() or '').strip() if a.user_id else '',
        'texte': _texte_activite(a),
    } for a in activites]


def pieces_du_ticket(ticket):
    """Pièces posées / retirées : opération, désignation, quantité — JAMAIS un
    coût (même pour un compte qui voit les prix d'achat)."""
    return [{'operation': ligne['operation'], 'produit': ligne['produit_nom'] or '',
             'quantite': float(ligne['quantite'])}
            for ligne in pieces_unifiees(ticket)['lignes']]


def statuts_suivants_permis(ticket):
    """Statuts que ``machine_etats.statuts_suivants`` permet depuis le statut du
    ticket (aucun pour un ticket annulé : à réactiver à l'écran)."""
    if ticket.annule:
        return []
    return [s.value for s in machine_etats.statuts_suivants(ticket)]
