"""PACT118 — le registre d'édition en masse du socle est réellement BRANCHÉ.

Avant cette tâche, ``core.bulk_edit`` n'était alimenté que par les tests du
socle : le registre était VIDE en production, donc l'endpoint générique
``core/bulk-edit/`` ne pouvait servir aucun écran. Ces tests vérifient les
trois choses qui font la différence entre « le moteur existe » et « le moteur
sert » :

  1. les cibles CPQ sont bien enregistrées au démarrage de l'app et visibles
     dans le catalogue du socle ;
  2. une modification en masse via le SOCLE change réellement les lignes de la
     société — et JAMAIS celles d'une autre société ;
  3. la liste blanche tient : un champ non déclaré est refusé (aucune
     écriture sauvage), et notamment aucun champ de prix.
"""
from decimal import Decimal

from django.test import TestCase

from core import bulk_edit
from apps.cpq import bulk_targets
from apps.cpq.models import OffreGroupee, QuestionConfigurateur
from testkit.factories import CompanyFactory, UserFactory


class BulkTargetsCpqTests(TestCase):
    def setUp(self):
        # `ready()` a déjà enregistré les cibles ; on ré-enregistre pour rendre
        # le test indépendant de l'ordre de chargement (l'opération est
        # idempotente par contrat).
        bulk_targets.register_bulk_targets()
        self.company = CompanyFactory()
        self.autre = CompanyFactory()
        self.user = UserFactory(company=self.company)

    def test_les_cibles_cpq_sont_dans_le_catalogue_du_socle(self):
        noms = {c['name'] for c in bulk_edit.list_bulk_targets()}
        self.assertIn('cpq.offre-groupee', noms)
        self.assertIn('cpq.question-configurateur', noms)
        self.assertIn('cpq.contrainte-compatibilite', noms)

    def test_le_catalogue_expose_les_champs_modifiables(self):
        cible = bulk_edit.get_bulk_target('cpq.offre-groupee')
        self.assertEqual(cible['fields'], ['actif'])
        self.assertEqual(cible['label'], 'Offres groupées')

    def test_edition_en_masse_modifie_les_lignes_de_la_societe(self):
        a = OffreGroupee.objects.create(
            company=self.company, nom='Pack A', prix_total=Decimal('1000.00'))
        b = OffreGroupee.objects.create(company=self.company, nom='Pack B')
        modifies = bulk_edit.apply_bulk_edit(
            'cpq.offre-groupee', self.company, self.user,
            [a.id, b.id], {'actif': False})
        self.assertEqual(modifies, 2)
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertFalse(a.actif)
        self.assertFalse(b.actif)

    def test_une_ligne_d_une_autre_societe_est_ignoree(self):
        mienne = OffreGroupee.objects.create(
            company=self.company, nom='Mienne')
        etrangere = OffreGroupee.objects.create(
            company=self.autre, nom='Autre')
        modifies = bulk_edit.apply_bulk_edit(
            'cpq.offre-groupee', self.company, self.user,
            [mienne.id, etrangere.id], {'actif': False})
        self.assertEqual(modifies, 1)
        etrangere.refresh_from_db()
        self.assertTrue(etrangere.actif)

    def test_un_champ_hors_liste_blanche_est_refuse(self):
        offre = OffreGroupee.objects.create(company=self.company, nom='Pack')
        with self.assertRaises(bulk_edit.ChampNonModifiable):
            bulk_edit.apply_bulk_edit(
                'cpq.offre-groupee', self.company, self.user,
                [offre.id], {'prix_total': Decimal('1.00')})
        offre.refresh_from_db()
        self.assertIsNone(offre.prix_total)

    def test_questions_du_configurateur_editables_en_masse(self):
        q1 = QuestionConfigurateur.objects.create(
            company=self.company, texte='Q1', ordre=1)
        q2 = QuestionConfigurateur.objects.create(
            company=self.company, texte='Q2', ordre=2)
        modifies = bulk_edit.apply_bulk_edit(
            'cpq.question-configurateur', self.company, self.user,
            [q1.id, q2.id], {'actif': False})
        self.assertEqual(modifies, 2)
        q1.refresh_from_db()
        self.assertFalse(q1.actif)
