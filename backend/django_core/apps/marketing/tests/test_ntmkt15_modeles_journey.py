"""NTMKT15 — Bibliothèque de modèles de journeys.

Couvre : la commande de seed est idempotente (re-run = no-op), instancier un
modèle crée une séquence ÉDITABLE portant le bon graphe (nœuds + arcs
NTMKT12), et le modèle source n'est jamais modifié.
"""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from authentication.models import Company

from apps.marketing import services as mkt_services
from apps.marketing.models import (
    ArcJourney, ModeleJourney, NoeudJourney, SequenceRelance,
)


class SeedModelesJourneyTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(slug='ntmkt15', nom='NTMKT15')

    def _seed(self):
        out = StringIO()
        call_command('seed_modeles_journey', '--company-slug', 'ntmkt15',
                     stdout=out)
        return out.getvalue()

    def test_seed_cree_quatre_modeles_puis_est_un_noop(self):
        self._seed()
        self.assertEqual(
            ModeleJourney.objects.filter(company=self.co).count(), 4)
        self._seed()
        self.assertEqual(
            ModeleJourney.objects.filter(company=self.co).count(), 4)

    def test_chaque_modele_porte_un_graphe_coherent(self):
        self._seed()
        for modele in ModeleJourney.objects.filter(company=self.co):
            cles = {n['cle'] for n in modele.graphe['noeuds']}
            self.assertTrue(cles)
            for arc in modele.graphe['arcs']:
                self.assertIn(arc['source'], cles)
                self.assertIn(arc['cible'], cles)


class InstancierModeleTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(slug='ntmkt15b', nom='NTMKT15 B')
        self.modele = ModeleJourney.objects.create(
            company=self.co, nom='Gabarit', categorie='Test',
            graphe={
                'noeuds': [
                    {'cle': 'a', 'type_noeud': 'declencheur', 'libelle': 'A',
                     'position_x': 10, 'position_y': 20},
                    {'cle': 'b', 'type_noeud': 'action', 'libelle': 'B',
                     'config': {'canal': 'email'}},
                    {'cle': 'c', 'type_noeud': 'sortie', 'libelle': 'C'},
                ],
                'arcs': [
                    {'source': 'a', 'cible': 'b', 'condition': 'a_ouvert',
                     'ordre': 1},
                    {'source': 'a', 'cible': 'c', 'condition': 'toujours',
                     'ordre': 2},
                    {'source': 'a', 'cible': 'inconnu'},
                ],
            })

    def test_instanciation_cree_une_sequence_editable_avec_le_graphe(self):
        sequence = mkt_services.instancier_modele_journey(self.co, self.modele)
        self.assertIsInstance(sequence, SequenceRelance)
        self.assertFalse(sequence.actif)
        self.assertEqual(sequence.company_id, self.co.id)
        noeuds = NoeudJourney.objects.filter(sequence=sequence)
        self.assertEqual(noeuds.count(), 3)
        depart = noeuds.get(libelle='A')
        self.assertEqual(depart.position_x, 10)
        self.assertEqual(noeuds.get(libelle='B').config, {'canal': 'email'})
        arcs = ArcJourney.objects.filter(source__sequence=sequence)
        # L'arc vers une clé inconnue est ignoré, jamais une référence morte.
        self.assertEqual(arcs.count(), 2)
        self.assertEqual(
            sorted(a.condition for a in arcs), ['a_ouvert', 'toujours'])
        self.assertTrue(all(a.company_id == self.co.id for a in arcs))

    def test_deux_instanciations_sont_independantes(self):
        s1 = mkt_services.instancier_modele_journey(
            self.co, self.modele, nom='Copie 1')
        s2 = mkt_services.instancier_modele_journey(
            self.co, self.modele, nom='Copie 2')
        self.assertNotEqual(s1.id, s2.id)
        self.assertEqual(NoeudJourney.objects.filter(sequence=s1).count(), 3)
        self.assertEqual(NoeudJourney.objects.filter(sequence=s2).count(), 3)
        # Le modèle source reste intact.
        self.modele.refresh_from_db()
        self.assertEqual(len(self.modele.graphe['noeuds']), 3)

    def test_le_graphe_instancie_est_executable(self):
        sequence = mkt_services.instancier_modele_journey(
            self.co, self.modele, nom='Exécutable')
        self.assertTrue(mkt_services.sequence_a_graphe(sequence))
        from apps.compta import services as compta_services
        compta_services.inscrire_lead_sequence(self.co, sequence, lead_id=77)
        traces = mkt_services.executer_journeys_dus(self.co)
        # Sans ouverture tracée, la branche « toujours » mène à la sortie.
        self.assertEqual(traces, [])
