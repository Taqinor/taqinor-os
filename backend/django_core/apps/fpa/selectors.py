"""Sélecteurs LECTURE SEULE de l'app FP&A (apps.fpa)."""
from decimal import Decimal

from django.db.models import Sum

from .models import HypotheseRecrutement, LigneBudgetDepartement


# NTFPA14 — seuil de dérive par défaut (15 %) ; surchargeable via Paramètres
# (best-effort ; le repli reste 15 % sans configuration).
SEUIL_DERIVE_DEFAUT = Decimal('0.15')


def seuil_derive(company):
    """Seuil de dérive configuré pour la société (fraction), repli 15 %."""
    try:
        from apps.parametres.models import CompanyProfile
        profil = CompanyProfile.objects.filter(company=company).first()
        val = getattr(profil, 'fpa_seuil_derive', None) if profil else None
        if val is not None:
            return Decimal(str(val))
    except Exception:
        pass
    return SEUIL_DERIVE_DEFAUT


def derive_hypotheses(company, cycle):
    """NTFPA14 — dérive des hypothèses de recrutement CONFIRMÉES vs PRÉVUES par
    département, pour un cycle donné.

    Compare, par département, la masse salariale des hypothèses ``confirme`` à
    celle des hypothèses ``hypothese`` (prévues) et flague un écart relatif
    au-delà du seuil de la société (défaut 15 %). Lecture seule ; renvoie une
    liste de dicts ``{departement_id, prevu, confirme, ecart_pct, depasse}``
    (seuls les départements avec au moins une hypothèse sont listés)."""
    seuil = seuil_derive(company)
    par_dept = {}
    qs = HypotheseRecrutement.objects.filter(company=company)
    for hyp in qs:
        slot = par_dept.setdefault(
            hyp.departement_id, {'prevu': Decimal('0'), 'confirme': Decimal('0')})
        montant = Decimal(str(hyp.salaire_brut_estime or 0))
        signe = Decimal('-1') if hyp.type_mouvement == 'depart' else Decimal('1')
        if hyp.statut == HypotheseRecrutement.Statut.CONFIRME:
            slot['confirme'] += signe * montant
        else:
            slot['prevu'] += signe * montant

    resultat = []
    for dept_id, vals in par_dept.items():
        prevu = vals['prevu']
        confirme = vals['confirme']
        base = prevu if prevu != 0 else Decimal('1')
        ecart_pct = (confirme - prevu) / abs(base)
        resultat.append({
            'departement_id': dept_id,
            'prevu': prevu,
            'confirme': confirme,
            'ecart_pct': ecart_pct,
            'depasse': abs(ecart_pct) > seuil,
        })
    return resultat


def budget_total_annuel(company, cycle_id, *, departement_id=None, categorie=None):
    """NTFPA3 — total annuel du budget (Σ ``montant_prevu``) pour un cycle,
    éventuellement filtré par département/catégorie. Lecture seule."""
    qs = LigneBudgetDepartement.objects.filter(company=company, cycle_id=cycle_id)
    if departement_id is not None:
        qs = qs.filter(departement_id=departement_id)
    if categorie is not None:
        qs = qs.filter(categorie=categorie)
    return qs.aggregate(total=Sum('montant_prevu'))['total'] or 0


def _delta_ligne(montant_base, delta_pct, delta_montant):
    """Applique un delta (pct puis montant absolu) à un montant de base."""
    montant = Decimal(str(montant_base or 0))
    if delta_pct is not None:
        montant += montant * Decimal(str(delta_pct)) / Decimal('100')
    if delta_montant is not None:
        montant += Decimal(str(delta_montant))
    return montant


def total_scenario(company, scenario):
    """NTFPA15 — total annuel DÉRIVÉ d'un scénario : total du budget de base du
    cycle + application des deltas du scénario (en LECTURE ; les lignes du
    cycle réel ne sont jamais modifiées).

    Un delta ciblant une ``ligne_budget`` précise s'applique à cette ligne ; un
    delta ciblant une ``categorie`` s'applique au total de cette catégorie."""
    cycle_id = scenario.cycle_id
    base_total = budget_total_annuel(company, cycle_id)

    total_par_categorie = {}
    lignes = LigneBudgetDepartement.objects.filter(
        company=company, cycle_id=cycle_id)
    for ligne in lignes:
        total_par_categorie[ligne.categorie] = (
            total_par_categorie.get(ligne.categorie, Decimal('0'))
            + Decimal(str(ligne.montant_prevu or 0)))

    total = Decimal(str(base_total))
    for delta in scenario.lignes.all():
        if delta.ligne_budget_id:
            ligne = LigneBudgetDepartement.objects.filter(
                pk=delta.ligne_budget_id).first()
            base = Decimal(str(ligne.montant_prevu or 0)) if ligne else Decimal('0')
        elif delta.categorie:
            base = total_par_categorie.get(delta.categorie, Decimal('0'))
        else:
            continue
        nouveau = _delta_ligne(base, delta.delta_pct, delta.delta_montant)
        total += (nouveau - base)
    return total


def comparer_scenarios(company, cycle_id, scenario_ids):
    """NTFPA16 — comparaison côte-à-côte : total du budget de base + un total
    dérivé par scénario, avec l'écart vs base. Lecture seule.

    Renvoie ``{'base': Decimal, 'scenarios': [{'id', 'nom', 'total',
    'ecart'}]}``."""
    from .models import ScenarioBudgetaire

    base = budget_total_annuel(company, cycle_id)
    scenarios = ScenarioBudgetaire.objects.filter(
        company=company, cycle_id=cycle_id, pk__in=scenario_ids
    ).prefetch_related('lignes')
    rows = []
    for scenario in scenarios:
        total = total_scenario(company, scenario)
        rows.append({
            'id': scenario.pk, 'nom': scenario.nom,
            'total': total, 'ecart': total - Decimal(str(base)),
        })
    return {'base': Decimal(str(base)), 'scenarios': rows}


def revenu_engage_carnet(company, mois_debut, mois_fin):
    """NTFPA12 — revenu ENGAGÉ (carnet de commandes) par mois, lu via
    ``ventes.selectors`` (jamais ``ventes.models``). Renvoie ``{'YYYY-MM':
    Decimal}`` — devis acceptés non facturés, 100 % pondéré (déjà signé),
    distinct du pipeline probabiliste NTFPA11 (pas de double-compte)."""
    from apps.ventes import selectors as ventes_selectors

    return ventes_selectors.carnet_commande_par_mois(
        company, mois_debut, mois_fin)


def _ecart(a, b):
    """Écart (€, %) de ``a`` par rapport à ``b`` (base). % = None si base 0."""
    a = Decimal(str(a or 0))
    b = Decimal(str(b or 0))
    ecart_eur = a - b
    ecart_pct = (ecart_eur / abs(b) * Decimal('100')) if b != 0 else None
    return ecart_eur, ecart_pct


def prefixes_categorie(company, categorie):
    """NTFPA21 — préfixes CGNC couvrant une catégorie (mapping ou repli)."""
    from .models import DEFAULT_COMPTE_CGNC_PREFIXES, MappingCategorieCompte

    mappes = list(
        MappingCategorieCompte.objects
        .filter(company=company, categorie=categorie)
        .values_list('compte_cgnc_prefixe', flat=True))
    if mappes:
        return tuple(mappes)
    return DEFAULT_COMPTE_CGNC_PREFIXES.get(categorie, ())


def variance_budget_vs_reel(company, cycle, mois):
    """NTFPA19 — variance par département/catégorie pour un mois : ``prévu``
    (LigneBudgetDepartement) vs ``réel`` comptable (grand livre par préfixe
    CGNC mappé, NTFPA21, via ``compta.selectors``) vs dernière prévision
    glissante du même mois.

    Renvoie une liste de dicts par (département, catégorie) avec les 3 valeurs
    et l'écart €/% des 3 paires (prévu/réel, prévu/forecast, réel/forecast) +
    un drapeau ``depassement`` (réel > prévu de plus de 10 %). Lecture seule.
    """
    from apps.compta import selectors as compta_selectors

    from .models import (
        CycleBudgetaire, LigneBudgetDepartement, LignePrevisionGlissante,
    )

    if not isinstance(cycle, CycleBudgetaire):
        cycle = CycleBudgetaire.objects.filter(
            company=company, pk=cycle).first()
    if cycle is None:
        return []
    annee = cycle.date_debut.year

    # Réel comptable par catégorie pour ce mois (une lecture GL par catégorie).
    lignes = LigneBudgetDepartement.objects.filter(
        company=company, cycle=cycle, mois=mois
    ).select_related('departement')

    reel_par_categorie = {}
    forecast_par_categorie = {}

    def _reel(categorie):
        if categorie not in reel_par_categorie:
            reel_par_categorie[categorie] = compta_selectors.total_reel_par_prefixes_mois(
                company, prefixes_categorie(company, categorie), annee, mois)
        return reel_par_categorie[categorie]

    def _forecast(categorie):
        if categorie not in forecast_par_categorie:
            # Dernière prévision glissante portant ce mois relatif=mois.
            ligne = (
                LignePrevisionGlissante.objects
                .filter(company=company, categorie=categorie, mois_relatif=mois)
                .order_by('-prevision__date_reference')
                .first())
            forecast_par_categorie[categorie] = (
                ligne.montant_prevu if ligne else Decimal('0'))
        return forecast_par_categorie[categorie]

    resultat = []
    for ligne in lignes:
        prevu = Decimal(str(ligne.montant_prevu or 0))
        reel = Decimal(str(_reel(ligne.categorie) or 0))
        forecast = Decimal(str(_forecast(ligne.categorie) or 0))
        e_pr_reel = _ecart(reel, prevu)
        e_pr_fc = _ecart(forecast, prevu)
        e_reel_fc = _ecart(reel, forecast)
        depassement = bool(
            prevu != 0 and (reel - prevu) / abs(prevu) > Decimal('0.10'))
        resultat.append({
            'departement_id': ligne.departement_id,
            'departement': ligne.departement.nom,
            'categorie': ligne.categorie,
            'mois': mois,
            'prevu': prevu, 'reel': reel, 'forecast': forecast,
            'ecart_prevu_reel_eur': e_pr_reel[0],
            'ecart_prevu_reel_pct': e_pr_reel[1],
            'ecart_prevu_forecast_eur': e_pr_fc[0],
            'ecart_prevu_forecast_pct': e_pr_fc[1],
            'ecart_reel_forecast_eur': e_reel_fc[0],
            'ecart_reel_forecast_pct': e_reel_fc[1],
            'depassement': depassement,
        })
    return resultat
