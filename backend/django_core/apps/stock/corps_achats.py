"""ENF11 (api-fuzz full 24/10) — corps typés et garde de capacité des achats.

Un corps lu « à la main » (``request.data.get(...)``) laissait passer un objet
là où un texte était attendu, un caractère nul (refusé par PostgreSQL) ou un
entier hors colonne : 500. Ces classes sont À LA FOIS la forme publiée au
schéma (``@extend_schema(request=...)``) et le validateur du serveur
(``valider_corps``) : schéma == serveur.

``CapaciteMontantsBcfMixin`` traite l'autre cause de 500 du BCF : une ligne
« conforme » (quantité × prix) qui dépasse la colonne ``numeric(14, 2)`` de
son total ne pouvait pas être SERVIE (``InvalidOperation`` du sérialiseur de
réponse) alors qu'elle avait été écrite. Le refus dépend des montants déjà
composés, pas de la forme du corps : 409 ``ConflitEtat``.
"""
from datetime import timedelta

from rest_framework import serializers

from core.champs_stricts import ChaineStricte, DecimalSouple, EntierStrict, QUANTITE_MAX
from .erreurs_achats import ConflitEtat
from .utils.params import ID_MAX


def valider_lignes_modele_bcf(lignes):
    """Lignes d'un modèle de BCF (ERR fuzz modeles-bcf : une ligne sans produit
    — PATCH partiel — ou un produit en double violait NOT NULL / unique_together
    → 500). Sans produit = corps hors schéma (400) ; doublon entre lignes =
    règle d'état que le schéma ne porte pas (409, api-fuzz-full 24/10)."""
    produits = [ligne.get('produit') for ligne in lignes]
    if None in produits:
        raise serializers.ValidationError({'lignes': ['Chaque ligne exige un produit.']})
    if len(set(produits)) != len(produits):
        raise ConflitEtat({'lignes': ["Un même produit ne figure qu'une fois."]})
    return lignes


def valider_corps(classe, request):
    """Valide ``request.data`` avec la classe PUBLIÉE ``classe`` (400 nommant
    les champs ; un corps non objet y répond aussi 400) et rend les données
    validées."""
    saisie = classe(data=request.data)
    saisie.is_valid(raise_exception=True)
    return saisie.validated_data


def ajouter_jours_ou_none(jour, jours):
    """``jour`` + ``jours`` ; ``None`` si le résultat sort du calendrier (un
    délai fournisseur démesuré levait ``OverflowError``, 500)."""
    try:
        return jour + timedelta(days=jours)
    except OverflowError:
        return None


class BcfEnvoyerEmailCorps(serializers.Serializer):
    """``POST bons-commande-fournisseur/{id}/envoyer-email/`` (tout facultatif)."""
    to_email = serializers.EmailField(required=False, allow_blank=True, max_length=254)
    sujet = ChaineStricte(required=False, allow_blank=True, max_length=300)
    corps = ChaineStricte(required=False, allow_blank=True)


class BcfConfirmerCorps(serializers.Serializer):
    """``POST bons-commande-fournisseur/{id}/confirmer/``."""
    date_confirmee_fournisseur = serializers.DateField()
    numero_confirmation_fournisseur = ChaineStricte(
        required=False, allow_blank=True, max_length=100)


class BcfReviserLigneCorps(serializers.Serializer):
    """Ligne d'une révision de BCF : les clés que ``reviser_bcf`` lit."""
    id = EntierStrict(required=False, min_value=1, max_value=ID_MAX)
    quantite = EntierStrict(required=False, min_value=1, max_value=ID_MAX)
    designation = ChaineStricte(required=False, allow_blank=True, max_length=255)
    prix_achat_unitaire = DecimalSouple(required=False, max_digits=10, decimal_places=2)
    prix_achat_unitaire_devise = DecimalSouple(required=False, max_digits=12, decimal_places=2)


class BcfReviserCorps(serializers.Serializer):
    """``POST bons-commande-fournisseur/{id}/reviser/`` (tout facultatif)."""
    date_commande = serializers.DateField(required=False, allow_null=True)
    date_livraison_prevue = serializers.DateField(required=False, allow_null=True)
    note = ChaineStricte(required=False, allow_blank=True)
    lignes = serializers.ListField(child=BcfReviserLigneCorps(), required=False)


class ControleQualiteCorps(serializers.Serializer):
    """``POST receptions-fournisseur/{id}/controle-qualite/``."""
    resultat = serializers.ChoiceField(choices=['conforme', 'non_conforme'])
    unites_controlees = EntierStrict(required=False, min_value=0, max_value=ID_MAX)
    observation = ChaineStricte(required=False, allow_blank=True)


class RetourValiderScanneCorps(serializers.Serializer):
    """``POST retours-fournisseur/{id}/valider-scanne/`` : casier relevé par
    ligne (clé = identifiant de ligne, valeur = identifiant de casier)."""
    bins_source = serializers.DictField(
        child=EntierStrict(min_value=1, max_value=ID_MAX, allow_null=True), required=False)


class UniteControlerScanCorps(serializers.Serializer):
    """``POST unites-logistiques/{id}/controler-scan/``."""
    produit = EntierStrict(min_value=1, max_value=ID_MAX)
    quantite = EntierStrict(required=False, min_value=1, max_value=QUANTITE_MAX)


class RapprocherPeseesCorps(serializers.Serializer):
    """``POST receptions-fournisseur/{id}/rapprocher-pesees/`` : ``note``
    facultative, vraie chaîne JSON sans caractère nul (un corps non objet
    répondait 500)."""
    note = ChaineStricte(required=False, allow_blank=True)


class UniteAjouterLigneCorps(serializers.Serializer):
    """``POST unites-logistiques/{id}/lignes/`` : une quantité hors colonne
    (entier 32 bits) faisait un 500 à l'écriture ; le plafond est celui des
    autres saisies de stock (``QUANTITE_MAX``). ``lot`` : nul / absent = sans lot."""
    produit = EntierStrict(min_value=1, max_value=ID_MAX)
    quantite = EntierStrict(min_value=1, max_value=QUANTITE_MAX)
    lot = EntierStrict(required=False, allow_null=True, min_value=1, max_value=ID_MAX)


class ProduitDecoupeCorps(serializers.Serializer):
    """``POST produits/decoupes/`` : des quantités hors colonne entière faisaient
    un 500 au crédit du stock ; plafond ``QUANTITE_MAX`` publié. ``emplacement`` /
    ``lot_source`` : nul ou absent = non précisé."""
    produit_source = EntierStrict(min_value=1, max_value=ID_MAX)
    quantite_consommee = EntierStrict(min_value=1, max_value=QUANTITE_MAX)
    produit_cible = EntierStrict(min_value=1, max_value=ID_MAX)
    quantite_produite = EntierStrict(min_value=1, max_value=QUANTITE_MAX)
    emplacement = EntierStrict(required=False, allow_null=True, min_value=1, max_value=ID_MAX)
    lot_source = EntierStrict(required=False, allow_null=True, min_value=1, max_value=ID_MAX)
