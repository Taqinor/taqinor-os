"""Sélecteurs de lecture SAV (point d'entrée cross-app).

XSAV10 — ``csat_par_technicien`` agrège les réponses ``TicketSatisfaction``
par technicien/mois. Point d'entrée pour le rapport service (apps.reporting) :
plutôt que d'importer ``apps.sav.models`` directement, l'app appelante lit ce
sélecteur (règle de modularité CLAUDE.md).

DC37 — Réconciliation des numéros de série capturés à la réception
(`stock.LigneReceptionFournisseur.numeros_serie`, posés par FG61) avec le parc
installé (`sav.Equipement`). La réconciliation se fait PAR PRODUIT + numéro de
série : on retrouve l'unité posée correspondant à une série reçue, pour relier
garantie/RMA de bout en bout (matériel reçu → matériel installé).

Conçu pour être appelé par le côté stock SANS importer `apps.sav.models` :
le stock passe l'``id`` de produit et la liste de séries reçues en arguments
bruts ; ce module lit uniquement `sav.Equipement` (règle de modularité
CLAUDE.md — les lectures cross-app passent par les selectors de l'app cible).
"""
from .models import Equipement, Ticket, TicketSatisfaction


def reconcile_serials_to_equipements(company, produit_id, serials):
    """Réconcilie une liste de séries reçues à des `sav.Equipement` du parc.

    Args:
        company: la société (scoping multi-tenant, jamais None en usage normal).
        produit_id: l'``id`` du `stock.Produit` de la ligne de réception
            (le FK produit est conservé sur la ligne — DC37).
        serials: itérable de numéros de série reçus (chaînes). ``None`` toléré.

    Returns:
        dict {
            'matched':   {serie: equipement_id, …}  séries déjà au parc,
            'unmatched': [serie, …]                 séries pas (encore) posées,
        }
        La correspondance exige : même société, même produit, même série
        (insensible aux espaces de bord). Les séries vides sont ignorées.
    """
    cleaned = []
    seen = set()
    for raw in (serials or []):
        if raw is None:
            continue
        serie = str(raw).strip()
        if not serie or serie in seen:
            continue
        seen.add(serie)
        cleaned.append(serie)

    if not cleaned:
        return {'matched': {}, 'unmatched': []}

    qs = Equipement.objects.filter(
        produit_id=produit_id, numero_serie__in=cleaned)
    if company is not None:
        qs = qs.filter(company=company)

    matched = {}
    for serie, eq_id in qs.values_list('numero_serie', 'id'):
        # Première unité trouvée par série suffit (série unique par société).
        matched.setdefault(serie, eq_id)

    unmatched = [s for s in cleaned if s not in matched]
    return {'matched': matched, 'unmatched': unmatched}


def equipements_par_produit(
        company, produit_id, *, serie_debut=None, serie_fin=None):
    """XQHS5 — équipements posés du parc pour une ``CampagneRappel``.

    Renvoie le parc réel (``sav.Equipement``) d'un produit donné, filtré à la
    société ; optionnellement borné à une plage de numéros de série
    (comparaison alphabétique — utile pour un rappel « lot/série X à Y »).
    Lu UNIQUEMENT via ce sélecteur par les autres apps (jamais un import de
    ``apps.sav.models``).

    Renvoie une liste de dicts légers (pas le queryset ORM, pour ne jamais
    fuiter le modèle hors de l'app).
    """
    qs = Equipement.objects.filter(company=company, produit_id=produit_id)
    if serie_debut:
        qs = qs.filter(numero_serie__gte=serie_debut)
    if serie_fin:
        qs = qs.filter(numero_serie__lte=serie_fin)
    return [
        {
            'id': eq.id,
            'numero_serie': eq.numero_serie,
            'installation_id': eq.installation_id,
            'statut': eq.statut,
        }
        for eq in qs.only(
            'id', 'numero_serie', 'installation_id', 'statut')
    ]


def warranty_registry(equipements_qs, *, expiring_soon_days=60, today=None):
    """FG290 — Registre des garanties matériel & échéancier de fin PAR PARC.

    Regroupe un queryset d'``Equipement`` (déjà scopé société + visibilité par
    l'appelant) par parc/installation, et rend pour chaque unité ses deux dates
    de fin de garantie (matériel + production, CALCULÉES sur le modèle — jamais
    inventées ici) avec un statut d'alerte : ``expiree``, ``expire_bientot``
    (dans les ``expiring_soon_days`` jours), ``sous_garantie`` ou
    ``non_renseignee``.

    Args:
        equipements_qs: queryset ``Equipement`` déjà filtré/scopé par l'appelant.
        expiring_soon_days: fenêtre d'alerte « expire bientôt » (jours).
        today: date de référence (défaut : aujourd'hui, fuseau app).

    Returns:
        dict {
            'today': 'YYYY-MM-DD',
            'expiring_soon_days': int,
            'parcs': [ {installation, client_nom, items:[…], alertes:{…}}, … ],
            'totaux': {equipements, expirees, expire_bientot, sous_garantie,
                       non_renseignee},
        }
        Les parcs sont triés par prochaine échéance de garantie (la plus proche
        d'abord) pour que l'échéancier serve directement de liste d'action.
    """
    import datetime
    from django.utils import timezone

    if today is None:
        today = timezone.localdate()
    soon = today + datetime.timedelta(days=expiring_soon_days)

    def _statut(date_fin):
        if date_fin is None:
            return 'non_renseignee'
        if date_fin < today:
            return 'expiree'
        if date_fin <= soon:
            return 'expire_bientot'
        return 'sous_garantie'

    qs = equipements_qs.select_related(
        'produit', 'installation', 'installation__client')

    parcs = {}
    totaux = {'equipements': 0, 'expirees': 0, 'expire_bientot': 0,
              'sous_garantie': 0, 'non_renseignee': 0}
    _stat_key = {'expiree': 'expirees', 'expire_bientot': 'expire_bientot',
                 'sous_garantie': 'sous_garantie',
                 'non_renseignee': 'non_renseignee'}

    for eq in qs:
        inst = eq.installation
        inst_id = inst.id if inst else None
        if inst_id not in parcs:
            client = getattr(inst, 'client', None) if inst else None
            client_nom = ''
            if client is not None:
                client_nom = (
                    f"{(client.prenom or '').strip()} "
                    f"{(client.nom or '').strip()}").strip()
            parcs[inst_id] = {
                'installation': inst_id,
                'installation_nom': str(inst) if inst else '',
                'client_nom': client_nom,
                'items': [],
                'alertes': {'expirees': 0, 'expire_bientot': 0,
                            'sous_garantie': 0, 'non_renseignee': 0},
                '_prochaine': None,
            }
        st = _statut(eq.date_fin_garantie)
        st_prod = _statut(eq.date_fin_garantie_production)
        item = {
            'equipement': eq.id,
            'produit': getattr(eq.produit, 'nom', '') or '',
            'marque': getattr(eq.produit, 'marque', '') or '',
            'numero_serie': eq.numero_serie or '',
            'date_pose': eq.date_pose.isoformat() if eq.date_pose else None,
            'date_fin_garantie': (
                eq.date_fin_garantie.isoformat()
                if eq.date_fin_garantie else None),
            'date_fin_garantie_production': (
                eq.date_fin_garantie_production.isoformat()
                if eq.date_fin_garantie_production else None),
            'statut_garantie': st,
            'statut_garantie_production': st_prod,
            'statut': eq.statut,
            # XSAV13 — garantie légale de conformité (loi 31-08, biens
            # meubles) : impérative, 12 mois à compter de la pose.
            'date_fin_garantie_legale': (
                eq.date_fin_garantie_legale.isoformat()
                if eq.date_fin_garantie_legale else None),
            'sous_garantie_legale_seule': eq.sous_garantie_legale_seule,
        }
        parc = parcs[inst_id]
        parc['items'].append(item)
        parc['alertes'][_stat_key[st]] += 1
        totaux['equipements'] += 1
        totaux[_stat_key[st]] += 1
        # Prochaine échéance du parc = la plus proche date de fin non nulle.
        if eq.date_fin_garantie is not None:
            cur = parc['_prochaine']
            if cur is None or eq.date_fin_garantie < cur:
                parc['_prochaine'] = eq.date_fin_garantie

    # Tri des parcs : échéance la plus proche d'abord (None = tout en fin).
    _MAX = datetime.date.max

    def _sort_key(p):
        return p['_prochaine'] or _MAX

    parcs_list = sorted(parcs.values(), key=_sort_key)
    for p in parcs_list:
        p['prochaine_echeance'] = (
            p['_prochaine'].isoformat() if p['_prochaine'] else None)
        del p['_prochaine']

    return {
        'today': today.isoformat(),
        'expiring_soon_days': expiring_soon_days,
        'parcs': parcs_list,
        'totaux': totaux,
    }


def contrat_maintenance_existe(pk, company):
    """``True`` si un ``ContratMaintenance`` existe pour ``pk`` DANS ``company`` — XCTR13.

    Point d'entrée cross-app en LECTURE SEULE pour la validation à l'écriture
    de ``Contrat.sav_contrat_maintenance_id`` (``apps.contrats``) — jamais un
    import de ``sav.models`` depuis ``contrats`` : l'app appelante passe
    l'``id`` et la société, ce module répond par un simple booléen scopé
    société (aucun objet ``ContratMaintenance`` n'est exposé hors de l'app).
    """
    from .models import ContratMaintenance

    if not pk:
        return False
    return ContratMaintenance.objects.filter(pk=pk, company=company).exists()


def contrats_maintenance_facturables(company):
    """``ContratMaintenance`` actifs à ``facturation_active=True`` — XCTR13.

    Lecture seule, scopée société. Alimente le MRR combiné du tableau de bord
    contrats (``apps.contrats.selectors.tableau_de_bord_contrats``) SANS
    exposer le modèle lui-même — l'appelant ne reçoit que les champs
    nécessaires au calcul MRR (id, prix, periodicite).
    """
    from .models import ContratMaintenance

    qs = ContratMaintenance.objects.filter(
        company=company, actif=True, facturation_active=True,
        prix__isnull=False,
    ).only('id', 'prix', 'periodicite')
    return [
        {'id': cm.id, 'prix': cm.prix, 'periodicite': cm.periodicite}
        for cm in qs
    ]


def csat_par_technicien(company, *, date_debut=None, date_fin=None):
    """XSAV10 — Agrégat CSAT (note moyenne, n réponses) par technicien/mois.

    Regroupe les ``TicketSatisfaction`` de la société sur la plage
    ``[date_debut, date_fin]`` (inclusive, sur ``date_creation`` — bornes
    optionnelles) par (technicien du ticket, mois AAAA-MM). Un ticket sans
    technicien assigné entre dans le seau ``technicien=None`` (« non assigné »).

    Renvoie une liste de dicts triée par mois puis technicien :
      [{'mois': 'YYYY-MM', 'technicien_id': int|None,
        'technicien_nom': str, 'nb_reponses': int, 'note_moyenne': float}, …]
    """
    from django.db.models import Avg, Count
    from django.db.models.functions import TruncMonth

    qs = TicketSatisfaction.objects.filter(company=company)
    if date_debut is not None:
        qs = qs.filter(date_creation__date__gte=date_debut)
    if date_fin is not None:
        qs = qs.filter(date_creation__date__lte=date_fin)

    rows = (qs
            .annotate(mois=TruncMonth('date_creation'))
            .values('mois', 'ticket__technicien_responsable_id',
                    'ticket__technicien_responsable__username')
            .annotate(nb_reponses=Count('id'), note_moyenne=Avg('note'))
            .order_by('mois', 'ticket__technicien_responsable_id'))

    out = []
    for row in rows:
        out.append({
            'mois': row['mois'].strftime('%Y-%m') if row['mois'] else None,
            'technicien_id': row['ticket__technicien_responsable_id'],
            'technicien_nom': (
                row['ticket__technicien_responsable__username'] or 'Non assigné'),
            'nb_reponses': row['nb_reponses'],
            'note_moyenne': round(float(row['note_moyenne']), 2)
            if row['note_moyenne'] is not None else None,
        })
    return out


def taux_reouverture(company, *, group_by='technicien', date_debut=None,
                     date_fin=None):
    """XSAV11 — Taux de réouverture par technicien OU par type de panne.

    ``group_by`` ∈ {'technicien', 'type'}. Un ticket compte comme « réouvert »
    si ``reopen_count > 0``. Filtre optionnel sur ``date_creation``.

    Renvoie une liste de dicts triée par taux décroissant :
      [{'cle': int|str|None, 'libelle': str,
        'nb_tickets': int, 'nb_reouverts': int, 'taux': float}, …]
    ``taux`` est un pourcentage (0-100), arrondi à 2 décimales.
    """
    from django.db.models import Case, Count, When, IntegerField

    qs = Ticket.objects.filter(company=company)
    if date_debut is not None:
        qs = qs.filter(date_creation__date__gte=date_debut)
    if date_fin is not None:
        qs = qs.filter(date_creation__date__lte=date_fin)

    if group_by == 'type':
        field, label_field = 'type', None
    else:
        field, label_field = (
            'technicien_responsable_id', 'technicien_responsable__username')

    values = [field] if label_field is None else [field, label_field]
    rows = (qs
            .values(*values)
            .annotate(
                nb_tickets=Count('id'),
                nb_reouverts=Count(Case(
                    When(reopen_count__gt=0, then=1),
                    output_field=IntegerField())),
            )
            .order_by('-nb_reouverts'))

    out = []
    for row in rows:
        nb_tickets = row['nb_tickets']
        nb_reouverts = row['nb_reouverts']
        taux = round((nb_reouverts / nb_tickets) * 100, 2) if nb_tickets else 0.0
        cle = row[field]
        if group_by == 'type':
            libelle = dict(Ticket.Type.choices).get(cle, cle or 'Inconnu')
        else:
            libelle = row.get(label_field) or 'Non assigné'
        out.append({
            'cle': cle, 'libelle': libelle,
            'nb_tickets': nb_tickets, 'nb_reouverts': nb_reouverts,
            'taux': taux,
        })
    out.sort(key=lambda r: r['taux'], reverse=True)
    return out


def ticket_scoped(company, ticket_id):
    """XQHS23 — un ``sav.Ticket`` scopé société, par id (lecture seule).

    Point d'entrée pour le pont QHSE (``qhse.services.creer_ncr_depuis_ticket``) :
    QHSE lit le ticket via CE sélecteur plutôt que d'importer
    ``apps.sav.models`` directement (règle de modularité cross-app,
    CLAUDE.md). Renvoie ``None`` si le ticket n'existe pas dans la société."""
    return Ticket.objects.filter(company=company, id=ticket_id).first()


def produits_par_tickets(company, ticket_ids):
    """XQHS23 — map ``{ticket_id: {'produit_id': int|None, 'produit_nom':
    str|None}}`` pour un lot de tickets SAV, via leur équipement lié.

    Point d'entrée LECTURE SEULE pour QHSE (``taux_defaillance_par_produit``) :
    QHSE ne lit jamais ``sav.models``/``stock.models`` directement — cette
    fonction lit ``sav.Ticket``/``sav.Equipement`` (même app) + le nom du
    produit (FK intra-app vers ``stock.Produit``, lecture seule ici)."""
    tickets = (
        Ticket.objects
        .filter(company=company, id__in=list(ticket_ids))
        .select_related('equipement__produit')
    )
    out = {}
    for ticket in tickets:
        equipement = ticket.equipement
        if equipement is not None and equipement.produit_id:
            out[ticket.id] = {
                'produit_id': equipement.produit_id,
                'produit_nom': equipement.produit.nom,
            }
        else:
            out[ticket.id] = {'produit_id': None, 'produit_nom': None}
    return out
