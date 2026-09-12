"""Tests NTWFL2 — apps.stock.models.demarrer_approbation_bcf_depuis_matrice
(pont BonCommandeFournisseur -> core.MatriceApprobation / core.workflow).

Couvre :
  * société SANS matrice ``purchase_order`` configurée : aucun effet
    (``None``, comportement historique inchangé) ;
  * société AVEC une matrice couvrante : un ``WorkflowInstance`` démarre,
    conforme à la chaîne de paliers ;
  * un second appel réutilise l'instance ``en_cours`` déjà démarrée (pas de
    doublon).
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, Produit,
    demarrer_approbation_bcf_depuis_matrice,
)
from core.models import MatriceApprobation, WorkflowInstance


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


class DemarrerApprobationBcfDepuisMatriceTests(TestCase):
    def setUp(self):
        self.company = _company('ntwfl2-bcf')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur NTWFL2')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur NTWFL2', sku='OND-NTWFL2',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1200'))

    def _bcf(self, prix_unitaire=Decimal('60000'), quantite=1):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-NTWFL2-1',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.BROUILLON)
        bc.lignes.create(
            produit=self.produit, quantite=quantite,
            prix_achat_unitaire=prix_unitaire)
        return bc

    def test_sans_matrice_ne_fait_rien(self):
        bc = self._bcf()
        resultat = demarrer_approbation_bcf_depuis_matrice(bc)
        self.assertIsNone(resultat)
        self.assertEqual(WorkflowInstance.objects.count(), 0)

    def test_matrice_couvrante_demarre_instance_a_deux_paliers(self):
        MatriceApprobation.objects.create(
            company=self.company, type_objet='purchase_order',
            departement='achats', montant_min=Decimal('50000'),
            montant_max=None,
            chaine_paliers=[
                {'palier': 1, 'role_requis': 'responsable'},
                {'palier': 2, 'role_requis': 'admin'},
            ])
        bc = self._bcf(prix_unitaire=Decimal('60000'), quantite=1)

        instance = demarrer_approbation_bcf_depuis_matrice(bc)

        self.assertIsNotNone(instance)
        self.assertEqual(instance.statut, WorkflowInstance.STATUT_EN_COURS)
        self.assertEqual(instance.step_instances.count(), 2)
        self.assertEqual(instance.object_id, bc.id)

    def test_second_appel_reutilise_instance_en_cours(self):
        MatriceApprobation.objects.create(
            company=self.company, type_objet='purchase_order',
            departement='achats', montant_min=Decimal('50000'),
            chaine_paliers=[{'palier': 1, 'role_requis': 'responsable'}])
        bc = self._bcf(prix_unitaire=Decimal('60000'))

        i1 = demarrer_approbation_bcf_depuis_matrice(bc)
        i2 = demarrer_approbation_bcf_depuis_matrice(bc)

        self.assertEqual(i1.id, i2.id)
        self.assertEqual(WorkflowInstance.objects.count(), 1)

    def test_montant_sous_le_seuil_ne_demarre_rien(self):
        MatriceApprobation.objects.create(
            company=self.company, type_objet='purchase_order',
            departement='achats', montant_min=Decimal('50000'),
            chaine_paliers=[{'palier': 1, 'role_requis': 'responsable'}])
        bc = self._bcf(prix_unitaire=Decimal('100'), quantite=1)

        resultat = demarrer_approbation_bcf_depuis_matrice(bc)
        self.assertIsNone(resultat)
