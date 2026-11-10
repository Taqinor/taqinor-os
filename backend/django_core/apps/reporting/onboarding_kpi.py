"""NTDMO41/42 — KPI INTERNES d'onboarding produit (équipe TAQINOR uniquement).

Même patron que ``i18n_kpi.py`` / ``p2p_kpi.py`` : un module d'agrégation qui
lit ce qui existe (modèles ``apps.onboarding``, lecture directe — onboarding
n'est pas un des cinq domaines cœur) et rend ``None`` plutôt qu'un chiffre
approché. AUCUNE table nouvelle. Ces KPI portent sur l'ENSEMBLE des sociétés
clientes : ils ne sont donc PAS dans le catalogue tenant ``KpiAlerte.Kpi`` (un
picker par société — y ajouter une valeur l'exposerait à chaque tenant) mais
servis par ``GET /reporting/kpi-onboarding-interne/``, réservé aux super-admins,
lu depuis le cache rempli par la tâche nocturne (NTDMO31, regroupée : une seule
tâche planifiée).

* ``temps_jusqua_valeur`` (NTDMO41) — sociétés NON démo : délai médian (jours)
  entre ``Company.date_creation`` et la complétion du DERNIER item actif du
  catalogue global (« obligatoire » = tout item actif du catalogue) — chaque
  item compte comme complété à la 1re complétion de n'importe quel utilisateur
  de la société. Une société n'ayant pas tout complété est exclue (pas de
  valeur inventée). Pas de segmentation par secteur : ``Company`` ne porte
  aucun champ secteur à ce jour (« si connu »).
* ``adoption_tours`` (NTDMO42) — par tour du catalogue : utilisateurs actifs de
  sociétés non démo ayant un ``TourProgress.vu_le`` posé / utilisateurs actifs.
  LIMITE DOCUMENTÉE : ``TourProgress`` ne distingue pas « terminé » de « fermé
  prématurément » (``vu_le`` couvre les deux, cf. apps/onboarding/models.py) ;
  le pourcentage est donc « tour vu ou fermé » et ``fin_vs_passe`` vaut
  ``None`` jusqu'à ce que l'app onboarding journalise la distinction.
"""
from statistics import median

from django.core.cache import cache

CLE_CACHE = 'reporting:kpi_onboarding_interne'
TTL_SECONDES = 26 * 3600

RAISON_FIN_VS_PASSE = (
    "TourProgress.vu_le couvre « terminé » ET « fermé » : la fin n'est pas "
    "distinguable du passage prématuré tant que apps/onboarding ne journalise "
    "pas la différence.")


def temps_jusqua_valeur():
    """Délai médian en jours (``None`` si aucune société n'a tout complété)
    + nombre de sociétés mesurées."""
    from apps.onboarding.models import (
        OnboardingChecklistItem, OnboardingProgress)
    from authentication.models import Company

    items = list(OnboardingChecklistItem.objects.filter(
        company__isnull=True, actif=True).values_list('id', flat=True))
    vide = {'mediane_jours': None, 'societes_mesurees': 0}
    if not items:
        return vide
    requis = set(items)
    par_societe = {}  # company_id -> {item_id: 1re complétion}
    for cid, iid, ts in OnboardingProgress.objects.filter(
            complete_le__isnull=False, item_id__in=items,
            company__est_demo=False).values_list(
            'company_id', 'item_id', 'complete_le'):
        faits = par_societe.setdefault(cid, {})
        if iid not in faits or ts < faits[iid]:
            faits[iid] = ts
    creations = dict(Company.objects.filter(
        est_demo=False, id__in=list(par_societe)).values_list(
        'id', 'date_creation'))
    delais = [
        (max(faits.values()) - creations[cid]).total_seconds() / 86400
        for cid, faits in par_societe.items()
        if set(faits) >= requis and cid in creations
    ]
    if not delais:
        return vide
    return {'mediane_jours': round(median(delais), 1),
            'societes_mesurees': len(delais)}


def adoption_tours():
    """Une ligne par tour du catalogue global (6 aujourd'hui)."""
    from apps.onboarding.models import ProductTourStep, TourProgress
    from authentication.models import CustomUser

    tours = sorted(set(ProductTourStep.objects.filter(
        company__isnull=True).values_list('tour_key', flat=True)))
    eligibles = CustomUser.objects.filter(
        is_active=True, company__isnull=False, company__est_demo=False).count()
    lignes = []
    for cle in tours:
        vus = TourProgress.objects.filter(
            tour_key=cle, vu_le__isnull=False, user__is_active=True,
            company__est_demo=False).count()
        lignes.append({
            'tour_key': cle,
            'utilisateurs_eligibles': eligibles,
            'vus_ou_fermes': vus,
            'completion_pct': (
                round(vus * 100 / eligibles, 1) if eligibles else None),
            'fin_vs_passe': None,
        })
    return lignes


def kpis_onboarding_internes():
    return {
        'temps_jusqua_valeur': temps_jusqua_valeur(),
        'adoption_tours': adoption_tours(),
        'fin_vs_passe_raison': RAISON_FIN_VS_PASSE,
    }


def precalculer():
    """Calcule ET met en cache (tâche nocturne regroupée NTDMO31/42)."""
    data = kpis_onboarding_internes()
    cache.set(CLE_CACHE, data, TTL_SECONDES)
    return data


def depuis_cache():
    data = cache.get(CLE_CACHE)
    return data if data is not None else precalculer()
