"""Sélecteurs LECTURE SEULE du module Hôtellerie & restauration."""
from decimal import Decimal

from .models import Chambre, Recette, Reservation

# NTHOT11 — statuts jamais comptés dans les nuits vendues/revenus (annulation
# ou no-show : la chambre n'a jamais généré de nuitée facturable).
_STATUTS_EXCLUS_REVENUS = [
    Reservation.Statut.ANNULEE, Reservation.Statut.NO_SHOW,
]


def dashboard_hotellerie(company, debut, fin):
    """NTHOT11 — Tableau de bord RevPAR/ADR/TO sur ``[debut, fin)``.

    - ADR (Average Daily Rate) = revenus chambres / nuits vendues.
    - RevPAR = revenus chambres / nuits disponibles totales (nb chambres ×
      nb jours de la période).
    - Taux d'occupation = nuits vendues / nuits disponibles.
    - No-show rate = réservations no-show / total réservations de la période.

    Les réservations ``annulee``/``no_show`` sont EXCLUES du numérateur revenus
    ET du dénominateur nuits vendues (jamais comptées comme une nuit vendue).
    Renvoie des ``Decimal('0')`` (jamais de division par zéro) sur une fenêtre
    sans données."""
    reservations = Reservation.objects.filter(
        company=company, date_arrivee__lt=fin, date_depart__gt=debut)

    vendables = reservations.exclude(statut__in=_STATUTS_EXCLUS_REVENUS)

    nuits_vendues = 0
    revenus_chambres = Decimal('0')
    for reservation in vendables:
        start = max(reservation.date_arrivee, debut)
        end = min(reservation.date_depart, fin)
        nights = max((end - start).days, 0)
        nuits_vendues += nights
        if reservation.prix_nuit_snapshot:
            revenus_chambres += Decimal(nights) * reservation.prix_nuit_snapshot

    nb_chambres = Chambre.objects.filter(company=company).count()
    nb_jours = max((fin - debut).days, 0)
    nuits_disponibles = nb_chambres * nb_jours

    adr = (
        (revenus_chambres / nuits_vendues) if nuits_vendues else Decimal('0'))
    revpar = (
        (revenus_chambres / nuits_disponibles)
        if nuits_disponibles else Decimal('0'))
    taux_occupation = (
        (Decimal(nuits_vendues) / nuits_disponibles)
        if nuits_disponibles else Decimal('0'))

    total_reservations = reservations.count()
    no_show_count = reservations.filter(
        statut=Reservation.Statut.NO_SHOW).count()
    no_show_rate = (
        (Decimal(no_show_count) / total_reservations)
        if total_reservations else Decimal('0'))

    return {
        'adr': adr,
        'revpar': revpar,
        'taux_occupation': taux_occupation,
        'no_show_rate': no_show_rate,
        'nuits_vendues': nuits_vendues,
        'nuits_disponibles': nuits_disponibles,
        'revenus_chambres': revenus_chambres,
        'total_reservations': total_reservations,
        'no_show_count': no_show_count,
    }


# ── NTHOT14 — Coût matière théorique vs réel ────────────────────────────────
# Discipline « rule prix_achat » (CLAUDE.md) : AUCUNE fonction ci-dessous ne
# renvoie jamais un ``prix_achat`` UNITAIRE brut dans son payload — uniquement
# des coûts déjà AGRÉGÉS (cout_matiere/pourcentage/écart). Le gating par la
# permission ``prix_achat_voir`` reste appliqué côté vue par l'appelant (ex.
# NTHOT28, hors périmètre ici) — jamais dans un ticket/menu client.

def cout_matiere_theorique(recette):
    """NTHOT14 — Coût matière théorique d'UNE ``Recette`` : Σ(quantité
    ingrédient × ``prix_achat`` COURANT du produit, résolu via
    ``apps.stock.selectors.get_produit_scoped`` — jamais un import direct du
    modèle ``stock.Produit``). Recalculée à CHAQUE appel (jamais mise en
    cache) : un changement de prix d'achat d'un ingrédient se répercute
    immédiatement sur le prochain appel."""
    from apps.stock import selectors as stock_selectors

    total = Decimal('0')
    for ingredient in recette.ingredients.all():
        produit = stock_selectors.get_produit_scoped(
            recette.company, ingredient.produit_id)
        if produit is None:
            continue
        total += Decimal(ingredient.quantite) * Decimal(produit.prix_achat)
    return total


def pourcentage_food_cost(recette):
    """NTHOT14 — ``cout_matiere_theorique / prix_vente_ht`` (``Decimal('0')``
    si le plat n'a pas de prix de vente renseigné — jamais une division par
    zéro)."""
    if not recette.prix_vente_ht:
        return Decimal('0')
    return cout_matiere_theorique(recette) / Decimal(recette.prix_vente_ht)


def _ingredients_produits_de_la_societe(company):
    """Renvoie ``{nom_produit: prix_achat}`` pour tous les produits utilisés
    comme ingrédient par au moins une ``Recette`` de ``company`` — lecture
    via ``apps.stock.selectors`` uniquement."""
    from apps.stock import selectors as stock_selectors

    ingredient_produit_ids = set(
        Recette.objects.filter(company=company)
        .values_list('ingredients__produit_id', flat=True))
    ingredient_produit_ids.discard(None)

    out = {}
    for produit_id in ingredient_produit_ids:
        produit = stock_selectors.get_produit_scoped(company, produit_id)
        if produit is not None:
            out[produit.nom] = Decimal(produit.prix_achat)
    return out


def cout_matiere_reel(company, debut, fin):
    """NTHOT14 — Coût matière RÉEL valorisé sur ``[debut, fin]`` : Σ des
    sorties de stock des produits utilisés comme ingrédient par au moins une
    recette de la société, valorisées au ``prix_achat`` courant.

    Lecture au travers du sélecteur agrégé existant de ``apps.stock``
    (``mouvements_agreges``, JAMAIS un import du modèle ``MouvementStock`` —
    frontière cross-app, CLAUDE.md) : ce sélecteur agrège par LIBELLÉ produit
    (il n'expose pas l'id produit dans sa sortie), le rapprochement avec les
    ingrédients de recette se fait donc par NOM produit — best-effort
    documenté, suffisant tant qu'un établissement ne duplique pas le nom d'un
    produit ingrédient. Renvoie ``{'total': Decimal, 'par_produit': [...]}``
    — jamais de ``prix_achat`` unitaire dans la sortie."""
    from apps.stock import selectors as stock_selectors

    prix_par_nom = _ingredients_produits_de_la_societe(company)
    if not prix_par_nom:
        return {'total': Decimal('0'), 'par_produit': []}

    mouvements = stock_selectors.mouvements_agreges(
        company, group_by='produit', date_min=debut, date_max=fin)

    total = Decimal('0')
    par_produit = []
    for m in mouvements:
        prix_achat = prix_par_nom.get(m['libelle'])
        if prix_achat is None or not m['sorties']:
            continue
        valeur = Decimal(m['sorties']) * prix_achat
        total += valeur
        par_produit.append({'produit': m['libelle'], 'valeur': valeur})
    return {'total': total, 'par_produit': par_produit}


def ecart_theorique_reel(company, debut, fin, *, ventes_par_recette=None):
    """NTHOT14 — Écart coût matière théorique vs réel sur ``[debut, fin]``
    (indicateur pertes/gaspillage/vol).

    ``ventes_par_recette`` (optionnel) : ``{recette_id: quantite_vendue}`` —
    fourni par le futur pont POS (NTHOT15, hors périmètre ici) ; sans lui, le
    théorique est calculé sur AUCUNE vente tracée (``0``) — jamais une fausse
    précision inventée. Renvoie ``ecart_pct = None`` quand le théorique est
    nul (rien à comparer), jamais une division par zéro."""
    ventes_par_recette = ventes_par_recette or {}

    theorique = Decimal('0')
    for recette_id, quantite_vendue in ventes_par_recette.items():
        try:
            recette = Recette.objects.get(pk=recette_id, company=company)
        except Recette.DoesNotExist:
            continue
        theorique += cout_matiere_theorique(recette) * Decimal(quantite_vendue)

    reel = cout_matiere_reel(company, debut, fin)['total']
    ecart_pct = ((reel - theorique) / theorique) if theorique else None

    return {
        'theorique': theorique,
        'reel': reel,
        'ecart': reel - theorique,
        'ecart_pct': ecart_pct,
    }
