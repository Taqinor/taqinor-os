"""NTDATA3 — datasets BI « stock & achats » pour l'explorateur du noyau.

Même patron que ``apps/sav/bi_datasets.py`` : l'app PROPRIÉTAIRE déclare, le
noyau exécute. ``core`` reste fondation et n'importe jamais ``apps.stock``.

* ``stock_produits``   — catégorie, marque, quantité en stock, seuil, drapeau
  « stock bas » ; prix/valeur d'ACHAT sous permission.
* ``stock_mouvements`` — type (entrée/sortie/transfert/ajustement/rebut), mois,
  catégorie du produit, quantité.
* ``stock_bcf``        — bons de commande fournisseur : fournisseur, statut,
  mois, montant d'achat (sous permission).

LES PRIX D'ACHAT SONT SOUS PERMISSION, DANS LE MOTEUR (AUD801)
--------------------------------------------------------------
``prix_achat``, ``valeur_achat`` et le ``montant`` d'un bon de commande
fournisseur sont des données INTERNES (règle du dépôt : ``prix_achat`` ne
figure jamais dans une sortie client). Le masquage n'est PAS « laissé à
l'appelant » — c'est précisément le défaut qu'AUD801 a corrigé : il est
déclaré au DATASET via ``gated_fields``, et ``core.data_explorer`` écarte le
champ de TOUTES les positions de la spec (select, filtres, group_by, tris,
agrégats et projection par défaut) pour tout lecteur sans
``can_view_buy_prices`` — et TOUJOURS quand ``user`` est ``None`` (extrait
planifié, job).

POURQUOI ``quantite_disponible`` N'EST PAS EXPOSÉ
-------------------------------------------------
Le « disponible » du dépôt vaut ``quantite_stock − réservé − quarantaine``, et
ces deux retranchements NE SONT PAS des colonnes : ``reserved_quantities``
délègue à ``apps.installations.selectors.reserved_quantities_for_company`` et
``quantite_en_quarantaine`` à un agrégat de blocages qualité — deux cartes
Python calculées par société. Les injecter dans un queryset supposerait soit un
``CASE`` géant par produit, soit un import direct des modèles d'une autre app
(interdit : les lectures cross-app passent par les selectors). Une annotation
ORM approchée rendrait un disponible FAUX ; la règle du dépôt tranche — un
chiffre est réel ou il est OMIS. ``quantite_stock``, ``seuil_alerte`` et
``est_low_stock`` (stock BRUT vs seuil, définition historique de
``StockProduitSerializer.get_is_low_stock``) sont exposés tels quels.

NOMS DE CHAMPS — pourquoi ``categorie__nom`` et ``fournisseur__nom``
--------------------------------------------------------------------
``categorie`` (Produit) et ``fournisseur`` (bon de commande) sont de VRAIES
colonnes FK : Django refuse une annotation qui porterait leur nom. On expose
donc le CHEMIN ORM tel quel (``categorie__nom``) plutôt que d'inventer un
alias — la liste blanche du moteur accepte les chemins traversants.
"""
from __future__ import annotations

PRODUITS_DATASET = 'stock_produits'
PRODUITS_FIELDS = [
    'id', 'categorie', 'categorie__nom', 'marque', 'quantite_stock',
    'seuil_alerte', 'est_low_stock', 'prix_achat', 'valeur_achat',
]
# Champ -> attribut de permission du LECTEUR (AUD801).
PRODUITS_GATED = {
    'prix_achat': 'can_view_buy_prices',
    'valeur_achat': 'can_view_buy_prices',
}

MOUVEMENTS_DATASET = 'stock_mouvements'
MOUVEMENTS_FIELDS = [
    'id', 'type', 'mois', 'produit_categorie', 'quantite',
]

BCF_DATASET = 'stock_bcf'
BCF_FIELDS = [
    'id', 'fournisseur', 'fournisseur__nom', 'statut', 'mois', 'montant',
]
BCF_GATED = {'montant': 'can_view_buy_prices'}


def produits_queryset(company, user):
    """Queryset ``stock.Produit`` DÉJÀ scopé société (archivés exclus).

    ``est_low_stock`` reprend MOT POUR MOT la définition historique du
    sérialiseur produit (``seuil_alerte > 0 AND quantite_stock <=
    seuil_alerte``) — jamais une seconde définition concurrente.
    """
    from django.db.models import (
        BooleanField, Case, DecimalField, ExpressionWrapper, F, Q, Value, When,
    )

    from .models import Produit

    valeur_field = DecimalField(max_digits=16, decimal_places=2)
    return Produit.objects.filter(
        company=company, is_archived=False,
    ).annotate(
        est_low_stock=Case(
            When(Q(seuil_alerte__gt=0)
                 & Q(quantite_stock__lte=F('seuil_alerte')),
                 then=Value(True)),
            default=Value(False),
            output_field=BooleanField(),
        ),
        valeur_achat=ExpressionWrapper(
            F('prix_achat') * F('quantite_stock'),
            output_field=valeur_field),
    )


def mouvements_queryset(company, user):
    """Queryset ``stock.MouvementStock`` DÉJÀ scopé société."""
    from django.db.models import F
    from django.db.models.functions import TruncMonth

    from .models import MouvementStock

    return MouvementStock.objects.filter(company=company).annotate(
        type=F('type_mouvement'),
        mois=TruncMonth('date'),
        produit_categorie=F('produit__categorie__nom'),
    )


def bcf_queryset(company, user):
    """Queryset ``achats.BonCommandeFournisseur`` DÉJÀ scopé société.

    ``montant`` = somme SQL de ``quantite × prix_achat_unitaire`` sur les
    lignes — la MÊME définition que la propriété
    ``BonCommandeFournisseur.total_achat`` (qui somme ``ligne.total_achat``),
    portée par une sous-requête corrélée pour ne pas multiplier la ligne
    d'en-tête par ses lignes. Montant d'ACHAT ⇒ sous permission (``BCF_GATED``).
    """
    from decimal import Decimal

    from django.db.models import (
        DecimalField, ExpressionWrapper, F, OuterRef, Subquery, Sum, Value,
    )
    from django.db.models.functions import Coalesce, TruncMonth

    # Import FONCTION-LOCAL : le bon de commande fournisseur vit dans
    # ``apps.achats`` depuis ODX19 ; `stock` reste sans import au chargement.
    from apps.achats.models import (
        BonCommandeFournisseur, LigneBonCommandeFournisseur,
    )

    montant_field = DecimalField(max_digits=16, decimal_places=2)
    total = Subquery(
        LigneBonCommandeFournisseur.objects
        .filter(bon_commande=OuterRef('pk'))
        .values('bon_commande')
        .annotate(total=Sum(ExpressionWrapper(
            F('quantite') * F('prix_achat_unitaire'),
            output_field=montant_field)))
        .values('total')[:1],
        output_field=montant_field,
    )
    return BonCommandeFournisseur.objects.filter(company=company).annotate(
        mois=TruncMonth('date_commande'),
        montant=Coalesce(total, Value(Decimal('0'), montant_field),
                         output_field=montant_field),
    )


def register_dataset():
    """Enregistre les trois datasets stock/achats (idempotent)."""
    from core import data_explorer

    data_explorer.register_dataset(
        PRODUITS_DATASET, 'Produits', PRODUITS_FIELDS, produits_queryset,
        gated_fields=PRODUITS_GATED)
    data_explorer.register_dataset(
        MOUVEMENTS_DATASET, 'Mouvements de stock', MOUVEMENTS_FIELDS,
        mouvements_queryset)
    data_explorer.register_dataset(
        BCF_DATASET, 'Bons de commande fournisseur', BCF_FIELDS,
        bcf_queryset, gated_fields=BCF_GATED)
