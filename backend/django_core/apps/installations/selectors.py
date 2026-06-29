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
