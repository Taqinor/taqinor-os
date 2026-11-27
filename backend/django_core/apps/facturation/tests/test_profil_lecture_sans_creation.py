"""Profil société — les lectures des vues facture ne créent pas le profil.

Nouveau fichier car : aucun module existant ne couvre ces actions sans base,
et ce garde tourne en SimpleTestCase. ``CompanyProfile.get`` est un
get_or_create : une lecture pure sur une société sans profil créait la ligne
(fuseau par défaut) et périmait les simulations de calepinage. Ces actions ne
font que LIRE le profil (aucun ``save`` sur l'objet) : elles passent par
``CompanyProfile.lire``. Les actions sont des vues (base requise pour les
jouer) : le test inspecte le code de l'action elle-même.
"""
import inspect

from django.test import SimpleTestCase

from apps.facturation.views.facture import FactureViewSet
from apps.facturation.views.facture_cycle import FactureCycleActionsMixin
from apps.facturation.views.facture_documents import (
    FactureDocumentsActionsMixin)


class VuesFactureLisentSansCreerTests(SimpleTestCase):

    def _lit_sans_creer(self, fonction):
        source = inspect.getsource(fonction)
        self.assertNotIn('CompanyProfile.get(', source)
        self.assertIn('CompanyProfile.lire(', source)

    def test_creation_de_facture_devise_et_escompte(self):
        self._lit_sans_creer(FactureViewSet.perform_create)

    def test_remise_en_brouillon(self):
        self._lit_sans_creer(FactureCycleActionsMixin.remettre_brouillon)

    def test_marquer_payee(self):
        self._lit_sans_creer(FactureCycleActionsMixin.marquer_payee)

    def test_export_ubl(self):
        self._lit_sans_creer(FactureDocumentsActionsMixin.ubl)
