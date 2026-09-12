"""Tests NTWFL2 — core.workflow.demarrer_depuis_matrice (pont matrice ->
moteur d'exécution BPM).

Couvre :
- Sans matrice couvrante : aucune instance/définition créée (``None``).
- Avec une matrice à 2 paliers : ``WorkflowInstance`` à 2 étapes conforme,
  la première active en attente.
- Réutilisation (mise en cache) de la ``WorkflowDefinition`` par signature de
  chaîne : deux démarrages successifs avec la MÊME chaîne ne créent PAS une
  deuxième définition.
- Une chaîne DIFFÉRENTE matérialise une nouvelle définition (l'ancienne
  reste intacte, ``WorkflowInstance.definition`` est en PROTECT).
"""
import datetime

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from core import workflow
from core.models import MatriceApprobation, WorkflowDefinition, WorkflowInstance


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class DemarrerDepuisMatriceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = make_company('ntwfl2', 'NTWFL2')

    def test_sans_matrice_ne_cree_rien(self):
        target = self.company
        before = WorkflowDefinition.objects.count()
        resultat = workflow.demarrer_depuis_matrice(
            target, 'purchase_order', 1000, self.company)
        self.assertIsNone(resultat)
        self.assertEqual(WorkflowDefinition.objects.count(), before)
        self.assertEqual(WorkflowInstance.objects.count(), 0)

    def test_matrice_a_deux_paliers_demarre_instance_conforme(self):
        MatriceApprobation.objects.create(
            company=self.company, type_objet='purchase_order',
            departement='Achats', montant_min=50000, montant_max=None,
            chaine_paliers=[
                {'palier': 1, 'nombre_approbateurs_requis': 1,
                 'role_requis': 'responsable'},
                {'palier': 2, 'nombre_approbateurs_requis': 1,
                 'role_requis': 'admin'},
            ])
        target = self.company
        now = timezone.make_aware(datetime.datetime(2026, 6, 1, 9, 0, 0))

        instance = workflow.demarrer_depuis_matrice(
            target, 'purchase_order', 75000, self.company,
            departement='Achats', now=now)

        self.assertIsNotNone(instance)
        self.assertEqual(instance.statut, WorkflowInstance.STATUT_EN_COURS)
        self.assertEqual(instance.step_instances.count(), 2)
        etape = workflow.etape_courante_de(instance)
        self.assertEqual(etape.ordre, 1)
        self.assertEqual(etape.step_def.role_requis, 'responsable')

    def test_montant_hors_matrice_ne_demarre_rien(self):
        MatriceApprobation.objects.create(
            company=self.company, type_objet='purchase_order',
            departement='Achats', montant_min=50000, montant_max=None,
            chaine_paliers=[{'palier': 1, 'role_requis': 'responsable'}])
        resultat = workflow.demarrer_depuis_matrice(
            self.company, 'purchase_order', 100, self.company,
            departement='Achats')
        self.assertIsNone(resultat)

    def test_meme_chaine_reutilise_la_meme_definition(self):
        MatriceApprobation.objects.create(
            company=self.company, type_objet='expense', departement='',
            chaine_paliers=[{'palier': 1, 'role_requis': 'responsable'}])
        target = self.company

        i1 = workflow.demarrer_depuis_matrice(
            target, 'expense', 10, self.company)
        i2 = workflow.demarrer_depuis_matrice(
            target, 'expense', 10, self.company)

        self.assertEqual(i1.definition_id, i2.definition_id)
        self.assertEqual(
            WorkflowDefinition.objects.filter(company=self.company).count(), 1)

    def test_chaine_modifiee_materialise_une_nouvelle_definition(self):
        matrice = MatriceApprobation.objects.create(
            company=self.company, type_objet='refund', departement='',
            chaine_paliers=[{'palier': 1, 'role_requis': 'responsable'}])
        i1 = workflow.demarrer_depuis_matrice(
            self.company, 'refund', 10, self.company)

        matrice.chaine_paliers = [
            {'palier': 1, 'role_requis': 'responsable'},
            {'palier': 2, 'role_requis': 'admin'},
        ]
        matrice.save(update_fields=['chaine_paliers'])
        i2 = workflow.demarrer_depuis_matrice(
            self.company, 'refund', 10, self.company)

        self.assertNotEqual(i1.definition_id, i2.definition_id)
        self.assertEqual(i2.step_instances.count(), 2)
        # L'ancienne définition reste intacte (PROTECT — aucune régression
        # sur l'instance historique déjà démarrée).
        i1.refresh_from_db()
        self.assertEqual(i1.step_instances.count(), 1)
