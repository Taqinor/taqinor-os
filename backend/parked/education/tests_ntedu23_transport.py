"""NTEDU23 — transport scolaire : circuits, arrêts, affectations.

Le point sensible testé ici est le SOFT WARNING : un circuit sans véhicule
disponible produit un avertissement, JAMAIS un refus d'enregistrement. La
disponibilité est lue par le sélecteur ``apps.flotte.selectors`` — jamais un
import de ``flotte.models`` depuis ``education``.
"""
import ast
from datetime import date, time
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.flotte.models import Vehicule
from apps.flotte.selectors import vehicule_operationnel
from authentication.models import Company

from .models import (
    AffectationTransport, AnneeScolaire, ArretTransport, CircuitTransport,
    Classe, Eleve, Famille, Niveau)
from .services import avertissement_vehicule_circuit

User = get_user_model()


class TransportFixtureMixin:
    def setUp(self):
        super().setUp()
        self.company, _ = Company.objects.get_or_create(
            slug='ecole-transport-test',
            defaults={'nom': 'École Transport Test'})
        self.user = User.objects.create_user(
            username='admin@ecole-transport-test.ma', password='x',
            company=self.company)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

        self.annee = AnneeScolaire.objects.create(
            company=self.company, libelle='2026-2027',
            date_debut=date(2026, 9, 1), date_fin=date(2027, 6, 30))
        self.niveau = Niveau.objects.create(
            company=self.company, nom='CP', cycle=Niveau.Cycle.PRIMAIRE,
            ordre=1)
        self.classe = Classe.objects.create(
            company=self.company, annee_scolaire=self.annee,
            niveau=self.niveau, nom='CP A', capacite_max=30)
        self.famille = Famille.objects.create(
            company=self.company, nom='Bennani')
        self.eleve = Eleve.objects.create(
            company=self.company, famille=self.famille, nom='Bennani',
            prenom='Yasmine', classe=self.classe)

        self.bus_actif = Vehicule.objects.create(
            company=self.company, immatriculation='12345-A-6',
            statut=Vehicule.Statut.ACTIF)
        self.bus_maintenance = Vehicule.objects.create(
            company=self.company, immatriculation='98765-B-1',
            statut=Vehicule.Statut.MAINTENANCE)

        self.circuit_ok = CircuitTransport.objects.create(
            company=self.company, nom='Circuit Nord',
            vehicule=self.bus_actif)
        self.circuit_sans_bus = CircuitTransport.objects.create(
            company=self.company, nom='Circuit Sud')


class NTEDU23SelecteurFlotteTests(TransportFixtureMixin, TestCase):
    def test_vehicule_actif_est_operationnel(self):
        self.assertTrue(
            vehicule_operationnel(self.company, self.bus_actif.id))

    def test_vehicule_en_maintenance_ne_l_est_pas(self):
        self.assertFalse(
            vehicule_operationnel(self.company, self.bus_maintenance.id))

    def test_vehicule_absent_ou_hors_societe_ne_l_est_pas(self):
        autre, _ = Company.objects.get_or_create(
            slug='ecole-transport-autre',
            defaults={'nom': 'École Transport Autre'})
        self.assertFalse(vehicule_operationnel(self.company, None))
        self.assertFalse(vehicule_operationnel(autre, self.bus_actif.id))


class NTEDU23AvertissementTests(TransportFixtureMixin, TestCase):
    def test_circuit_avec_bus_actif_sans_avertissement(self):
        self.assertEqual(avertissement_vehicule_circuit(self.circuit_ok), '')

    def test_circuit_sans_vehicule_avertit(self):
        message = avertissement_vehicule_circuit(self.circuit_sans_bus)
        self.assertIn('Circuit Sud', message)
        self.assertIn('Aucun véhicule', message)

    def test_circuit_avec_bus_indisponible_avertit(self):
        self.circuit_ok.vehicule = self.bus_maintenance
        self.circuit_ok.save(update_fields=['vehicule'])
        message = avertissement_vehicule_circuit(self.circuit_ok)
        self.assertIn("n'est pas en service", message)


class NTEDU23ApiTests(TransportFixtureMixin, TestCase):
    def test_crud_circuit_arret_affectation(self):
        resp = self.client.post(
            '/api/django/education/transport/circuits/',
            {'nom': 'Circuit Est', 'vehicule': self.bus_actif.id},
            format='json')
        self.assertEqual(resp.status_code, 201)
        circuit_id = resp.data['id']
        # La société est TOUJOURS posée côté serveur.
        self.assertEqual(
            CircuitTransport.objects.get(pk=circuit_id).company, self.company)

        resp = self.client.post(
            '/api/django/education/transport/arrets/',
            {'circuit': circuit_id, 'nom': 'Place Hassan II', 'ordre': 1,
             'heure_passage_estimee': '07:15:00'}, format='json')
        self.assertEqual(resp.status_code, 201)
        arret_id = resp.data['id']

        resp = self.client.post(
            '/api/django/education/transport/affectations/',
            {'eleve': self.eleve.id, 'circuit': circuit_id,
             'arret': arret_id, 'date_debut': '2026-09-01'}, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['avertissement'], '')

    def test_affectation_sur_circuit_sans_vehicule_est_enregistree(self):
        """Le critère NTEDU23 : avertissement OUI, blocage NON."""
        resp = self.client.post(
            '/api/django/education/transport/affectations/',
            {'eleve': self.eleve.id, 'circuit': self.circuit_sans_bus.id,
             'date_debut': '2026-09-01'}, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertIn('Aucun véhicule', resp.data['avertissement'])
        self.assertTrue(
            AffectationTransport.objects.filter(
                company=self.company, eleve=self.eleve,
                circuit=self.circuit_sans_bus).exists())

    def test_affectation_sur_circuit_a_bus_immobilise_est_enregistree(self):
        self.circuit_sans_bus.vehicule = self.bus_maintenance
        self.circuit_sans_bus.save(update_fields=['vehicule'])
        resp = self.client.post(
            '/api/django/education/transport/affectations/',
            {'eleve': self.eleve.id, 'circuit': self.circuit_sans_bus.id,
             'date_debut': '2026-09-01'}, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertIn("n'est pas en service", resp.data['avertissement'])

    def test_liste_scopee_par_societe(self):
        autre, _ = Company.objects.get_or_create(
            slug='ecole-transport-tierce',
            defaults={'nom': 'École Transport Tierce'})
        CircuitTransport.objects.create(company=autre, nom='Circuit Étranger')
        resp = self.client.get('/api/django/education/transport/circuits/')
        self.assertEqual(resp.status_code, 200)
        noms = {c['nom'] for c in (resp.data.get('results') or resp.data)}
        self.assertNotIn('Circuit Étranger', noms)

    def test_arret_ordonne_le_long_du_circuit(self):
        ArretTransport.objects.create(
            company=self.company, circuit=self.circuit_ok, nom='B', ordre=2,
            heure_passage_estimee=time(7, 30))
        ArretTransport.objects.create(
            company=self.company, circuit=self.circuit_ok, nom='A', ordre=1,
            heure_passage_estimee=time(7, 15))
        noms = list(
            self.circuit_ok.arrets.values_list('nom', flat=True))
        self.assertEqual(noms, ['A', 'B'])


class NTEDU23FrontiereCrossAppTests(TestCase):
    def test_education_n_importe_jamais_flotte_models(self):
        """Frontière cross-app : lecture via ``flotte/selectors.py`` seulement.

        Contrôle sur les IMPORTS RÉELS (AST) des modules de production de
        l'app — les modules de TEST peuvent légitimement instancier un
        ``Vehicule`` pour poser leur fixture."""
        racine = Path(__file__).resolve().parent
        for chemin in racine.rglob('*.py'):
            if chemin.name.startswith('test'):
                continue
            if 'migrations' in chemin.parts:
                continue
            arbre = ast.parse(chemin.read_text(encoding='utf-8'))
            for noeud in ast.walk(arbre):
                modules = []
                if isinstance(noeud, ast.Import):
                    modules = [alias.name for alias in noeud.names]
                elif isinstance(noeud, ast.ImportFrom):
                    modules = [noeud.module or '']
                for module in modules:
                    self.assertNotEqual(
                        module, 'apps.flotte.models',
                        f'{chemin.name} importe flotte.models : passer par '
                        f'apps.flotte.selectors.')
