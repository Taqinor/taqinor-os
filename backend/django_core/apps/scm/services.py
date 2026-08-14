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

from .models import ClassificationABC, EvenementDemande, PolitiqueStock, PrevisionDemande

# Convention du module : les historiques exposés par ``_historique_sorties_
# mensuelles`` sont MENSUELS ; ``core.safety_stock.compute_safety_stock``
# attend une consommation JOURNALIÈRE (mêmes unités que son ``lead_time_days``).
# Conversion mensuel -> journalier au mois normalisé de 30 jours (même
# convention que ``core.stock_reorder``, qui travaille déjà en jours).
JOURS_PAR_MOIS = 30.0

# NTSCM6 — niveau de service PAR DÉFAUT selon la classe ABC (NTSCM4), à la
# création d'une PolitiqueStock UNIQUEMENT (un recalcul n'écrase jamais un
# niveau déjà personnalisé par l'acheteur).
SERVICE_LEVEL_PAR_CLASSE = {'A': Decimal('95'), 'B': Decimal('90'), 'C': Decimal('85')}

# Délai fournisseur (jours) utilisé quand aucun historique de livraison
# n'est exploitable (produit sans fournisseur, ou fournisseur jamais livré).
DEFAULT_LEAD_TIME_DAYS = 15.0


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


def lead_time_moyen_fournisseur(company, produit):
    """Délai fournisseur moyen (jours) — réutilise le scorecard FG59 déjà
    bâti (``apps.stock.services.supplier_performance``, LECTURE SEULE,
    import fonction-local) plutôt que de dupliquer un calcul de délai côté
    ``apps.scm``. Repli :data:`DEFAULT_LEAD_TIME_DAYS` si le produit n'a pas
    de fournisseur ou qu'aucune livraison n'a encore été confirmée."""
    if not produit.fournisseur_id:
        return DEFAULT_LEAD_TIME_DAYS
    from apps.stock.services import supplier_performance

    perf = supplier_performance(company, produit.fournisseur)
    avg = perf.get('avg_lead_time_days')
    return float(avg) if avg is not None else DEFAULT_LEAD_TIME_DAYS


def recalculer_politiques_stock(company):
    """NTSCM6 — recalcule (tâche périodique) les ``PolitiqueStock`` de tous
    les produits actifs d'une société :

      * ``classe_abc`` — snapshot depuis ``ClassificationABC`` (NTSCM4,
        défaut 'C' si le produit n'a encore jamais été classé) ;
      * ``service_level_pct`` — initialisé selon la classe
        (:data:`SERVICE_LEVEL_PAR_CLASSE`) À LA CRÉATION SEULEMENT, jamais
        écrasé si déjà personnalisé par l'acheteur ;
      * ``stock_securite_calcule`` — NTSCM5 (:func:`appliquer_politique_stock`) ;
      * ``point_commande`` (ROP) = ``conso_moy_journalière × délai
        fournisseur moyen + stock_securite`` — où ``stock_securite`` est
        ``stock_securite_manuel`` si renseigné (override acheteur), sinon
        ``stock_securite_calcule``.

    Idempotent (``get_or_create``/``save`` par produit). Renvoie la liste des
    ``PolitiqueStock`` recalculées."""
    from django.apps import apps as django_apps

    Produit = django_apps.get_model('stock', 'Produit')
    produits = Produit.objects.filter(company=company, is_archived=False)
    classes = dict(
        ClassificationABC.objects.filter(company=company)
        .values_list('produit_id', 'classe'))

    resultats = []
    for produit in produits:
        classe = classes.get(produit.id, 'C')
        niveau_defaut = SERVICE_LEVEL_PAR_CLASSE.get(classe, Decimal('95'))

        politique, created = PolitiqueStock.objects.get_or_create(
            company=company, produit=produit,
            defaults={'service_level_pct': niveau_defaut, 'classe_abc': classe},
        )
        service_level = niveau_defaut if created else politique.service_level_pct

        lead_time_days = lead_time_moyen_fournisseur(company, produit)
        calc = appliquer_politique_stock(
            produit, service_level, company, lead_time_days=lead_time_days)

        stock_securite_effectif = (
            politique.stock_securite_manuel
            if politique.stock_securite_manuel is not None
            else Decimal(str(calc['stock_securite']))
        )
        point_commande = (
            Decimal(str(calc['avg_daily_consumption'])) * Decimal(str(lead_time_days))
            + stock_securite_effectif
        )

        politique.classe_abc = classe
        politique.service_level_pct = service_level
        politique.stock_securite_calcule = Decimal(str(calc['stock_securite']))
        politique.point_commande = point_commande.quantize(Decimal('0.01'))
        politique.revise_le = timezone.now()
        politique.save(update_fields=[
            'classe_abc', 'service_level_pct', 'stock_securite_calcule',
            'point_commande', 'revise_le', 'updated_at',
        ])
        resultats.append(politique)
    return resultats
