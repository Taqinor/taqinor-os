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
