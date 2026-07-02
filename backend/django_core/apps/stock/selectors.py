"""Sélecteurs LECTURE SEULE du domaine Stock exposés aux AUTRES apps.

Point d'entrée cross-app : les autres apps lisent les produits à travers ces
fonctions plutôt qu'en important `apps.stock.models` directement (voir CLAUDE.md,
règle de modularité). Comportement strictement identique aux requêtes inline
d'origine.
"""


def get_produit_scoped(company, pk):
    """Produit scopé société par id, ou None. Lecture seule."""
    from .models import Produit
    return Produit.objects.filter(id=pk, company=company).first()


def get_produit_or_raise(company, pk):
    """Produit scopé société par id. Lève Produit.DoesNotExist (ou ValueError/
    TypeError sur pk invalide) — pour les appelants qui gèrent ces exceptions."""
    from .models import Produit
    return Produit.objects.get(pk=pk, company=company)


def produit_does_not_exist():
    """Classe d'exception Produit.DoesNotExist (pour un `except` côté appelant
    sans importer le modèle)."""
    from .models import Produit
    return Produit.DoesNotExist


def lock_produit(pk):
    """Produit verrouillé pour mise à jour (select_for_update). À utiliser dans
    une transaction. Lève Produit.DoesNotExist si absent."""
    from .models import Produit
    return Produit.objects.select_for_update().get(pk=pk)


def get_emplacement_scoped(company, pk):
    """EmplacementStock scopé société par id, ou None. Lecture seule."""
    from .models import EmplacementStock
    return EmplacementStock.objects.filter(id=pk, company=company).first()


def valid_produit_ids(company, ids):
    """Sous-ensemble des `ids` qui existent comme Produit de la société (set).
    Lecture seule."""
    from .models import Produit
    if not ids:
        return set()
    return set(
        Produit.objects.filter(id__in=list(ids), company=company)
        .values_list('id', flat=True)
    )


def get_fournisseur_by_id(company, fournisseur_id):
    """FG83 — Renvoie un Fournisseur scopé société par son id, ou None.
    Point d'accès cross-app : SAV utilise ce sélecteur pour ne pas importer
    directement apps.stock.models.Fournisseur."""
    from .models import Fournisseur
    return Fournisseur.objects.filter(
        id=fournisseur_id, company=company).first()


# ── DC30 / DC31 — Identité tiers fournisseur DÉRIVÉE (jamais re-stockée) ──────
# La Comptabilité (comptes auxiliaires tiers, DC30) et les Contrats (parties,
# DC31) ne RECOPIENT JAMAIS nom/ICE/IF/RC/RIB d'un fournisseur sur leur propre
# modèle : ils gardent une référence (FK chaîne ``stock.Fournisseur`` ou couple
# typé tiers_type='fournisseur'/tiers_id) et LISENT l'identité au vol via ce
# sélecteur. Identité = source unique sur Fournisseur (DC15). LECTURE SEULE.

def get_fournisseur_tiers_identity(company, fournisseur_id):
    """Identité légale d'un fournisseur (tiers) pour un compte auxiliaire compta
    (DC30) ou une partie au contrat (DC31), scopée société.

    Renvoie ``{type_tiers, id, nom, ice, identifiant_fiscal, rc, rib, email,
    telephone, adresse}`` ou ``None`` si le fournisseur n'appartient pas à la
    société. Aucune de ces valeurs ne doit être recopiée sur le compte/la
    partie : c'est l'accesseur unique d'identité tiers fournisseur. LECTURE
    SEULE."""
    f = get_fournisseur_by_id(company, fournisseur_id)
    if f is None:
        return None
    return {
        'type_tiers': 'fournisseur',
        'id': f.id,
        'nom': f.nom,
        'ice': f.ice,
        'identifiant_fiscal': f.identifiant_fiscal,
        'rc': f.rc,
        'rib': f.rib,
        'email': f.email,
        'telephone': f.telephone,
        'adresse': f.adresse,
    }


# ── FG131 — Achats / AP : données pour le rapprochement 3 voies ──────────────
# Point d'entrée cross-app LECTURE SEULE pour la Comptabilité (apps.compta) : le
# rapprochement 3 voies (BC ↔ réception ↔ facture fournisseur) lit les trois
# montants à travers ces sélecteurs plutôt qu'en important apps.stock.models.
# AUCUNE de ces fonctions n'écrit ; les montants d'achat restent INTERNES.


def get_bon_commande_fournisseur(company, bc_id):
    """BonCommandeFournisseur scopé société par id, ou None. Lecture seule."""
    from .models import BonCommandeFournisseur
    return BonCommandeFournisseur.objects.filter(
        id=bc_id, company=company).first()


def get_bcf_by_id(bc_id):
    """QS3 — BCF par id, NON scopé (l'appelant a déjà authentifié via un jeton
    ShareLink borné à ce BCF). Renvoie l'objet ou None. Lecture seule."""
    from .models import BonCommandeFournisseur
    return BonCommandeFournisseur.objects.filter(id=bc_id).first()


def render_bcf_pdf_by_id(bc_id):
    """QS3 — Rend à la volée le PDF FOURNISSEUR d'un BCF (bytes) + son nom de
    fichier cohérent. Renvoie ``(pdf_bytes, filename)`` ou ``(None, None)``.

    Point d'entrée cross-app : ``ventes`` (endpoint public tokenisé) appelle CE
    sélecteur au lieu d'importer les modèles/utils de ``stock`` directement. Le
    PDF montre légitimement les PRIX D'ACHAT au FOURNISSEUR (le jeton l'y
    autorise) — il n'est jamais servi à un client final."""
    bcf = get_bcf_by_id(bc_id)
    if bcf is None:
        return None, None
    from .utils.pdf_fournisseur import generate_bcf_pdf
    pdf_bytes = generate_bcf_pdf(bcf)
    from apps.ventes.utils.filenames import document_filename
    filename = document_filename(
        'Bon-de-commande', bcf.reference,
        client=bcf.fournisseur if bcf.fournisseur_id else None,
        company=bcf.company)
    return pdf_bytes, filename


def montant_commande_bcf(bon_commande):
    """Montant HT COMMANDÉ d'un bon de commande fournisseur (Σ lignes :
    quantité × prix d'achat unitaire). INTERNE. Renvoie un Decimal."""
    from decimal import Decimal
    total = Decimal('0')
    for ligne in bon_commande.lignes.all():
        total += Decimal(str(ligne.quantite or 0)) * (
            ligne.prix_achat_unitaire or Decimal('0'))
    return total


def montant_recu_bcf(bon_commande):
    """Montant HT REÇU pour un BCF : Σ sur les réceptions CONFIRMÉES de
    (quantité reçue × prix d'achat unitaire de la ligne de commande). Reflète
    la marchandise effectivement entrée en stock. INTERNE. Renvoie un Decimal.
    """
    from decimal import Decimal
    from .models import LigneReceptionFournisseur
    total = Decimal('0')
    lignes = (LigneReceptionFournisseur.objects
              .filter(reception__bon_commande=bon_commande,
                      reception__statut='confirme')
              .select_related('ligne_commande'))
    for ligne in lignes:
        pu = (ligne.ligne_commande.prix_achat_unitaire
              if ligne.ligne_commande else Decimal('0'))
        total += Decimal(str(ligne.quantite or 0)) * (pu or Decimal('0'))
    return total


def montant_facture_bcf(bon_commande):
    """Montant HT FACTURÉ rattaché à un BCF : Σ des ``montant_ht`` des
    FactureFournisseur liées (statuts de règlement confondus ; une facture
    reste due tant qu'elle existe). INTERNE. Renvoie un Decimal."""
    from decimal import Decimal
    from django.db.models import Sum
    from .models import FactureFournisseur
    agg = (FactureFournisseur.objects
           .filter(bon_commande=bon_commande)
           .aggregate(total=Sum('montant_ht')))
    return agg['total'] or Decimal('0')


def three_way_amounts(company, bc_id):
    """FG131 — Les trois montants HT du rapprochement 3 voies pour un BCF :
    commandé (BC) ↔ reçu (réception) ↔ facturé (facture fournisseur).

    Renvoie un dict ``{exists, bon_commande_id, reference, fournisseur_id,
    fournisseur_nom, statut, montant_commande, montant_recu, montant_facture}``
    ou ``{'exists': False}`` si le BCF n'appartient pas à la société. LECTURE
    SEULE ; montants INTERNES (jamais client-facing)."""
    bon = get_bon_commande_fournisseur(company, bc_id)
    if bon is None:
        return {'exists': False}
    return {
        'exists': True,
        'bon_commande_id': bon.id,
        'reference': bon.reference,
        'fournisseur_id': bon.fournisseur_id,
        'fournisseur_nom': bon.fournisseur.nom if bon.fournisseur_id else None,
        'statut': bon.statut,
        'montant_commande': montant_commande_bcf(bon),
        'montant_recu': montant_recu_bcf(bon),
        'montant_facture': montant_facture_bcf(bon),
    }
