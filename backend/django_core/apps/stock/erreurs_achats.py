"""ENF11 (achats) — refus MÉTIER des écritures d'achats, avec leur vrai statut.

Un refus qui dépend de l'ÉTAT des données (fournisseur bloqué, BCF encore en
brouillon, facture en exception, solde dépassé…) n'est pas une entrée mal
formée : le corps était conforme au schéma, c'est la situation qui s'oppose.
Il répond donc 409 (état nommé dans le message), et une référence qui ne
résout rien (aucun fournisseur trouvé pour le document, BCF absent) répond 404 —
jamais un 400 « corps invalide » que le schéma ne permettait pas d'éviter.

``IntrouvableMetier`` et ``EtatIncompatible`` sont des ``ValueError`` (les appelants historiques qui
attrapent ``ValueError`` continuent de fonctionner) que les vues traduisent en
404 / 409 ; ``ConflitEtat`` est une exception DRF (409) levable depuis un
serializer, là où un ``ValidationError`` donnerait un 400.
"""
from contextlib import contextmanager
from decimal import Decimal

from django.db import DataError, transaction
from rest_framework import status
from rest_framework.exceptions import APIException, NotFound, ValidationError

from core.champs_stricts import IdInconnu404Mixin, _ids_inconnus_seulement

#: SQLSTATE Postgres « numeric value out of range » (psycopg2 ``pgcode``).
_SQLSTATE_HORS_PLAGE = '22003'


class IntrouvableMetier(ValueError):
    """Une référence métier ne résout rien (fournisseur, bon de commande…)."""


class EtatIncompatible(ValueError):
    """L'état courant des données refuse l'opération (traduit en 409)."""


def statut_refus_metier(exc):
    """Statut HTTP d'un ``ValueError`` de service : ``IntrouvableMetier`` →
    404, ``EtatIncompatible`` → 409, toute autre forme (entrée illisible) → 400."""
    if isinstance(exc, IntrouvableMetier):
        return status.HTTP_404_NOT_FOUND
    if isinstance(exc, EtatIncompatible):
        return status.HTTP_409_CONFLICT
    return status.HTTP_400_BAD_REQUEST


class ConflitEtat(APIException):
    """409 — l'état courant des données s'oppose à l'écriture demandée."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "L'état actuel du document s'oppose à cette opération."
    default_code = 'state_conflict'


class IdInconnu404LignesMixin(IdInconnu404Mixin):
    """``IdInconnu404Mixin`` étendu aux lignes IMBRIQUÉES (ENF11, réception) :
    ``lignes[].ligne_commande`` inconnu (``0`` compris) répond 404 comme une
    clé de premier niveau — même corps DRF. Toute autre erreur garde le 400."""

    def is_valid(self, *, raise_exception=False):
        valide = super().is_valid(raise_exception=False)
        if valide or not raise_exception:
            return valide
        if self._ligne_commande_inconnue_seulement():
            raise NotFound(self.errors)
        if _ids_inconnus_seulement(self.errors, self.fields):
            raise NotFound(self.errors)
        raise ValidationError(self.errors)

    def _ligne_commande_inconnue_seulement(self):
        erreurs = self.errors
        lignes = erreurs.get('lignes') if isinstance(erreurs, dict) else None
        if not isinstance(lignes, list) or not all(
                isinstance(e, dict) for e in lignes):
            return False
        inconnues = 0
        for erreur in lignes:
            if not erreur:
                continue
            details = erreur.get('ligne_commande')
            if set(erreur) != {'ligne_commande'} or not isinstance(
                    details, list) or any(
                    getattr(d, 'code', None) != 'does_not_exist'
                    for d in details):
                return False
            inconnues += 1
        reste = {nom: v for nom, v in erreurs.items() if nom != 'lignes'}
        return bool(inconnues) and (
            not reste or _ids_inconnus_seulement(reste, self.fields))


_MESSAGE_COMPTEUR = (
    'Quantité impossible à enregistrer : le stock du produit ou du '
    'casier dépasserait la capacité de son compteur.')


@contextmanager
def debordement_compteur_en_409(message=_MESSAGE_COMPTEUR):
    """CI #997 fuzz (3) — écriture de stock dans un point de sauvegarde : un
    compteur entier (``quantite_stock``, casier, emplacement) qui DÉBORDERAIT
    sa colonne (SQLSTATE 22003) répond 409 nommé — c'est le niveau déjà
    enregistré qui s'oppose, le corps était conforme — au lieu d'un 500. Rien
    n'est écrit (point de sauvegarde annulé). Toute autre erreur base remonte
    telle quelle."""
    try:
        with transaction.atomic():
            yield
    except DataError as exc:
        cause = exc.__cause__
        if (getattr(cause, 'pgcode', None) or getattr(cause, 'sqlstate', None)) != _SQLSTATE_HORS_PLAGE:
            raise
        raise ConflitEtat(message)


#: Plus grand total de ligne / de document que ``total_achat`` sait servir
#: (``DecimalField(max_digits=14, decimal_places=2)``).
PLAFOND_MONTANT = Decimal('999999999999.99')
#: Plus grand prix unitaire d'une colonne ``max_digits=10, decimal_places=2``.
PLAFOND_PRIX = Decimal('99999999.99')

MESSAGE_CAPACITE = (
    'Montants hors capacité : le total d’une ligne ou du bon de commande '
    'dépasserait 999 999 999 999,99 (quantité × prix d’achat).')


def controler_capacite_montants(lignes):
    """``lignes`` : couples ``(quantité, prix unitaire MAD)``. Lève
    ``ConflitEtat`` (409) si un prix, un total de ligne ou le total du
    document dépasse sa colonne."""
    total = Decimal('0')
    for quantite, prix in lignes:
        prix = abs(Decimal(prix or 0))
        montant = abs(int(quantite or 0)) * prix
        if prix > PLAFOND_PRIX or montant > PLAFOND_MONTANT:
            raise ConflitEtat(MESSAGE_CAPACITE)
        total += montant
    if total > PLAFOND_MONTANT:
        raise ConflitEtat(MESSAGE_CAPACITE)


def controler_capacite_bcf(bon):
    """Même contrôle sur les lignes DÉJÀ écrites d'un BCF (après révision)."""
    controler_capacite_montants(
        (ligne.quantite, ligne.prix_achat_unitaire) for ligne in bon.lignes.all())


class CapaciteMontantsBcfMixin:
    """Mixin de ``BonCommandeFournisseurSerializer`` : refuse (409) des lignes
    dont le prix converti ou le total ne tiendrait pas en base, AVANT toute
    écriture. À placer AVANT ``serializers.ModelSerializer``."""

    #: Champs d'une ligne existante repris quand ils ne sont pas transmis
    #: (même liste que ``_upsert_lignes``).
    _CHAMPS_CAPACITE = ('quantite', 'prix_achat_unitaire', 'prix_achat_unitaire_devise')

    def validate(self, attrs):
        attrs = super().validate(attrs)
        lignes = attrs.get('lignes')
        if not lignes:
            return attrs
        from .services import apply_devise_ligne_bcf
        instance = getattr(self, 'instance', None)
        devise = attrs.get('devise', getattr(instance, 'devise', None))
        taux = attrs.get('taux_change', getattr(instance, 'taux_change', None))
        existantes = ({ligne.id: ligne for ligne in instance.lignes.all()}
                      if instance is not None else {})
        montants = []
        for data in lignes:
            base = existantes.get(data.get('id'))
            fusion = {champ: data.get(champ, getattr(base, champ, None))
                      for champ in self._CHAMPS_CAPACITE}
            apply_devise_ligne_bcf(fusion, devise, taux)
            montants.append((fusion['quantite'], fusion['prix_achat_unitaire']))
        controler_capacite_montants(montants)
        return attrs
