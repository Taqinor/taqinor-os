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


def pareto_pannes(company, *, group_by='produit', date_debut=None,
                  date_fin=None):
    """XSAV14 — Pareto des pannes par MODÈLE DE PRODUIT ou par FOURNISSEUR.

    ``group_by`` ∈ {'produit', 'fournisseur'}. Compte les tickets CORRECTIFS
    de la société (annulés exclus) portant une ``cause`` codifiée, groupés par
    le produit de l'équipement lié (ou son fournisseur, lu via
    ``stock.selectors`` — jamais un import direct de ``stock.models``).
    Filtre optionnel sur ``date_creation`` (bornes inclusives).

    Renvoie une liste de dicts triée par nombre décroissant (Pareto), chacun
    avec le compte cumulé % (colonne Pareto classique) :
      [{'cle': int|str|None, 'libelle': str, 'nb_tickets': int,
        'pct': float, 'pct_cumule': float,
        'causes': [{'cause': str, 'nb': int}, …]}, …]

    Un ticket sans équipement lié, ou dont l'équipement n'a pas de produit
    résolu, est ignoré (pas de bucket « Inconnu » — un Pareto sans donnée
    fiable ne serait pas exploitable pour une réclamation garantie FG83)."""
    qs = (Ticket.objects
          .filter(company=company, type=Ticket.Type.CORRECTIF, annule=False,
                  equipement__isnull=False, cause__isnull=False)
          .select_related('equipement', 'equipement__produit', 'cause'))
    if date_debut is not None:
        qs = qs.filter(date_creation__date__gte=date_debut)
    if date_fin is not None:
        qs = qs.filter(date_creation__date__lte=date_fin)

    fournisseur_cache = {}

    def _fournisseur_for(produit):
        pid = getattr(produit, 'id', None)
        if pid is None:
            return None, None
        if pid in fournisseur_cache:
            return fournisseur_cache[pid]
        fid = getattr(produit, 'fournisseur_id', None)
        nom = None
        if fid:
            try:
                from apps.stock.selectors import get_fournisseur_by_id
                f = get_fournisseur_by_id(company, fid)
                nom = getattr(f, 'nom', None) if f else None
            except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
                nom = None
        fournisseur_cache[pid] = (fid, nom)
        return fid, nom

    buckets = {}
    total = 0
    for t in qs:
        produit = getattr(t.equipement, 'produit', None)
        if produit is None:
            continue
        if group_by == 'fournisseur':
            fid, fnom = _fournisseur_for(produit)
            if fid is None:
                continue
            cle, libelle = fid, (fnom or f'Fournisseur #{fid}')
        else:
            cle, libelle = produit.id, (getattr(produit, 'nom', '') or '—')
        bucket = buckets.setdefault(
            cle, {'cle': cle, 'libelle': libelle, 'nb_tickets': 0,
                  '_causes': {}})
        bucket['nb_tickets'] += 1
        cause_nom = t.cause.nom
        bucket['_causes'][cause_nom] = bucket['_causes'].get(cause_nom, 0) + 1
        total += 1

    rows = sorted(buckets.values(), key=lambda b: b['nb_tickets'], reverse=True)
    cumule = 0
    out = []
    for row in rows:
        nb = row['nb_tickets']
        pct = round((nb / total) * 100, 2) if total else 0.0
        cumule += nb
        pct_cumule = round((cumule / total) * 100, 2) if total else 0.0
        causes = sorted(
            ({'cause': c, 'nb': n} for c, n in row['_causes'].items()),
            key=lambda c: c['nb'], reverse=True)
        out.append({
            'cle': row['cle'], 'libelle': row['libelle'], 'nb_tickets': nb,
            'pct': pct, 'pct_cumule': pct_cumule, 'causes': causes,
        })
    return out


# ── XSAV15 — MTBF / MTTR / coût cumulé par équipement ────────────────────────

def fiabilite_equipement(equipement, *, include_couts=False):
    """XSAV15 — MTBF / MTTR / coût cumulé pour UN équipement.

    * MTBF (jours) = écart MOYEN entre les ``date_ouverture`` de tickets
      CORRECTIFS successifs du même équipement (non annulés), triés
      chronologiquement. ``None`` si moins de 2 tickets correctifs datés.
    * MTTR (jours) = écart MOYEN ``date_resolution - date_ouverture`` sur les
      tickets correctifs RÉSOLUS/CLÔTURÉS ayant les deux dates. ``None`` si
      aucun ticket résolu daté.
    * ``cout_cumule`` (Ticket.cout + PieceConsommee valorisées au prix
      D'ACHAT interne) — calculé UNIQUEMENT si ``include_couts=True``
      (gated ``prix_achat_voir`` côté appelant, jamais côté PDF/client).
    * ``reparer_vs_remplacer`` : ``'remplacer'`` si le coût cumulé dépasse le
      prix de vente catalogue de l'équipement (le remplacement serait moins
      cher que les réparations cumulées), ``'reparer'`` sinon, ``None`` sans
      coût calculable.

    Renvoie un dict plat (jamais l'instance ORM) — sûr à sérialiser tel quel.
    """
    tickets = list(
        Ticket.objects.filter(
            equipement=equipement, type=Ticket.Type.CORRECTIF, annule=False,
        ).order_by('date_ouverture', 'id'))

    # ── MTBF : écart moyen entre ouvertures successives ──
    ouvertures = [t.date_ouverture for t in tickets if t.date_ouverture]
    ouvertures.sort()
    ecarts = [
        (ouvertures[i] - ouvertures[i - 1]).days
        for i in range(1, len(ouvertures))
    ]
    mtbf_jours = round(sum(ecarts) / len(ecarts), 1) if ecarts else None

    # ── MTTR : écart moyen ouverture → résolution ──
    durees = []
    for t in tickets:
        if t.date_ouverture and t.date_resolution:
            durees.append((t.date_resolution - t.date_ouverture).days)
    mttr_jours = round(sum(durees) / len(durees), 1) if durees else None

    result = {
        'equipement_id': equipement.id,
        'nb_tickets_correctifs': len(tickets),
        'mtbf_jours': mtbf_jours,
        'mttr_jours': mttr_jours,
    }

    if not include_couts:
        return result

    from decimal import Decimal
    from .models import PieceConsommee

    cout_tickets = sum(
        (t.cout for t in tickets if t.cout is not None), Decimal('0'))
    pieces = (PieceConsommee.objects
              .filter(ticket__in=tickets)
              .select_related('produit'))
    cout_pieces = sum(
        (p.quantite * p.produit.prix_achat for p in pieces), Decimal('0'))
    cout_cumule = cout_tickets + cout_pieces

    prix_vente = getattr(equipement.produit, 'prix_vente', None)
    reparer_vs_remplacer = None
    if prix_vente is not None:
        reparer_vs_remplacer = (
            'remplacer' if cout_cumule > prix_vente else 'reparer')

    result.update({
        'cout_cumule': float(cout_cumule),
        'cout_tickets': float(cout_tickets),
        'cout_pieces': float(cout_pieces),
        'prix_catalogue': float(prix_vente) if prix_vente is not None else None,
        'reparer_vs_remplacer': reparer_vs_remplacer,
    })
    return result


def fiabilite_equipements(company, *, include_couts=False, limit=None):
    """XSAV15 — Fiabilité (MTBF/MTTR/coût) de TOUS les équipements de la
    société ayant au moins un ticket correctif, triée par coût cumulé
    décroissant (si ``include_couts``) sinon par nombre de tickets
    correctifs décroissant — la liste sert à identifier les « citrons »."""
    qs = (Equipement.objects
          .filter(company=company, tickets__type=Ticket.Type.CORRECTIF,
                  tickets__annule=False)
          .select_related('produit')
          .distinct())
    rows = [
        fiabilite_equipement(eq, include_couts=include_couts) for eq in qs
    ]
    for row, eq in zip(rows, qs):
        row['produit_nom'] = getattr(eq.produit, 'nom', '') or ''
        row['numero_serie'] = eq.numero_serie or ''
    key = (
        (lambda r: r.get('cout_cumule') or 0) if include_couts
        else (lambda r: r['nb_tickets_correctifs']))
    rows.sort(key=key, reverse=True)
    if limit:
        rows = rows[:limit]
    return rows


# ── XSAV18 — Rentabilité par contrat de maintenance ───────────────────────────

def _revenu_contrat_maintenance(contrat):
    """XSAV18 — Revenu facturé pour CE contrat (FG40).

    Les factures récurrentes du contrat ne sont, à ce jour, liées QUE par leur
    libellé texte (``creer_facture_contrat`` pose
    ``f'Maintenance — contrat #{contrat.pk} (...)'``, cf. `apps.ventes.services`
    — aucun FK dédié n'existe encore). Lecture SEULE, best-effort : une erreur
    (app ventes absente/erreur) renvoie 0 plutôt que de bloquer la
    rentabilité. Somme les montants TTC des factures non annulées dont le
    libellé référence ce contrat."""
    from decimal import Decimal
    try:
        from apps.ventes.models import Facture
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        return Decimal('0')

    marqueur = f'contrat #{contrat.pk}'
    qs = (Facture.objects
          .filter(company=contrat.company, libelle__icontains=marqueur)
          .exclude(statut=Facture.Statut.ANNULEE))
    return sum((f.montant_ttc for f in qs), Decimal('0'))


def rentabilite_contrat(contrat):
    """XSAV18 — P&L d'UN contrat de maintenance.

    Revenu = factures récurrentes FG40 référençant ce contrat (cf.
    ``_revenu_contrat_maintenance``). Coût = tickets liés (même client +
    même chantier que le contrat, quand un chantier est posé ; sinon même
    client seul) : ``Ticket.cout`` + pièces consommées valorisées au prix
    D'ACHAT interne (jamais le prix de vente). ``marge`` = revenu - coût ;
    ``marge_par_visite`` = marge / nombre de tickets PRÉVENTIFS liés (visites
    de maintenance), ``None`` si aucune visite (pas de division par zéro).

    Admin-only côté appelant (gated `prix_achat_voir`) — jamais exposé au
    client, jamais dans un PDF. Renvoie un dict plat."""
    from decimal import Decimal
    from .models import PieceConsommee

    qs_tickets = Ticket.objects.filter(company=contrat.company, client=contrat.client)
    if contrat.installation_id:
        qs_tickets = qs_tickets.filter(installation=contrat.installation)
    tickets = list(qs_tickets)

    cout_tickets = sum(
        (t.cout for t in tickets if t.cout is not None), Decimal('0'))
    pieces = (PieceConsommee.objects
              .filter(ticket__in=tickets)
              .select_related('produit'))
    cout_pieces = sum(
        (p.quantite * p.produit.prix_achat for p in pieces), Decimal('0'))
    cout = cout_tickets + cout_pieces

    revenu = _revenu_contrat_maintenance(contrat)
    marge = revenu - cout

    nb_visites = sum(1 for t in tickets if t.type == Ticket.Type.PREVENTIF)
    marge_par_visite = (
        float(marge / nb_visites) if nb_visites else None)

    return {
        'contrat_id': contrat.pk,
        'client_id': contrat.client_id,
        'installation_id': contrat.installation_id,
        'revenu': float(revenu),
        'cout': float(cout),
        'marge': float(marge),
        'nb_visites': nb_visites,
        'marge_par_visite': marge_par_visite,
    }


def rentabilite_contrats(company, *, limit=None):
    """XSAV18 — Rentabilité de TOUS les contrats de maintenance actifs de la
    société, classée par marge CROISSANTE (les contrats vendus à perte
    apparaissent en premier — la vue d'action prioritaire avant renouvellement)."""
    from .models import ContratMaintenance

    contrats = ContratMaintenance.objects.filter(company=company)
    rows = [rentabilite_contrat(c) for c in contrats]
    rows.sort(key=lambda r: r['marge'])
    if limit:
        rows = rows[:limit]
    return rows


# ── XSAV21 — Suggestion de tickets similaires résolus ─────────────────────────

_STOPWORDS_FR = {
    'le', 'la', 'les', 'un', 'une', 'des', 'de', 'du', 'et', 'ou', 'a',
    'au', 'aux', 'en', 'dans', 'sur', 'pour', 'par', 'avec', 'sans', 'ne',
    'pas', 'est', 'sont', 'il', 'elle', 'ce', 'cette', 'ces', 'que', 'qui',
    'plus', 'ne', "s", "l", "d", "n", "c", "qu",
}


def _mots_cles(texte):
    """Ensemble de mots-clés normalisés (minuscule, ponctuation ignorée,
    mots vides français filtrés, longueur ≥ 3) — stdlib pure, déterministe."""
    import re

    if not texte:
        return set()
    bruts = re.findall(r"[a-zà-ÿ0-9]+", texte.lower())
    return {m for m in bruts if len(m) >= 3 and m not in _STOPWORDS_FR}


def tickets_similaires(ticket, *, limit=5):
    """XSAV21 — Tickets RÉSOLUS de la société les plus proches de ``ticket``,
    classés par pertinence DÉTERMINISTE (aucune dépendance, stdlib pure) :

      1. même produit d'équipement (+100)
      2. même type de panne codifiée (``cause`` — XSAV14) (+50)
      3. similarité texte de la description (recoupement de mots-clés,
         Jaccard × 10, arrondi 2 décimales)

    Exclut : les tickets OUVERTS (seuls RESOLU/CLOTURE comptent comme des
    résolutions passées à suggérer), les tickets d'une autre société
    (cross-tenant), le ticket lui-même, et les tickets annulés. À égalité de
    score, l'ordre est stabilisé par ``-id`` (le plus récent d'abord) — pas
    d'ordre aléatoire d'un run à l'autre."""
    company = ticket.company_id
    equipement = ticket.equipement
    produit_id = getattr(equipement, 'produit_id', None)
    cause_id = ticket.cause_id

    mots_ref = _mots_cles(ticket.description)

    statuts_resolus = (Ticket.Statut.RESOLU, Ticket.Statut.CLOTURE)
    qs = (Ticket.objects
          .filter(company=company, statut__in=statuts_resolus, annule=False)
          .exclude(pk=ticket.pk)
          .select_related('equipement', 'equipement__produit', 'cause'))

    scored = []
    for cand in qs:
        score = 0.0
        if produit_id is not None and cand.equipement_id and \
                cand.equipement.produit_id == produit_id:
            score += 100
        if cause_id is not None and cand.cause_id == cause_id:
            score += 50
        mots_cand = _mots_cles(cand.description)
        if mots_ref and mots_cand:
            inter = len(mots_ref & mots_cand)
            union = len(mots_ref | mots_cand)
            jaccard = (inter / union) if union else 0.0
            score += round(jaccard * 10, 2)
        if score > 0:
            scored.append((score, cand))

    scored.sort(key=lambda pair: (-pair[0], -pair[1].pk))

    out = []
    for score, cand in scored[:limit]:
        out.append({
            'id': cand.id,
            'reference': cand.reference,
            'score': round(score, 2),
            'produit_nom': getattr(cand.equipement, 'produit', None)
            and cand.equipement.produit.nom,
            'cause_nom': getattr(cand.cause, 'nom', None),
            'resume_resolution': (cand.description or '')[:300],
            'date_resolution': (
                cand.date_resolution.isoformat()
                if cand.date_resolution else None),
        })
    return out
