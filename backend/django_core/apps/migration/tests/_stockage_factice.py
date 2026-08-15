"""Stockage objet FACTICE pour les tests NTMIG33/35/38.

Les fichiers source vivent dans MinIO (NTMIG35). Les tests ne doivent ni
dépendre d'un service externe ni écrire sur disque : on remplace les trois
fonctions de :mod:`apps.migration.stockage` par un dictionnaire en mémoire, ce
qui teste exactement la logique de l'app (quelle clé est posée, relue,
supprimée) sans tester boto3.
"""
from unittest import mock

from apps.migration import stockage


class StockageFactice:
    """Mini-magasin clé → octets, avec les mêmes contrats que le vrai."""

    def __init__(self):
        self.objets = {}
        self.compteur = 0

    def enregistrer(self, company_id, lot_id, octets, filename):
        self.compteur += 1
        cle = stockage.cle_pour(company_id, lot_id, filename)
        cle = f'{cle}#{self.compteur}'
        self.objets[cle] = bytes(octets)
        return cle

    def lire(self, cle):
        return self.objets.get(cle) if cle else None

    def supprimer(self, cle):
        if cle:
            self.objets.pop(cle, None)


def patcher_stockage(testcase):
    """Branche un :class:`StockageFactice` pour la durée du test."""
    faux = StockageFactice()
    for nom in ('enregistrer', 'lire', 'supprimer'):
        correctif = mock.patch.object(stockage, nom, getattr(faux, nom))
        correctif.start()
        testcase.addCleanup(correctif.stop)
    return faux
