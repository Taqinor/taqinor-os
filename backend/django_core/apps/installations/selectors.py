"""Sélecteurs LECTURE SEULE du domaine Installations exposés aux AUTRES apps.

Point d'entrée cross-app : les autres apps lisent les chantiers / interventions /
réservations de stock à travers ces fonctions plutôt qu'en important
`apps.installations.models` directement (voir CLAUDE.md, règle de modularité).
Comportement strictement identique aux requêtes inline d'origine.
"""
from django.db.models import Sum


def installation_for_devis(devis):
    """Le chantier lié à un devis (ou None). Lecture seule."""
    from .models import Installation
    return Installation.objects.filter(devis=devis).first()


def installation_summaries_for_devis(devis_qs):
    """Map {devis_id: {id, reference, statut}} des chantiers liés à un lot de
    devis — une seule requête (évite un N+1 sur la fiche lead)."""
    from .models import Installation
    return {
        i.devis_id: {'id': i.id, 'reference': i.reference, 'statut': i.statut}
        for i in Installation.objects.filter(devis__in=devis_qs)
    }


def installation_scoped(company, pk):
    """Chantier (Installation) scopé société, par id, avec client préchargé."""
    from .models import Installation
    return (Installation.objects
            .filter(company=company, id=pk)
            .select_related('client')
            .first())


def installation_gps_map(installation_ids):
    """Map {installation_id: (gps_lat, gps_lng)} pour un lot de chantiers — une
    seule requête. Lecture seule, point d'entrée cross-app : les autres apps
    (ex. SAV, pour le tri de tournée par proximité) lisent le GPS du chantier à
    travers ce sélecteur plutôt qu'en important `installations.models`. Une
    coordonnée manquante reste à None (l'appelant la traite comme « sans GPS »).
    """
    from .models import Installation
    rows = (Installation.objects
            .filter(id__in=installation_ids)
            .values_list('id', 'gps_lat', 'gps_lng'))
    return {iid: (lat, lng) for iid, lat, lng in rows}


def installation_qs_for_remise():
    """Queryset Installation prêt pour la fiche de remise (relations préchargées).
    L'appelant applique son propre scope société puis filtre par pk."""
    from .models import Installation
    return (Installation.objects
            .select_related('client', 'devis', 'company',
                            'technicien_responsable')
            .prefetch_related('devis__lignes__produit'))


def intervention_scoped(company, pk):
    """Intervention scopée société, par id, avec chantier + client préchargés."""
    from .models import Intervention
    return (Intervention.objects
            .filter(company=company, id=pk)
            .select_related('installation', 'installation__client')
            .first())


def reserved_quantity_for_produit(produit):
    """Quantité d'un produit ENGAGÉE par des réservations de chantier actives et
    non encore consommées (0 si aucune). Lecture seule."""
    agg = (_active_reservations()
           .filter(produit=produit)
           .aggregate(total=Sum('quantite')))
    return agg['total'] or 0


def reserved_quantities_for_company(company):
    """Map {produit_id: quantité réservée active} pour toute la société — un seul
    agrégat (évite un N+1 sur la liste produits). Lecture seule."""
    rows = (_active_reservations()
            .filter(company=company)
            .values('produit_id')
            .annotate(total=Sum('quantite')))
    return {r['produit_id']: (r['total'] or 0) for r in rows}


def own_reservation_map(installation):
    """Map {produit_id: quantité} des réservations actives non consommées propres
    à CE chantier (pour ne pas les décompter de son propre disponible)."""
    rows = (_active_reservations()
            .filter(installation=installation)
            .values_list('produit_id', 'quantite'))
    return {pid: qte for pid, qte in rows}


def update_installation_lead(absorbed_lead, survivor_lead):
    """Réassigne les chantiers liés au lead absorbé vers le lead survivant (fusion
    de leads). Renvoie le nombre de chantiers réassignés."""
    from .models import Installation
    return Installation.objects.filter(lead=absorbed_lead).update(
        lead=survivor_lead)


def _active_reservations():
    from .models import StockReservation
    return StockReservation.objects.filter(active=True, consomme=False)


# ── FG294 — Budget projet vs réel (engagé / dépensé) ─────────────────────────
# Le sélecteur ci-dessous AGRÈGE le réel d'un budget de programme à partir de
# trois sources qui vivent dans D'AUTRES apps, sans JAMAIS importer leurs
# modèles (règle de modularité CLAUDE.md, contrat import-linter) :
#   * devis du programme (``ProjetDevis`` → ``ventes.Devis``) — montant contracté
#     CLIENT (HT/TTC), lu via ``apps.get_model('ventes', 'Devis')`` (lecture
#     ORM, aucune arête d'import au chargement) ;
#   * coûts fournisseur rattachés (``BudgetEngagement`` → BCF / facture
#     fournisseur) — engagé = montant commandé du BCF, dépensé = montant facturé,
#     lus via ``apps.stock.selectors`` (import LOCAL à la fonction) ;
#   * main-d'œuvre des chantiers du programme (``Installation.labour_*`` ×
#     ``tarif_jour_mo``), même app — FK directe.
# Toute donnée manquante DÉGRADE proprement (montant = 0) ; aucun statut n'est
# touché.

def _dec(value):
    from decimal import Decimal, InvalidOperation
    if value is None:
        return Decimal('0')
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal('0')


def _devis_totaux_programme(projet):
    """(Σ total HT, Σ total TTC) des devis rattachés au programme. Lu via
    ``apps.get_model`` — aucune arête d'import vers ``ventes`` au chargement. Un
    devis introuvable / illisible dégrade à 0."""
    from decimal import Decimal
    from django.apps import apps as django_apps
    devis_ids = list(projet.devis.values_list('devis_id', flat=True))
    if not devis_ids:
        return Decimal('0'), Decimal('0')
    devis_model = django_apps.get_model('ventes', 'Devis')
    total_ht = Decimal('0')
    total_ttc = Decimal('0')
    for devis in devis_model.objects.filter(id__in=devis_ids):
        try:
            total_ht += _dec(devis.total_ht)
            total_ttc += _dec(devis.total_ttc)
        except Exception:  # pragma: no cover - défensif
            continue
    return total_ht, total_ttc


def _engagements_fournisseur(budget, company):
    """Réel fournisseur d'un budget, ventilé par catégorie.

    Renvoie ``(engage_par_cat, depense_par_cat)`` — deux dicts
    {catégorie: Decimal}. Engagé = Σ montants COMMANDÉS des BCF rattachés ;
    dépensé = Σ montants HT FACTURÉS des factures fournisseur rattachées. Les
    montants sont lus via ``apps.stock.selectors`` (import LOCAL — aucune arête
    d'import au chargement). Un objet introuvable pour la société dégrade à 0."""
    from decimal import Decimal
    from apps.stock import selectors as stock_selectors
    engage = {}
    depense = {}
    for eng in budget.engagements.all():
        cat = eng.categorie
        if eng.source == eng.Source.BON_COMMANDE and eng.bon_commande_id:
            bon = stock_selectors.get_bon_commande_fournisseur(
                company, eng.bon_commande_id)
            montant = (stock_selectors.montant_commande_bcf(bon)
                       if bon is not None else Decimal('0'))
            engage[cat] = engage.get(cat, Decimal('0')) + _dec(montant)
        elif eng.source == eng.Source.FACTURE and eng.facture_id:
            montant = _facture_fournisseur_ht(company, eng.facture_id)
            depense[cat] = depense.get(cat, Decimal('0')) + _dec(montant)
    return engage, depense


def _facture_fournisseur_ht(company, facture_id):
    """Montant HT d'une facture fournisseur scopée société (0 si introuvable).
    Lu via ``apps.get_model`` — aucune arête d'import vers ``stock`` au
    chargement."""
    from decimal import Decimal
    from django.apps import apps as django_apps
    model = django_apps.get_model('stock', 'FactureFournisseur')
    fac = model.objects.filter(id=facture_id, company=company).first()
    if fac is None:
        return Decimal('0')
    return _dec(fac.montant_ht)


def _main_oeuvre_reelle(projet, tarif_jour):
    """(jours-homme réels Σ, coût main-d'œuvre réel) des chantiers du programme.

    Σ ``Installation.labour_jours_reels`` sur les chantiers rattachés
    (``ProjetChantier`` → ``Installation``, même app, FK directe) × ``tarif_jour``
    (MAD/jour). Tarif 0 → coût 0."""
    from decimal import Decimal
    from .models import Installation
    inst_ids = list(projet.chantiers.values_list('installation_id', flat=True))
    if not inst_ids:
        return Decimal('0'), Decimal('0')
    jours = Decimal('0')
    for inst in Installation.objects.filter(id__in=inst_ids):
        jours += _dec(inst.labour_jours_reels)
    return jours, jours * _dec(tarif_jour)


def budget_projet_synthese(budget):
    """FG294 — synthèse budget vs réel (engagé / dépensé) d'un programme.

    AGRÈGE, pour le ``BudgetProjet`` donné, le réel à partir des devis du
    programme, des bons de commande / factures fournisseur rattachés et de la
    main-d'œuvre des chantiers, puis le compare au budget par catégorie et au
    total, et lève un drapeau de DÉPASSEMENT.

    Renvoie un dict plat (jamais d'instance de modèle d'une autre app) :
      ``devise`` ; ``budget`` (par catégorie + total) ;
      ``engage`` / ``depense`` (par catégorie + total — engagé = BCF commandés +
      main-d'œuvre, dépensé = factures fournisseur + main-d'œuvre) ;
      ``reste`` (budget total − dépensé total) ;
      ``devis_total_ht`` / ``devis_total_ttc`` (montant contracté client) ;
      ``seuil_alerte_pct`` ; ``depassement`` (bool) ; ``categories_depassees``
      (liste des catégories dont le dépensé excède le budget).

    Le ``depassement`` est vrai quand le dépensé total dépasse le budget total
    majoré du seuil (``budget × (1 + seuil/100)``). Lecture seule, import-linter
    safe (lectures cross-app via sélecteurs / ``apps.get_model``)."""
    from decimal import Decimal
    company = budget.company
    projet = budget.projet

    budget_cat = {
        'materiel': _dec(budget.budget_materiel),
        'main_oeuvre': _dec(budget.budget_main_oeuvre),
        'sous_traitance': _dec(budget.budget_sous_traitance),
        'divers': _dec(budget.budget_divers),
    }
    budget_total = sum(budget_cat.values(), Decimal('0'))

    eng_fourn, dep_fourn = _engagements_fournisseur(budget, company)
    mo_jours, mo_cout = _main_oeuvre_reelle(projet, budget.tarif_jour_mo)

    cats = ('materiel', 'main_oeuvre', 'sous_traitance', 'divers')
    engage_cat = {c: eng_fourn.get(c, Decimal('0')) for c in cats}
    depense_cat = {c: dep_fourn.get(c, Decimal('0')) for c in cats}
    # La main-d'œuvre des chantiers s'ajoute à la catégorie main_oeuvre, à la
    # fois en engagé et en dépensé (le temps passé est un coût encouru).
    engage_cat['main_oeuvre'] += mo_cout
    depense_cat['main_oeuvre'] += mo_cout

    engage_total = sum(engage_cat.values(), Decimal('0'))
    depense_total = sum(depense_cat.values(), Decimal('0'))

    seuil = _dec(budget.seuil_alerte_pct)
    plafond = budget_total * (Decimal('1') + seuil / Decimal('100'))
    depassement = budget_total > 0 and depense_total > plafond
    categories_depassees = [
        c for c in cats if budget_cat[c] > 0 and depense_cat[c] > budget_cat[c]
    ]

    devis_ht, devis_ttc = _devis_totaux_programme(projet)

    def _floats(d):
        return {k: float(v) for k, v in d.items()}

    return {
        'budget_id': budget.id,
        'projet_id': projet.id,
        'devise': budget.devise,
        'budget': {**_floats(budget_cat), 'total': float(budget_total)},
        'engage': {**_floats(engage_cat), 'total': float(engage_total)},
        'depense': {**_floats(depense_cat), 'total': float(depense_total)},
        'reste': float(budget_total - depense_total),
        'main_oeuvre_jours_reels': float(mo_jours),
        'devis_total_ht': float(devis_ht),
        'devis_total_ttc': float(devis_ttc),
        'seuil_alerte_pct': float(seuil),
        'depassement': bool(depassement),
        'categories_depassees': categories_depassees,
    }


# ── FG295 — P&L de projet consolidé (revenu − coûts → marge) ─────────────────
# Le sélecteur ``projet_pnl`` consolide, pour UN ``Projet``, le résultat de TOUS
# ses chantiers : REVENU (factures CLIENT émises sur les devis du programme) −
# COÛTS (matériel via BCF/factures fournisseur, sous-traitance, imports, et
# main-d'œuvre des chantiers) → marge brute + marge %. Il RÉUTILISE l'agrégation
# des coûts réels de FG294 (``_engagements_fournisseur`` + ``_main_oeuvre_reelle``)
# et lit les apps ``ventes``/``stock`` SANS importer leurs modèles
# (``apps.get_model`` + ``apps.stock.selectors`` — import-linter safe). Toute
# donnée manquante DÉGRADE proprement à 0 ; AUCUN statut n'est touché.

def _factures_revenu_programme(projet, company):
    """(Σ revenu HT, Σ revenu TTC) des factures CLIENT émises sur les devis du
    programme. Lu via ``apps.get_model('ventes', 'Facture')`` — aucune arête
    d'import vers ``ventes`` au chargement. Les factures ANNULÉES sont exclues
    (elles ne sont pas un revenu). Une facture introuvable / illisible dégrade
    à 0. Le revenu est scopé société (jamais la facture d'une autre société)."""
    from decimal import Decimal
    from django.apps import apps as django_apps
    devis_ids = list(projet.devis.values_list('devis_id', flat=True))
    if not devis_ids:
        return Decimal('0'), Decimal('0')
    facture_model = django_apps.get_model('ventes', 'Facture')
    revenu_ht = Decimal('0')
    revenu_ttc = Decimal('0')
    factures = (facture_model.objects
                .filter(devis_id__in=devis_ids, company=company)
                .exclude(statut='annulee'))
    for facture in factures:
        try:
            revenu_ht += _dec(facture.total_ht)
            revenu_ttc += _dec(facture.total_ttc)
        except Exception:  # pragma: no cover - défensif
            continue
    return revenu_ht, revenu_ttc


def projet_pnl(projet):
    """FG295 — P&L de projet CONSOLIDÉ : résultat (marge) de TOUS les chantiers
    d'un programme, sous-traitance et imports inclus.

    REVENU = Σ factures CLIENT émises sur les devis du programme (HT/TTC) ;
    COÛTS = coûts RÉELS encourus = dépensé fournisseur (matériel + sous-traitance
    + divers/imports, via les ``BudgetEngagement`` du budget du programme) +
    main-d'œuvre des chantiers (jours réels × tarif). On RÉUTILISE l'agrégation
    de FG294 : si le programme n'a pas de budget, le coût fournisseur dégrade à 0
    et seule la main-d'œuvre est comptée (tarif 0 → 0).

    Renvoie un dict PLAT (jamais d'instance de modèle d'une autre app) :
      ``devise`` ; ``revenu`` (ht/ttc) ; ``couts`` (par catégorie + total) ;
      ``marge_brute`` (revenu HT − coûts) ; ``marge_pct`` (marge / revenu HT,
      0 si revenu nul) ; ``main_oeuvre_jours_reels``. Lecture seule, import-linter
      safe (lectures cross-app via ``apps.get_model`` / ``apps.stock.selectors``).
    """
    from decimal import Decimal
    company = projet.company

    revenu_ht, revenu_ttc = _factures_revenu_programme(projet, company)

    # ── Coûts réels — réutilise l'agrégation FG294 ──────────────────────────
    # Coûts fournisseur (matériel / sous-traitance / divers-imports) = DÉPENSÉ
    # des factures fournisseur rattachées au budget du programme. L'engagé (BCF
    # commandé non encore facturé) n'est PAS un coût ENCOURU : un P&L compte le
    # dépensé. Sans budget rattaché → 0 (dégradation propre).
    budget = getattr(projet, 'budget', None)
    cats = ('materiel', 'main_oeuvre', 'sous_traitance', 'divers')
    couts_cat = {c: Decimal('0') for c in cats}
    tarif_jour = budget.tarif_jour_mo if budget is not None else Decimal('0')
    if budget is not None:
        _eng_fourn, dep_fourn = _engagements_fournisseur(budget, company)
        for c in cats:
            couts_cat[c] += dep_fourn.get(c, Decimal('0'))

    # Main-d'œuvre des chantiers (jours réels × tarif) — même app, FK directe.
    mo_jours, mo_cout = _main_oeuvre_reelle(projet, tarif_jour)
    couts_cat['main_oeuvre'] += mo_cout

    couts_total = sum(couts_cat.values(), Decimal('0'))
    marge_brute = revenu_ht - couts_total
    marge_pct = (marge_brute / revenu_ht * Decimal('100')
                 if revenu_ht > 0 else Decimal('0'))

    def _floats(d):
        return {k: float(v) for k, v in d.items()}

    return {
        'projet_id': projet.id,
        'devise': budget.devise if budget is not None else 'MAD',
        'revenu': {'ht': float(revenu_ht), 'ttc': float(revenu_ttc)},
        'couts': {**_floats(couts_cat), 'total': float(couts_total)},
        'marge_brute': float(marge_brute),
        'marge_pct': float(marge_pct),
        'main_oeuvre_jours_reels': float(mo_jours),
    }


# ── FG299 — Plan de charge des équipes (capacité vs affecté) ─────────────────
# Vue de PLAN DE CHARGE des équipes terrain : sur une fenêtre de dates, on
# compare la CAPACITÉ de chaque technicien (jours ouvrés × heures/jour) à sa
# CHARGE AFFECTÉE (interventions où il est technicien principal OU membre
# d'équipe, dont `date_prevue` tombe dans la fenêtre) pour détecter la
# SUR-RÉSERVATION (sur-booking). Pure agrégation — aucun nouveau modèle, lecture
# seule, scopée société. Distinct de PROJ18 (ressources de PROGRAMME, app
# gestion_projet) : ici ce sont les ÉQUIPES TERRAIN sur les interventions.
#
# Effort d'une intervention : on compte 1 intervention ≈ 1 journée de travail
# (proxy le plus simple et lisible — il n'existe pas de durée saisie par
# intervention), soit `heures_par_jour` heures de charge. La capacité est en
# jours ouvrés (lundi→vendredi) de la fenêtre × `heures_par_jour`.

def _jours_ouvres(debut, fin):
    """Nombre de jours ouvrés (lundi→vendredi) dans la fenêtre [debut, fin]
    INCLUSIVE. 0 si la fenêtre est vide/inversée. Pas de dépendance externe
    (aucun calendrier de jours fériés) — garde simple et déterministe."""
    if debut is None or fin is None or fin < debut:
        return 0
    import datetime
    jours = 0
    jour = debut
    un = datetime.timedelta(days=1)
    while jour <= fin:
        if jour.weekday() < 5:  # 0=lundi … 4=vendredi
            jours += 1
        jour += un
    return jours


def plan_de_charge_equipes(company, debut, fin, heures_par_jour=8):
    """FG299 — plan de charge des équipes terrain : capacité vs affecté par
    technicien sur la fenêtre [debut, fin] inclusive, avec drapeau de
    SUR-RÉSERVATION.

    Pour CHAQUE technicien de la société qui porte au moins une intervention
    dans la fenêtre (comme technicien principal OU comme membre d'équipe), on
    calcule :
      * ``capacite_heures`` = jours ouvrés de la fenêtre × ``heures_par_jour`` ;
      * ``affecte_count``   = nombre d'interventions distinctes affectées ;
      * ``affecte_heures``  = ``affecte_count`` × ``heures_par_jour`` ;
      * ``charge_pct``      = affecté / capacité × 100 (0 si capacité nulle) ;
      * ``sur_reservation`` = affecté > capacité (jamais vrai si capacité 0 et
        affecté 0 ; vrai si une charge existe alors que la capacité est nulle,
        ex. fenêtre sans aucun jour ouvré → toute affectation est en
        sur-réservation).

    Renvoie un dict PLAT (jamais d'instance de modèle d'une autre app) :
      ``debut`` / ``fin`` (ISO) ; ``heures_par_jour`` ; ``jours_ouvres`` ;
      ``capacite_heures`` (par technicien, identique pour tous) ;
      ``techniciens`` (liste triée nom) ; ``totaux`` (Σ capacité / Σ affecté /
      nb en sur-réservation). Lecture seule, scopée société, garde
      division-par-zéro. Une intervention sans aucun technicien ni équipe est
      regroupée sous ``non_assigne`` (affichée pour visibilité, jamais en
      sur-réservation)."""
    from collections import OrderedDict
    from django.contrib.auth import get_user_model
    from .models import Intervention

    try:
        heures_par_jour = float(heures_par_jour)
    except (TypeError, ValueError):
        heures_par_jour = 8.0
    if heures_par_jour < 0:
        heures_par_jour = 0.0

    jours_ouvres = _jours_ouvres(debut, fin)
    capacite_heures = jours_ouvres * heures_par_jour

    qs = (Intervention.objects
          .filter(company=company)
          .filter(date_prevue__gte=debut, date_prevue__lte=fin)
          .prefetch_related('equipe')
          .only('id', 'technicien_id', 'date_prevue'))

    # {user_id|None: set(intervention_id)} — un set évite de compter deux fois
    # une intervention où un technicien est À LA FOIS principal et membre.
    affecte = OrderedDict()
    non_assigne = set()
    for interv in qs:
        membres = set()
        if interv.technicien_id:
            membres.add(interv.technicien_id)
        # Utilise le cache de prefetch (``.all()``) plutôt qu'un values_list qui
        # rejouerait une requête par intervention (N+1).
        for membre in interv.equipe.all():
            membres.add(membre.id)
        if not membres:
            non_assigne.add(interv.id)
            continue
        for membre_id in membres:
            affecte.setdefault(membre_id, set()).add(interv.id)

    User = get_user_model()
    user_ids = [uid for uid in affecte if uid is not None]
    users = {u.id: u for u in User.objects.filter(id__in=user_ids)} \
        if user_ids else {}

    def _nom(user, uid):
        if user is None:
            return str(uid)
        nom = ''
        getter = getattr(user, 'get_full_name', None)
        if callable(getter):
            nom = (getter() or '').strip()
        return nom or getattr(user, 'username', str(uid))

    techniciens = []
    total_affecte = 0
    nb_sur_reservation = 0
    for uid, interv_ids in affecte.items():
        count = len(interv_ids)
        affecte_heures = count * heures_par_jour
        total_affecte += count
        if capacite_heures > 0:
            charge_pct = affecte_heures / capacite_heures * 100
        else:
            charge_pct = 0.0
        sur_reservation = affecte_heures > capacite_heures
        if sur_reservation:
            nb_sur_reservation += 1
        techniciens.append({
            'technicien_id': uid,
            'nom': _nom(users.get(uid), uid),
            'capacite_heures': float(capacite_heures),
            'affecte_count': count,
            'affecte_heures': float(affecte_heures),
            'charge_pct': round(float(charge_pct), 1),
            'sur_reservation': bool(sur_reservation),
        })

    techniciens.sort(key=lambda t: t['nom'].lower())

    return {
        'debut': debut.isoformat() if debut is not None else None,
        'fin': fin.isoformat() if fin is not None else None,
        'heures_par_jour': float(heures_par_jour),
        'jours_ouvres': jours_ouvres,
        'capacite_heures': float(capacite_heures),
        'techniciens': techniciens,
        'non_assigne_count': len(non_assigne),
        'totaux': {
            'capacite_heures': float(capacite_heures * len(techniciens)),
            'affecte_count': total_affecte,
            'nb_sur_reservation': nb_sur_reservation,
        },
    }


# ── FG301 — Nivellement de charge (resource levelling) ───────────────────────
# Construit sur FG299 (plan de charge) + FG300 (conflits) : à partir de la charge
# par technicien sur une fenêtre, on PROPOSE de déplacer des interventions des
# techniciens SUR-CHARGÉS (affecté > capacité) vers les techniciens SOUS-CHARGÉS
# (affecté < capacité) pour rééquilibrer. C'est une proposition LECTURE SEULE :
# rien n'est jamais muté — on renvoie une liste de déplacements suggérés
# (quelle intervention → quel technicien sous-chargé). Pure agrégation, scopée
# société, aucun nouveau modèle.
#
# Capacité = jours ouvrés de la fenêtre (proxy : 1 intervention ≈ 1 journée, comme
# FG299) ; ``heures_par_jour`` ne sert qu'à exprimer les heures pour cohérence
# d'affichage. Un technicien est sur-chargé si son nombre d'interventions affectées
# dépasse les jours ouvrés disponibles. Pour chaque excédent on cherche le
# technicien sous-chargé avec le PLUS de marge restante, en ÉVITANT de recréer un
# conflit FG300 (on ne propose pas un destinataire déjà affecté ce jour-là).

def nivellement_charge(company, debut, fin, heures_par_jour=8):
    """FG301 — propose un rééquilibrage des interventions des techniciens
    SUR-CHARGÉS vers les SOUS-CHARGÉS, sur la fenêtre [debut, fin] inclusive.

    Réutilise la logique de charge de FG299 : pour chaque technicien (principal
    OU membre d'équipe) on compte ses interventions distinctes prévues dans la
    fenêtre, comparé à la capacité = jours ouvrés (proxy 1 intervention ≈ 1 jour).
    Un technicien dont la charge dépasse la capacité est SUR-CHARGÉ ; en dessous,
    SOUS-CHARGÉ (marge = capacité − charge).

    Pour chaque intervention en excès d'un technicien sur-chargé, on propose de la
    déplacer vers le technicien sous-chargé qui a LE PLUS de marge restante, sans
    recréer un conflit FG300 (jamais un destinataire déjà affecté ce jour-là, ni
    déjà ciblé par une proposition le même jour). Les interventions déplacées
    « en premier » sont celles dont la date est la plus tardive (on garde le début
    de fenêtre stable). Une intervention sans date prévue n'est jamais proposée
    (pas de créneau ⇒ pas de risque de conflit à arbitrer).

    Renvoie un dict PLAT (jamais d'instance de modèle d'une autre app) :
      ``debut`` / ``fin`` (ISO ou None) ; ``heures_par_jour`` ; ``jours_ouvres`` ;
      ``capacite_jours`` (= jours ouvrés, identique pour tous) ;
      ``surcharges`` (techniciens sur-chargés : {technicien_id, nom, charge,
        capacite, exces}) ; ``propositions`` (liste de déplacements suggérés,
        triée par date puis nom source) — chaque entrée =
        {intervention_id, installation_id, type_intervention, date, de_id,
         de_nom, vers_id, vers_nom} ; ``totaux`` (nb_surcharges,
         nb_propositions, nb_non_resolues = interventions en excès sans
         destinataire possible).
    Lecture seule, NE MUTE RIEN, scopée société, garde division-par-zéro et
    fenêtre vide/None/inversée (renvoie des listes vides, jamais d'exception).
    """
    from collections import OrderedDict
    from django.contrib.auth import get_user_model
    from .models import Intervention

    try:
        heures_par_jour = float(heures_par_jour)
    except (TypeError, ValueError):
        heures_par_jour = 8.0
    if heures_par_jour < 0:
        heures_par_jour = 0.0

    jours_ouvres = _jours_ouvres(debut, fin)

    base = {
        'debut': debut.isoformat() if debut is not None else None,
        'fin': fin.isoformat() if fin is not None else None,
        'heures_par_jour': float(heures_par_jour),
        'jours_ouvres': jours_ouvres,
        'capacite_jours': jours_ouvres,
        'surcharges': [],
        'propositions': [],
        'totaux': {
            'nb_surcharges': 0,
            'nb_propositions': 0,
            'nb_non_resolues': 0,
        },
    }
    # Fenêtre vide / None / inversée → rien à niveler (garde explicite).
    if debut is None or fin is None or fin < debut:
        return base

    qs = (Intervention.objects
          .filter(company=company)
          .filter(date_prevue__gte=debut, date_prevue__lte=fin)
          .filter(date_prevue__isnull=False)
          .prefetch_related('equipe')
          .only('id', 'installation_id', 'type_intervention',
                'technicien_id', 'date_prevue'))

    # {user_id: OrderedDict{intervention_id: interv}} — affectation par technicien.
    # Un OrderedDict évite de compter deux fois une intervention où un technicien
    # est À LA FOIS principal ET membre d'équipe (clé = id).
    affecte = OrderedDict()
    # {user_id: set(jour)} — jours déjà occupés par chaque technicien (pour ne pas
    # recréer un conflit FG300 en déplaçant une intervention vers lui).
    jours_occupes = {}

    for interv in qs.order_by('date_prevue', 'id'):
        membres = set()
        if interv.technicien_id:
            membres.add(interv.technicien_id)
        for membre in interv.equipe.all():
            membres.add(membre.id)
        for membre_id in membres:
            affecte.setdefault(membre_id, OrderedDict())[interv.id] = interv
            jours_occupes.setdefault(membre_id, set()).add(interv.date_prevue)

    if not affecte:
        return base

    capacite = jours_ouvres  # jours ouvrés ; proxy 1 intervention ≈ 1 jour

    # Noms des techniciens (un seul accès DB).
    User = get_user_model()
    users = {u.id: u for u in User.objects.filter(id__in=list(affecte))}

    def _nom(uid):
        user = users.get(uid)
        if user is None:
            return str(uid)
        getter = getattr(user, 'get_full_name', None)
        nom = ''
        if callable(getter):
            nom = (getter() or '').strip()
        return nom or getattr(user, 'username', str(uid))

    # Marge restante par technicien sous-chargé (capacité − charge), mutée au fil
    # des propositions pour répartir équitablement.
    marge = {}
    surcharges = []
    for uid, intervs in affecte.items():
        charge = len(intervs)
        if charge > capacite:
            surcharges.append((uid, charge))
        elif charge < capacite:
            marge[uid] = capacite - charge

    surcharges.sort(key=lambda s: (-(s[1]), _nom(s[0]).lower(), s[0]))

    propositions = []
    nb_non_resolues = 0

    for uid, charge in surcharges:
        exces = charge - capacite
        if exces <= 0:
            continue
        intervs = affecte[uid]
        # On déplace en priorité les interventions les plus TARDIVES (garde le
        # début de fenêtre stable) ; tri déterministe par date puis id.
        candidats = sorted(
            intervs.values(),
            key=lambda iv: (iv.date_prevue, iv.id), reverse=True)
        deplaces = 0
        for interv in candidats:
            if deplaces >= exces:
                break
            jour = interv.date_prevue
            # Destinataires éligibles : sous-chargés, marge > 0, pas eux-mêmes,
            # PAS déjà occupés ce jour-là (anti-conflit FG300), pas déjà affectés
            # à CETTE intervention.
            deja = set(affecte.get(interv.id, {}))  # techniciens de l'interv
            meilleur = None
            meilleure_marge = 0
            for dest_id, m in marge.items():
                if m <= 0 or dest_id == uid or dest_id in deja:
                    continue
                if jour in jours_occupes.get(dest_id, set()):
                    continue
                if m > meilleure_marge:
                    meilleure_marge = m
                    meilleur = dest_id
            if meilleur is None:
                nb_non_resolues += 1
                continue
            propositions.append({
                'intervention_id': interv.id,
                'installation_id': interv.installation_id,
                'type_intervention': interv.type_intervention,
                'date': jour.isoformat(),
                'de_id': uid,
                'de_nom': _nom(uid),
                'vers_id': meilleur,
                'vers_nom': _nom(meilleur),
            })
            # Met à jour l'état pour les propositions suivantes (équité +
            # anti-conflit) — n'écrit RIEN en base.
            marge[meilleur] -= 1
            jours_occupes.setdefault(meilleur, set()).add(jour)
            deplaces += 1

    surcharges_out = [{
        'technicien_id': uid,
        'nom': _nom(uid),
        'charge': charge,
        'capacite': capacite,
        'exces': charge - capacite,
    } for uid, charge in surcharges]

    propositions.sort(key=lambda p: (p['date'], p['de_nom'].lower(),
                                     p['intervention_id']))

    base['surcharges'] = surcharges_out
    base['propositions'] = propositions
    base['totaux'] = {
        'nb_surcharges': len(surcharges_out),
        'nb_propositions': len(propositions),
        'nb_non_resolues': nb_non_resolues,
    }
    return base


def reserve_scoped(company, pk):
    """Réserve (F16 — point de finition) scopée société, par id, ou ``None``.

    Point d'entrée cross-app LECTURE SEULE : les autres apps (ex. QHSE, pour le
    pont Réserve → NCR) lisent une ``Reserve`` à travers ce sélecteur plutôt
    qu'en important ``installations.models`` directement. Scopé société :
    ``None`` si la réserve n'appartient pas à ``company``."""
    from .models import Reserve
    return (Reserve.objects
            .filter(company=company, pk=pk)
            .select_related('intervention', 'intervention__installation')
            .first())


def reserve_resume(reserve):
    """Résumé LECTURE SEULE d'une ``Reserve`` pour un pont cross-app (→ NCR).

    Renvoie un dict plat ``{id, description, statut, intervention_id,
    chantier_id}`` — jamais l'instance du modèle — pour qu'une autre app
    construise une fiche (ex. non-conformité QHSE) sans importer le modèle ni
    coupler les apps. ``chantier_id`` est l'id du chantier (Installation) de
    l'intervention, ``None`` s'il n'y en a pas."""
    intervention = getattr(reserve, 'intervention', None)
    chantier_id = getattr(intervention, 'installation_id', None)
    return {
        'id': reserve.id,
        'description': reserve.description or '',
        'statut': reserve.statut,
        'intervention_id': reserve.intervention_id,
        'chantier_id': chantier_id,
    }


# ── FG300 — Détection de conflits d'affectation (double-booking) ─────────────
# Alerte quand une MÊME ressource (technicien principal, membre d'équipe, ou
# camionnette) est affectée à DEUX interventions ou plus dont les créneaux se
# CHEVAUCHENT. Les interventions ne portent qu'une DATE (`date_prevue`, granularité
# jour) — le « créneau » est donc la journée : deux interventions de la même
# ressource le MÊME jour se chevauchent et constituent un conflit. Pure détection,
# lecture seule, scopée société, AUCUN nouveau modèle. Distinct de FG299 (plan de
# charge agrégé) : ici on liste les COLLISIONS concrètes à corriger.

def conflits_affectation(company, debut, fin):
    """FG300 — liste les conflits d'affectation (double-booking) d'une ressource
    sur la fenêtre [debut, fin] inclusive.

    Une ressource est un TECHNICIEN (principal OU membre d'équipe) ou une
    CAMIONNETTE (`Intervention.camionnette`, un EmplacementStock). Un conflit
    existe quand la même ressource porte ≥ 2 interventions dont le créneau se
    chevauche ; les interventions n'ayant qu'une date prévue (granularité jour),
    le chevauchement = même `date_prevue`. Seules les interventions dont
    `date_prevue` tombe dans [debut, fin] sont considérées (les interventions
    sans date prévue sont ignorées : pas de créneau ⇒ pas de collision).

    Renvoie un dict PLAT (jamais d'instance de modèle) :
      ``debut`` / ``fin`` (ISO ou None) ; ``conflits`` (liste triée par date puis
      type de ressource puis nom), chaque entrée =
        ``{type, ressource_id, ressource_nom, date, interventions: [{id,
        installation_id, type_intervention, statut}], count}`` ;
      ``totaux`` (``nb_conflits``, ``nb_techniciens``, ``nb_camionnettes``).
    Lecture seule, scopée société. Garde les fenêtres vides/None : si la fenêtre
    est absente ou inversée, renvoie une liste vide (jamais d'exception)."""
    from collections import OrderedDict
    from django.contrib.auth import get_user_model
    from .models import Intervention

    base = {
        'debut': debut.isoformat() if debut is not None else None,
        'fin': fin.isoformat() if fin is not None else None,
        'conflits': [],
        'totaux': {'nb_conflits': 0, 'nb_techniciens': 0, 'nb_camionnettes': 0},
    }
    # Fenêtre vide / None / inversée → aucune collision (garde explicite).
    if debut is None or fin is None or fin < debut:
        return base

    qs = (Intervention.objects
          .filter(company=company)
          .filter(date_prevue__gte=debut, date_prevue__lte=fin)
          .filter(date_prevue__isnull=False)
          .select_related('camionnette')
          .prefetch_related('equipe')
          .only('id', 'installation_id', 'type_intervention', 'statut',
                'date_prevue', 'technicien_id', 'camionnette_id',
                'camionnette__nom'))

    # (jour, type, ressource_id) → liste d'interventions partageant le créneau.
    # OrderedDict pour un parcours déterministe (ordre d'insertion = tri date qs).
    par_creneau = OrderedDict()
    tech_ids = set()
    # {camionnette_id: nom} — lu sur l'instance FK déjà chargée (select_related),
    # sans importer le modèle de stock (couplage évité).
    camion_noms = {}

    def _add(jour, type_ressource, ressource_id, interv):
        if ressource_id is None:
            return
        cle = (jour, type_ressource, ressource_id)
        par_creneau.setdefault(cle, []).append(interv)

    for interv in qs.order_by('date_prevue', 'id'):
        jour = interv.date_prevue
        if interv.technicien_id:
            tech_ids.add(interv.technicien_id)
            _add(jour, 'technicien', interv.technicien_id, interv)
        for membre in interv.equipe.all():
            tech_ids.add(membre.id)
            _add(jour, 'technicien', membre.id, interv)
        if interv.camionnette_id:
            camion = getattr(interv, 'camionnette', None)
            nom_camion = getattr(camion, 'nom', None) if camion else None
            if nom_camion:
                camion_noms[interv.camionnette_id] = nom_camion
            _add(jour, 'camionnette', interv.camionnette_id, interv)

    # Évite de compter deux fois une intervention où un technicien est À LA FOIS
    # principal ET membre d'équipe sur le même créneau (dédoublonnage par id).
    for cle, intervs in par_creneau.items():
        seen = set()
        uniques = []
        for iv in intervs:
            if iv.id not in seen:
                seen.add(iv.id)
                uniques.append(iv)
        par_creneau[cle] = uniques

    # Noms des techniciens (un seul accès DB).
    User = get_user_model()
    users = {u.id: u for u in User.objects.filter(id__in=tech_ids)} \
        if tech_ids else {}

    def _nom_user(uid):
        user = users.get(uid)
        if user is None:
            return str(uid)
        getter = getattr(user, 'get_full_name', None)
        nom = ''
        if callable(getter):
            nom = (getter() or '').strip()
        return nom or getattr(user, 'username', str(uid))

    def _nom_camion(eid):
        # Nom déjà capté sur l'instance FK chargée ; sinon repli sur l'id.
        return camion_noms.get(eid) or f'#{eid}'

    conflits = []
    nb_tech = 0
    nb_camion = 0
    for (jour, type_ressource, ressource_id), intervs in par_creneau.items():
        if len(intervs) < 2:
            continue  # un seul créneau ⇒ pas de collision
        if type_ressource == 'technicien':
            nom = _nom_user(ressource_id)
            nb_tech += 1
        else:
            nom = _nom_camion(ressource_id)
            nb_camion += 1
        conflits.append({
            'type': type_ressource,
            'ressource_id': ressource_id,
            'ressource_nom': nom,
            'date': jour.isoformat(),
            'count': len(intervs),
            'interventions': [{
                'id': iv.id,
                'installation_id': iv.installation_id,
                'type_intervention': iv.type_intervention,
                'statut': iv.statut,
            } for iv in intervs],
        })

    conflits.sort(key=lambda c: (
        c['date'], c['type'], c['ressource_nom'].lower(), c['ressource_id']))

    base['conflits'] = conflits
    base['totaux'] = {
        'nb_conflits': len(conflits),
        'nb_techniciens': nb_tech,
        'nb_camionnettes': nb_camion,
    }
    return base


# ── FG302 — Calendrier de disponibilité des ressources terrain ───────────────
# ``IndisponibiliteRessource`` (congé/formation/arrêt/autre) marque une ressource
# — TECHNICIEN (utilisateur) ou CAMIONNETTE (EmplacementStock) — comme absente sur
# [date_debut, date_fin] inclusive. Le plan de charge (FG299), la détection de
# conflits (FG300) et le nivellement (FG301) peuvent appeler ``ressource_indisponible``
# pour EXCLURE une ressource absente. Pure lecture, scopée société.

def ressource_indisponible(company, user_or_vehicle, debut, fin):
    """FG302 — ``True`` si la ressource ``user_or_vehicle`` est marquée
    indisponible (congé/formation/arrêt/autre) à un quelconque moment de la
    fenêtre [debut, fin] inclusive, pour la société donnée.

    ``user_or_vehicle`` accepte soit une instance (utilisateur OU
    ``EmplacementStock`` camionnette), soit un id entier — interprété comme un
    technicien quand c'est un entier (cas le plus courant côté FG299/300/301).
    Une indisponibilité [d, f] CHEVAUCHE la fenêtre [debut, fin] dès que
    ``d <= fin`` ET ``f >= debut`` (chevauchement d'intervalles inclusifs).

    Garde les fenêtres None/inversées : renvoie ``False`` (aucune contrainte) si
    la fenêtre est absente ou inversée, ou si la ressource est ``None``. Lecture
    seule, scopée société (jamais d'indisponibilité d'une autre société)."""
    from django.db.models import Q
    from .models import IndisponibiliteRessource

    if user_or_vehicle is None or debut is None or fin is None or fin < debut:
        return False

    # Résout la ressource en filtre technicien OU camionnette.
    tech_id = None
    camion_id = None
    if isinstance(user_or_vehicle, int):
        tech_id = user_or_vehicle
    else:
        meta = getattr(user_or_vehicle, '_meta', None)
        model_name = getattr(meta, 'model_name', '') if meta else ''
        if model_name == 'emplacementstock':
            camion_id = getattr(user_or_vehicle, 'pk', None)
        else:
            # Utilisateur (ou tout autre objet porteur d'un pk) → technicien.
            tech_id = getattr(user_or_vehicle, 'pk', None)

    if tech_id is None and camion_id is None:
        return False

    cible = Q(technicien_id=tech_id) if tech_id is not None \
        else Q(camionnette_id=camion_id)

    return (IndisponibiliteRessource.objects
            .filter(company=company)
            .filter(cible)
            .filter(date_debut__lte=fin, date_fin__gte=debut)
            .exists())


# ── FG303 — Planning des camionnettes (capacité véhicule) ────────────────────
# Vue de PLANNING PAR VÉHICULE : sur une fenêtre de dates, on regroupe PAR
# CAMIONNETTE (``Intervention.camionnette`` — un ``stock.EmplacementStock``) les
# interventions qui lui sont affectées, avec leur date / chantier / technicien,
# et on dérive une CHARGE JOURNALIÈRE (combien d'interventions par jour) en
# EXCLUANT les jours où la camionnette est marquée INDISPONIBLE (FG302
# ``IndisponibiliteRessource``). Pure agrégation — aucun nouveau modèle, lecture
# seule, scopée société. Cohérent avec FG300 (conflits) : deux interventions le
# MÊME jour sur la même camionnette sont une SUR-RÉSERVATION du véhicule.
#
# La granularité reste la JOURNÉE (les interventions ne portent qu'une
# ``date_prevue``). La « capacité » d'une camionnette est, par jour ouvré
# disponible, 1 intervention (proxy simple, comme FG299/FG301) ; au-delà le jour
# est en SUR-RÉSERVATION. Un jour d'indisponibilité a une capacité nulle : toute
# intervention ce jour-là est en sur-réservation (le véhicule est censé absent).

def planning_camionnettes(company, debut, fin, capacite_jour=1):
    """FG303 — planning par camionnette sur la fenêtre [debut, fin] inclusive.

    Pour CHAQUE camionnette (``Intervention.camionnette`` — un EmplacementStock)
    qui porte au moins une intervention datée dans la fenêtre, on renvoie :
      * ``interventions`` : la liste (triée par date puis id) des interventions
        affectées, chacune = {id, date, chantier_id, chantier_reference,
        type_intervention, statut, technicien_id, technicien_nom} ;
      * ``charge`` : la charge JOURNALIÈRE = liste {date, count, indisponible,
        sur_reservation} pour chaque jour de la fenêtre où la camionnette a ≥ 1
        intervention OU est indisponible ; ``indisponible`` reflète FG302,
        ``sur_reservation`` est vrai quand ``count`` dépasse la capacité du jour
        (0 si indisponible, sinon ``capacite_jour``) ;
      * ``total_interventions`` / ``jours_sur_reservation`` (compteurs).

    Une indisponibilité FG302 [d, f] retire la capacité du véhicule sur ces jours
    (capacité 0) — toute intervention qui y tombe est donc en sur-réservation, et
    un jour 100 % indisponible sans intervention apparaît quand même dans
    ``charge`` (indisponible=True, count=0) pour la visibilité.

    Renvoie un dict PLAT (jamais d'instance de modèle d'une autre app) :
      ``debut`` / ``fin`` (ISO ou None) ; ``capacite_jour`` ;
      ``camionnettes`` (liste triée par nom) ; ``totaux`` (nb_camionnettes,
      nb_interventions, nb_jours_sur_reservation). Lecture seule, scopée société,
      garde les fenêtres vides/None/inversées (renvoie des listes vides, jamais
      d'exception). Le nom de la camionnette est lu sur l'instance FK déjà
      chargée (``select_related``) — le modèle de stock n'est JAMAIS importé."""
    from collections import OrderedDict
    from django.contrib.auth import get_user_model
    from .models import Intervention

    try:
        capacite_jour = int(capacite_jour)
    except (TypeError, ValueError):
        capacite_jour = 1
    if capacite_jour < 0:
        capacite_jour = 0

    base = {
        'debut': debut.isoformat() if debut is not None else None,
        'fin': fin.isoformat() if fin is not None else None,
        'capacite_jour': capacite_jour,
        'camionnettes': [],
        'totaux': {
            'nb_camionnettes': 0,
            'nb_interventions': 0,
            'nb_jours_sur_reservation': 0,
        },
    }
    # Fenêtre vide / None / inversée → rien à planifier (garde explicite).
    if debut is None or fin is None or fin < debut:
        return base

    qs = (Intervention.objects
          .filter(company=company)
          .filter(date_prevue__gte=debut, date_prevue__lte=fin)
          .filter(date_prevue__isnull=False)
          .filter(camionnette__isnull=False)
          .select_related('camionnette', 'installation', 'technicien')
          .only('id', 'date_prevue', 'type_intervention', 'statut',
                'technicien_id', 'camionnette_id', 'camionnette__nom',
                'installation_id', 'installation__reference'))

    # {camionnette_id: {'nom': str, 'interventions': [interv]}} — ordre stable.
    par_camion = OrderedDict()
    tech_ids = set()
    for interv in qs.order_by('date_prevue', 'id'):
        cid = interv.camionnette_id
        camion = getattr(interv, 'camionnette', None)
        nom = getattr(camion, 'nom', None) if camion else None
        entree = par_camion.setdefault(
            cid, {'nom': nom or f'#{cid}', 'interventions': []})
        entree['interventions'].append(interv)
        if interv.technicien_id:
            tech_ids.add(interv.technicien_id)

    # Noms des techniciens (un seul accès DB).
    User = get_user_model()
    users = {u.id: u for u in User.objects.filter(id__in=tech_ids)} \
        if tech_ids else {}

    def _nom_user(uid):
        if uid is None:
            return None
        user = users.get(uid)
        if user is None:
            return str(uid)
        getter = getattr(user, 'get_full_name', None)
        nom = ''
        if callable(getter):
            nom = (getter() or '').strip()
        return nom or getattr(user, 'username', str(uid))

    # Jours d'indisponibilité par camionnette (FG302) recoupant la fenêtre.
    indispo_jours = _camionnette_indispo_jours(
        company, list(par_camion), debut, fin)

    camionnettes = []
    total_interventions = 0
    total_jours_sur = 0
    for cid, entree in par_camion.items():
        intervs = entree['interventions']
        total_interventions += len(intervs)
        jours_indispo = indispo_jours.get(cid, set())

        # Charge journalière : compte des interventions par jour.
        par_jour = OrderedDict()
        for interv in intervs:
            jour = interv.date_prevue
            par_jour[jour] = par_jour.get(jour, 0) + 1

        # Réunit les jours « avec interventions » et les jours « indisponibles »
        # (pour qu'un jour 100 % absent reste visible, count=0).
        jours = set(par_jour) | jours_indispo
        charge = []
        for jour in sorted(jours):
            count = par_jour.get(jour, 0)
            indisponible = jour in jours_indispo
            cap = 0 if indisponible else capacite_jour
            sur_reservation = count > cap
            if sur_reservation:
                total_jours_sur += 1
            charge.append({
                'date': jour.isoformat(),
                'count': count,
                'indisponible': indisponible,
                'sur_reservation': bool(sur_reservation),
            })

        interventions_out = [{
            'id': interv.id,
            'date': interv.date_prevue.isoformat(),
            'chantier_id': interv.installation_id,
            'chantier_reference': getattr(
                getattr(interv, 'installation', None), 'reference', '') or '',
            'type_intervention': interv.type_intervention,
            'statut': interv.statut,
            'technicien_id': interv.technicien_id,
            'technicien_nom': _nom_user(interv.technicien_id),
        } for interv in sorted(
            intervs, key=lambda iv: (iv.date_prevue, iv.id))]

        camionnettes.append({
            'camionnette_id': cid,
            'nom': entree['nom'],
            'interventions': interventions_out,
            'charge': charge,
            'total_interventions': len(intervs),
            'jours_sur_reservation': sum(
                1 for c in charge if c['sur_reservation']),
        })

    camionnettes.sort(key=lambda c: (c['nom'].lower(), c['camionnette_id']))

    base['camionnettes'] = camionnettes
    base['totaux'] = {
        'nb_camionnettes': len(camionnettes),
        'nb_interventions': total_interventions,
        'nb_jours_sur_reservation': total_jours_sur,
    }
    return base


def _camionnette_indispo_jours(company, camion_ids, debut, fin):
    """FG303 — pour un lot de camionnettes, l'ensemble des JOURS de la fenêtre
    [debut, fin] inclusive où chacune est marquée indisponible (FG302
    ``IndisponibiliteRessource`` de cible camionnette). Renvoie
    {camionnette_id: set(date)}. Lecture seule, scopée société. Une
    indisponibilité [d, f] est tronquée à la fenêtre demandée."""
    import datetime
    from .models import IndisponibiliteRessource

    out = {}
    if not camion_ids or debut is None or fin is None or fin < debut:
        return out

    rows = (IndisponibiliteRessource.objects
            .filter(company=company)
            .filter(camionnette_id__in=list(camion_ids))
            .filter(date_debut__lte=fin, date_fin__gte=debut)
            .values_list('camionnette_id', 'date_debut', 'date_fin'))
    un = datetime.timedelta(days=1)
    for cid, d_debut, d_fin in rows:
        # Tronque l'indisponibilité à la fenêtre demandée (bornes inclusives).
        jour = max(d_debut, debut)
        borne = min(d_fin, fin)
        jours = out.setdefault(cid, set())
        while jour <= borne:
            jours.add(jour)
            jour += un
    return out


def chantier_card(chantier_id, company):
    """S8 — fiche-carte LECTURE SEULE d'un chantier (Installation) pour le
    partage dans la messagerie. Scopée société : None si le chantier n'appartient
    pas à la société. Format {label, subtitle, url}."""
    from .models import Installation
    chantier = (Installation.objects.filter(pk=chantier_id, company=company)
                .select_related('client').first())
    if chantier is None:
        return None
    parts = []
    try:
        parts.append(chantier.get_statut_display())
    except Exception:  # pragma: no cover - défensif
        pass
    client = getattr(chantier, 'client', None)
    if client is not None:
        parts.append(str(client))
    if getattr(chantier, 'site_ville', None):
        parts.append(chantier.site_ville)
    return {
        'label': f'Chantier {chantier.reference}',
        'subtitle': ' · '.join(p for p in parts if p),
        'url': f'/installations/{chantier.pk}',
    }


def sous_traitant_attestations_manquantes(sous_traitant, a_la_date=None):
    """FG307 — liste des pièces obligatoires expirées/manquantes d'un
    sous-traitant à une date (aujourd'hui par défaut). Lecture seule.

    Une pièce OBLIGATOIRE invalide (expirée) compte ; une attestation absente
    n'est PAS énumérée ici (on ne devine pas le référentiel exigé), mais
    ``sous_traitant_affectable`` ci-dessous traite l'absence totale comme un
    blocage explicite côté appelant. Renvoie une liste de dicts
    {type_piece, date_expiration}."""
    manquantes = []
    for att in sous_traitant.attestations.all():
        if att.obligatoire and not att.est_valide(a_la_date):
            manquantes.append({
                'type_piece': att.type_piece,
                'date_expiration': att.date_expiration,
            })
    return manquantes


def sous_traitant_affectable(sous_traitant, a_la_date=None):
    """FG307 — vrai si le sous-traitant peut être affecté à une date : actif ET
    aucune pièce obligatoire expirée. Lecture seule, point d'entrée cross-app
    (le planning/l'affectation lisent ce sélecteur plutôt que la table
    d'attestations directement)."""
    if not getattr(sous_traitant, 'actif', True):
        return False
    return not sous_traitant_attestations_manquantes(sous_traitant, a_la_date)


def sous_traitant_scorecard(sous_traitant):
    """FG308 — scorecard cumulée d'un sous-traitant : moyenne de chaque axe
    (qualité / délai / sécurité) et note globale sur toutes ses évaluations.
    Lecture seule, point d'entrée cross-app. Renvoie un dict (None si aucune
    évaluation)."""
    from django.db.models import Avg
    agg = sous_traitant.evaluations.aggregate(
        qualite=Avg('note_qualite'),
        delai=Avg('note_delai'),
        securite=Avg('note_securite'),
    )
    nb = sous_traitant.evaluations.count()
    if nb == 0:
        return {
            'nb_evaluations': 0,
            'note_qualite': None,
            'note_delai': None,
            'note_securite': None,
            'note_globale': None,
        }

    def _r(v):
        return round(v, 2) if v is not None else None

    moyennes = [agg['qualite'], agg['delai'], agg['securite']]
    valides = [m for m in moyennes if m is not None]
    globale = round(sum(valides) / len(valides), 2) if valides else None
    return {
        'nb_evaluations': nb,
        'note_qualite': _r(agg['qualite']),
        'note_delai': _r(agg['delai']),
        'note_securite': _r(agg['securite']),
        'note_globale': globale,
    }


def rfq_comparatif(rfq):
    """FG311 — comparatif des offres d'une RFQ : nombre d'offres, offre la moins
    chère, offre la plus rapide (délai), offre retenue. Lecture seule, point
    d'entrée cross-app. Montants INTERNES. Renvoie un dict."""
    offres = list(rfq.offres.all())
    if not offres:
        return {
            'nb_offres': 0,
            'moins_chere_id': None,
            'plus_rapide_id': None,
            'retenue_id': None,
        }
    moins_chere = min(offres, key=lambda o: o.montant_ht)
    avec_delai = [o for o in offres if o.delai_jours is not None]
    plus_rapide = min(avec_delai, key=lambda o: o.delai_jours) if (
        avec_delai) else None
    retenue = next((o for o in offres if o.retenue), None)
    return {
        'nb_offres': len(offres),
        'moins_chere_id': moins_chere.id,
        'plus_rapide_id': plus_rapide.id if plus_rapide else None,
        'retenue_id': retenue.id if retenue else None,
    }


def bcf_montant_achat(company, bcf_id):
    """FG312 — total d'achat HT d'un bon de commande fournisseur scopé société
    (0 si introuvable). Lu via ``apps.get_model`` — aucune arête d'import vers
    ``stock`` au chargement. Montant INTERNE."""
    from decimal import Decimal
    from django.apps import apps as django_apps
    model = django_apps.get_model('stock', 'BonCommandeFournisseur')
    bcf = model.objects.filter(id=bcf_id, company=company).first()
    if bcf is None:
        return Decimal('0')
    return _dec(bcf.total_achat)


def seuil_approbation_bcf_actif(company):
    """FG312 — le seuil d'approbation BCF actif d'une société (ou None). Lecture
    seule."""
    from .models import SeuilApprobationBCF
    return (SeuilApprobationBCF.objects
            .filter(company=company, actif=True)
            .order_by('-date_creation')
            .first())


def palier_requis_bcf(company, montant):
    """FG312 — palier requis (responsable/admin) pour approuver un BCF de
    ``montant`` selon le seuil actif. Sans seuil configuré, le défaut est
    « admin » (prudence : tout achat exige le palier le plus haut). Lecture
    seule."""
    from .models_approbation_bcf import PALIER_ADMIN
    seuil = seuil_approbation_bcf_actif(company)
    if seuil is None:
        return PALIER_ADMIN
    return seuil.palier_requis(montant)


def controle_budgetaire_commande(company, montant, *, projet_id=None,
                                 categorie='materiel'):
    """FG313 — contrôle budgétaire AVANT de valider une commande : un montant
    d'achat prévu tient-il dans le budget restant du programme ?

    Compare ``montant`` au reste de la catégorie (``materiel`` par défaut) du
    ``BudgetProjet`` du programme (engagé déjà déduit), et au reste total. Sans
    budget configuré pour le programme, on n'a pas de référence : ``controle =
    'non_configure'`` (l'appelant décide — on ne bloque pas faute de budget).
    Lecture seule, import-linter safe. Montants INTERNES. Renvoie un dict plat."""
    from decimal import Decimal
    from .models import BudgetProjet

    montant = _dec(montant)
    if not projet_id:
        return {
            'controle': 'non_configure',
            'depasse': False,
            'reste_categorie': None,
            'reste_total': None,
            'montant': float(montant),
        }
    budget = (BudgetProjet.objects
              .filter(company=company, projet_id=projet_id)
              .select_related('projet')
              .first())
    if budget is None:
        return {
            'controle': 'non_configure',
            'depasse': False,
            'reste_categorie': None,
            'reste_total': None,
            'montant': float(montant),
        }
    synthese = budget_projet_synthese(budget)
    budget_cat = Decimal(str(synthese['budget'].get(categorie, 0)))
    engage_cat = Decimal(str(synthese['engage'].get(categorie, 0)))
    reste_cat = budget_cat - engage_cat
    reste_total = Decimal(str(synthese['budget']['total'])) - Decimal(
        str(synthese['engage']['total']))
    depasse = montant > reste_cat
    return {
        'controle': 'ok' if not depasse else 'depassement',
        'depasse': depasse,
        'categorie': categorie,
        'reste_categorie': float(reste_cat),
        'reste_total': float(reste_total),
        'montant': float(montant),
    }


def landed_cost_dossier(dossier):
    """FG316 — coût de revient débarqué (landed cost) d'un dossier d'import.

    Répartit le TOTAL des frais (``FraisImport``) sur les lignes de SKU
    (``LandedCostLigne``) AU PRORATA de leur valeur FOB, puis renvoie, par ligne,
    la quote-part de frais, le coût débarqué total et le coût débarqué unitaire.
    Montants INTERNES — jamais client-facing. Lecture seule, import-linter safe.
    Renvoie un dict {total_fob, total_frais, total_landed, lignes:[...]}."""
    from decimal import Decimal

    lignes = list(dossier.landed_lignes.all())
    total_frais = sum((f.montant for f in dossier.frais.all()), Decimal('0'))
    total_fob = sum((ln.valeur_fob for ln in lignes), Decimal('0'))

    details = []
    total_landed = Decimal('0')
    for ln in lignes:
        if total_fob > 0:
            quote_part = (total_frais * ln.valeur_fob / total_fob).quantize(
                Decimal('0.01'))
        else:
            quote_part = Decimal('0')
        landed_total = (ln.valeur_fob or Decimal('0')) + quote_part
        q = ln.quantite or Decimal('0')
        landed_unitaire = (
            (landed_total / q).quantize(Decimal('0.01'))
            if q else Decimal('0'))
        total_landed += landed_total
        details.append({
            'ligne_id': ln.id,
            'produit_id': ln.produit_id,
            'designation': ln.designation,
            'quantite': float(q),
            'valeur_fob': float(ln.valeur_fob or Decimal('0')),
            'quote_part_frais': float(quote_part),
            'cout_debarque_total': float(landed_total),
            'cout_debarque_unitaire': float(landed_unitaire),
        })
    return {
        'dossier_id': dossier.id,
        'total_fob': float(total_fob),
        'total_frais': float(total_frais),
        'total_landed': float(total_landed),
        'lignes': details,
    }
