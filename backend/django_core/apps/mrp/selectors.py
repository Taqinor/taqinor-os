"""Sélecteurs (lecture seule) de l'app `mrp` (Groupe NTMFG)."""
from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone as dj_timezone


def _dec(value):
    try:
        return Decimal(str(value))
    except Exception:  # noqa: BLE001 — valeur non numérique -> 0, jamais de crash.
        return Decimal('0')


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
        en_cours = _dec(
            OrdreFabrication.objects.filter(
                company=company, produit_id=produit_id,
                statut__in=en_cours_statuts,
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
            'demande': str(demande),
            'stock_disponible': str(stock_dispo),
            'en_cours_fabrication': str(en_cours),
            'stock_securite': str(securite),
            'besoin_net': str(besoin_net),
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
