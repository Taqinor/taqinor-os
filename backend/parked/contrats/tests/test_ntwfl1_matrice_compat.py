"""Tests NTWFL1 — apps.contrats.lancer_workflow_approbation, vue de
compatibilité vers core.MatriceApprobation (``type_objet='contract'``).

Couvre :
- Une ``MatriceApprobation`` couvrante prime sur ``RegleApprobation`` legacy
  (une étape par palier de sa ``chaine_paliers``, ``regle=None``).
- Sans matrice correspondante, le comportement HISTORIQUE (``RegleApprobation``)
  reste inchangé (repli).
- Le ``role_requis`` d'un palier se traduit en ``niveau_approbation`` connu.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.contrats import services
from apps.contrats.models import Contrat, EtapeApprobation, RegleApprobation
from core.models import MatriceApprobation


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_contrat(company, montant=Decimal('80000'), type_contrat='vente'):
    return Contrat.objects.create(
        company=company, objet='Contrat NTWFL1', montant=montant,
        type_contrat=type_contrat)


class LancerWorkflowMatriceCompatTests(TestCase):
    def setUp(self):
        self.co = make_company('ntwfl1-contrat', 'NTWFL1 Contrat')

    def test_matrice_couvrante_prime_sur_regle_legacy(self):
        RegleApprobation.objects.create(
            company=self.co, libelle='Legacy', montant_min=Decimal('50000'),
            niveau_approbation='responsable', nombre_approbateurs=1)
        MatriceApprobation.objects.create(
            company=self.co, type_objet='contract', departement='',
            montant_min=Decimal('50000'), montant_max=None,
            chaine_paliers=[
                {'palier': 1, 'role_requis': 'responsable'},
                {'palier': 2, 'role_requis': 'admin'},
            ])
        contrat = make_contrat(self.co, montant=Decimal('80000'))

        etapes = services.lancer_workflow_approbation(contrat)

        self.assertEqual(len(etapes), 2)
        self.assertEqual([e.niveau for e in etapes], [1, 2])
        self.assertEqual(etapes[0].niveau_approbation, 'responsable')
        self.assertEqual(etapes[1].niveau_approbation, 'administrateur')
        self.assertTrue(all(e.regle_id is None for e in etapes))
        self.assertTrue(
            all(e.statut == EtapeApprobation.Statut.EN_ATTENTE for e in etapes))

    def test_sans_matrice_repli_sur_regle_legacy_inchange(self):
        RegleApprobation.objects.create(
            company=self.co, libelle='Legacy', montant_min=Decimal('50000'),
            niveau_approbation='direction', nombre_approbateurs=2)
        contrat = make_contrat(self.co, montant=Decimal('80000'))

        etapes = services.lancer_workflow_approbation(contrat)

        self.assertEqual(len(etapes), 2)
        self.assertEqual(etapes[0].niveau_approbation, 'direction')
        self.assertIsNotNone(etapes[0].regle_id)

    def test_matrice_inactive_ignoree_repli_legacy(self):
        MatriceApprobation.objects.create(
            company=self.co, type_objet='contract', actif=False,
            chaine_paliers=[{'palier': 1, 'role_requis': 'responsable'}])
        RegleApprobation.objects.create(
            company=self.co, libelle='Legacy', nombre_approbateurs=1)
        contrat = make_contrat(self.co, montant=Decimal('1'))

        etapes = services.lancer_workflow_approbation(contrat)
        self.assertEqual(len(etapes), 1)
        self.assertIsNotNone(etapes[0].regle_id)
