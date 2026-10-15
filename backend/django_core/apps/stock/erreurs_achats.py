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


@contextmanager
def debordement_compteur_en_409():
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
        raise ConflitEtat(
            'Quantité impossible à enregistrer : le stock du produit ou du '
            'casier dépasserait la capacité de son compteur.')
