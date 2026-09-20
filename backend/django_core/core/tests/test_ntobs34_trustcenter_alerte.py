"""Tests NTOBS34 — marqueur d'alerte d'expiration sur le trust center (schéma).

Ce que le champ doit garantir : défaut FAUX (donc la première alerte partira),
et une entrée déjà alertée reste marquée — c'est tout ce sur quoi le balayage
périodique s'appuie pour ne jamais réémettre deux fois la même alerte.

La CHARGE UTILE publique du trust center ne doit PAS exposer ce marqueur :
c'est un détail d'exploitation interne, pas une information de confiance.
"""
from django.test import TestCase

from core.trust_center import TrustCenterEntry, TrustCenterEntrySerializer


class AlerteExpirationTests(TestCase):

    def _entree(self, titre='ISO 27001'):
        return TrustCenterEntry.objects.create(
            categorie=TrustCenterEntry.Categorie.CERTIFICATION,
            titre=titre)

    def test_defaut_faux(self):
        entree = self._entree()
        self.assertFalse(entree.alerte_expiration_envoyee)

    def test_marqueur_persiste(self):
        entree = self._entree('ISO 9001')
        entree.alerte_expiration_envoyee = True
        entree.save(update_fields=['alerte_expiration_envoyee', 'updated_at'])

        entree.refresh_from_db()
        self.assertTrue(entree.alerte_expiration_envoyee)

    def test_marqueur_absent_de_la_charge_publique(self):
        entree = self._entree('Hébergement Maroc')
        donnees = TrustCenterEntrySerializer(entree).data
        self.assertNotIn('alerte_expiration_envoyee', donnees)
