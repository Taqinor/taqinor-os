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
from django.utils import timezone

from .models import (
    Equipement, EquipeMaintenance, KbArticle, Ticket, TicketActivity,
    TicketSatisfaction,
)


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


def client_a_contrat_actif(client, company):
    """YSERV10 — ``True`` si ``client`` a AU MOINS UN ``ContratMaintenance``
    ``actif=True`` dans ``company``. Lecture cross-app en SEUL BOOLÉEN
    (aucun objet exposé) — le point d'entrée que ``apps.sav.receivers``
    utilise pour décider de proposer (ou non) un contrat d'entretien à la
    réception d'un chantier."""
    from .models import ContratMaintenance

    if client is None:
        return False
    return ContratMaintenance.objects.filter(
        client=client, company=company, actif=True).exists()


def taux_attache(company, *, date_debut=None, date_fin=None):
    """YSERV10 — KPI taux d'attache : part des chantiers réceptionnés de la
    période qui ont un ``ContratMaintenance`` ``actif`` créé (``date_debut``)
    dans les 90 jours suivant la réception (``Installation.date_reception``
    — posé exactement à la transition RECEPTIONNE, jamais approximé par
    ``updated_at``).

    Renvoie ``{'total': int, 'avec_contrat': int, 'taux_pct': float}``
    (``taux_pct`` à 0.0 si ``total`` est nul — jamais une division par zéro).
    Frontière cross-app : les chantiers sont lus via
    ``apps.installations.selectors.chantiers_receptionnes`` — jamais un
    import du modèle ``Installation``."""
    from datetime import timedelta

    from apps.installations.selectors import chantiers_receptionnes

    from .models import ContratMaintenance

    chantiers = chantiers_receptionnes(
        company, date_debut=date_debut, date_fin=date_fin)

    total = 0
    avec_contrat = 0
    for _id, client_id, date_reception in chantiers:
        total += 1
        horizon = date_reception + timedelta(days=90)
        has_contrat = ContratMaintenance.objects.filter(
            company=company, client_id=client_id, actif=True,
            date_debut__gte=date_reception, date_debut__lte=horizon,
        ).exists()
        if has_contrat:
            avec_contrat += 1

    taux_pct = round((avec_contrat / total) * 100, 1) if total else 0.0
    return {'total': total, 'avec_contrat': avec_contrat, 'taux_pct': taux_pct}


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


def droits_restants(contrat, annee=None):
    """XCTR3 — Compteurs de droits inclus (entitlements) consommés/restants
    pour ``contrat`` sur l'année civile ``annee`` (défaut : année courante).

    Compte les tickets PREVENTIF (visites) et CORRECTIF (déplacements) ouverts
    sur le contrat (via `installation` — même pivot que les visites générées)
    dont ``date_ouverture`` tombe dans les bornes de l'année civile demandée.
    Un quota NULL sur le contrat = illimité : jamais d'avertissement, le champ
    ``restant`` renvoie ``None`` (pas de division/quota calculée).
    """
    from datetime import date as _date

    annee = annee or timezone.localdate().year
    debut = _date(annee, 1, 1)
    fin = _date(annee, 12, 31)

    if contrat.installation_id:
        base_qs = Ticket.objects.filter(
            company_id=contrat.company_id,
            installation_id=contrat.installation_id,
            date_ouverture__gte=debut, date_ouverture__lte=fin,
        )
        visites_consommees = base_qs.filter(type=Ticket.Type.PREVENTIF).count()
        deplacements_consommes = base_qs.filter(type=Ticket.Type.CORRECTIF).count()
    else:
        visites_consommees = 0
        deplacements_consommes = 0

    def _restant(inclus, consomme):
        if inclus is None:
            return None
        return max(0, inclus - consomme)

    return {
        'annee': annee,
        'visites_incluses_an': contrat.visites_incluses_an,
        'visites_consommees': visites_consommees,
        'visites_restantes': _restant(
            contrat.visites_incluses_an, visites_consommees),
        'deplacements_inclus_an': contrat.deplacements_inclus_an,
        'deplacements_consommes': deplacements_consommes,
        'deplacements_restants': _restant(
            contrat.deplacements_inclus_an, deplacements_consommes),
    }


def taux_resolution_a_distance(company, *, date_debut=None, date_fin=None,
                               group_by_technicien=False):
    """YSERV12 — Taux de résolution À DISTANCE (KPI d'évitement de
    déplacement) : tickets résolus à distance / tickets résolus (statut
    RESOLU/CLOTURE, ``canal_resolution`` renseigné), sur la fenêtre
    ``[date_debut, date_fin]`` (bornes optionnelles, sur ``date_resolution``).

    ``group_by_technicien=True`` renvoie une ventilation par technicien
    responsable (clé ``None`` = non assigné) en plus du total. Un ticket sans
    ``canal_resolution`` (jamais renseigné — comportement historique) est
    EXCLU du dénominateur : le taux ne porte que sur les tickets où le canal
    est connu. Aucune division par zéro (0 résolu → taux ``None``)."""
    qs = Ticket.objects.filter(
        company=company,
        statut__in=(Ticket.Statut.RESOLU, Ticket.Statut.CLOTURE),
        canal_resolution__isnull=False,
    )
    if date_debut is not None:
        qs = qs.filter(date_resolution__gte=date_debut)
    if date_fin is not None:
        qs = qs.filter(date_resolution__lte=date_fin)

    def _taux(queryset):
        total = queryset.count()
        if not total:
            return {'resolus': 0, 'a_distance': 0, 'taux_pct': None}
        a_distance = queryset.filter(
            canal_resolution=Ticket.CanalResolution.A_DISTANCE).count()
        return {
            'resolus': total,
            'a_distance': a_distance,
            'taux_pct': round((a_distance / total) * 100, 1),
        }

    result = {'global': _taux(qs)}
    if group_by_technicien:
        techniciens = qs.values_list(
            'technicien_responsable_id',
            'technicien_responsable__username').distinct()
        par_technicien = []
        for tech_id, tech_nom in techniciens:
            par_technicien.append({
                'technicien_id': tech_id,
                'technicien_nom': tech_nom,
                **_taux(qs.filter(technicien_responsable_id=tech_id)),
            })
        result['par_technicien'] = par_technicien
    return result


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


def ratio_deflection_kb(company):
    """XSAV22 — Ratio de déflection KB sur le portail client : consultations
    d'articles KB depuis le formulaire d'ouverture de ticket vs demandes de
    ticket réellement créées. Point d'entrée pour le rapport service
    (apps.reporting), même motif que ``csat_par_technicien`` ci-dessus.

    Lit UNIQUEMENT via les selectors des apps cibles (jamais leurs modèles,
    règle de modularité CLAUDE.md) : ``apps.kb.selectors`` (consultations) et
    ``apps.portail.selectors`` (tickets créés).

    Renvoie ``{'consultations_kb': int, 'tickets_crees': int, 'ratio': float}``
    — ``ratio`` = consultations / (consultations + tickets), dans ``[0, 1]``,
    ``0.0`` quand il n'y a ni consultation ni ticket (pas de division par
    zéro)."""
    from apps.kb.selectors import consultations_portail_total
    from apps.portail.selectors import demandes_ticket_count

    consultations = consultations_portail_total(company)
    tickets = demandes_ticket_count(company)
    total = consultations + tickets
    ratio = round(consultations / total, 4) if total else 0.0
    return {
        'consultations_kb': consultations,
        'tickets_crees': tickets,
        'ratio': ratio,
    }


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


# ── XSAV25 — Pièces compatibles par modèle d'équipement ───────────────────────

def pieces_compatibles(company, produit_equipement_id):
    """XSAV25 — Pièces catalogue COMPATIBLES avec ``produit_equipement_id``,
    triées en premier (le picker de pièces du ticket les propose avant le
    reste du catalogue). Lecture via ``stock.selectors`` pour les champs
    produit affichés — jamais un import direct de ``apps.stock.models``.

    Suit la chaîne de supersession (``remplace_par``) UN niveau : si une
    pièce compatible est marquée remplacée, la pièce de remplacement est
    ajoutée à la liste (dédupliquée) avec une note explicite.

    Renvoie une liste de dicts plats :
      [{'piece_id': int, 'nom': str, 'sku': str, 'note': str,
        'remplace_par_id': int|None, 'remplace_par_nom': str|None}, …]
    """
    from apps.stock.selectors import get_produit_scoped
    from .models import CompatibilitePiece

    qs = (CompatibilitePiece.objects
          .filter(company=company, produit_equipement_id=produit_equipement_id)
          .select_related('piece', 'remplace_par'))

    out = []
    seen = set()
    for cp in qs:
        piece = cp.piece
        if piece.id in seen:
            continue
        seen.add(piece.id)
        remplace_par = cp.remplace_par
        out.append({
            'piece_id': piece.id,
            'nom': piece.nom,
            'sku': getattr(piece, 'sku', '') or '',
            'note': cp.note,
            'remplace_par_id': remplace_par.id if remplace_par else None,
            'remplace_par_nom': remplace_par.nom if remplace_par else None,
        })
        if remplace_par is not None and remplace_par.id not in seen:
            seen.add(remplace_par.id)
            resolved = get_produit_scoped(company, remplace_par.id) or remplace_par
            out.append({
                'piece_id': resolved.id,
                'nom': resolved.nom,
                'sku': getattr(resolved, 'sku', '') or '',
                'note': f'Remplace {piece.nom} (référence discontinuée).',
                'remplace_par_id': None,
                'remplace_par_nom': None,
            })
    return out


def ticket_scoped(company, ticket_id):
    """XQHS23 — un ``sav.Ticket`` scopé société, par id (lecture seule).

    Point d'entrée pour le pont QHSE (``qhse.services.creer_ncr_depuis_ticket``) :
    QHSE lit le ticket via CE sélecteur plutôt que d'importer
    ``apps.sav.models`` directement (règle de modularité cross-app,
    CLAUDE.md). Renvoie ``None`` si le ticket n'existe pas dans la société."""
    return Ticket.objects.filter(company=company, id=ticket_id).first()


def equipement_scoped_by_serial(company, numero_serie):
    """XSTK7 — un ``sav.Equipement`` scopé société, par n° de série (lecture
    seule). Point d'entrée cross-app pour le rapport de traçabilité
    bout-en-bout de ``apps.stock`` (jamais son modèle importé directement).
    Renvoie ``None`` si aucun équipement ne porte ce n° de série dans la
    société."""
    return (Equipement.objects
            .filter(company=company, numero_serie=numero_serie)
            .select_related('produit', 'installation', 'installation__client')
            .first())


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


# ── XSAV28 — Triage IA du ticket : articles KB pertinents ───────────────────

def kb_articles_pertinents(company, texte, *, limit=3):
    """XSAV28 — articles KB (FG87) les plus pertinents pour ``texte`` (mots-
    clés recoupés — même technique déterministe que ``tickets_similaires``,
    stdlib pure). Sert de contexte au brouillon de réponse IA : jamais
    utilisé pour appliquer quoi que ce soit automatiquement."""
    mots_ref = _mots_cles(texte)
    if not mots_ref:
        return []
    qs = KbArticle.objects.filter(company=company)
    scored = []
    for art in qs:
        mots_art = _mots_cles(f'{art.titre} {art.corps}')
        if not mots_art:
            continue
        inter = len(mots_ref & mots_art)
        if inter <= 0:
            continue
        union = len(mots_ref | mots_art)
        jaccard = inter / union if union else 0.0
        scored.append((jaccard, art))
    scored.sort(key=lambda pair: (-pair[0], -pair[1].pk))
    return [
        {'id': art.id, 'titre': art.titre,
         'extrait': (art.corps or '')[:300]}
        for _score, art in scored[:limit]
    ]


# ── ZMFG4 — Tableau de bord maintenance par équipe/statut ────────────────────

def resume_par_equipe(company):
    """ZMFG4 — Résumé du dashboard SAV par équipe de maintenance (ZMFG1) :
    pour chaque équipe active de la société, compte les tickets OUVERTS
    (``Ticket.OPEN_STATUTS``, non annulés), les tickets en retard SLA
    (``sla_breach=True``), les préventifs dus (``type=preventif`` et ouverts)
    et les correctifs urgents (``type=correctif``, ``priorite=urgente``,
    ouverts). Les tickets SANS équipe sont regroupés sous la clé ``None``
    (« Sans équipe ») pour que le total reste cohérent avec la liste globale.

    Renvoie une liste de dicts :
      [{'equipe_id': int|None, 'equipe_nom': str,
        'ouverts': int, 'en_retard_sla': int,
        'preventifs_dus': int, 'correctifs_urgents': int}, …]
    triée par nom d'équipe (« Sans équipe » toujours en dernier)."""
    base = Ticket.objects.filter(
        company=company, statut__in=Ticket.OPEN_STATUTS, annule=False)

    equipes = list(EquipeMaintenance.objects.filter(
        company=company, actif=True).order_by('nom'))

    out = []
    for equipe in equipes:
        qs = base.filter(equipe_id=equipe.id)
        out.append({
            'equipe_id': equipe.id,
            'equipe_nom': equipe.nom,
            'ouverts': qs.count(),
            'en_retard_sla': qs.filter(sla_breach=True).count(),
            'preventifs_dus': qs.filter(type=Ticket.Type.PREVENTIF).count(),
            'correctifs_urgents': qs.filter(
                type=Ticket.Type.CORRECTIF,
                priorite=Ticket.Priorite.URGENTE).count(),
        })

    sans_equipe = base.filter(equipe__isnull=True)
    out.append({
        'equipe_id': None,
        'equipe_nom': 'Sans équipe',
        'ouverts': sans_equipe.count(),
        'en_retard_sla': sans_equipe.filter(sla_breach=True).count(),
        'preventifs_dus': sans_equipe.filter(
            type=Ticket.Type.PREVENTIF).count(),
        'correctifs_urgents': sans_equipe.filter(
            type=Ticket.Type.CORRECTIF,
            priorite=Ticket.Priorite.URGENTE).count(),
    })
    return out


# ── ZSAV6 — Vue « activité » : file d'action suivante par ticket ────────────

def file_action(company, *, today=None):
    """ZSAV6 — Regroupe les tickets OUVERTS de la société par « action
    attendue » (parité Odoo « Activity view »), chaque ticket dans EXACTEMENT
    un bucket (le premier qui matche, dans l'ordre ci-dessous) :

      * ``a_repondre``  — ``date_premiere_reponse`` absente (FG81) ;
      * ``a_planifier`` — ``statut=PLANIFIE`` sans ``date_tournee`` (FG88) ;
      * ``a_relancer``  — ``statut=EN_COURS`` et plus de la moitié du délai
        SLA écoulé (``date_ouverture`` → ``sla_due_at``), sans échéance SLA
        calculable = jamais dans ce bucket ;
      * ``a_cloturer``  — ``statut=RESOLU`` dormant (aucune activité chatter
        depuis ≥ 7 jours, ou depuis la résolution si pas d'activité) ;
      * ``sans_action``  — aucun des cas ci-dessus (ticket NOUVEAU sans
        réponse... capturé par ``a_repondre`` en priorité — ce bucket ne
        contient que les tickets ouverts qui ne matchent RIEN d'autre).

    Renvoie ``{'buckets': {cle: {'count': int, 'ids': [int, …]}, …}}``.
    Les tickets annulés sont exclus (jamais « à traiter »)."""
    from datetime import timedelta

    if today is None:
        today = timezone.localdate()

    buckets = {
        'a_repondre': [], 'a_planifier': [], 'a_relancer': [],
        'a_cloturer': [], 'sans_action': [],
    }

    qs = (Ticket.objects
          .filter(company=company, statut__in=Ticket.OPEN_STATUTS + [
              Ticket.Statut.RESOLU], annule=False)
          .prefetch_related('activites'))

    for t in qs:
        if t.statut in Ticket.OPEN_STATUTS and t.date_premiere_reponse is None:
            buckets['a_repondre'].append(t.id)
            continue
        if t.statut == Ticket.Statut.PLANIFIE and t.date_tournee is None:
            buckets['a_planifier'].append(t.id)
            continue
        if (t.statut == Ticket.Statut.EN_COURS
                and t.date_ouverture and t.sla_due_at):
            total_jours = (t.sla_due_at - t.date_ouverture).days
            if total_jours > 0:
                ecoules = (today - t.date_ouverture).days
                if ecoules >= total_jours / 2:
                    buckets['a_relancer'].append(t.id)
                    continue
        if t.statut == Ticket.Statut.RESOLU:
            # XSAV24 journalise désormais TOUJOURS la création du ticket dans
            # son chatter (kind=CREATION) — la dernière activité n'est donc
            # plus jamais absente, mais cette entrée automatique ne prouve
            # rien sur l'activité APRÈS résolution (elle précède toujours la
            # résolution). On ne regarde que le chatter de SUIVI (notes,
            # modifications) pour la dormance ; sans ticket suivi, on retombe
            # sur la date de résolution elle-même.
            derniere = (t.activites
                        .exclude(kind=TicketActivity.Kind.CREATION)
                        .order_by('-created_at')
                        .values_list('created_at', flat=True).first())
            reference_dt = (
                timezone.localtime(derniere).date() if derniere
                else t.date_resolution or t.date_ouverture)
            if reference_dt is not None and (
                    today - reference_dt) >= timedelta(days=7):
                buckets['a_cloturer'].append(t.id)
                continue
        if t.statut in Ticket.OPEN_STATUTS:
            buckets['sans_action'].append(t.id)

    return {
        'buckets': {
            cle: {'count': len(ids), 'ids': ids}
            for cle, ids in buckets.items()
        }
    }


# ── ZMFG8 — Affichage unifié des pièces (ajout/retrait/recyclage) ───────────

def pieces_unifiees(ticket):
    """ZMFG8 — Liste UNIFIÉE des pièces d'un ticket, regroupant
    ``PieceConsommee`` (ajout) et ``PieceRetiree`` (retrait/recyclage) en une
    seule structure typée par ``operation``, avec sous-totaux par type de
    quantité. Pure lecture — aucun mouvement de stock déclenché ici (délégué
    à `services.retirer_piece`/l'enregistrement de consommation existant)."""
    from decimal import Decimal

    rows = []
    for piece in ticket.pieces.select_related('produit').all():
        rows.append({
            'id': piece.id,
            'operation': piece.operation,
            'produit_id': piece.produit_id,
            'produit_nom': getattr(piece.produit, 'nom', None),
            'quantite': piece.quantite,
        })
    for piece in ticket.pieces_retirees.select_related('produit').all():
        rows.append({
            'id': piece.id,
            'operation': piece.operation,
            'produit_id': piece.produit_id,
            'produit_nom': getattr(piece.produit, 'nom', None),
            'quantite': piece.quantite,
            'destination': piece.destination,
        })

    sous_totaux = {'ajout': Decimal('0'), 'retrait': Decimal('0'),
                   'recyclage': Decimal('0')}
    for row in rows:
        sous_totaux[row['operation']] += Decimal(str(row['quantite']))

    return {'lignes': rows, 'sous_totaux': sous_totaux}


# ── ZMFG11 — Prochaine défaillance estimée + prochain entretien dû ─────────

def estimations_maintenance(equipement):
    """ZMFG11 — Deux dérivés lecture-seule complétant XSAV15 (MTBF/MTTR) :

    * ``prochaine_defaillance_estimee`` = date du DERNIER ticket correctif +
      MTBF (jours). ``None`` si moins de 2 tickets correctifs datés (MTBF
      indéfini) — jamais de division par zéro (`fiabilite_equipement` gère
      déjà ce cas en amont).
    * ``prochain_entretien_du`` = la plus proche entre (a) la prochaine
      visite du ``ContratMaintenance`` ACTIF du client qui couvre cet
      équipement (``sav.selectors``, XCTR2) et (b) l'échéance de seuil
      compteur (XSAV17) si l'équipement en porte un et qu'un relevé existe.
      ``None`` si aucune des deux source n'est disponible.

    Renvoie un dict plat, jamais l'instance ORM."""
    from datetime import timedelta
    from decimal import Decimal

    from .models import ContratMaintenance, ReleveCompteurEquipement

    # ── Prochaine défaillance estimée ──
    fiabilite = fiabilite_equipement(equipement, include_couts=False)
    prochaine_defaillance_estimee = None
    if fiabilite['mtbf_jours'] is not None:
        dernier = (Ticket.objects
                   .filter(equipement=equipement, type=Ticket.Type.CORRECTIF,
                           annule=False, date_ouverture__isnull=False)
                   .order_by('-date_ouverture', '-id')
                   .values_list('date_ouverture', flat=True).first())
        if dernier is not None:
            prochaine_defaillance_estimee = dernier + timedelta(
                days=round(fiabilite['mtbf_jours']))

    # ── Prochain entretien dû ──
    candidats = []

    client = getattr(equipement.installation, 'client', None) or equipement.client_vente
    if client is not None:
        contrat = (ContratMaintenance.objects
                   .filter(client=client, actif=True)
                   .order_by('-date_creation').first())
        if contrat is not None and contrat.couvre_equipement(equipement):
            candidats.append(contrat.prochaine_visite())

    if equipement.entretien_toutes_les_heures:
        dernier_releve = (ReleveCompteurEquipement.objects
                          .filter(equipement=equipement)
                          .order_by('-date', '-id').first())
        if dernier_releve is not None:
            valeur_reference = (
                equipement.dernier_entretien_compteur_valeur
                if equipement.dernier_entretien_compteur_valeur is not None
                else Decimal('0'))
            restant = (equipement.entretien_toutes_les_heures
                       - (dernier_releve.valeur - valeur_reference))
            if restant <= 0:
                candidats.append(timezone.localdate())
            # Un compteur cumulatif ne donne pas de DATE d'échéance sans
            # une cadence d'usage connue — seul un franchissement déjà
            # atteint (restant <= 0) produit une candidate ici ; sinon on
            # laisse le contrat temporel (a) faire foi.

    prochain_entretien_du = min(candidats) if candidats else None

    return {
        'equipement_id': equipement.id,
        'prochaine_defaillance_estimee': prochaine_defaillance_estimee,
        'prochain_entretien_du': prochain_entretien_du,
    }


def ticket_chatter_envelope(ticket):
    """ARC9 — timeline chatter du ticket dans l'ENVELOPPE UNIFORME.

    Projette ``sav.TicketActivity`` vers le format commun consommé par
    ``records.serializers.UniformChatterSerializer`` — même contrat de lecture
    que ``crm.selectors.lead_chatter_envelope`` et
    ``contrats.selectors.contrat_chatter_envelope``. Lecture seule, aucune
    table modifiée. Le ticket est déjà borné société par l'appelant.
    """
    rows = ticket.activites.select_related('user').all()
    return [{
        'id': a.id,
        'kind': a.kind,
        'field': a.field or '',
        'field_label': a.field_label or '',
        'old_value': a.old_value or '',
        'new_value': a.new_value or '',
        'body': a.body or '',
        'user_username': a.user.username if a.user_id else None,
        'created_at': a.created_at,
        'source': 'sav.ticketactivity',
    } for a in rows]


# ── VX214 — kinds d'EXÉCUTION pour « Ma file » (jamais une 2ᵉ boîte) ────────

def affectations_pour(user):
    """VX214 — tickets SAV ouverts affectés à `user` (technicien responsable),
    prêts pour l'union « Ma file » (``apps.records.views.ma_file``) — contrat
    commun ``{kind, title, due, link, urgency}``, MÊME forme que ``crm.
    selectors.ma_file_commercial_items`` (VX83). Lecture seule, scopée
    société + utilisateur ; jamais un import de ``notifications``/``records``.

    Un ticket « transféré » à ce technicien reste simplement un ticket OUVERT
    (``OPEN_STATUTS``) dont il est le ``technicien_responsable`` — aucun champ
    dédié d'horodatage de transfert n'existe aujourd'hui ; le champ qui
    compte pour la file est « qui doit agir maintenant », pas « depuis
    quand » (VX218 couvre déjà le badge « Nouveau » côté chantiers)."""
    if user is None or not getattr(user, 'company_id', None):
        return []
    from django.utils import timezone

    from .models import Ticket

    company = user.company
    today = timezone.localdate()
    items = []

    tickets = (Ticket.objects
               .filter(company=company, technicien_responsable=user,
                       statut__in=Ticket.OPEN_STATUTS)
               .select_related('client')
               .order_by('date_ouverture'))
    for t in tickets:
        due = t.date_ouverture
        if due is None:
            urgency = 'today'
        elif due < today:
            urgency = 'overdue'
        else:
            urgency = 'today'
        client_nom = getattr(t.client, 'nom', '') or ''
        items.append({
            'kind': 'ticket_transfere',
            'title': f'Ticket {t.reference} — {client_nom or "client"} '
                     f'({t.get_statut_display()})',
            'due': due,
            'link': '/sav',
            'urgency': urgency,
        })
    return items
