"""Sélecteurs (lecture seule) de l'app `mrp` (Groupe NTMFG)."""
from datetime import timedelta
from decimal import ROUND_CEILING, Decimal

from django.db.models import Sum
from django.utils import timezone as dj_timezone

from .services import temps_operation_min


def _dec(value):
    try:
        return Decimal(str(value))
    except Exception:  # noqa: BLE001 — valeur non numérique -> 0, jamais de crash.
        return Decimal('0')


def _fmt_dec(value):
    """Chaîne décimale normalisée, sans zéros de fin parasites (`'15.00'` ->
    `'15'`, mais `'12.50'` -> `'12.5'`). L'arithmétique `Decimal` hérite de
    l'échelle de ses opérandes (ex. `Produit.quantite_stock` — IntegerField,
    scale 0 — combiné à `KitComposant.quantite`/`OrdreFabrication.quantite` —
    DecimalField(2) — dans une même soustraction), donc un `str()` brut sur le
    résultat produit un format incohérent selon le chemin de calcul emprunté
    (`'15.00'` vs `'15'` pour la même grandeur logique). `format(value, 'f')`
    évite la notation scientifique qu'introduirait `Decimal.normalize()` sur
    un entier rond (ex. `Decimal('20').normalize()` -> `Decimal('2E+1')`)."""
    value = value if isinstance(value, Decimal) else _dec(value)
    if value == 0:
        return '0'
    s = format(value, 'f')
    if '.' in s:
        s = s.rstrip('0').rstrip('.')
    return s or '0'


# ── NTMFG5 — Calcul des besoins nets (MRP) multi-produits sur horizon ────
#
# Le réappro existant (FG54/62/65/326/364) réagit produit par produit sous un
# seuil statique ; ce calcul agrège la demande DÉPENDANTE (nomenclature d'un
# produit fabriqué, explosée récursivement sur 2 niveaux via
# `stock.services.exploser_kit_par_id`, ID-only, jamais d'import de modèle
# `stock`) + la demande INDÉPENDANTE (devis signés / prévisions) contre le
# stock disponible + les OF déjà planifiés produisant ce composant.
#
# La demande indépendante n'a AUCUN sélecteur cross-app existant qui
# l'agrège proprement par produit (ni `ventes.selectors`, ni
# `installations.selectors` n'exposent une telle vue) : elle est donc reçue
# en PARAMÈTRE explicite `demande_independante` ({produit_id: quantité}),
# fourni par l'appelant (ex. une synthèse construite côté `ventes`/CRM pour
# les devis signés non livrés). C'est un point de branchement documenté,
# pas une intégration inventée.

def calculer_besoins_nets(company, *, produits=None, demande_independante=None,
                          stock_securite_pct=Decimal('0'), horizon_jours=None,
                          today=None):
    """NTMFG5 — besoin net par produit = demande (indépendante + dépendante
    des nomenclatures, avec sécurité) − (stock disponible + OF planifiés
    produisant ce composant), borné à >= 0.

    `produits` : liste explicite de produit_id à évaluer (défaut : tous les
    produits ayant une `Gamme` active de cette société).
    `demande_independante` : {produit_id: quantité} — devis signés/prévisions
    (voir note ci-dessus).
    `stock_securite_pct` : % de la demande ajouté en stock de sécurité.
    `horizon_jours` : si fourni, une date de besoin = aujourd'hui + horizon
    est calculée pour chaque produit en rupture.

    Renvoie une liste de dicts triés par désignation :
      {produit_id, produit_nom, sku, demande, stock_disponible,
       en_cours_fabrication, stock_securite, besoin_net,
       proposition ('fabriquer'|'acheter'|None), date_besoin}.
    Un produit dont le besoin net est nul n'est PAS en rupture mais reste
    listé (proposition=None) pour visibilité — l'appelant filtre s'il ne
    veut que les ruptures (`besoin_net` != '0')."""
    from apps.stock.selectors import get_produit_scoped
    from apps.stock.services import available_quantity, exploser_kit_par_id

    from .models import Gamme, OrdreFabrication

    today = today or dj_timezone.localdate()
    demande_totale = {
        int(k): _dec(v) for k, v in (demande_independante or {}).items()}
    stock_securite_pct = _dec(stock_securite_pct)

    if produits is None:
        cible = list(
            Gamme.objects.filter(company=company, actif=True)
            .values_list('produit_id', flat=True).distinct())
    else:
        cible = [int(p) for p in produits]

    resultats = {}

    def _traiter(produit_id):
        if produit_id in resultats:
            return
        produit_obj = get_produit_scoped(company, produit_id)
        if produit_obj is None:
            return
        stock_dispo = _dec(available_quantity(produit_obj))
        en_cours_statuts = [
            OrdreFabrication.Statut.PLANIFIE, OrdreFabrication.Statut.LANCE]
        # NTMFG16 — un OF prototype (première pièce bonne, hors production
        # normale) n'entre JAMAIS dans le besoin net agrégé.
        en_cours = _dec(
            OrdreFabrication.objects.filter(
                company=company, produit_id=produit_id,
                statut__in=en_cours_statuts, est_prototype=False,
            ).aggregate(total=Sum('quantite'))['total'] or 0)
        demande = demande_totale.get(produit_id, Decimal('0'))
        securite = (
            demande * stock_securite_pct / Decimal('100')
            if stock_securite_pct else Decimal('0'))
        besoin_brut = demande + securite
        besoin_net = max(besoin_brut - stock_dispo - en_cours, Decimal('0'))
        gamme = (Gamme.objects.filter(
                    company=company, produit_id=produit_id, actif=True)
                 .order_by('-version').first())
        date_besoin = None
        proposition = None
        if besoin_net > 0:
            proposition = 'fabriquer' if gamme is not None else 'acheter'
            if horizon_jours is not None:
                date_besoin = today + timedelta(days=int(horizon_jours))

        resultats[produit_id] = {
            'produit_id': produit_id,
            'produit_nom': produit_obj.nom,
            'sku': produit_obj.sku or '',
            'demande': _fmt_dec(demande),
            'stock_disponible': _fmt_dec(stock_dispo),
            'en_cours_fabrication': _fmt_dec(en_cours),
            'stock_securite': _fmt_dec(securite),
            'besoin_net': _fmt_dec(besoin_net),
            'proposition': proposition,
            'date_besoin': date_besoin.isoformat() if date_besoin else None,
        }

        # 2e niveau — un besoin net à FABRIQUER explose la nomenclature de sa
        # gamme (si elle en a une) et ajoute la demande dépendante des
        # composants, traités dans la passe suivante.
        if besoin_net > 0 and gamme is not None and gamme.kit_source_id:
            lignes = exploser_kit_par_id(
                company, gamme.kit_source_id, besoin_net) or []
            for ligne in lignes:
                cid = ligne['produit_id']
                demande_totale[cid] = (
                    demande_totale.get(cid, Decimal('0')) + _dec(ligne['quantite']))

    for produit_id in cible:
        _traiter(produit_id)
    # Composants découverts par explosion (2e niveau) mais absents de la
    # liste cible initiale — traités dans une seconde passe.
    for produit_id in list(demande_totale.keys()):
        _traiter(produit_id)

    return sorted(resultats.values(), key=lambda r: r['produit_nom'].lower())


# ── NTMFG6 — dispo par ligne de réservation d'un OF ──────────────────────

def disponibilite_par_ligne_of(of):
    """NTMFG6 — pour chaque `ReservationOF` de cet OF, la disponibilité
    courante du produit réservé (statut disponible/partiel/manquant).
    Lecture seule, ne modifie aucune réservation."""
    from apps.stock.selectors import get_produit_scoped
    from apps.stock.services import available_quantity

    lignes = []
    for reservation in of.reservations.select_related('produit').all():
        produit_obj = reservation.produit or get_produit_scoped(
            of.company, reservation.produit_id)
        if produit_obj is None:
            continue
        dispo = _dec(available_quantity(produit_obj))
        quantite = _dec(reservation.quantite)
        if dispo <= 0:
            statut = 'manquant'
        elif dispo >= quantite:
            statut = 'disponible'
        else:
            statut = 'partiel'
        lignes.append({
            'reservation_id': reservation.id,
            'produit_id': produit_obj.id,
            'produit_nom': produit_obj.nom,
            'quantite_reservee': str(quantite),
            'disponible': str(dispo),
            'consomme': reservation.consomme,
            'statut': statut,
        })
    return lignes


# ── NTMFG7 — Ordonnancement à capacité finie : Gantt de charge inter-ordres ─

_STATUTS_EN_CHARGE = ('planifie', 'lance')


def charge_postes(company, debut, fin):
    """NTMFG7 — charge (minutes prévues) par poste de charge et par jour,
    sur la fenêtre [`debut`, `fin`] (inclus, `datetime.date`), pour toutes
    les `OperationOF` planifiées d'OF `planifie`/`lance`. Le temps prévu est
    TOUJOURS recalculé depuis `operation_gamme` × la quantité de l'OF (jamais
    lu sur `temps_reel_min`, réservé au réalisé — NTMFG8) — cohérent même si
    l'opération n'a pas encore démarré. Renvoie une liste triée par poste
    puis par jour :
      [{poste_id, poste_nom, jour, minutes_planifiees, capacite_minutes,
        taux_charge_pct, surcharge, alerte_maintenance}].

    `alerte_maintenance` (NTMFG14) — badge NON BLOQUANT : vrai si ce poste a
    au moins une échéance d'entretien `a_faire` en retard, indépendamment de
    la charge planifiée elle-même."""
    from .models import OperationOF

    operations = (
        OperationOF.objects
        .filter(
            poste_charge__company=company,
            date_planifiee__gte=debut, date_planifiee__lte=fin,
            ordre_fabrication__statut__in=_STATUTS_EN_CHARGE)
        .select_related('poste_charge', 'operation_gamme', 'ordre_fabrication'))

    charge = {}  # (poste_id, jour) -> minutes.
    postes_vus = {}
    for op in operations:
        temps = (temps_operation_min(op.operation_gamme, op.ordre_fabrication.quantite)
                 if op.operation_gamme_id else Decimal('0'))
        cle = (op.poste_charge_id, op.date_planifiee)
        charge[cle] = charge.get(cle, Decimal('0')) + temps
        postes_vus[op.poste_charge_id] = op.poste_charge

    postes_en_alerte = postes_en_alerte_maintenance(company)
    resultats = []
    for (poste_id, jour), minutes in charge.items():
        poste = postes_vus[poste_id]
        capacite_min = _dec(poste.capacite_heures_jour) * 60
        taux = (
            (minutes / capacite_min * 100) if capacite_min > 0 else Decimal('0'))
        resultats.append({
            'poste_id': poste_id,
            'poste_nom': poste.nom,
            'jour': jour.isoformat(),
            'minutes_planifiees': _fmt_dec(minutes),
            'capacite_minutes': _fmt_dec(capacite_min),
            'taux_charge_pct': str(taux.quantize(Decimal('0.1'))),
            'surcharge': minutes > capacite_min,
            'alerte_maintenance': poste_id in postes_en_alerte,
        })
    resultats.sort(key=lambda r: (r['poste_nom'].lower(), r['jour']))
    return resultats


# ── NTMFG14 — Alerte maintenance de poste (Gantt + terminal) ─────────────

def postes_en_alerte_maintenance(company, today=None):
    """NTMFG14 — ensemble des `poste_charge_id` de `company` portant AU
    MOINS une `EcheanceEntretienPoste` `a_faire` dont `date_prevue` est
    dépassée. Lecture seule, utilisée pour le badge non bloquant du Gantt
    (NTMFG7) et l'avertissement du terminal atelier (NTMFG8)."""
    from .models import EcheanceEntretienPoste

    today = today or dj_timezone.localdate()
    return set(
        EcheanceEntretienPoste.objects.filter(
            plan__poste_charge__company=company,
            statut=EcheanceEntretienPoste.Statut.A_FAIRE,
            date_prevue__lt=today,
        ).values_list('plan__poste_charge_id', flat=True))


# ── NTMFG11 — Coût de revient standard vs réel ────────────────────────────

def cout_standard_courant(company, produit_id):
    """NTMFG11 — dernière version FIGÉE du coût standard d'un produit (la
    plus récente par version), ou `None`. Lecture seule."""
    from .models import CoutStandard

    return (CoutStandard.objects
            .filter(company=company, produit_id=produit_id)
            .order_by('-version').first())


def _cout_reel_of(of):
    """Coût matière RÉEL de cet OF (basé sur ce qui a réellement été
    consommé par le backflush NTMFG4 — `of.quantite`, la même base que
    `services._composants_of`) + coût main-d'œuvre RÉEL (Σ temps réel ×
    coût horaire poste, opérations terminées)."""
    from apps.stock.selectors import get_produit_scoped
    from apps.stock.services import cout_achat_courant, exploser_kit_par_id

    cout_matiere = Decimal('0')
    if of.gamme_id and of.gamme.kit_source_id:
        lignes = exploser_kit_par_id(
            of.company_id, of.gamme.kit_source_id, of.quantite) or []
        for ligne in lignes:
            produit = get_produit_scoped(of.company_id, ligne['produit_id'])
            if produit is None:
                continue
            prix = cout_achat_courant(produit) or Decimal('0')
            cout_matiere += _dec(prix) * _dec(ligne['quantite'])

    cout_mo = Decimal('0')
    quantite_bonne = Decimal('0')
    for op in of.operations.filter(statut='terminee').select_related('poste_charge'):
        cout_mo += (_dec(op.temps_reel_min) / Decimal('60')) * _dec(op.poste_charge.cout_horaire)
        quantite_bonne += _dec(op.quantite_bonne)
    if quantite_bonne == 0:
        quantite_bonne = _dec(of.quantite)
    return cout_matiere, cout_mo, quantite_bonne


def analyse_couts(company, *, produit_id=None, date_debut=None, date_fin=None):
    """NTMFG11 — rapport d'écarts (Σ des OF TERMINÉS de la période) vs le
    coût standard COURANT, décomposé matière/main-d'œuvre/rendement, groupé
    par produit. `updated_at` sert de proxy de date de clôture (l'OF ne
    porte pas de champ `date_terminee` dédié). STRICTEMENT INTERNE."""
    from .models import OrdreFabrication

    # NTMFG16 — un OF prototype (première pièce bonne) n'entre jamais dans
    # l'analyse d'écarts vs coût standard de production normale.
    qs = (OrdreFabrication.objects
          .filter(company=company, statut=OrdreFabrication.Statut.TERMINE,
                  est_prototype=False)
          .select_related('produit', 'gamme'))
    if produit_id:
        qs = qs.filter(produit_id=produit_id)
    if date_debut:
        qs = qs.filter(updated_at__date__gte=date_debut)
    if date_fin:
        qs = qs.filter(updated_at__date__lte=date_fin)

    par_produit = {}
    for of in qs:
        standard = cout_standard_courant(company, of.produit_id)
        if standard is None:
            continue
        cout_matiere_reel, cout_mo_reel, quantite_bonne = _cout_reel_of(of)
        cout_matiere_std = standard.cout_matiere * _dec(of.quantite)
        cout_mo_std = standard.cout_main_oeuvre * _dec(of.quantite)
        ecart_rendement = (
            (quantite_bonne - _dec(of.quantite)) * standard.cout_unitaire_total)

        entry = par_produit.setdefault(of.produit_id, {
            'produit_id': of.produit_id,
            'produit_nom': of.produit.nom,
            'nb_of': 0,
            'cout_matiere_standard': Decimal('0'),
            'cout_matiere_reel': Decimal('0'),
            'cout_main_oeuvre_standard': Decimal('0'),
            'cout_main_oeuvre_reel': Decimal('0'),
            'ecart_rendement': Decimal('0'),
        })
        entry['nb_of'] += 1
        entry['cout_matiere_standard'] += cout_matiere_std
        entry['cout_matiere_reel'] += cout_matiere_reel
        entry['cout_main_oeuvre_standard'] += cout_mo_std
        entry['cout_main_oeuvre_reel'] += cout_mo_reel
        entry['ecart_rendement'] += ecart_rendement

    resultats = []
    for entry in par_produit.values():
        ecart_matiere = entry['cout_matiere_reel'] - entry['cout_matiere_standard']
        ecart_mo = entry['cout_main_oeuvre_reel'] - entry['cout_main_oeuvre_standard']
        resultats.append({
            'produit_id': entry['produit_id'],
            'produit_nom': entry['produit_nom'],
            'nb_of': entry['nb_of'],
            'cout_matiere_standard': str(entry['cout_matiere_standard']),
            'cout_matiere_reel': str(entry['cout_matiere_reel']),
            'ecart_matiere': str(ecart_matiere),
            'cout_main_oeuvre_standard': str(entry['cout_main_oeuvre_standard']),
            'cout_main_oeuvre_reel': str(entry['cout_main_oeuvre_reel']),
            'ecart_main_oeuvre': str(ecart_mo),
            'ecart_rendement': str(entry['ecart_rendement']),
            'ecart_total': str(ecart_matiere + ecart_mo + entry['ecart_rendement']),
        })
    resultats.sort(key=lambda r: r['produit_nom'].lower())
    return resultats


# ── NTMFG12 — TRS/OEE par poste de charge ─────────────────────────────────

def _jours_ouvres_fenetre(debut, fin):
    """Nombre de jours ouvrés (lun-ven) entre `debut` et `fin` inclus."""
    if fin < debut:
        return 0
    return sum(
        1 for i in range((fin - debut).days + 1)
        if (debut + timedelta(days=i)).weekday() < 5) or 0


def _operations_terminees_poste(poste, debut, fin):
    """NTMFG16 — un OF prototype (première pièce bonne) est EXCLU du calcul
    TRS/OEE de production normale (mais reste soumis au même contrôle
    qualité — NTMFG13 hors périmètre de ce lot)."""
    from .models import OperationOF

    return (OperationOF.objects
            .filter(
                poste_charge=poste, statut='terminee',
                terminee_le__date__gte=debut, terminee_le__date__lte=fin,
                ordre_fabrication__est_prototype=False)
            .select_related('operation_gamme', 'ordre_fabrication'))


def _oee_composants(operations):
    """Calcule les 3 facteurs OEE bruts (avant produit) sur un jeu
    d'opérations déjà filtré. Renvoie un dict — jamais de division par zéro
    (dénominateur nul => facteur 0, `donnees=False`)."""
    temps_actif = Decimal('0')
    temps_standard_theorique = Decimal('0')
    quantite_bonne = Decimal('0')
    quantite_rebut = Decimal('0')
    for op in operations:
        temps_actif += _dec(op.temps_reel_min)
        quantite_bonne += _dec(op.quantite_bonne)
        quantite_rebut += _dec(op.quantite_rebut)
        if op.operation_gamme_id:
            temps_standard_theorique += temps_operation_min(
                op.operation_gamme, op.quantite_bonne)

    return {
        'temps_actif_min': temps_actif,
        'temps_standard_theorique_min': temps_standard_theorique,
        'quantite_bonne': quantite_bonne,
        'quantite_rebut': quantite_rebut,
    }


def oee_poste(company, poste_id, debut, fin):
    """NTMFG12 — TRS/OEE (disponibilité × performance × qualité) d'un poste
    sur [`debut`, `fin`] (dates incluses) :
      * disponibilité = temps actif (NTMFG8, pauses exclues) ÷ temps planifié
        de capacité (`capacite_heures_jour` × jours ouvrés de la fenêtre) ;
      * performance = temps standard théorique (gamme × quantité BONNE) ÷
        temps réel ;
      * qualité = quantité bonne ÷ (bonne + rebut).
    Renvoie `None` si le poste est introuvable pour cette société. Sans
    aucune opération terminée sur la fenêtre, les 3 facteurs et le TRS
    valent 0 (`donnees=False`, jamais de division par zéro)."""
    from .models import PosteDeCharge

    poste = PosteDeCharge.objects.filter(id=poste_id, company=company).first()
    if poste is None:
        return None

    operations = list(_operations_terminees_poste(poste, debut, fin))
    comp = _oee_composants(operations)

    jours_ouvres = _jours_ouvres_fenetre(debut, fin)
    capacite_min = _dec(poste.capacite_heures_jour) * 60 * jours_ouvres

    disponibilite = (
        min(comp['temps_actif_min'] / capacite_min, Decimal('1'))
        if capacite_min > 0 else Decimal('0'))
    performance = (
        min(comp['temps_standard_theorique_min'] / comp['temps_actif_min'], Decimal('2'))
        if comp['temps_actif_min'] > 0 else Decimal('0'))
    total_qte = comp['quantite_bonne'] + comp['quantite_rebut']
    qualite = (comp['quantite_bonne'] / total_qte) if total_qte > 0 else Decimal('0')
    trs = disponibilite * performance * qualite

    return {
        'poste_id': poste.id,
        'poste_nom': poste.nom,
        'debut': debut.isoformat(),
        'fin': fin.isoformat(),
        'donnees': bool(operations),
        'nb_operations': len(operations),
        'disponibilite_pct': str((disponibilite * 100).quantize(Decimal('0.1'))),
        'performance_pct': str((performance * 100).quantize(Decimal('0.1'))),
        'qualite_pct': str((qualite * 100).quantize(Decimal('0.1'))),
        'trs_pct': str((trs * 100).quantize(Decimal('0.1'))),
    }


def oee_tendance_hebdomadaire(company, poste_id, debut, fin):
    """NTMFG12 — TRS du poste PAR SEMAINE ISO sur [`debut`, `fin`] (tendance).
    Une semaine sans opération terminée n'apparaît pas dans le résultat."""
    from .models import PosteDeCharge

    poste = PosteDeCharge.objects.filter(id=poste_id, company=company).first()
    if poste is None:
        return []

    operations = list(_operations_terminees_poste(poste, debut, fin))
    par_semaine = {}
    for op in operations:
        annee, semaine, _ = op.terminee_le.isocalendar()
        par_semaine.setdefault((annee, semaine), []).append(op)

    resultats = []
    for (annee, semaine), ops in sorted(par_semaine.items()):
        comp = _oee_composants(ops)
        capacite_min = _dec(poste.capacite_heures_jour) * 60 * 5  # 1 semaine ouvrée.
        disponibilite = (
            min(comp['temps_actif_min'] / capacite_min, Decimal('1'))
            if capacite_min > 0 else Decimal('0'))
        performance = (
            min(comp['temps_standard_theorique_min'] / comp['temps_actif_min'], Decimal('2'))
            if comp['temps_actif_min'] > 0 else Decimal('0'))
        total_qte = comp['quantite_bonne'] + comp['quantite_rebut']
        qualite = (comp['quantite_bonne'] / total_qte) if total_qte > 0 else Decimal('0')
        trs = disponibilite * performance * qualite
        resultats.append({
            'annee': annee,
            'semaine': semaine,
            'trs_pct': str((trs * 100).quantize(Decimal('0.1'))),
        })
    return resultats


# ── NTMFG18 — Simulation « et si » de charge (AUCUNE écriture) ───────────

def simuler_charge(company, lignes, *, date_souhaitee=None):
    """NTMFG18 — charge ADDITIONNELLE par poste qu'induirait la fabrication
    de `lignes` (``[{produit_id, quantite}, ...]``) au-delà de la charge
    déjà planifiée (NTMFG7), sur le jour `date_souhaitee` (défaut
    aujourd'hui). AUCUNE écriture — pur calcul.

    Renvoie ``{tenable, poste_goulot, retard_jours, lignes: [...]}`` où
    `tenable` vaut :
      * ``'sans_gamme'`` — aucun produit de la demande n'a de gamme active
        (ex. devis 100% négoce) : no-op pour l'appelant ;
      * ``'tenable'`` — la charge additionnelle tient dans la capacité
        disponible du jour ;
      * ``'tenable_avec_retard'`` — dépassement absorbable en décalant de
        `retard_jours` jour(s) (poste identifié par `poste_goulot`) ;
      * ``'non_tenable'`` — un poste requis a une capacité NULLE (jamais
        absorbable par un simple décalage)."""
    from .models import Gamme

    date_souhaitee = date_souhaitee or dj_timezone.localdate()
    charge_additionnelle = {}  # poste_id -> minutes additionnelles.
    postes_vus = {}
    produits_avec_gamme = 0

    for ligne in (lignes or []):
        produit_id = ligne.get('produit_id')
        quantite = _dec(ligne.get('quantite') or 0)
        if not produit_id or quantite <= 0:
            continue
        gamme = (
            Gamme.objects.filter(
                company=company, produit_id=produit_id, actif=True)
            .order_by('-version').first())
        if gamme is None:
            continue
        produits_avec_gamme += 1
        for operation in gamme.operations.select_related('poste_charge').all():
            temps = temps_operation_min(operation, quantite)
            poste = operation.poste_charge
            charge_additionnelle[poste.id] = (
                charge_additionnelle.get(poste.id, Decimal('0')) + temps)
            postes_vus[poste.id] = poste

    if produits_avec_gamme == 0:
        return {
            'tenable': 'sans_gamme', 'poste_goulot': None, 'retard_jours': 0,
            'lignes': [],
        }

    existante = charge_postes(company, date_souhaitee, date_souhaitee)
    existante_par_poste = {
        r['poste_id']: _dec(r['minutes_planifiees']) for r in existante}

    resultats = []
    goulot = None
    pire_retard = 0
    non_tenable = False
    for poste_id, minutes_add in charge_additionnelle.items():
        poste = postes_vus[poste_id]
        capacite_min = _dec(poste.capacite_heures_jour) * 60
        deja = existante_par_poste.get(poste_id, Decimal('0'))
        total = deja + minutes_add
        depasse = capacite_min <= 0 or total > capacite_min
        retard_jours = None
        if capacite_min > 0:
            if total > capacite_min:
                retard_jours = int(
                    (total / capacite_min).to_integral_value(rounding=ROUND_CEILING)) - 1
                retard_jours = max(retard_jours, 1)
            else:
                retard_jours = 0
        resultats.append({
            'poste_id': poste_id,
            'poste_nom': poste.nom,
            'minutes_additionnelles': _fmt_dec(minutes_add),
            'minutes_deja_planifiees': _fmt_dec(deja),
            'capacite_minutes': _fmt_dec(capacite_min),
            'depasse': depasse,
        })
        if depasse:
            if retard_jours is None:
                non_tenable = True
                if goulot is None:
                    goulot = poste.nom
            elif retard_jours > pire_retard:
                pire_retard = retard_jours
                goulot = poste.nom

    if non_tenable:
        verdict = 'non_tenable'
    elif pire_retard > 0:
        verdict = 'tenable_avec_retard'
    else:
        verdict = 'tenable'

    resultats.sort(key=lambda r: r['poste_nom'].lower())
    return {
        'tenable': verdict,
        'poste_goulot': goulot,
        'retard_jours': pire_retard,
        'lignes': resultats,
    }


def oee_tous_postes(company, debut, fin):
    """NTMFG12 — TRS de TOUS les postes actifs de la société sur la fenêtre
    (comparaison inter-postes), triés par TRS décroissant."""
    from .models import PosteDeCharge

    resultats = []
    for poste in PosteDeCharge.objects.filter(company=company, actif=True):
        resultats.append(oee_poste(company, poste.id, debut, fin))
    resultats.sort(key=lambda r: Decimal(r['trs_pct']), reverse=True)
    return resultats
