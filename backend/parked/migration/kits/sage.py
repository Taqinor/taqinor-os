"""NTMIG12 — kit Sage : mappings prédéfinis par export CSV.

Couvre les exports CSV Sage 100/Ligne 100 courants : ``Tiers`` (clients ET
fournisseurs selon le type — deux clés de registre distinctes, même colonnes
sources), ``Articles`` (produits), ``Documents de vente`` (devis/factures).

Spécificités Sage prises en charge par l'appelant (``dataimport.parse_rows``/
``migration.validation``), PAS ici — ce module ne fait QUE déclarer le
mapping :

* séparateur ``;`` — détecté par le parseur CSV générique (``csv.Sniffer``
  côté ``dataimport``, inchangé par ce kit) ;
* décimale virgule — couverte par ``validation.valider_montant`` (accepte
  ``,`` et ``.``) et par la sommation financière (NTMIG7, même normalisation) ;
* encodage Windows-1252 en repli de l'utf-8 — c'est le rôle de
  ``dataimport.parse_rows`` (décodage), un KIT ne décode rien.
"""
from . import Kit, cle_kit

KIT_REGISTRY = {
    # Tiers (type Client) → clients.
    cle_kit('sage', 'clients'): Kit(
        mapping={
            'code tiers': 'external_id', 'compte': 'external_id',
            'raison sociale': 'nom', 'nom': 'nom',
            'e-mail': 'email', 'email': 'email',
            'telephone': 'telephone', 'téléphone': 'telephone',
            'adresse': 'adresse',
            'ice': 'ice', 'n° ice': 'ice',
        },
        cle_dedup='code tiers',
        regles_format={'email': ['email'], 'telephone': ['telephone'],
                       'ice': ['ice']},
    ),
    # Tiers (type Fournisseur) → fournisseurs — MÊMES colonnes sources, cible
    # différente (l'export Sage ne distingue le type que par une colonne
    # `type tiers`/`compte` filtrée en amont par l'intégrateur, hors du kit).
    cle_kit('sage', 'fournisseurs'): Kit(
        mapping={
            'code tiers': 'external_id', 'compte': 'external_id',
            'raison sociale': 'nom', 'nom': 'nom',
            'contact': 'contact_personne',
            'e-mail': 'email', 'email': 'email',
            'telephone': 'telephone', 'téléphone': 'telephone',
            'adresse': 'adresse',
        },
        cle_dedup='code tiers',
        regles_format={'email': ['email'], 'telephone': ['telephone']},
    ),
    # Articles → products.
    cle_kit('sage', 'products'): Kit(
        mapping={
            'reference': 'sku', 'référence': 'sku', 'code article': 'sku',
            'libelle': 'nom', 'libellé': 'nom', 'designation': 'nom',
            'marque': 'marque',
            'prix de vente': 'prix_vente', 'prix vente ttc': 'prix_vente',
            'prix d\'achat': 'prix_achat', 'prix achat': 'prix_achat',
            'stock': 'quantite_stock', 'quantite': 'quantite_stock',
        },
        colonnes_montant=('prix de vente', 'prix vente ttc'),
        cle_dedup='reference',
        regles_format={'prix_vente': ['montant'], 'prix_achat': ['montant']},
    ),
    # Documents de vente (devis) → devis (en-têtes seulement).
    cle_kit('sage', 'devis'): Kit(
        mapping={
            'numero piece': 'reference_source', 'numéro pièce': 'reference_source',
            'code tiers': 'client_external_id', 'client': 'client_nom',
            'statut': 'statut',
            'date piece': 'date_creation', 'date pièce': 'date_creation',
            'net a payer ht': 'montant_ht_source',
            'net à payer ht': 'montant_ht_source',
            'total ttc': 'montant_ttc_source',
        },
        colonnes_montant=('net a payer ht', 'net à payer ht'),
        cle_dedup='numero piece',
        transformations={'date_creation': ['parser_date_multi_format']},
    ),
    # Documents de vente (factures) → factures (en-têtes seulement).
    cle_kit('sage', 'factures'): Kit(
        mapping={
            'numero piece': 'reference_source', 'numéro pièce': 'reference_source',
            'code tiers': 'client_external_id', 'client': 'client_nom',
            'statut': 'statut',
            'date piece': 'date_emission', 'date pièce': 'date_emission',
            'net a payer ht': 'montant_ht_source',
            'net à payer ht': 'montant_ht_source',
            'total ttc': 'montant_ttc_source',
        },
        colonnes_montant=('net a payer ht', 'net à payer ht'),
        cle_dedup='numero piece',
        transformations={'date_emission': ['parser_date_multi_format']},
    ),
}
