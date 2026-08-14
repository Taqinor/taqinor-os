"""Services (écriture/orchestration) de planification supply chain (Groupe
NTSCM). Toute lecture cross-app (``apps.stock``, ``apps.ventes``…) passe par
le ``selectors.py``/``services.py`` de l'app cible, jamais un import de
modèle — voir chaque fonction pour le détail de sa frontière.
"""
import math
from calendar import monthrange
from datetime import date
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from core.demand_forecast import forecast_demand
from core.safety_stock import compute_safety_stock

from .models import EvenementDemande, PrevisionDemande

# Convention du module : les historiques exposés par ``_historique_sorties_
# mensuelles`` sont MENSUELS ; ``core.safety_stock.compute_safety_stock``
# attend une consommation JOURNALIÈRE (mêmes unités que son ``lead_time_days``).
# Conversion mensuel -> journalier au mois normalisé de 30 jours (même
# convention que ``core.stock_reorder``, qui travaille déjà en jours).
JOURS_PAR_MOIS = 30.0


def _historique_sorties_mensuelles(company, produit_id, fenetre_mois):
    """Sorties ``stock.MouvementStock`` mensuelles d'un produit, sur
    ``fenetre_mois`` mois glissants jusqu'à aujourd'hui.

    ``apps.stock.selectors.mouvements_agreges`` n'agrège que sur UNE
    dimension à la fois (produit OU mois, jamais les deux ensemble — voir
    ``apps/stock/selectors.py``) : il ne peut donc pas fournir un historique
    PAR PRODUIT ET PAR MOIS. Faute d'un sélecteur adapté côté ``apps.stock``
    (que cette lane n'a pas le droit d'écrire — frontière cross-app,
    CLAUDE.md), le modèle est résolu DYNAMIQUEMENT via
    ``django.apps.apps.get_model`` pour une agrégation en LECTURE SEULE —
    exactement le même patron que ``installations.selectors`` (FG294/FG295)
    pour ses agrégats cross-app : jamais un ``from apps.stock.models import
    MouvementStock`` statique, jamais une écriture dans ``apps.stock``.
    Renvoie ``[(periode:'YYYY-MM', quantite:float), ...]`` trié."""
    from django.apps import apps as django_apps
    from django.db.models import Sum
    from django.db.models.functions import TruncMonth

    MouvementStock = django_apps.get_model('stock', 'MouvementStock')

    today = timezone.localdate()
    idx = today.year * 12 + (today.month - 1) - max(0, int(fenetre_mois))
    y0, m0 = divmod(idx, 12)
    debut = date(y0, m0 + 1, 1)

    qs = (
        MouvementStock.objects
        .filter(
            company=company, produit_id=produit_id,
            type_mouvement=MouvementStock.TypeMouvement.SORTIE,
            date__date__gte=debut)
        .annotate(mois=TruncMonth('date'))
        .values('mois')
        .annotate(total=Sum('quantite'))
        .order_by('mois')
    )
    return [
        (f'{row["mois"].year:04d}-{row["mois"].month:02d}', float(row['total'] or 0))
        for row in qs
    ]


def _evenements_du_mois(company, produit, periode):
    """NTSCM3 — événements chevauchant le mois ``periode`` ('YYYY-MM') pour
    ce produit : match explicite sur le produit, sur sa catégorie (événement
    à ``produit`` vide), ou événement GLOBAL (``produit`` et ``categorie``
    vides tous les deux)."""
    y, m = int(periode[:4]), int(periode[5:7])
    debut_mois = date(y, m, 1)
    fin_mois = date(y, m, monthrange(y, m)[1])

    qs = EvenementDemande.objects.filter(
        company=company, date_debut__lte=fin_mois, date_fin__gte=debut_mois,
    ).filter(
        Q(produit=produit)
        | Q(produit__isnull=True, categorie_id=produit.categorie_id)
        | Q(produit__isnull=True, categorie__isnull=True)
    )
    return qs


def _appliquer_evenements(company, produit, periode, quantite_base):
    """NTSCM3 — applique l'impact cumulé (somme des ``impact_pct``, jamais en
    dessous de 0) des événements chevauchant ``periode`` à la quantité de
    base issue de la prévision (NTSCM2)."""
    facteur = Decimal('1')
    for ev in _evenements_du_mois(company, produit, periode):
        facteur += (ev.impact_pct or Decimal('0')) / Decimal('100')
    if facteur < 0:
        facteur = Decimal('0')
    return (Decimal(str(quantite_base)) * facteur).quantize(Decimal('0.01'))


def generer_previsions(
    produit, horizon_mois, company, *, segment='', fenetre_mois=24, user=None,
):
    """NTSCM2/3 — génère/rafraîchit les ``PrevisionDemande`` d'un produit sur
    ``horizon_mois`` mois, à partir de son historique de sorties (fenêtre
    ``fenetre_mois`` mois, réutilise :func:`core.demand_forecast.forecast_demand`),
    puis applique l'impact cumulé des ``EvenementDemande`` (NTSCM3)
    chevauchant chaque mois cible.

    ``produit`` est une instance ``stock.Produit`` déjà résolue par
    l'APPELANT (via ``apps.stock.selectors`` — jamais un import de modèle
    ici). Idempotent par ``(company, produit, segment, periode)``
    (``update_or_create``). Renvoie la liste des ``PrevisionDemande`` créées
    ou mises à jour."""
    historique = _historique_sorties_mensuelles(company, produit.id, fenetre_mois)
    resultat = forecast_demand(historique, horizon_mois=horizon_mois)

    methode = (
        PrevisionDemande.Methode.MOYENNE_MOBILE if resultat.used_fallback
        else PrevisionDemande.Methode.SAISONNIER
    )

    previsions = []
    for periode, quantite in resultat.previsions:
        quantite_ajustee = _appliquer_evenements(company, produit, periode, quantite)
        obj, _ = PrevisionDemande.objects.update_or_create(
            company=company, produit=produit, segment=segment or '', periode=periode,
            defaults={
                'quantite_prevue': quantite_ajustee,
                'methode': methode,
                'genere_le': timezone.now(),
                'genere_par': user,
            },
        )
        previsions.append(obj)
    return previsions


def appliquer_politique_stock(
    produit, service_level_pct, company, *, lead_time_days=0, fenetre_mois=12,
):
    """NTSCM5 — calcule le stock de sécurité au niveau de service pour un
    produit, à partir de son historique de sorties mensuelles (réutilise
    ``_historique_sorties_mensuelles``, comme NTSCM2) et
    :func:`core.safety_stock.compute_safety_stock`.

    NE PERSISTE RIEN : ``PolitiqueStock`` n'existe pas encore à ce stade de
    la lane (NTSCM6, tâche SUIVANTE, définit le modèle et appelle CETTE
    fonction pour écrire ``PolitiqueStock.stock_securite_calcule``) —
    fonction pure de calcul, réutilisable.

    Renvoie un dict ``{stock_securite, avg_daily_consumption, std_dev_daily,
    nb_mois_historique}``."""
    historique = _historique_sorties_mensuelles(company, produit.id, fenetre_mois)
    valeurs_mensuelles = [q for _, q in historique]
    n = len(valeurs_mensuelles)
    moyenne_mensuelle = (sum(valeurs_mensuelles) / n) if n else 0.0
    if n > 1:
        variance = sum((v - moyenne_mensuelle) ** 2 for v in valeurs_mensuelles) / n
        ecart_type_mensuel = math.sqrt(variance)
    else:
        ecart_type_mensuel = 0.0

    avg_daily = moyenne_mensuelle / JOURS_PAR_MOIS
    std_daily = ecart_type_mensuel / JOURS_PAR_MOIS

    stock_securite = compute_safety_stock(
        avg_daily, std_daily, lead_time_days, service_level_pct)

    return {
        'stock_securite': round(stock_securite, 2),
        'avg_daily_consumption': round(avg_daily, 4),
        'std_dev_daily': round(std_daily, 4),
        'nb_mois_historique': n,
    }
