"""Groupe NTWMS (vague 3) — sélecteurs LECTURE SEULE du pilotage d'entrepôt.

Regroupe les agrégations « cockpit » que le responsable d'entrepôt consulte
(NTWMS29), la simulation de capacité what-if (NTWMS33), l'alerte passive de
sur-capacité (NTWMS42) et l'interleaving rangement→prélèvement (NTWMS36).

Aucune écriture, aucun modèle : ces fonctions LISENT. La hiérarchie de casiers
appartient à ``installations`` (``BinLocation``/``BinAffectation``, FG319) et
la capacité à ``installations.CategorieStockage`` (ZSTK9) : elles sont lues
via les modèles de cette app en STRING-FK/import local — jamais dupliquées.

Toutes les fonctions qui ont besoin d'une date la reçoivent en paramètre
(``aujourdhui``) et retombent sur ``django.utils.timezone`` — jamais
``datetime.now()`` naïf.
"""
from decimal import Decimal

from django.db.models import F, Sum
from django.utils import timezone

# Fenêtre par défaut (jours) des alertes de péremption du cockpit.
HORIZON_PEREMPTION_JOURS = 30
# Une vague LANCÉE depuis plus longtemps que ça est signalée « en retard ».
RETARD_VAGUE_HEURES = 24
# Seuil de remplissage (%) au-delà duquel une zone est dite en sur-capacité.
SEUIL_SURCAPACITE_PCT = Decimal('95')


def _dec(value):
    try:
        return Decimal(str(value))
    except Exception:  # noqa: BLE001 — valeur non numérique -> 0, jamais de crash.
        return Decimal('0')


def _fmt_dec(value):
    """Chaîne décimale normalisée (``'8.00'`` -> ``'8'``, ``'12.50'`` ->
    ``'12.5'``). Même helper que ``apps.mrp.selectors._fmt_dec`` : sans lui, la
    même grandeur se sérialise différemment selon le chemin de calcul (échelle
    héritée des opérandes) et les tests d'API deviennent instables."""
    value = value if isinstance(value, Decimal) else _dec(value)
    if value == 0:
        return '0'
    s = format(value, 'f')
    if '.' in s:
        s = s.rstrip('0').rstrip('.')
    return s or '0'


def _pct(occupe, capacite):
    """Taux de remplissage en % (Decimal). Capacité inconnue/0 -> None : on
    n'invente jamais un taux sur une capacité non renseignée."""
    capacite = _dec(capacite)
    if capacite <= 0:
        return None
    return (_dec(occupe) / capacite * Decimal('100')).quantize(Decimal('0.01'))


# ═══════════════════════════════════════════════════════════════════════════
# Remplissage par zone — socle commun de NTWMS29 / NTWMS33 / NTWMS42
# ═══════════════════════════════════════════════════════════════════════════

def remplissage_par_zone(company, *, emplacement_id=None):
    """Occupation/capacité agrégées par ZONE de casiers (FG319).

    La capacité d'un casier vient de sa ``CategorieStockage.qte_max`` (ZSTK9) ;
    un casier sans catégorie n'apporte AUCUNE capacité (on ne devine pas) mais
    son occupation reste comptée — le taux d'une zone dont aucun casier n'a de
    capacité déclarée vaut donc ``None``, jamais 0 %.

    Renvoie une liste triée par zone :
    ``[{zone, nb_casiers, occupe, capacite, taux_pct}]``.
    """
    from apps.installations.models import BinAffectation, BinLocation

    bins = (BinLocation.objects
            .filter(company=company, archived=False)
            .select_related('categorie'))
    if emplacement_id:
        bins = bins.filter(emplacement_id=emplacement_id)
    bins = list(bins)
    if not bins:
        return []

    occupe_par_bin = {
        row['bin_id']: row['total'] or 0
        for row in (BinAffectation.objects
                    .filter(company=company, bin_id__in=[b.id for b in bins])
                    .values('bin_id').annotate(total=Sum('quantite')))
    }

    zones = {}
    for b in bins:
        cle = (b.zone or '').strip() or '(sans zone)'
        agg = zones.setdefault(
            cle, {'zone': cle, 'nb_casiers': 0, 'occupe': 0, 'capacite': 0,
                  'capacite_connue': False})
        agg['nb_casiers'] += 1
        agg['occupe'] += int(occupe_par_bin.get(b.id, 0) or 0)
        qte_max = getattr(b.categorie, 'qte_max', None) if b.categorie_id else None
        if qte_max:
            agg['capacite'] += int(qte_max)
            agg['capacite_connue'] = True

    resultat = []
    for agg in sorted(zones.values(), key=lambda a: a['zone']):
        taux = _pct(agg['occupe'], agg['capacite']) if agg['capacite_connue'] else None
        resultat.append({
            'zone': agg['zone'],
            'nb_casiers': agg['nb_casiers'],
            'occupe': agg['occupe'],
            'capacite': agg['capacite'] if agg['capacite_connue'] else None,
            'taux_pct': _fmt_dec(taux) if taux is not None else None,
        })
    return resultat


# ═══════════════════════════════════════════════════════════════════════════
# NTWMS33 — Simulateur de capacité entrepôt (what-if)
# ═══════════════════════════════════════════════════════════════════════════

def simuler_capacite(company, *, zone, quantite_supplementaire=0,
                     produit_id=None, emplacement_id=None):
    """Projette le taux de remplissage d'une ZONE si on y ajoutait
    ``quantite_supplementaire`` unités (typiquement une grosse réception
    fournisseur à venir).

    LECTURE SEULE — aucune réservation, aucun mouvement : c'est un what-if
    destiné à décider OÙ stocker avant que la marchandise n'arrive.

    Renvoie ``{zone, capacite, occupe_actuel, taux_actuel_pct, quantite_ajoutee,
    occupe_projete, taux_projete_pct, depassement, unites_en_trop}``.
    ``capacite``/``taux_*`` valent ``None`` quand aucun casier de la zone ne
    déclare de capacité (``CategorieStockage.qte_max``) : sans capacité connue
    il n'y a pas de dépassement possible à annoncer.
    """
    zone_cle = (zone or '').strip()
    if not zone_cle:
        raise ValueError('La zone est obligatoire.')
    try:
        ajout = int(quantite_supplementaire or 0)
    except (TypeError, ValueError):
        raise ValueError('Quantité supplémentaire invalide.')
    if ajout < 0:
        raise ValueError('La quantité supplémentaire ne peut pas être négative.')

    lignes = remplissage_par_zone(company, emplacement_id=emplacement_id)
    courante = next((z for z in lignes if z['zone'] == zone_cle), None)
    if courante is None:
        raise ValueError(f'Zone « {zone_cle} » introuvable dans cette société.')

    capacite = courante['capacite']
    occupe = courante['occupe']
    projete = occupe + ajout
    taux_projete = _pct(projete, capacite) if capacite else None
    depassement = bool(capacite) and projete > capacite
    return {
        'zone': zone_cle,
        'produit': produit_id,
        'capacite': capacite,
        'occupe_actuel': occupe,
        'taux_actuel_pct': courante['taux_pct'],
        'quantite_ajoutee': ajout,
        'occupe_projete': projete,
        'taux_projete_pct': _fmt_dec(taux_projete) if taux_projete is not None else None,
        'depassement': depassement,
        'unites_en_trop': max(projete - capacite, 0) if capacite else 0,
        'avertissement': (
            f'La zone {zone_cle} dépasserait sa capacité de '
            f'{projete - capacite} unité(s).' if depassement else ''),
    }


# ═══════════════════════════════════════════════════════════════════════════
# NTWMS42 — Alerte PASSIVE de sur-stockage par zone
# ═══════════════════════════════════════════════════════════════════════════

def zones_en_surcapacite(company, *, seuil_pct=None, emplacement_id=None):
    """Zones dont le taux de remplissage franchit ``seuil_pct`` (défaut 95 %).

    Complément PASSIF de ``simuler_capacite`` : ici personne ne demande, on
    constate. Une zone sans capacité déclarée n'est jamais signalée."""
    seuil = _dec(seuil_pct) if seuil_pct is not None else SEUIL_SURCAPACITE_PCT
    if seuil <= 0:
        seuil = SEUIL_SURCAPACITE_PCT
    alertes = []
    for z in remplissage_par_zone(company, emplacement_id=emplacement_id):
        if z['taux_pct'] is None:
            continue
        if _dec(z['taux_pct']) >= seuil:
            alertes.append({**z, 'seuil_pct': _fmt_dec(seuil)})
    return alertes


# ═══════════════════════════════════════════════════════════════════════════
# NTWMS29 — Tableau de bord entrepôt (cockpit WMS)
# ═══════════════════════════════════════════════════════════════════════════

def cockpit_entrepot(company, *, maintenant=None,
                     horizon_peremption_jours=HORIZON_PEREMPTION_JOURS,
                     retard_vague_heures=RETARD_VAGUE_HEURES,
                     emplacement_id=None):
    """Agrégat LECTURE SEULE de l'écran ``/stock/entrepot``.

    Cinq blocs, un par question que se pose un responsable d'entrepôt le matin :
    remplissage par zone, vagues de prélèvement en cours (et EN RETARD),
    comptages tournants dus, expéditions du jour par transporteur, lots proches
    de la péremption (FEFO). L'horloge est INJECTABLE (``maintenant``) : ce
    sélecteur ne lit jamais l'heure quand l'appelant la fournit.
    """
    import datetime

    from .models import LotEntrepot
    from .models_wms import (
        ExpeditionTransporteur, PlanComptageTournant, VaguePicking,
    )

    maintenant = maintenant or timezone.now()
    aujourdhui = timezone.localdate(maintenant)
    limite_retard = maintenant - datetime.timedelta(
        hours=int(retard_vague_heures or 0))

    # ── 1. Remplissage par zone ────────────────────────────────────────────
    zones = remplissage_par_zone(company, emplacement_id=emplacement_id)

    # ── 2. Vagues de prélèvement en cours + retard ────────────────────────
    vagues = (VaguePicking.objects
              .filter(company=company, statut=VaguePicking.Statut.LANCEE)
              .prefetch_related('lignes')
              .order_by('date_lancement', 'id'))
    vagues_data, vagues_retard = [], 0
    for vague in vagues:
        lignes = list(vague.lignes.all())
        demande = sum(int(li.quantite_demandee or 0) for li in lignes)
        preleve = sum(int(li.quantite_prelevee or 0) for li in lignes)
        en_retard = bool(vague.date_lancement
                         and vague.date_lancement < limite_retard)
        if en_retard:
            vagues_retard += 1
        vagues_data.append({
            'id': vague.id,
            'reference': vague.reference,
            'date_lancement': (vague.date_lancement.isoformat()
                               if vague.date_lancement else None),
            'lignes': len(lignes),
            'quantite_demandee': demande,
            'quantite_prelevee': preleve,
            'reste_a_prelever': max(demande - preleve, 0),
            'en_retard': en_retard,
        })

    # ── 3. Comptages tournants DUS ────────────────────────────────────────
    comptages = []
    for plan in (PlanComptageTournant.objects
                 .filter(company=company, actif=True)
                 .order_by('classe_abc')):
        if plan.est_du(aujourdhui):
            comptages.append({
                'id': plan.id,
                'classe_abc': plan.classe_abc,
                'frequence_jours': plan.frequence_jours,
                'date_dernier_comptage': (
                    plan.date_dernier_comptage.isoformat()
                    if plan.date_dernier_comptage else None),
            })

    # ── 4. Expéditions du jour, par transporteur ──────────────────────────
    expeditions = (ExpeditionTransporteur.objects
                   .filter(company=company,
                           date_expedition__date=aujourdhui)
                   .exclude(statut=ExpeditionTransporteur.Statut.ANNULE))
    par_transporteur = {}
    for exp in expeditions:
        cle = exp.transporteur_provider or 'aucun'
        agg = par_transporteur.setdefault(
            cle, {'transporteur': cle, 'nb': 0, 'cout_total': Decimal('0')})
        agg['nb'] += 1
        agg['cout_total'] += _dec(exp.cout_reel)
    expeditions_data = [
        {'transporteur': a['transporteur'], 'nb': a['nb'],
         'cout_total': _fmt_dec(a['cout_total'])}
        for a in sorted(par_transporteur.values(),
                        key=lambda a: a['transporteur'])
    ]

    # ── 5. Lots proches de la péremption (FEFO) ───────────────────────────
    horizon = aujourdhui + datetime.timedelta(
        days=int(horizon_peremption_jours or 0))
    lots = (LotEntrepot.objects
            .filter(company=company, quantite_restante__gt=0,
                    date_peremption__isnull=False,
                    date_peremption__lte=horizon)
            .select_related('produit')
            .order_by('date_peremption', 'id'))
    lots_data = [{
        'id': lot.id,
        'numero_lot': lot.numero_lot,
        'produit': lot.produit_id,
        'produit_nom': getattr(lot.produit, 'nom', ''),
        'date_peremption': lot.date_peremption.isoformat(),
        'jours_restants': (lot.date_peremption - aujourdhui).days,
        'quantite_restante': lot.quantite_restante,
        'perime': lot.date_peremption < aujourdhui,
    } for lot in lots]

    return {
        'date': aujourdhui.isoformat(),
        'zones': zones,
        'zones_en_surcapacite': zones_en_surcapacite(
            company, emplacement_id=emplacement_id),
        'vagues': vagues_data,
        'vagues_en_retard': vagues_retard,
        'comptages_dus': comptages,
        'expeditions_du_jour': expeditions_data,
        'lots_peremption': lots_data,
        'horizon_peremption_jours': int(horizon_peremption_jours or 0),
    }


# ═══════════════════════════════════════════════════════════════════════════
# NTWMS36 — Interleaving : après un rangement, la tâche de prélèvement la plus
# proche du trajet retour (au lieu d'un aller-retour à vide)
# ═══════════════════════════════════════════════════════════════════════════

def suggerer_tache_retour(company, *, zone_courante, operateur=None,
                          limite=1):
    """Ligne(s) de prélèvement (NTWMS4) à faire sur le TRAJET RETOUR.

    Le magasinier vient de ranger un produit en zone C : plutôt que de le
    renvoyer au quai de réception à vide, on lui propose la ligne de
    prélèvement en attente la plus proche — d'abord la MÊME zone, puis, à
    défaut, la zone la plus proche par ordre de parcours décroissant (on
    revient vers la sortie, jamais on repart au fond).

    LECTURE SEULE : rien n'est réservé ni assigné ici — le poste scanner
    affiche la suggestion, l'opérateur confirme via l'action de prélèvement
    existante. ``operateur`` n'est utilisé que pour la traçabilité de l'appel
    (aucun filtre : une vague n'est pas nominative aujourd'hui).
    """
    from .models_wms import LignePicking, VaguePicking

    zone_cle = (zone_courante or '').strip()
    try:
        limite = max(1, int(limite or 1))
    except (TypeError, ValueError):
        limite = 1

    lignes = (LignePicking.objects
              .filter(company=company,
                      vague__statut=VaguePicking.Statut.LANCEE,
                      quantite_prelevee__lt=F('quantite_demandee'))
              .select_related('produit', 'bin', 'vague')
              .order_by('ordre_parcours', 'id'))

    memes_zones, autres = [], []
    for ligne in lignes:
        zone_ligne = (getattr(ligne.bin, 'zone', '') or '').strip()
        cible = memes_zones if (zone_cle and zone_ligne == zone_cle) else autres
        cible.append(ligne)

    # Trajet RETOUR : à défaut de la même zone, on redescend vers la sortie
    # (ordre de parcours DÉCROISSANT = du fond vers le quai).
    autres.sort(key=lambda li: -(getattr(li.bin, 'ordre', 0) or 0))
    retenues = (memes_zones + autres)[:limite]

    return [{
        'ligne_id': ligne.id,
        'vague_id': ligne.vague_id,
        'vague_reference': ligne.vague.reference,
        'produit': ligne.produit_id,
        'produit_nom': getattr(ligne.produit, 'nom', ''),
        'bin': ligne.bin_id,
        'bin_code': getattr(ligne.bin, 'code', ''),
        'zone': (getattr(ligne.bin, 'zone', '') or ''),
        'meme_zone': bool(zone_cle
                          and (getattr(ligne.bin, 'zone', '') or '').strip()
                          == zone_cle),
        'quantite_restante': ligne.reste_a_prelever,
        'ordre_parcours': ligne.ordre_parcours,
    } for ligne in retenues]
