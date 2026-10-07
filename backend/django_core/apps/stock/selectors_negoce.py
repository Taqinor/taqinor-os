"""Groupe NTDST — Sélecteurs NÉGOCE (lecture seule).

  * NTDST10 — disponibilité ATP (Available-To-Promise) : « j'en ai combien
    MAINTENANT, et à partir de QUAND j'en aurai » ;
  * NTDST18 — catalogue B2B temps réel : prix résolu POUR UN CLIENT + ATP.

Aucune de ces fonctions n'expose ``prix_achat`` : le catalogue B2B est destiné
à un portail client.
"""
from decimal import Decimal

from django.utils import timezone


def _dec(value):
    try:
        return Decimal(str(value))
    except Exception:  # noqa: BLE001 — valeur non numérique -> 0, jamais de crash.
        return Decimal('0')


def _horizon_atp(company):
    """Fenêtre (jours) de recherche des commandes fournisseur confirmées
    (``ParametresNegoce.atp_horizon_jours``, NTDST30 — défaut 30)."""
    from .models import ParametresNegoce
    params = ParametresNegoce.objects.filter(company=company).first()
    return int(getattr(params, 'atp_horizon_jours', None) or 30)


def atp_produit(company, produit, *, emplacement=None, aujourdhui=None):
    """NTDST10 — disponibilité DATÉE d'un produit.

    ``disponible_maintenant`` = stock en main − réservé canonique (chantier +
    assemblage, ``installations.selectors.reserved_quantity_for_produit``) −
    quarantaine qualité (jamais négatif) : même disponible que la liste
    produits (ASTK100).
    ``disponible_le`` = date de la PREMIÈRE commande fournisseur CONFIRMÉE par
    le fournisseur (``date_confirmee_fournisseur``) dans l'horizon, dont le
    reliquat n'est pas déjà couvert par une réservation.

    Un produit en stock renvoie ``disponible_le = None`` : il est disponible
    tout de suite, il n'y a pas de date à promettre.
    """
    import datetime

    from .models import BonCommandeFournisseur, LigneBonCommandeFournisseur

    aujourdhui = aujourdhui or timezone.localdate()
    from apps.installations.selectors import reserved_quantity_for_produit

    from .services_wms import quantite_en_quarantaine

    stock = int(produit.quantite_stock or 0)
    reserve = int(reserved_quantity_for_produit(produit) or 0)
    en_quarantaine = int(quantite_en_quarantaine(
        company, produit=produit) or 0)
    maintenant = max(stock - reserve - en_quarantaine, 0)
    # ASTK101 — le déficit (réservé au-delà du stock) consomme d'abord les
    # reliquats confirmés : pas de promesse d arrivée déjà due à un chantier.
    deficit = max(reserve - stock, 0)

    horizon = aujourdhui + datetime.timedelta(days=_horizon_atp(company))
    lignes = (LigneBonCommandeFournisseur.objects
              .filter(produit=produit,
                      bon_commande__company=company,
                      bon_commande__statut__in=[
                          BonCommandeFournisseur.Statut.BROUILLON,
                          BonCommandeFournisseur.Statut.ENVOYE,
                      ],
                      bon_commande__date_confirmee_fournisseur__isnull=False,
                      bon_commande__date_confirmee_fournisseur__lte=horizon)
              .select_related('bon_commande')
              .order_by('bon_commande__date_confirmee_fournisseur'))

    disponible_le = None
    quantite_a_cette_date = 0
    for ligne in lignes:
        restant = max(int(ligne.quantite or 0)
                      - int(ligne.quantite_recue or 0), 0)
        if restant <= 0:
            continue
        absorbe = min(deficit, restant)
        deficit -= absorbe
        restant -= absorbe
        if restant <= 0:
            continue
        disponible_le = ligne.bon_commande.date_confirmee_fournisseur
        quantite_a_cette_date = restant
        break

    return {
        'produit': produit.id,
        'disponible_maintenant': maintenant,
        'quantite_reservee': reserve,
        'disponible_le': (disponible_le.isoformat()
                          if disponible_le else None),
        'quantite_a_cette_date': quantite_a_cette_date,
        'emplacement': getattr(emplacement, 'id', emplacement),
    }


def catalogue_b2b(company, client, *, categorie=None, marque=None,
                  recherche='', limite=50, offset=0, aujourdhui=None):
    """NTDST18 — catalogue produit d'un CLIENT donné.

    Prix RÉSOLU par ``ventes.services.prix_applicable`` (listes de prix et
    règles XSAL1/XSAL2 — point d'entrée cross-app sanctionné, jamais un
    import de ``ventes.models``), disponibilité ATP (NTDST10), image produit.
    ``prix_achat`` n'apparaît JAMAIS ici.
    """
    from apps.ventes.services import prix_applicable

    from .models import Produit

    qs = (Produit.objects
          .filter(company=company, is_archived=False)
          .select_related('categorie', 'photo')
          .order_by('nom', 'id'))
    if categorie:
        qs = qs.filter(categorie_id=categorie)
    if marque:
        qs = qs.filter(marque__iexact=marque)
    recherche = (recherche or '').strip()
    if recherche:
        from django.db.models import Q
        qs = qs.filter(Q(nom__icontains=recherche)
                       | Q(sku__icontains=recherche)
                       | Q(marque__icontains=recherche))

    total = qs.count()
    try:
        limite = max(1, min(int(limite or 50), 200))
        offset = max(0, int(offset or 0))
    except (TypeError, ValueError):
        limite, offset = 50, 0

    resultats = []
    for produit in qs[offset:offset + limite]:
        resolu = prix_applicable(produit=produit, client=client, quantite=1)
        atp = atp_produit(company, produit, aujourdhui=aujourdhui)
        resultats.append({
            'id': produit.id,
            'nom': produit.nom,
            'sku': produit.sku or '',
            'marque': produit.marque or '',
            'categorie': produit.categorie_id,
            'categorie_nom': getattr(produit.categorie, 'nom', '') or '',
            'prix': str(_dec(resolu['prix'])),
            'prix_source': resolu['source'],
            'liste_nom': resolu.get('liste_nom'),
            'image_id': produit.photo_id,
            'disponible_maintenant': atp['disponible_maintenant'],
            'disponible_le': atp['disponible_le'],
            'quantite_a_cette_date': atp['quantite_a_cette_date'],
        })
    return {
        'client': getattr(client, 'id', client),
        'total': total,
        'limite': limite,
        'offset': offset,
        'produits': resultats,
    }
