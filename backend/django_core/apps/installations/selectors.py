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


def demandes_achat_soumises_stale(company, cutoff):
    """VX213 (d) — réquisitions d'achat restées SOUMISE (jamais décidées) et
    inchangées depuis ``cutoff`` (datetime seuil). Lecture seule, exposée au
    balayage SLA de ``notifications`` (miroir de ``_sweep_sav_breaching``).

    ``date_modification`` (auto_now) reflète la dernière touche : une DA soumise
    non décidée n'est plus modifiée, donc c'est le proxy de « soumise depuis ».
    Scopée company ; le sweep en dérive les approbateurs (managers)."""
    from .models import DemandeAchat
    return (DemandeAchat.objects
            .filter(company=company,
                    statut=DemandeAchat.Statut.SOUMISE,
                    date_modification__lte=cutoff)
            .select_related('chantier'))


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


def intervention_recente_pour_chantier(company, installation_id, *,
                                       depuis_jours, avant=None,
                                       exclure_ticket_id=None):
    """XFSM15 — la plus récente ``Intervention`` TERMINÉE/VALIDÉE du même
    chantier dans les ``depuis_jours`` derniers jours (avant ``avant``, ou
    aujourd'hui). Sert à suggérer une récidive à la création d'un ticket SAV
    sans que ``apps.sav`` importe ``installations.models`` directement.

    ``exclure_ticket_id`` écarte l'intervention déjà liée au ticket en cours
    d'édition (évite qu'un ticket se suggère lui-même comme son origine).
    Renvoie ``None`` si aucune intervention récente ne matche."""
    from django.utils import timezone
    from .models import Intervention

    if not installation_id or not depuis_jours:
        return None
    avant = avant or timezone.localdate()
    seuil = avant - timezone.timedelta(days=int(depuis_jours))
    statuts_ok = [Intervention.Statut.TERMINEE, Intervention.Statut.VALIDEE]
    qs = (Intervention.objects
          .filter(company=company, installation_id=installation_id,
                  statut__in=statuts_ok, date_realisee__isnull=False,
                  date_realisee__gte=seuil, date_realisee__lte=avant)
          .order_by('-date_realisee'))
    if exclure_ticket_id:
        qs = qs.exclude(ticket_id=exclure_ticket_id)
    return qs.first()


def interventions_ouvertes_pour_ticket(ticket_id):
    """YSERV2 — Interventions liées à ``ticket_id`` PAS ENCORE TERMINÉE/
    VALIDÉE. Point d'entrée cross-app en LECTURE SEULE pour la garde de
    clôture ``apps.sav.views.TicketViewSet`` (jamais un import du modèle
    ``Intervention`` depuis ``sav``). Renvoie une liste de dicts plats
    (jamais l'instance ORM) — vide si aucune intervention liée."""
    from .models import Intervention

    if not ticket_id:
        return []
    statuts_ouverts = [
        s for s in Intervention.Statut.values
        if s not in (Intervention.Statut.TERMINEE, Intervention.Statut.VALIDEE)
    ]
    qs = Intervention.objects.filter(
        ticket_id=ticket_id, statut__in=statuts_ouverts)
    return [{'id': i.id, 'statut': i.statut} for i in qs]


def reserved_quantity_for_produit(produit):
    """Quantité d'un produit ENGAGÉE par des réservations actives et non
    encore consommées — chantier (N14) + ordre d'assemblage (XMFG2). Lecture
    seule."""
    agg = (_active_reservations()
           .filter(produit=produit)
           .aggregate(total=Sum('quantite')))
    agg_asm = (_active_reservations_assemblage()
               .filter(produit=produit)
               .aggregate(total=Sum('quantite')))
    return (agg['total'] or 0) + (agg_asm['total'] or 0)


def serie_entrepot_scoped_by_serial(company, produit_id, numero_serie):
    """ZSTK6 — `SerieEntrepot` (FG323) scopée société, par (produit, n° de
    série), avec chantier + client préchargés. Point d'entrée cross-app pour
    le résolveur de scan de `apps.stock` (jamais son modèle importé
    directement) — LECTURE SEULE, None si introuvable/hors société."""
    from .models import SerieEntrepot
    return (SerieEntrepot.objects
            .filter(company=company, produit_id=produit_id,
                    numero_serie=numero_serie)
            .select_related('installation', 'installation__client')
            .first())


def reserved_quantities_for_company(company):
    """Map {produit_id: quantité réservée active} pour toute la société —
    chantier (N14) + ordre d'assemblage (XMFG2), un seul agrégat par source
    (évite un N+1 sur la liste produits). Lecture seule."""
    rows = (_active_reservations()
            .filter(company=company)
            .values('produit_id')
            .annotate(total=Sum('quantite')))
    out = {r['produit_id']: (r['total'] or 0) for r in rows}
    rows_asm = (_active_reservations_assemblage()
                .filter(company=company)
                .values('produit_id')
                .annotate(total=Sum('quantite')))
    for r in rows_asm:
        out[r['produit_id']] = out.get(r['produit_id'], 0) + (r['total'] or 0)
    return out


def _active_reservations_assemblage():
    from .models import ReservationAssemblage
    return ReservationAssemblage.objects.filter(active=True, consomme=False)


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


# ── XMFG3 — Assembler-à-la-commande : kit actif par produit composite ────────

def kit_map_for_produits_composes(company, produit_ids):
    """XMFG3 — map {produit_id: kit_id} pour les produits qui sont l'article
    composite (`produit_compose`) d'un KIT ACTIF de cette société. Point
    d'entrée cross-app pour `stock` (réappro FG54/FG364 : distinguer
    « acheter » de « assembler N »). Lecture seule."""
    from .models import Kit
    if not produit_ids:
        return {}
    rows = (Kit.objects
            .filter(company=company, active=True,
                    produit_compose_id__in=produit_ids)
            .values_list('produit_compose_id', 'id'))
    return {pid: kid for pid, kid in rows}


def materiel_consigne_quantite_totale(company):
    """YSTCK8 — quantité TOTALE de matériel consigné DÉTENU (FG327,
    `MaterielConsigne`, non possédé — jamais valorisé). Point d'entrée
    cross-app pour `stock` (garde de valorisation
    `stock_valuation_excludes_materiel_consigne`), lecture seule."""
    from django.db.models import Sum
    from .models_consignation import MaterielConsigne
    agg = (MaterielConsigne.objects
           .filter(company=company, statut=MaterielConsigne.Statut.DETENU)
           .aggregate(total=Sum('quantite')))
    return agg['total'] or 0


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


def membres_intervention(interv):
    """DC40 — membres (ids d'utilisateurs) affectés à une intervention, résolus
    via l'équipe terrain CANONIQUE.

    Une seule DÉFINITION d'équipe : quand ``equipe_ref`` (FK → ``Equipe``) est
    posée, les membres proviennent de l'équipe canonique (``Equipe.membres``) ;
    sinon on retombe sur le M2M ad-hoc historique (``Intervention.equipe``). Le
    ``technicien`` principal est toujours inclus s'il existe. Utilise les caches
    de prefetch (``.all()``) — jamais de requête par intervention (pas de N+1).

    Renvoie un ``set`` d'ids d'utilisateurs (sans doublon)."""
    membres = set()
    if interv.technicien_id:
        membres.add(interv.technicien_id)
    equipe_ref = getattr(interv, 'equipe_ref', None)
    if equipe_ref is not None:
        # Équipe CANONIQUE : les membres proviennent d'``Equipe.membres``.
        for membre in equipe_ref.membres.all():
            membres.add(membre.id)
    else:
        # Repli sur le M2M ad-hoc historique de l'intervention.
        for membre in interv.equipe.all():
            membres.add(membre.id)
    return membres


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

    # DC40 — on résout les membres via l'équipe terrain CANONIQUE
    # (``equipe_ref``) quand elle est posée, sinon via le M2M ad-hoc historique.
    # On prefetch les DEUX pour éviter tout N+1 (``membres_intervention``).
    qs = (Intervention.objects
          .filter(company=company, annulee=False)
          .filter(date_prevue__gte=debut, date_prevue__lte=fin)
          .prefetch_related('equipe', 'equipe_ref__membres')
          .only('id', 'technicien_id', 'date_prevue', 'equipe_ref_id'))

    # {user_id|None: set(intervention_id)} — un set évite de compter deux fois
    # une intervention où un technicien est À LA FOIS principal et membre.
    affecte = OrderedDict()
    non_assigne = set()
    for interv in qs:
        # Membres résolus via l'équipe canonique (repli M2M ad-hoc) — DC40.
        membres = membres_intervention(interv)
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

    # DC40 — résolution des membres via l'équipe CANONIQUE (repli M2M ad-hoc).
    qs = (Intervention.objects
          .filter(company=company)
          .filter(date_prevue__gte=debut, date_prevue__lte=fin)
          .filter(date_prevue__isnull=False)
          .prefetch_related('equipe', 'equipe_ref__membres')
          .only('id', 'installation_id', 'type_intervention',
                'technicien_id', 'date_prevue', 'equipe_ref_id'))

    # {user_id: OrderedDict{intervention_id: interv}} — affectation par technicien.
    # Un OrderedDict évite de compter deux fois une intervention où un technicien
    # est À LA FOIS principal ET membre d'équipe (clé = id).
    affecte = OrderedDict()
    # {user_id: set(jour)} — jours déjà occupés par chaque technicien (pour ne pas
    # recréer un conflit FG300 en déplaçant une intervention vers lui).
    jours_occupes = {}

    for interv in qs.order_by('date_prevue', 'id'):
        membres = membres_intervention(interv)
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

    # DC40 — membres résolus via l'équipe CANONIQUE (repli M2M ad-hoc).
    qs = (Intervention.objects
          .filter(company=company)
          .filter(date_prevue__gte=debut, date_prevue__lte=fin)
          .filter(date_prevue__isnull=False)
          .select_related('camionnette')
          .prefetch_related('equipe', 'equipe_ref__membres')
          .only('id', 'installation_id', 'type_intervention', 'statut',
                'date_prevue', 'technicien_id', 'camionnette_id',
                'equipe_ref_id', 'camionnette__nom'))

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
        # Membres = technicien principal + équipe canonique (repli ad-hoc) —
        # ``_add`` déduplique déjà par créneau, mais on couvre chaque membre.
        for membre_id in membres_intervention(interv):
            tech_ids.add(membre_id)
            _add(jour, 'technicien', membre_id, interv)
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
    # DC34 — `sous_traitant` est un stock.Fournisseur(type='service') ; ses
    # attestations sont accessibles via le related_name `installations_*`.
    for att in sous_traitant.installations_attestations.all():
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
    d'attestations directement).

    DC34 — le drapeau ``actif`` vit désormais sur le profil sous-traitant
    (``stock.SousTraitantProfile``) porté par le Fournisseur ; on le lit à
    travers le sélecteur stock (jamais d'import de apps.stock.models)."""
    from apps.stock.selectors import sous_traitant_est_actif
    if not sous_traitant_est_actif(sous_traitant):
        return False
    return not sous_traitant_attestations_manquantes(sous_traitant, a_la_date)


def sous_traitant_scorecard(sous_traitant):
    """FG308 — scorecard cumulée d'un sous-traitant : moyenne de chaque axe
    (qualité / délai / sécurité) et note globale sur toutes ses évaluations.
    Lecture seule, point d'entrée cross-app. Renvoie un dict (None si aucune
    évaluation)."""
    from django.db.models import Avg
    # DC34 — `sous_traitant` est un stock.Fournisseur(type='service') ; ses
    # évaluations sont accessibles via le related_name `installations_*`.
    agg = sous_traitant.installations_evaluations.aggregate(
        qualite=Avg('note_qualite'),
        delai=Avg('note_delai'),
        securite=Avg('note_securite'),
    )
    nb = sous_traitant.installations_evaluations.count()
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


def bcf_approbation_valide(company, bcf_id, montant):
    """YPROC4 — l'ENVOI d'un BCF est-il autorisé côté approbation FG312 ?

    Sans seuil ``SeuilApprobationBCF`` actif configuré pour la société :
    ``True`` (compatibilité totale — le workflow d'approbation n'existe pas
    pour cette société, comportement historique inchangé).

    Avec un seuil actif : exige une ``ApprobationBCF`` existante pour ce BCF,
    au palier requis par le montant ACTUEL (``palier_requis_bcf``), ET dont le
    ``montant_approuve`` couvre au moins ce montant actuel — une hausse du
    total du BCF depuis l'approbation invalide celle-ci (cohérent avec la
    ré-approbation XPUR18). Lecture seule, jamais d'écriture ici."""
    from decimal import Decimal
    from .models_approbation_bcf import ApprobationBCF

    seuil = seuil_approbation_bcf_actif(company)
    if seuil is None:
        return True

    montant = montant or Decimal('0')
    palier_requis = seuil.palier_requis(montant)
    approbation = (ApprobationBCF.objects
                   .filter(company=company, bcf_id=bcf_id)
                   .order_by('-date_approbation')
                   .first())
    if approbation is None:
        return False
    if approbation.palier != palier_requis:
        return False
    if (approbation.montant_approuve or Decimal('0')) < montant:
        return False
    return True


def palier_manquant_bcf_detail(company, montant):
    """YPROC4 — libellé FR du palier requis pour le message de refus 400
    quand ``bcf_approbation_valide`` est faux (jamais utilisé pour bloquer
    directement — seulement pour le message)."""
    from .models_approbation_bcf import PALIER_CHOICES
    palier = palier_requis_bcf(company, montant)
    libelles = dict(PALIER_CHOICES)
    return libelles.get(palier, palier)


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


def prix_convenu_fournisseur(company, produit_id, *, fournisseur_id=None,
                             a_la_date=None):
    """FG318 — prix convenu d'un produit auprès d'un fournisseur À UNE DATE,
    d'après les contrats de prix EN VIGUEUR (actif + période couvrante). Si
    plusieurs contrats matchent, on prend la plus haute version. Lecture seule,
    montants INTERNES. Renvoie un dict (prix None si aucun accord en vigueur)."""
    from .models import ContratPrixLigne

    qs = (ContratPrixLigne.objects
          .filter(contrat__company=company, produit_id=produit_id)
          .select_related('contrat'))
    if fournisseur_id:
        qs = qs.filter(contrat__fournisseur_id=fournisseur_id)
    candidates = [
        ln for ln in qs if ln.contrat.est_en_vigueur(a_la_date)
    ]
    if not candidates:
        return {
            'produit_id': produit_id,
            'prix_convenu': None,
            'remise_pct': None,
            'contrat_id': None,
            'version': None,
        }
    meilleur = max(candidates, key=lambda ln: ln.contrat.version)
    return {
        'produit_id': produit_id,
        'prix_convenu': float(meilleur.prix_convenu),
        'remise_pct': (
            float(meilleur.remise_pct)
            if meilleur.remise_pct is not None else None),
        'contrat_id': meilleur.contrat_id,
        'version': meilleur.contrat.version,
    }


def _bin_respecte_capacite(bin_loc, produit_id, quantite):
    """ZSTK9 - le casier respecte-t-il la capacite/compatibilite de sa
    categorie de stockage pour CETTE quantite entrante ? Sans categorie posee
    sur le casier, toujours True (comportement historique inchange)."""
    cat = getattr(bin_loc, 'categorie', None)
    if cat is None:
        return True
    from django.db.models import Sum
    from .models import BinAffectation
    existantes = BinAffectation.objects.filter(bin=bin_loc)
    if not cat.melange_autorise:
        autre_produit = existantes.exclude(produit_id=produit_id).exists()
        if autre_produit:
            return False
    if cat.qte_max is not None:
        deja = existantes.filter(produit_id=produit_id).aggregate(
            total=Sum('quantite'))['total'] or 0
        if deja + (quantite or 0) > cat.qte_max:
            return False
    return True


def _bin_cible_regle(company, produit_id, emplacement_id=None):
    """ZSTK9 - casier cible depuis la premiere `RegleRangement` ACTIVE
    applicable (par priorite croissante), ou None sans regle. Une regle par
    `produit` prime sur une regle par `categorie_produit` de meme priorite
    (ordre naturel de la requete : produit d'abord)."""
    from .models_storage_rules import RegleRangement
    qs = RegleRangement.objects.filter(
        company=company, actif=True, bin_cible__archived=False)
    if emplacement_id:
        qs = qs.filter(bin_cible__emplacement_id=emplacement_id)
    par_produit = qs.filter(produit_id=produit_id).select_related(
        'bin_cible').order_by('priorite', 'id').first()
    if par_produit is not None:
        return par_produit.bin_cible

    produit = None
    try:
        from apps.stock.selectors import get_produit_scoped
        produit = get_produit_scoped(company, produit_id)
    except Exception:  # pragma: no cover - defensif
        produit = None
    categorie_nom = (
        getattr(produit.categorie, 'nom', None)
        if produit is not None and produit.categorie_id else None)
    if not categorie_nom:
        return None
    par_categorie = qs.filter(
        categorie_produit__iexact=categorie_nom).select_related(
        'bin_cible').order_by('priorite', 'id').first()
    return par_categorie.bin_cible if par_categorie is not None else None


def suggerer_bin_putaway(company, produit_id, emplacement_id=None,
                         quantite=0):
    """FG320/ZSTK9 - casier suggere pour ranger un produit recu.

    Priorite 0 (ZSTK9) : une `RegleRangement` ACTIVE applicable (par produit
    ou categorie produit, priorite croissante) dont le casier respecte sa
    capacite/compatibilite (`CategorieStockage`) pour la quantite entrante.
    Priorite 1 : un casier deja affecte a ce produit (FG319 BinAffectation),
    le plus rempli d'abord (sous la meme garde de capacite). Priorite 2 : le
    premier casier non archive de l'emplacement, par ordre de parcours, dont
    la capacite n'est pas depassee. Sans regle ni categorie posee nulle part,
    le comportement reste BYTE-IDENTIQUE a l'historique (FG320)."""
    from .models import BinLocation, BinAffectation

    regle_bin = _bin_cible_regle(company, produit_id, emplacement_id)
    if regle_bin is not None and _bin_respecte_capacite(
            regle_bin, produit_id, quantite):
        return regle_bin

    aff_qs = BinAffectation.objects.filter(
        company=company, produit_id=produit_id, bin__archived=False)
    if emplacement_id:
        aff_qs = aff_qs.filter(bin__emplacement_id=emplacement_id)
    for aff in aff_qs.select_related('bin').order_by('-quantite'):
        if _bin_respecte_capacite(aff.bin, produit_id, quantite):
            return aff.bin

    bin_qs = BinLocation.objects.filter(company=company, archived=False)
    if emplacement_id:
        bin_qs = bin_qs.filter(emplacement_id=emplacement_id)
    for candidate in bin_qs.order_by('ordre', 'code'):
        if _bin_respecte_capacite(candidate, produit_id, quantite):
            return candidate
    return None


def proposer_reapprovisionnement(company, quantites_actuelles=None):
    """FG326 - propositions de reapprovisionnement multi-depots.

    Pour chaque regle active dont le stock courant de l'emplacement cible passe
    sous `seuil_min`, propose un transfert depuis `emplacement_source` pour
    remonter a `seuil_max`. `quantites_actuelles` est un dict optionnel
    {regle_id: quantite} fourni par l'appelant ; a defaut, on lit le stock total
    du produit via stock.selectors (proxy consultatif). Couche de PROPOSITION :
    n'execute aucun mouvement.
    """
    from .models import RegleReappro
    from apps.stock import selectors as stock_selectors
    quantites_actuelles = quantites_actuelles or {}
    regles = RegleReappro.objects.filter(
        company=company, active=True,
    ).select_related('produit', 'emplacement_cible', 'emplacement_source')
    propositions = []
    for regle in regles:
        if regle.id in quantites_actuelles:
            actuel = quantites_actuelles[regle.id]
        else:
            produit = stock_selectors.get_produit_scoped(
                company, regle.produit_id)
            actuel = getattr(produit, 'quantite_stock', 0) or 0
        if actuel < regle.seuil_min:
            a_transferer = max(regle.seuil_max - actuel, 0)
            if a_transferer > 0:
                propositions.append({
                    'regle_id': regle.id,
                    'produit_id': regle.produit_id,
                    'produit_nom': getattr(regle.produit, 'nom', None),
                    'emplacement_cible_id': regle.emplacement_cible_id,
                    'emplacement_source_id': regle.emplacement_source_id,
                    'quantite_actuelle': actuel,
                    'seuil_min': regle.seuil_min,
                    'seuil_max': regle.seuil_max,
                    'quantite_proposee': a_transferer,
                })
    return propositions


def _haversine_km(lat1, lng1, lat2, lng2):
    """Distance approximative (km) entre deux points GPS (formule de Haversine)."""
    from math import radians, sin, cos, asin, sqrt
    lat1, lng1, lat2, lng2 = map(
        lambda v: radians(float(v)), (lat1, lng1, lat2, lng2))
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlng / 2) ** 2
    return 2 * 6371.0 * asin(sqrt(a))


def optimiser_tournee_livraison(company, jour, depart_lat=None,
                                depart_lng=None):
    """FG332 - ordonne les livraisons d'un jour par proximite (tournee).

    Recupere les livraisons planifiees/en transit de `jour`, lit la position GPS
    du SITE de chaque chantier, et les ordonne par plus proche voisin a partir
    d'un point de depart (le depot, si fourni, sinon la premiere livraison
    geolocalisee). Les livraisons sans GPS sont listees a la fin (non
    ordonnables). Lecture seule, consultative - n'execute aucune livraison.
    """
    from .models import Livraison
    qs = Livraison.objects.filter(
        company=company, date_prevue=jour,
        statut__in=[Livraison.Statut.PLANIFIEE, Livraison.Statut.EN_TRANSIT],
    ).select_related('installation')

    geolocalisees = []
    sans_gps = []
    for liv in qs:
        inst = liv.installation
        lat = getattr(inst, 'gps_lat', None)
        lng = getattr(inst, 'gps_lng', None)
        item = {
            'livraison_id': liv.id,
            'reference': liv.reference,
            'installation_id': liv.installation_id,
            'gps_lat': float(lat) if lat is not None else None,
            'gps_lng': float(lng) if lng is not None else None,
        }
        if lat is not None and lng is not None:
            geolocalisees.append(item)
        else:
            sans_gps.append(item)

    ordre = []
    restantes = list(geolocalisees)
    if restantes:
        if depart_lat is not None and depart_lng is not None:
            cur_lat, cur_lng = float(depart_lat), float(depart_lng)
        else:
            premiere = restantes.pop(0)
            premiere['ordre'] = 1
            ordre.append(premiere)
            cur_lat, cur_lng = premiere['gps_lat'], premiere['gps_lng']
        while restantes:
            prochain = min(restantes, key=lambda it: _haversine_km(
                cur_lat, cur_lng, it['gps_lat'], it['gps_lng']))
            prochain['ordre'] = len(ordre) + 1
            ordre.append(prochain)
            restantes.remove(prochain)
            cur_lat, cur_lng = prochain['gps_lat'], prochain['gps_lng']

    for item in sans_gps:
        item['ordre'] = None

    return {
        'jour': str(jour),
        'tournee': ordre,
        'sans_gps': sans_gps,
        'total': len(ordre) + len(sans_gps),
    }


def emplacement_a_decrementer_livraison(livraison):
    """FG333 - quel emplacement decrementer pour une livraison.

    En mode `depot`, c'est le depot de la livraison (le materiel y transite et
    en sort). En mode `direct_site`, le materiel est livre DIRECTEMENT sur site
    par le fournisseur sans passer par le depot : aucun emplacement a
    decrementer (retourne None). La decrementation reelle reste pilotee par le
    module stock ; ce helper lui indique la cible.
    """
    from .models import Livraison
    if livraison.mode_acheminement == Livraison.ModeAcheminement.DIRECT_SITE:
        return None
    return livraison.depot


# ── XKB1 — boîte d'approbations centralisée (lecture cross-app) ──────────────

def demandes_achat_en_attente(company):
    """XKB1 — réquisitions d'achat (FG310) SOUMISES d'une société (QuerySet).

    Sélecteur company-wide LECTURE SEULE utilisé par l'agrégateur
    d'approbations cross-app (``apps/reporting``). « En attente » = statut
    ``SOUMISE`` (seul statut approuvable, cf. ``DemandeAchatViewSet.approuver``).
    """
    from .models import DemandeAchat
    return (DemandeAchat.objects
            .filter(company=company, statut=DemandeAchat.Statut.SOUMISE)
            .select_related('chantier', 'programme')
            .order_by('date_besoin', 'id'))


# ── XSTK22 — suivi de livraison côté client (portail FG228) ─────────────────

def livraisons_client_portail(company, client_id):
    """XSTK22 — livraisons SCOPÉES à un client (celles de SES chantiers),
    au format PLAT attendu par le portail : date prévue, statut, numéro de
    suivi, articles (désignation/quantité SEULEMENT), et un lien de
    téléchargement de la preuve de livraison (FG330) une fois livrée.

    N'expose JAMAIS ``cout_transport`` ni un prix d'achat — c'est le contrat
    de ce sélecteur (testé). Lecture seule, scopée société ET client (jamais
    les livraisons d'un autre client)."""
    from .models import Livraison

    qs = (Livraison.objects
          .filter(company=company, installation__client_id=client_id)
          .select_related('installation')
          .prefetch_related('lignes', 'preuve')
          .order_by('-date_prevue', '-date_creation'))

    out = []
    for liv in qs:
        preuve = getattr(liv, 'preuve', None)
        out.append({
            'id': liv.id,
            'reference': liv.reference,
            'chantier_id': liv.installation_id,
            'date_prevue': liv.date_prevue,
            'statut': liv.statut,
            'statut_display': liv.get_statut_display(),
            'numero_suivi': liv.numero_suivi,
            'articles': [
                {'designation': ligne.designation
                 or (ligne.produit.nom if ligne.produit_id else ''),
                 'quantite': ligne.quantite}
                for ligne in liv.lignes.all()
            ],
            'pod_disponible': preuve is not None,
            'pod_url': (
                f'/api/django/installations/preuves-livraison/'
                f'{preuve.id}/' if preuve is not None else None),
        })
    return out


# ── XMFG15 — Analyse d'écarts par ordre + tableau de bord atelier ────────────
# Coût composants PRÉVU (BOM/lignes × cout_achat_courant) vs CONSOMMÉ réel
# (mouvements XMFG1 SORTIE + rebuts XMFG11 REBUT rattachés à la référence de
# l'ordre), temps prévu vs réel (XMFG14 `totaux_temps_ordre`). RESPONSABLE/
# ADMIN uniquement (coûts d'achat) — la permission est vérifiée côté vue.

def analyse_ecarts_ordre(ordre):
    """XMFG15 — analyse prévu-vs-réel d'un ordre d'assemblage : coût composants
    (prévu = BOM/lignes valorisées au coût d'achat courant ; réel = mouvements
    SORTIE + REBUT rattachés à ``ordre.reference``) et temps (XMFG14). Renvoie
    un dict PLAT :
      ``cout``: {prevu, reel, ecart, ecart_pct}
      ``temps``: {prevu, reel, ecart, complet} (minutes — XMFG14, `None` si
        aucune durée attendue n'est renseignée)
      ``rebut``: {quantite, cout} (partie du coût réel imputable au rebut)
    Lecture seule, ne mute rien."""
    from decimal import Decimal
    from apps.stock.selectors import mouvements_par_reference
    from .services import cout_prevu_assemblage, totaux_temps_ordre

    cout_prevu = cout_prevu_assemblage(ordre)

    cout_reel = Decimal('0')
    cout_rebut = Decimal('0')
    qte_rebut = 0
    for mvt in mouvements_par_reference(ordre.company, ordre.reference):
        prix = getattr(mvt.produit, 'prix_achat', None) or Decimal('0')
        montant = Decimal(str(mvt.quantite)) * Decimal(str(prix))
        if mvt.type_mouvement == 'sortie':
            cout_reel += montant
        elif mvt.type_mouvement == 'rebut':
            cout_reel += montant
            cout_rebut += montant
            qte_rebut += mvt.quantite

    ecart_cout = cout_reel - cout_prevu
    ecart_pct = (float(ecart_cout / cout_prevu * 100)
                 if cout_prevu else (0.0 if cout_reel == 0 else None))

    temps = totaux_temps_ordre(ordre)
    temps_prevu = temps['prevu']
    temps_ecart = (
        temps['reel'] - temps_prevu if temps_prevu is not None else None)

    return {
        'ordre_id': ordre.id,
        'reference': ordre.reference,
        'cout': {
            'prevu': float(cout_prevu),
            'reel': float(cout_reel),
            'ecart': float(ecart_cout),
            'ecart_pct': ecart_pct,
        },
        'temps': {
            'prevu': temps_prevu,
            'reel': temps['reel'],
            'ecart': temps_ecart,
            'complet': temps['complet'],
        },
        'rebut': {
            'quantite': qte_rebut,
            'cout': float(cout_rebut),
        },
    }


def panneau_atelier(company, *, date_debut=None, date_fin=None):
    """XMFG15 — panneau « Atelier » : ordres en retard (date_prevue dépassée,
    non terminés/annulés), en cours, terminés sur la période, taux de rebut
    (quantité rebutée / quantité totale consommée+rebutée sur les ordres
    terminés de la période), écart moyen (%) de coût sur les ordres terminés
    de la période. Filtrable par période (``date_creation`` pour les ordres
    en cours, ``date_terminaison`` pour les terminés). Lecture seule, scopée
    société."""
    from datetime import date as _date
    from .models import OrdreAssemblage

    today = _date.today()

    en_retard = list(OrdreAssemblage.objects.filter(
        company=company, statut=OrdreAssemblage.Statut.PLANIFIE,
        date_prevue__lt=today).select_related('kit'))
    en_cours = list(OrdreAssemblage.objects.filter(
        company=company, statut=OrdreAssemblage.Statut.EN_COURS)
        .select_related('kit'))

    termines_qs = OrdreAssemblage.objects.filter(
        company=company, statut=OrdreAssemblage.Statut.TERMINE)
    if date_debut is not None:
        termines_qs = termines_qs.filter(date_terminaison__date__gte=date_debut)
    if date_fin is not None:
        termines_qs = termines_qs.filter(date_terminaison__date__lte=date_fin)
    termines = list(termines_qs.select_related('kit'))

    qte_rebut_totale = 0
    qte_consomme_totale = 0
    ecarts_pct = []
    for ordre in termines:
        analyse = analyse_ecarts_ordre(ordre)
        qte_rebut_totale += analyse['rebut']['quantite']
        cout_prevu = analyse['cout']['prevu']
        if cout_prevu:
            qte_consomme_totale += 1  # comptage d'ordres, pas de quantité brute
        if analyse['cout']['ecart_pct'] is not None:
            ecarts_pct.append(analyse['cout']['ecart_pct'])

    taux_rebut = (
        qte_rebut_totale / max(len(termines), 1) if termines else 0.0)
    ecart_moyen_pct = (
        sum(ecarts_pct) / len(ecarts_pct) if ecarts_pct else 0.0)

    def _card(ordre):
        return {
            'id': ordre.id, 'reference': ordre.reference,
            'kit_id': ordre.kit_id,
            'kit_nom': getattr(ordre.kit, 'nom', None),
            'date_prevue': ordre.date_prevue,
            'statut': ordre.statut,
        }

    return {
        'debut': date_debut, 'fin': date_fin,
        'en_retard': [_card(o) for o in en_retard],
        'en_cours': [_card(o) for o in en_cours],
        'termines': [_card(o) for o in termines],
        'totaux': {
            'nb_en_retard': len(en_retard),
            'nb_en_cours': len(en_cours),
            'nb_termines': len(termines),
            'taux_rebut_moyen': round(taux_rebut, 2),
            'ecart_cout_moyen_pct': round(ecart_moyen_pct, 2),
        },
    }


# ── XFSM5 — Fenêtres de RDV promises + taux de ponctualité ───────────────────

def taux_ponctualite(company, *, debut=None, fin=None, technicien_id=None):
    """XFSM5 — KPI « taux d'arrivée à l'heure » : proportion des interventions
    ARRIVÉES (`arrivee_site_le` renseigné) dont `arrivee_dans_fenetre` est
    True, parmi celles où une fenêtre était promise et où l'arrivée a eu
    lieu. Filtrable par période (`arrivee_site_le`) et par technicien.
    Lecture seule via `apps.installations.selectors` (jamais d'import de
    models depuis `reporting`). Renvoie un dict PLAT
    {nb_mesurees, nb_a_lheure, taux_pct} — `taux_pct` est None si aucune
    intervention mesurable (jamais de division par zéro)."""
    from .models import Intervention

    qs = Intervention.objects.filter(
        company=company, arrivee_site_le__isnull=False,
        arrivee_dans_fenetre__isnull=False)
    if debut is not None:
        qs = qs.filter(arrivee_site_le__date__gte=debut)
    if fin is not None:
        qs = qs.filter(arrivee_site_le__date__lte=fin)
    if technicien_id is not None:
        qs = qs.filter(technicien_id=technicien_id)

    nb_mesurees = qs.count()
    nb_a_lheure = qs.filter(arrivee_dans_fenetre=True).count()
    taux_pct = (
        round(nb_a_lheure / nb_mesurees * 100, 2) if nb_mesurees else None)
    return {
        'nb_mesurees': nb_mesurees,
        'nb_a_lheure': nb_a_lheure,
        'taux_pct': taux_pct,
    }


# ── XFSM2 — Assistant de planification : créneau + technicien suggérés ──────
# Combine les ingrédients déjà existants (plan de charge FG299, conflits
# FG300, indisponibilités FG302, jours ouvrés, habilitations FG173/176,
# GPS chantier + haversine) SANS RIEN muter : pure lecture, propositions
# classées. Traduit `Intervention.Type` (choix fermé) vers les clés de
# `rh.INTERVENTION_HABILITATIONS` (cadre différent, best-effort — un type
# sans correspondance connue n'exige aucune habilitation).
_TYPE_VERS_HABILITATION = {
    'pose': 'pose_pv_bt',
    'raccordement': 'pose_pv_bt',
    'mise_en_service': 'operations_pv',
    'controle': 'operations_pv',
    'depannage': 'maintenance_bt',
}


def _techniciens_eligibles(company):
    """Techniciens éligibles : utilisateurs de la société déjà affectés à au
    moins une intervention (même bassin que FG299/FG301) — évite de proposer
    un compte admin/commercial jamais affecté sur le terrain."""
    from django.contrib.auth import get_user_model
    from .models import Intervention
    User = get_user_model()
    ids = set(Intervention.objects.filter(
        company=company, technicien_id__isnull=False)
        .values_list('technicien_id', flat=True).distinct())
    if not ids:
        return list(User.objects.filter(company=company))
    return list(User.objects.filter(company=company, id__in=ids))


def suggerer_creneau(company, *, chantier_id, type_intervention, duree_jours=1,
                     date_cible=None, n=3):
    """XFSM2 — les N (défaut 3) meilleures propositions de créneau + technicien
    pour un chantier/type/durée donnés, classées par :
      1. habilitation requise OK (FG173/176 — un technicien manquant/expiré
         n'est jamais proposé) ;
      2. pas de conflit (FG300 : le technicien n'a AUCUNE intervention prévue
         ce jour) ni d'indisponibilité (FG302) ;
      3. charge la plus faible (nb d'interventions déjà planifiées, FG299) ;
      4. distance au site la plus courte depuis les interventions DÉJÀ
         planifiées du technicien ce jour-là (0 si aucune — dépôt inconnu).
    Fenêtre de recherche : 14 jours ouvrés à partir de ``date_cible`` (défaut
    aujourd'hui). Lecture seule, NE MUTE RIEN, scopée société. Renvoie
    ``{propositions: [{technicien_id, nom, date, score...}], chantier_id}``."""
    import datetime
    from .models import Intervention

    chantier = installation_scoped(company, chantier_id)
    if chantier is None:
        return {'chantier_id': chantier_id, 'propositions': []}

    if date_cible is None:
        date_cible = datetime.date.today()

    techniciens = _techniciens_eligibles(company)
    if not techniciens:
        return {'chantier_id': chantier_id, 'propositions': []}

    # Vérification habilitation (best-effort, cadre différent — cf. mapping).
    habilitation_requise = _TYPE_VERS_HABILITATION.get(type_intervention)
    eligibles = []
    if habilitation_requise:
        from apps.rh.selectors import (
            dossier_employe_for_user, verifier_habilitation_requise)
        for tech in techniciens:
            dossier = dossier_employe_for_user(company, tech.id)
            if dossier is None:
                # Pas de fiche RH reliée : on ne peut pas vérifier → on ne
                # bloque PAS (garde RAPPORTE, l'appelant décide — ici on
                # considère éligible faute de donnée, cohérent avec le
                # blocage doux FG176).
                eligibles.append(tech)
                continue
            rapport = verifier_habilitation_requise(
                company, dossier, habilitation_requise)
            if rapport['autorise']:
                eligibles.append(tech)
    else:
        eligibles = techniciens

    if not eligibles:
        return {'chantier_id': chantier_id, 'propositions': []}

    site_lat = getattr(chantier, 'gps_lat', None)
    site_lng = getattr(chantier, 'gps_lng', None)

    # Fenêtre de recherche : 14 jours calendaires à partir de date_cible.
    candidats = []
    jour = date_cible
    jours_testes = 0
    while jours_testes < 14:
        # Interventions déjà planifiées CE JOUR (toute ressource confondue) —
        # sert de proxy de proximité : un technicien déjà dans le secteur ce
        # jour-là minimise le trajet total. Chargé UNE fois par jour (hors
        # boucle technicien) pour éviter un N+1.
        interventions_du_jour = list(
            Intervention.objects.filter(company=company, date_prevue=jour)
            .select_related('installation'))
        for tech in eligibles:
            if ressource_indisponible(company, tech.id, jour, jour):
                continue
            deja_ce_jour = [
                iv for iv in interventions_du_jour
                if iv.technicien_id == tech.id]
            if deja_ce_jour:
                # FG300 — conflit : le technicien porte déjà une intervention
                # ce jour-là → jamais proposé pour un NOUVEAU créneau ce jour.
                continue
            charge = Intervention.objects.filter(
                company=company, technicien_id=tech.id,
                date_prevue__gte=jour,
                date_prevue__lt=jour + datetime.timedelta(days=14)).count()
            # Distance au site la plus courte parmi les interventions déjà
            # planifiées CE JOUR (toute ressource) — 0 si aucune GPS
            # disponible (dépôt/site inconnu, jamais d'exception).
            distance = None
            if site_lat is not None and site_lng is not None:
                for iv in interventions_du_jour:
                    autre_lat = getattr(iv.installation, 'gps_lat', None)
                    autre_lng = getattr(iv.installation, 'gps_lng', None)
                    if autre_lat is None or autre_lng is None:
                        continue
                    d = _haversine_km(
                        site_lat, site_lng, autre_lat, autre_lng)
                    if distance is None or d < distance:
                        distance = d
            candidats.append({
                'technicien_id': tech.id,
                'nom': (getattr(tech, 'get_full_name', lambda: '')()
                        or tech.username),
                'date': jour.isoformat(),
                'charge': charge,
                'distance_km': round(distance, 1) if distance is not None
                else None,
            })
        jour += datetime.timedelta(days=1)
        jours_testes += 1

    candidats.sort(key=lambda c: (
        c['charge'],
        c['distance_km'] if c['distance_km'] is not None else float('inf'),
        c['date'], c['nom'].lower()))
    return {
        'chantier_id': chantier_id,
        'propositions': candidats[:max(int(n or 3), 1)],
    }


# ── XFSM7 — lien public « technicien en route » ──────────────────────────────
# Vitesse moyenne par défaut (km/h) pour l'ETA indicative — pas de service
# externe, juste une estimation de trajet urbain/interurbain marocain.
VITESSE_MOYENNE_KMH_DEFAUT = 40


def intervention_public_payload(interv):
    """XFSM7 — payload public (read-only, tokenisé) du suivi de visite : statut
    courant, nom (+ avatar si disponible) du technicien, fenêtre promise
    (XFSM5), et ETA estimée UNIQUEMENT si l'intervention est « En route » et
    qu'une position de départ + le GPS du chantier sont connus (distance
    haversine / vitesse moyenne paramétrable). Aucune donnée interne (jamais de
    coûts, jamais de position GPS live — voir XFSM23)."""
    from .field_services import haversine_km
    from .models import Intervention

    inst = interv.installation
    technicien = interv.technicien
    technicien_nom = None
    technicien_avatar_url = None
    if technicien is not None:
        technicien_nom = (
            getattr(technicien, 'get_full_name', lambda: '')()
            or technicien.username)
        avatar_key = getattr(technicien, 'avatar_key', '')
        if avatar_key:
            from authentication.avatars import presign_avatar
            technicien_avatar_url = presign_avatar(avatar_key)

    eta_minutes = None
    distance_km = None
    if (interv.statut == Intervention.Statut.EN_ROUTE
            and interv.depart_gps_lat is not None
            and interv.depart_gps_lng is not None):
        distance_km = haversine_km(
            interv.depart_gps_lat, interv.depart_gps_lng,
            getattr(inst, 'gps_lat', None), getattr(inst, 'gps_lng', None))
        if distance_km is not None:
            vitesse = VITESSE_MOYENNE_KMH_DEFAUT
            eta_minutes = round((distance_km / vitesse) * 60) if vitesse else None

    return {
        'statut': interv.statut,
        'statut_display': interv.get_statut_display(),
        'technicien_nom': technicien_nom,
        'technicien_avatar_url': technicien_avatar_url,
        'fenetre_debut': interv.fenetre_debut.isoformat() if interv.fenetre_debut else None,
        'fenetre_fin': interv.fenetre_fin.isoformat() if interv.fenetre_fin else None,
        'date_prevue': interv.date_prevue.isoformat() if interv.date_prevue else None,
        'distance_km': distance_km,
        'eta_minutes': eta_minutes,
        'site_ville': getattr(inst, 'site_ville', None),
    }


# ── ZFSM2 — lien public tokenisé du compte-rendu signé ───────────────────────
def intervention_rapport_public_payload(interv):
    """ZFSM2 — payload public (read-only, tokenisé) du compte-rendu signé :
    mêmes données que le PDF F19 (photos avant/après, réserves, matériel
    consommé SANS prix d'achat ni marge, signature), plus un lien de
    téléchargement du PDF. Aucune donnée interne."""
    from . import intervention_pdf

    inst = interv.installation
    return {
        'statut': interv.statut,
        'statut_display': interv.get_statut_display(),
        'type_intervention_display': interv.get_type_intervention_display(),
        'chantier_reference': getattr(inst, 'reference', None),
        'site_ville': getattr(inst, 'site_ville', None),
        'date_realisee': (
            interv.date_realisee.isoformat() if interv.date_realisee else None),
        'equipe': intervention_pdf._equipe_payload(interv),
        'photos': intervention_pdf._photos_payload(interv),
        'serials': intervention_pdf._serials_payload(interv),
        'consommation': intervention_pdf._consommation_payload(interv),
        'reserves': intervention_pdf._reserves_payload(interv),
        'signataire_nom': interv.signataire_nom or None,
        'signe_le': interv.signe_le.isoformat() if interv.signe_le else None,
        'pdf_url': (
            f'/api/django/public/installations/intervention-rapport/'
            f'{interv.lien_rapport_token}/pdf/'),
    }


# ── XFSM10 — astreinte / rotation après-heures ────────────────────────────────
def technicien_astreinte(company, dt):
    """XFSM10 — technicien d'astreinte couvrant l'instant ``dt`` (datetime
    aware) pour ``company``, ou None si aucune astreinte ne couvre ce moment.
    Lecture seule — consommable par d'autres apps (SAV pour le routage des
    urgences hors heures, paie pour la prime d'astreinte)."""
    from .models import Astreinte
    if company is None or dt is None:
        return None
    a = (Astreinte.objects
         .filter(company=company, date_debut__lte=dt, date_fin__gt=dt)
         .select_related('technicien')
         .order_by('-date_debut')
         .first())
    return a.technicien if a else None


def astreintes_periode(company, date_debut, date_fin):
    """XFSM10 — astreintes de ``company`` chevauchant [date_debut, date_fin)
    (bornes datetime aware). Lecture seule — consommable par la paie pour la
    prime d'astreinte (jamais d'import de ``apps.paie.models`` ici)."""
    from .models import Astreinte
    if company is None:
        return Astreinte.objects.none()
    qs = Astreinte.objects.filter(company=company)
    if date_debut is not None:
        qs = qs.filter(date_fin__gt=date_debut)
    if date_fin is not None:
        qs = qs.filter(date_debut__lt=date_fin)
    return qs.select_related('technicien').order_by('date_debut')


# ── XFSM22 — durée & pièces suggérées par l'historique (heuristique) ────────
_TOP_N_PIECES_DEFAUT = 5
_MIN_HISTORIQUE = 3  # silencieux sous ce nombre d'interventions d'historique.


def _mediane(valeurs):
    vals = sorted(v for v in valeurs if v is not None)
    n = len(vals)
    if n == 0:
        return None
    milieu = n // 2
    if n % 2 == 1:
        return vals[milieu]
    return (vals[milieu - 1] + vals[milieu]) / 2


def suggestion_duree_intervention(company, type_intervention, technicien=None):
    """XFSM22 — durée suggérée (minutes) = médiane des durées réelles F15 des
    interventions TERMINÉES de même ``type_intervention``, sur le même
    technicien s'il a assez d'historique (≥ ``_MIN_HISTORIQUE``), sinon replié
    sur toute la société. Silencieux (None) sous le seuil d'historique — pur
    sélecteur lecture seule, aucune dépendance ML."""
    from .field_capture import crew_time
    from .models import Intervention

    def _durees(qs):
        durees = []
        for interv in qs:
            minutes = crew_time(interv)['duree_sur_site_min']
            if minutes is not None:
                durees.append(minutes)
        return durees

    base = Intervention.objects.filter(
        company=company, type_intervention=type_intervention,
        statut__in=(Intervention.Statut.TERMINEE, Intervention.Statut.VALIDEE))

    if technicien is not None:
        qs_tech = base.filter(technicien=technicien)
        durees_tech = _durees(qs_tech)
        if len(durees_tech) >= _MIN_HISTORIQUE:
            return {
                'duree_suggeree_min': _mediane(durees_tech),
                'echantillon': len(durees_tech),
                'portee': 'technicien',
            }

    durees_societe = _durees(base)
    if len(durees_societe) < _MIN_HISTORIQUE:
        return {
            'duree_suggeree_min': None,
            'echantillon': len(durees_societe),
            'portee': 'societe',
        }
    return {
        'duree_suggeree_min': _mediane(durees_societe),
        'echantillon': len(durees_societe),
        'portee': 'societe',
    }


def suggestion_pieces_intervention(
        company, type_intervention, type_installation=None, top_n=_TOP_N_PIECES_DEFAUT):
    """XFSM22 — top-N produits les plus consommés (F11) sur les interventions
    similaires (même ``type_intervention`` + ``type_installation`` du chantier
    si fourni), triés par quantité totale consommée décroissante. Silencieux
    ([]) sous le seuil d'historique — pur sélecteur lecture seule."""
    from .models import ConsommationLigne, Intervention

    interventions = Intervention.objects.filter(
        company=company, type_intervention=type_intervention,
        statut__in=(Intervention.Statut.TERMINEE, Intervention.Statut.VALIDEE))
    if type_installation:
        interventions = interventions.filter(
            installation__type_installation=type_installation)

    if interventions.count() < _MIN_HISTORIQUE:
        return []

    lignes = (ConsommationLigne.objects
              .filter(consommation__intervention__in=interventions)
              .exclude(produit__isnull=True)
              .values('produit_id', 'designation')
              .annotate(total=Sum('quantite_utilisee'))
              .order_by('-total'))
    return [
        {
            'produit_id': row['produit_id'],
            'designation': row['designation'],
            'quantite_totale': row['total'],
        }
        for row in lignes[:max(int(top_n or _TOP_N_PIECES_DEFAUT), 1)]
    ]


def intervention_export_row(interv):
    """ZFSM7 — une ligne PLATE de l'export xlsx des interventions : chantier,
    client, ville, type, statut, priorité, dates, technicien, équipe, durée
    réelle (F15, `field_capture.crew_time`). SANS AUCUN coût interne ni marge
    (lecture seule, aucun champ `prix*`/`cout*`)."""
    from . import field_capture
    inst = interv.installation
    client_nom = ''
    if inst is not None and inst.client_id:
        client = inst.client
        client_nom = f'{getattr(client, "prenom", "") or ""} '.strip()
        client_nom = f'{client_nom} {getattr(client, "nom", "") or ""}'.strip()
    duree = field_capture.crew_time(interv).get('duree_sur_site_min')
    equipe_noms = ', '.join(
        u.username for u in interv.equipe.all()) if interv.pk else ''
    return [
        inst.reference if inst else '',
        client_nom,
        getattr(inst, 'site_ville', '') or '' if inst else '',
        interv.get_type_intervention_display(),
        interv.get_statut_display(),
        interv.get_priorite_display(),
        interv.date_prevue,
        interv.date_realisee,
        getattr(interv.technicien, 'username', '') or '',
        equipe_noms,
        duree if duree is not None else '',
    ]


# ── XMFG19 — Remplacement de masse d'un composant ───────────────────────────

def kits_utilisant_produit(company, produit_id):
    """XMFG19 — kits de pré-assemblage (FG328) de cette société utilisant ce
    produit dans leur nomenclature. Lecture seule, exposée à `stock` pour la
    préview du remplacement de masse. Renvoie une liste de dicts plats
    {kit_id, kit_nom, composant_id, quantite} — jamais d'instance exposée."""
    from .models import KitComposant
    out = []
    for c in (KitComposant.objects
              .filter(kit__company=company, produit_id=produit_id)
              .select_related('kit')
              .order_by('kit__nom', 'id')):
        out.append({
            'kit_id': c.kit_id,
            'kit_nom': c.kit.nom,
            'composant_id': c.id,
            'quantite': c.quantite,
        })
    return out


# ── VX214 — kinds d'EXÉCUTION pour « Ma file » (jamais une 2ᵉ boîte) ────────

def affectations_pour(user):
    """VX214 — items d'EXÉCUTION (installations) affectés à `user`, prêts pour
    l'union « Ma file » (``apps.records.views.ma_file``) — contrat commun
    ``{kind, title, due, link, urgency}``, MÊME forme que ``crm.selectors.
    ma_file_commercial_items`` (VX83). Lecture seule, scopée société +
    utilisateur ; jamais un import de ``notifications``/``records``.

    Trois familles :
      * chantiers ASSIGNÉS à ce technicien, encore actifs (statut canonique
        AVANT réception — ``RECEPTIONNE``/``CLOTURE`` exclus) — kind
        ``chantier_assigne`` ;
      * interventions DU JOUR (ou en retard) de ce technicien, pas encore
        terminées — kind ``intervention_du_jour`` ;
      * DA APPROUVÉES dont ce user est le demandeur, pas encore commandées
        (transition suivante = ``marquer_commandee``) — kind
        ``da_approuvee_a_commander``.
    """
    if user is None or not getattr(user, 'company_id', None):
        return []
    from .models import DemandeAchat, Installation, Intervention

    company = user.company
    today = None
    items = []

    actifs = [
        s for s in Installation.STATUT_ORDER
        if s not in (Installation.Statut.RECEPTIONNE, Installation.Statut.CLOTURE)
    ]
    chantiers = (Installation.objects
                 .filter(company=company, technicien_responsable=user,
                         statut__in=actifs)
                 .select_related('client')
                 .order_by('date_pose_prevue'))
    for inst in chantiers:
        if today is None:
            from django.utils import timezone
            today = timezone.localdate()
        due = inst.date_pose_prevue
        if due is None:
            urgency = 'today'
        elif due < today:
            urgency = 'overdue'
        elif due == today:
            urgency = 'today'
        else:
            urgency = 'upcoming'
        client_nom = getattr(inst.client, 'nom', '') or ''
        items.append({
            'kind': 'chantier_assigne',
            'title': f'Chantier {client_nom or ("#" + str(inst.id))} — '
                     f'{inst.get_statut_display()}',
            'due': due,
            'link': f'/chantiers?id={inst.id}',
            'urgency': urgency,
        })

    non_terminees = [
        s for s in Intervention.STATUT_ORDER
        if s not in (Intervention.Statut.TERMINEE, Intervention.Statut.VALIDEE)
    ]
    interventions = (Intervention.objects
                     .filter(company=company, technicien=user,
                             statut__in=non_terminees)
                     .select_related('installation', 'installation__client')
                     .order_by('date_prevue'))
    for interv in interventions:
        if today is None:
            from django.utils import timezone
            today = timezone.localdate()
        due = interv.date_prevue
        if due is None:
            urgency = 'today'
        elif due < today:
            urgency = 'overdue'
        elif due == today:
            urgency = 'today'
        else:
            urgency = 'upcoming'
        # Ne remonte QUE le jour même/en retard dans « Ma file » (une
        # intervention de la semaine prochaine n'a pas sa place dans la file
        # d'aujourd'hui — « Ma journée » F22 reste l'écran de planning complet).
        if urgency == 'upcoming':
            continue
        client_nom = getattr(getattr(interv, 'installation', None), 'client', None)
        client_nom = getattr(client_nom, 'nom', '') or ''
        items.append({
            'kind': 'intervention_du_jour',
            'title': f'Intervention {interv.get_type_intervention_display()} — '
                     f'{client_nom or ("chantier #" + str(interv.installation_id))}',
            'due': due,
            'link': f'/chantiers?id={interv.installation_id}' if interv.installation_id else None,
            'urgency': urgency,
        })

    das = (DemandeAchat.objects
           .filter(company=company, statut=DemandeAchat.Statut.APPROUVEE,
                   created_by=user)
           .order_by('date_decision'))
    for da in das:
        items.append({
            'kind': 'da_approuvee_a_commander',
            'title': f'Réquisition {da.reference} approuvée — à commander',
            'due': None,
            'link': f'/chantiers?id={da.chantier_id}' if da.chantier_id else None,
            'urgency': 'today',
        })

    return items
